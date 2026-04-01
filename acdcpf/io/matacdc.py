"""
Import from MatACDC / PyACDCPF format (hybrid AC/DC networks).
"""

import numpy as np
from ..network import Network, create_empty_network
from ..create.dc import create_dc_bus, create_dc_line, create_dc_load, create_dc_gen
from ..create.converters import create_vsc, create_dcdc
from .pypower import _import_ac


# MatACDC convdc control mode mapping:
#   type_dc: 1 = constant P, 2 = constant Vdc
#   type_ac: 1 = PQ (constant P,Q), 2 = PV (constant P, Vac)
_CONTROL_MODES = {
    (1, 1): "p_q",
    (1, 2): "p_vac",
    (2, 1): "vdc_q",
    (2, 2): "vdc_vac",
}


def from_matacdc(ppc: dict, pdc: dict, name: str = "",
                 f_hz: float = 50.0) -> Network:
    """
    Create an acdcpf Network from MatACDC / PyACDCPF style dictionaries.

    Converts a MATPOWER-format AC case (ppc) and a MatACDC-format DC
    case (pdc) into the acdcpf data model.  Bus names encode the
    original bus numbers (e.g. "Bus 5", "DC Bus 18") so the
    source numbering is preserved for reference.

    Parameters
    ----------
    ppc : dict
        AC power flow case in MATPOWER format with keys:

        - baseMVA : system MVA base (float)
        - bus : numpy array, columns
          [bus_i, type, Pd, Qd, Gs, Bs, area, Vm, Va, baseKV, zone, Vmax, Vmin]
        - gen : numpy array, columns
          [bus, Pg, Qg, Qmax, Qmin, Vg, mBase, status, Pmax, Pmin]
        - branch : numpy array, columns
          [fbus, tbus, r, x, b, rateA, rateB, rateC, ratio, angle, status]

    pdc : dict
        DC power flow case in MatACDC format with keys:

        - baseMVAac : AC base MVA (float)
        - baseMVAdc : DC base MVA (float)
        - pol       : number of poles (1 or 2)
        - busdc     : numpy array, columns
          [busdc_i, busac_i, grid, Pdc, Vdc, basekVdc, Vdcmax, Vdcmin, Cdc]
        - convdc    : numpy array, columns
          [busdc_i, type_dc, type_ac, P_g, Q_g, Vtar, rtf, xtf, bf,
          rc, xc, basekVac, Vmmax, Vmmin, Imax, status, LossA, LossB,
          LossCrec, LossCinv]
        - branchdc  : numpy array, columns
          [fbusdc, tbusdc, r, l, c, rateA, rateB, rateC, status, N]

    name : str, optional
        Network name (default: "").
    f_hz : float, optional
        System frequency in Hz (default: 50.0).

    Returns
    -------
    Network
        The populated acdcpf Network object.

    Notes
    -----
    **Sign convention** -- MatACDC uses generator convention for VSC
    converters (``P_g > 0`` = inverter, power injected into AC grid).
    acdcpf uses load convention (``P_s > 0`` = rectifier, power drawn
    from AC grid).  The function negates P and Q automatically.

    **Impedance conversion** -- AC branch impedances are converted from
    per-unit (on system MVA base) to physical units (Ohm, uS) using the
    from-bus rated voltage.  DC branch resistances are converted
    similarly using the from-bus DC base voltage.  Converter impedances
    (``rtf``, ``xtf``, ``rc``, ``xc``, ``bf``) are passed through as-is
    in per-unit on system base.

    **DC-DC converters** -- DC branches with ``N != 1`` are treated as
    DC-DC converter branches.  The voltage ratio ``d_ratio`` is computed
    from the bus base voltages: ``d_ratio = basekVdc_low / basekVdc_high``.

    Examples
    --------
    >>> from acdcpf.networks.case33h_ieee_AC import case33_ieee_AC
    >>> from acdcpf.networks.case33h_ieee_DC import case33_ieee_DC
    >>> import acdcpf as pf
    >>> ppc = case33_ieee_AC()
    >>> pdc = case33_ieee_DC()
    >>> net = pf.from_matacdc(ppc, pdc, name="IEEE 33-bus hybrid")
    >>> pf.run_pf(net)
    """
    baseMVA = float(ppc["baseMVA"])
    baseMVAdc = float(pdc.get("baseMVAdc", baseMVA))
    pol = int(pdc.get("pol", 1))

    net = create_empty_network(name=name, s_base=baseMVA, f_hz=f_hz, pol=pol)

    # -- AC side (reuse shared helper) -------------------------------------
    ac_bus_map = _import_ac(ppc, net)

    # ------------------------------------------------------------------
    # DC buses
    # ------------------------------------------------------------------
    dc_bus_map = {}   # matacdc busdc_i  ->  acdcpf index
    dc_bus_info = {}  # busdc_i  ->  (busac_i, grid, Pdc, Vdc, basekVdc)

    # Determine which DC buses are Vdc-slack from converter data
    vdc_slack_buses = set()
    for row in pdc["convdc"]:
        if int(row[1]) == 2:  # type_dc == 2 -> Vdc control
            vdc_slack_buses.add(int(row[0]))

    for row in pdc["busdc"]:
        busdc_i = int(row[0])
        busac_i = int(row[1])
        grid = int(row[2])
        pdc_mw = float(row[3])
        vdc = float(row[4])
        basekVdc = float(row[5])
        vdcmax = float(row[6])
        vdcmin = float(row[7])

        bus_type = "vdc" if busdc_i in vdc_slack_buses else "p"

        idx = create_dc_bus(
            net, v_base=basekVdc, dc_grid=grid,
            bus_type=bus_type, v_dc_pu=vdc,
            v_min=vdcmin, v_max=vdcmax,
            name=f"DC Bus {busdc_i}",
        )
        dc_bus_map[busdc_i] = idx
        dc_bus_info[busdc_i] = (busac_i, grid, pdc_mw, vdc, basekVdc)

    # ------------------------------------------------------------------
    # DC loads and generators  (from busdc Pdc)
    # ------------------------------------------------------------------
    for row in pdc["busdc"]:
        busdc_i = int(row[0])
        pdc_mw = float(row[3])

        if pdc_mw > 0:
            create_dc_load(
                net, bus=dc_bus_map[busdc_i], p_mw=pdc_mw,
                name=f"DC Load {busdc_i}",
            )
        elif pdc_mw < 0:
            create_dc_gen(
                net, bus=dc_bus_map[busdc_i], p_mw=abs(pdc_mw),
                name=f"DC Gen {busdc_i}",
            )

    # ------------------------------------------------------------------
    # DC lines  and  DC-DC converters  (from branchdc)
    # ------------------------------------------------------------------
    for row in pdc["branchdc"]:
        fbus, tbus = int(row[0]), int(row[1])
        r_pu = float(row[2])
        status = int(row[8])
        n_ratio = float(row[9])

        basekVdc_from = dc_bus_info[fbus][4]
        z_base_dc = basekVdc_from ** 2 / baseMVAdc
        r_ohm = r_pu * z_base_dc

        if abs(n_ratio - 1.0) < 1e-6:
            # Regular DC line
            create_dc_line(
                net, from_bus=dc_bus_map[fbus], to_bus=dc_bus_map[tbus],
                length_km=1.0, r_ohm_per_km=r_ohm,
                name=f"DC Line {fbus}-{tbus}",
                in_service=bool(status),
            )
        else:
            # DC-DC converter branch
            basekVdc_to = dc_bus_info[tbus][4]

            # Ensure from_bus = high-voltage side (V_m)
            if basekVdc_from >= basekVdc_to:
                from_idx = dc_bus_map[fbus]
                to_idx = dc_bus_map[tbus]
                d_ratio = basekVdc_to / basekVdc_from
            else:
                from_idx = dc_bus_map[tbus]
                to_idx = dc_bus_map[fbus]
                d_ratio = basekVdc_from / basekVdc_to

            create_dcdc(
                net, from_bus=from_idx, to_bus=to_idx,
                d_ratio=d_ratio, r_ohm=r_ohm,
                name=f"DCDC {fbus}-{tbus}",
                in_service=bool(status),
            )

    # ------------------------------------------------------------------
    # VSC converters
    # ------------------------------------------------------------------
    # Build DC-bus -> AC-bus lookup
    dc_to_ac = {}
    for row in pdc["busdc"]:
        busdc_i = int(row[0])
        busac_i = int(row[1])
        if busac_i > 0:
            dc_to_ac[busdc_i] = busac_i

    for row in pdc["convdc"]:
        busdc_i = int(row[0])
        type_dc = int(row[1])
        type_ac = int(row[2])
        p_g = float(row[3])       # MW  (MatACDC: + = inverter/gen on AC)
        q_g = float(row[4])       # MVAr
        v_tar = float(row[5])     # AC voltage target (pu)
        r_tf = float(row[6])
        x_tf = float(row[7])
        b_f = float(row[8])
        r_c = float(row[9])
        x_c = float(row[10])
        basekVac = float(row[11])
        imax = float(row[14])
        status = int(row[15])
        loss_a = float(row[16])
        loss_b = float(row[17])
        loss_c_rec = float(row[18])
        loss_c_inv = float(row[19])

        busac_i = dc_to_ac.get(busdc_i)
        if busac_i is None:
            continue  # no AC connection for this converter bus

        control_mode = _CONTROL_MODES.get((type_dc, type_ac), "p_q")

        # Negate P/Q: MatACDC gen convention -> acdcpf load convention
        p_mw = -p_g
        q_mvar = -q_g

        v_ac_pu = v_tar if type_ac == 2 else None
        v_dc_pu = dc_bus_info[busdc_i][3] if type_dc == 2 else None

        s_mva = (np.sqrt(3) * basekVac * imax) if imax > 0 else baseMVA

        create_vsc(
            net,
            ac_bus=ac_bus_map[busac_i],
            dc_bus=dc_bus_map[busdc_i],
            s_mva=s_mva,
            control_mode=control_mode,
            p_mw=p_mw,
            q_mvar=q_mvar,
            v_ac_pu=v_ac_pu,
            v_dc_pu=v_dc_pu,
            loss_a=loss_a,
            loss_b=loss_b,
            loss_c=loss_c_rec,
            loss_c_inv=loss_c_inv,
            r_tf_pu=r_tf,
            x_tf_pu=x_tf,
            r_c_pu=r_c,
            x_c_pu=x_c,
            b_filter_pu=b_f,
            loss_base_kv=basekVac,
            name=f"VSC DC{busdc_i}-AC{busac_i}",
            in_service=bool(status),
        )

    return net
