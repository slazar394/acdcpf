"""
Import from MATPOWER / PyPOWER format (AC-only networks).
"""

import numpy as np
from ..network import Network, create_empty_network
from ..create.ac import create_ac_bus, create_ac_line, create_ac_load, create_ac_gen


def _import_ac(ppc: dict, net: Network) -> dict:
    """
    Populate *net* with AC elements from a MATPOWER / PyPOWER case dict.

    Returns a mapping ``{matpower_bus_i: acdcpf_index}`` so callers can
    cross-reference the original bus numbering.
    """
    baseMVA = net.s_base

    # -- AC buses ----------------------------------------------------------
    ac_bus_map = {}   # matpower bus_i  ->  acdcpf index
    ac_bus_info = {}  # matpower bus_i  ->  (type, Vm, baseKV)

    for row in ppc["bus"]:
        bus_i = int(row[0])
        bus_type = int(row[1])  # 1=PQ, 2=PV, 3=slack
        baseKV = float(row[9])

        gs_pu = row[4] / baseMVA  # MW at V=1  ->  pu
        bs_pu = row[5] / baseMVA

        idx = create_ac_bus(
            net, vr_kv=baseKV, name=f"Bus {bus_i}",
            v_min_pu=float(row[12]), v_max_pu=float(row[11]),
            gs_pu=gs_pu, bs_pu=bs_pu,
        )
        ac_bus_map[bus_i] = idx
        ac_bus_info[bus_i] = (bus_type, float(row[7]), baseKV)

    # -- AC loads (from bus Pd / Qd) ---------------------------------------
    for row in ppc["bus"]:
        bus_i = int(row[0])
        pd, qd = float(row[2]), float(row[3])
        if pd != 0.0 or qd != 0.0:
            create_ac_load(
                net, bus=ac_bus_map[bus_i], p_mw=pd, q_mvar=qd,
                name=f"Load {bus_i}",
            )

    # -- AC generators -----------------------------------------------------
    for row in ppc["gen"]:
        bus_i = int(row[0])
        bus_type = ac_bus_info[bus_i][0]
        v_pu = float(row[5]) if bus_type in (2, 3) else None

        create_ac_gen(
            net, bus=ac_bus_map[bus_i],
            p_mw=float(row[1]), q_mvar=float(row[2]),
            v_pu=v_pu,
            q_min_mvar=float(row[4]), q_max_mvar=float(row[3]),
            name=f"Gen {bus_i}",
            in_service=bool(int(row[7])),
        )

    # -- AC branches -------------------------------------------------------
    for row in ppc["branch"]:
        fbus, tbus = int(row[0]), int(row[1])
        r_pu, x_pu, b_pu = float(row[2]), float(row[3]), float(row[4])
        rateA = float(row[5])
        ratio = float(row[8])
        angle = float(row[9])
        status = int(row[10])

        baseKV = ac_bus_info[fbus][2]
        z_base = baseKV ** 2 / baseMVA  # Ohm

        r_ohm = r_pu * z_base
        x_ohm = x_pu * z_base
        b_us = (b_pu / z_base * 1e6) if z_base > 0 else 0.0

        tap = ratio if ratio != 0 else 1.0
        max_i_ka = (rateA / (np.sqrt(3) * baseKV)) if rateA > 0 else None

        create_ac_line(
            net, from_bus=ac_bus_map[fbus], to_bus=ac_bus_map[tbus],
            length_km=1.0, r_ohm_per_km=r_ohm, x_ohm_per_km=x_ohm,
            b_us_per_km=b_us, tap=tap, shift_deg=angle,
            max_i_ka=max_i_ka,
            name=f"Line {fbus}-{tbus}",
            in_service=bool(status),
        )

    return ac_bus_map


def from_pypower(ppc: dict, name: str = "", f_hz: float = 50.0,
                 s_base: float = None, pol: int = 2) -> Network:
    """
    Create an acdcpf Network from a PyPOWER / MATPOWER case dictionary.

    Imports the AC side only (buses, loads, generators, branches).
    The returned network can then be extended with DC elements using
    the normal ``create_dc_bus``, ``create_vsc``, etc. calls.

    Bus names encode the original MATPOWER bus numbers (e.g. ``"Bus 5"``)
    so the source numbering is preserved for reference.

    Parameters
    ----------
    ppc : dict
        AC power flow case in MATPOWER / PyPOWER format with keys:

        - ``"baseMVA"`` : system MVA base (float)
        - ``"bus"`` : numpy array, columns
          ``[bus_i, type, Pd, Qd, Gs, Bs, area, Vm, Va, baseKV, zone,
          Vmax, Vmin]``
        - ``"gen"`` : numpy array, columns
          ``[bus, Pg, Qg, Qmax, Qmin, Vg, mBase, status, Pmax, Pmin]``
        - ``"branch"`` : numpy array, columns
          ``[fbus, tbus, r, x, b, rateA, rateB, rateC, ratio, angle,
          status]``

    name : str, optional
        Network name (default: ``""``).
    f_hz : float, optional
        System frequency in Hz (default: 50.0).
    s_base : float, optional
        Override system MVA base.  If *None* (default), uses
        ``ppc["baseMVA"]``.
    pol : int, optional
        Number of poles for future DC elements (default: 2).

    Returns
    -------
    Network
        A network containing only AC elements, ready for DC extensions.

    Examples
    --------
    >>> from pypower.case14 import case14
    >>> import acdcpf as pf
    >>> net = pf.from_pypower(case14(), name="IEEE 14-bus")
    >>> # Add DC elements on top
    >>> dc0 = pf.create_dc_bus(net, v_base=400.0, dc_grid=0, bus_type="vdc")
    >>> dc1 = pf.create_dc_bus(net, v_base=400.0, dc_grid=0, bus_type="p")
    >>> pf.create_dc_line(net, dc0, dc1, length_km=100, r_ohm_per_km=0.01)
    >>> pf.create_vsc(net, ac_bus=0, dc_bus=dc0, s_mva=200,
    ...               control_mode="vdc_q", v_dc_pu=1.0)
    >>> pf.run_pf(net)
    """
    baseMVA = float(s_base if s_base is not None else ppc["baseMVA"])

    net = create_empty_network(name=name, s_base=baseMVA, f_hz=f_hz, pol=pol)
    _import_ac(ppc, net)
    return net
