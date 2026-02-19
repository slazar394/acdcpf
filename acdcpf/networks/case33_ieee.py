"""
IEEE 33-bus distribution system with multi-terminal DC grid.

This network is based on the MATLAB case files case33_ieee_AC.m and case33_ieee_DC.m.

System composition:
- 21 AC buses (nodes 1,2,3,4,5,6,7,12,13,14,15,19,20,23,24,25,29,30,31,32,33)
- 12 DC buses forming 3 DC grids
- 7 VSC converters connecting AC and DC systems
- 9 DC lines

AC System:
- Bus 1: Slack bus (reference)
- Buses 5, 24, 29: PV buses with generators
- All other buses: PQ load buses

DC System:
- Grid 1 (buses 8,9,10,11): Connected via converters at DC buses 8 and 11
- Grid 2 (buses 26,27,28): Connected via converters at DC buses 26 and 28
- Grid 3 (buses 16,17,18,21,22): Connected via converters at DC buses 16, 18, and 21
"""

import math
from ..network import Network, create_empty_network
from ..create.ac import create_ac_bus, create_ac_line, create_ac_load, create_ac_gen
from ..create.dc import create_dc_bus, create_dc_line
from ..create.converters import create_vsc


def create_case33_ieee() -> Network:
    """
    Create the IEEE 33-bus distribution system with MTDC grid.

    Returns
    -------
    Network
        The complete hybrid AC/DC network.
    """
    net = create_empty_network(
        name="IEEE 33-bus with MTDC",
        s_base=100.0,
        f_hz=50.0,
        pol=1  # Monopolar DC grid
    )

    # Base voltage for AC system
    base_kv_ac = 12.67  # kV

    # ===================================================================
    # AC BUSES
    # Based on case33_ieee_AC.m bus matrix
    # Columns: bus_i, type, Pd, Qd, Gs, Bs, area, Vm, Va, baseKV, zone, Vmax, Vmin
    # ===================================================================

    # Create AC buses with their load data
    # Bus mapping: MATPOWER bus numbers -> internal indices
    bus_map = {}  # MATPOWER bus number -> internal index

    # Bus data: (bus_number, type, Pd_MW, Qd_MVAr, Vm_pu)
    ac_bus_data = [
        (1,  3, 0.00, 0.00, 1.05),   # Slack bus
        (2,  1, 0.20, 0.12, 1.00),
        (3,  1, 0.18, 0.08, 1.00),
        (4,  1, 0.24, 0.06, 1.00),
        (5,  2, 0.14, 0.06, 1.03),   # PV bus
        (6,  1, 0.20, 0.10, 1.00),
        (7,  1, 0.20, 0.10, 1.00),
        (12, 1, 0.12, 0.07, 1.00),
        (13, 1, 0.06, 0.02, 1.00),
        (14, 1, 0.40, 0.20, 1.00),
        (15, 1, 0.26, 0.11, 1.00),
        (19, 1, 0.18, 0.08, 1.00),
        (20, 1, 0.18, 0.08, 1.00),
        (23, 1, 0.18, 0.10, 1.00),
        (24, 2, 0.12, 0.06, 1.03),   # PV bus
        (25, 1, 0.30, 0.10, 1.00),
        (29, 2, 0.09, 0.04, 1.02),   # PV bus
        (30, 1, 0.10, 0.06, 1.00),
        (31, 1, 0.17, 0.05, 1.00),
        (32, 1, 0.15, 0.07, 1.00),
        (33, 1, 0.24, 0.16, 1.00),
    ]

    for bus_num, bus_type, pd, qd, vm in ac_bus_data:
        idx = create_ac_bus(net, vr_kv=base_kv_ac, name=f"Bus {bus_num}")
        bus_map[bus_num] = idx
        if pd != 0.0 or qd != 0.0:
            create_ac_load(net, bus=idx, p_mw=pd, q_mvar=qd, name=f"Load {bus_num}")

    # ===================================================================
    # AC GENERATORS
    # Based on case33_ieee_AC.m gen matrix
    # Columns: bus, Pg, Qg, Qmax, Qmin, Vg, mBase, status, Pmax, Pmin
    # Note: Q limits in original file are in MVAr (very small values typical
    # for distribution systems). We use the same values as MATPOWER.
    # ===================================================================

    # Generator at slack bus 1 (Qmax=500, Qmin=-500 from MATPOWER)
    create_ac_gen(net, bus=bus_map[1], p_mw=0.0, v_pu=1.05,
                  q_min_mvar=-500.0, q_max_mvar=500.0, name="Gen 1 (Slack)")

    # Generator at PV bus 5 (Pg=0.5 MW, Qmax=0.25, Qmin=0.05 from MATPOWER)
    # Note: Original has positive Qmin which forces Q generation
    create_ac_gen(net, bus=bus_map[5], p_mw=0.5, v_pu=1.03,
                  q_min_mvar=-50.0, q_max_mvar=50.0, name="Gen 5")

    # Generator at PV bus 24 (Pg=0.5 MW)
    create_ac_gen(net, bus=bus_map[24], p_mw=0.5, v_pu=1.03,
                  q_min_mvar=-50.0, q_max_mvar=50.0, name="Gen 24")

    # Generator at PV bus 29 (Pg=0.5 MW)
    create_ac_gen(net, bus=bus_map[29], p_mw=0.5, v_pu=1.02,
                  q_min_mvar=-50.0, q_max_mvar=50.0, name="Gen 29")

    # ===================================================================
    # AC LINES
    # Based on case33_ieee_AC.m branch matrix
    # Columns: fbus, tbus, r, x, b, rateA, rateB, rateC, ratio, angle, status
    # Note: r and x are in p.u. on 100 MVA base
    # Convert to ohm/km assuming length=1km (since given in pu)
    # Z_base = V^2 / S_base = (12.67)^2 / 100 = 1.605 ohm
    # ===================================================================

    z_base = base_kv_ac**2 / net.s_base  # ohm

    # Branch data: (fbus, tbus, r_pu, x_pu)
    # Using length_km=1.0 and converting r_pu to r_ohm
    ac_branch_data = [
        (1,  2,  0.058, 0.029),
        (2,  3,  0.308, 0.157),
        (3,  4,  0.228, 0.116),
        (4,  5,  0.238, 0.121),
        (5,  6,  0.511, 0.441),
        (6,  7,  0.117, 0.386),
        (12, 13, 0.916, 0.721),
        (13, 14, 0.338, 0.445),
        (14, 15, 0.369, 0.328),
        (2,  19, 0.102, 0.098),
        (19, 20, 0.939, 0.846),
        (3,  23, 0.282, 0.192),
        (23, 24, 0.560, 0.442),
        (24, 25, 0.559, 0.437),
        (25, 29, 0.312, 0.312),
        (29, 30, 0.317, 0.161),
        (30, 31, 0.608, 0.601),
        (31, 32, 0.194, 0.226),
        (31, 15, 1.248, 1.248),
        (32, 33, 0.213, 0.331),
    ]

    for fbus, tbus, r_pu, x_pu in ac_branch_data:
        # Convert pu values to ohm
        r_ohm = r_pu * z_base
        x_ohm = x_pu * z_base
        create_ac_line(net, from_bus=bus_map[fbus], to_bus=bus_map[tbus],
                       length_km=1.0, r_ohm_per_km=r_ohm, x_ohm_per_km=x_ohm,
                       b_us_per_km=0.0, name=f"Line {fbus}-{tbus}")

    # ===================================================================
    # DC BUSES
    # Based on case33_ieee_DC.m busdc matrix
    # Columns: busdc_i, busac_i, grid, Pdc, Vdc, basekVdc, Vdcmax, Vdcmin, Cdc
    # ===================================================================

    base_kv_dc = 20.67  # kV

    dc_bus_map = {}  # DC bus number -> internal index

    # DC bus data: (dc_bus_num, ac_bus_num, grid, Pdc, Vdc_pu)
    # ac_bus_num=0 means no AC connection
    dc_bus_data = [
        (8,  7,  1, 0.0, 1.02),
        (9,  0,  1, 0.0, 1.00),
        (10, 0,  1, 0.0, 1.00),
        (11, 12, 1, 0.0, 1.00),
        (16, 15, 3, 0.0, 1.00),
        (17, 0,  3, 0.0, 1.00),
        (18, 33, 3, 0.0, 1.00),
        (21, 20, 3, 0.0, 1.00),
        (22, 0,  3, 0.0, 1.00),
        (26, 6,  2, 0.0, 1.00),
        (27, 0,  2, 0.0, 1.00),
        (28, 29, 2, 0.0, 1.00),
    ]

    # DC buses with Vdc slack converters (type_dc=2 in convdc)
    vdc_slack_buses = {8, 26, 18}

    for dc_bus_num, ac_bus_num, grid, pdc, vdc_pu in dc_bus_data:
        # Set bus type based on converter control
        if dc_bus_num in vdc_slack_buses:
            bus_type = "vdc"
        else:
            bus_type = "p"
        idx = create_dc_bus(net, v_base=base_kv_dc, dc_grid=grid, v_dc_pu=vdc_pu,
                            bus_type=bus_type, name=f"DC Bus {dc_bus_num}")
        dc_bus_map[dc_bus_num] = idx

    # ===================================================================
    # DC LINES
    # Based on case33_ieee_DC.m branchdc matrix
    # Columns: fbusdc, tbusdc, r, l, c, rateA, rateB, rateC, status
    # r is in p.u. on DC base
    # ===================================================================

    z_base_dc = base_kv_dc**2 / net.s_base  # ohm

    # DC branch data: (fbus, tbus, r_pu)
    # Using length_km=1.0 and converting r_pu to r_ohm
    dc_branch_data = [
        (8,  9,  0.482),
        (9,  10, 0.487),
        (10, 11, 0.092),
        (16, 17, 0.603),
        (17, 18, 0.343),
        (21, 22, 0.332),
        (26, 27, 0.133),
        (27, 28, 0.496),
        (16, 22, 0.936),
    ]

    for fbus, tbus, r_pu in dc_branch_data:
        r_ohm = r_pu * z_base_dc
        create_dc_line(net, from_bus=dc_bus_map[fbus], to_bus=dc_bus_map[tbus],
                       length_km=1.0, r_ohm_per_km=r_ohm,
                       name=f"DC Line {fbus}-{tbus}")

    # ===================================================================
    # VSC CONVERTERS
    # Based on case33_ieee_DC.m convdc matrix
    # Columns: busdc_i, type_dc, type_ac, P_g, Q_g, Vtar, rtf, xtf, bf, rc, xc,
    #          basekVac, Vmmax, Vmmin, Imax, status, LossA, LossB, LossCrec, LossCinv
    #
    # type_dc: 1 = Vdc slack (controls DC voltage), 2 = P-controlled
    # type_ac: 1 = PQ control, 2 = PV/Vac control
    # P_g, Q_g are in per-unit on 100 MVA base
    # ===================================================================

    # Mapping DC bus numbers to AC bus numbers (from busdc data)
    dc_to_ac = {8: 7, 11: 12, 16: 15, 18: 33, 21: 20, 26: 6, 28: 29}

    # Converter data from case33_ieee_DC.m:
    # (dc_bus, type_dc, type_ac, P_g_MW, Q_g_MVAr, V_target, xc)
    #
    # NOTE: Power values in MatACDC convdc matrix are in MW/MVAr, NOT per-unit!
    # (See runacdcpf.m line 275: Pvsc = convdc(:, PCONV)/baseMVA to convert to pu)
    #
    # P-controlled converters (type_dc=2) with Vac control (type_ac=2):
    # These are AC slack converters for their islands - P is determined by island balance
    # DC bus 8 connects AC bus 7, DC bus 26 connects AC bus 6, DC bus 18 connects AC bus 33

    # Vdc slack converters (type_dc=1) with PQ control (type_ac=1):
    # These control DC voltage and have specified P, Q injections
    # DC bus 11: P=0.25 MW, Q=0.075 MVAr (rectifier - power into DC grid)
    # DC bus 28: P=0.76 MW, Q=0.25 MVAr (rectifier)
    # DC bus 16: P=0.28 MW, Q=0.092 MVAr (rectifier)
    # DC bus 21: P=-1.20 MW, Q=-0.40 MVAr (inverter - power out of DC grid)

    conv_data = [
        # (dc_bus, type_dc, type_ac, P_g_MW, Q_g_MVAr, V_target, xc)
        # MatACDC convention: type_dc=1 is P-control, type_dc=2 is Vdc-control
        # P convention: MatACDC P_g > 0 = inverter, Python P_s > 0 = rectifier (NEGATE P)
        # Q convention: Also needs negation for Python's load-based injection model
        #
        # Vdc slack with Vac control (type_dc=2, type_ac=2)
        (8,  2, 2,  0.00,  0.000, 1.03, 0.16428),
        (26, 2, 2,  0.00,  0.000, 1.00, 0.16428),
        (18, 2, 2,  0.00,  0.000, 1.00, 0.16428),
        # P-controlled with PQ control (type_dc=1, type_ac=1)
        # Both P and Q are negated for Python's convention
        (11, 1, 1, -0.25, -0.075, 1.00, 0.16428),  # MatACDC: P=+0.25, Q=+0.075
        (28, 1, 1, -0.76, -0.250, 1.00, 0.16428),  # MatACDC: P=+0.76, Q=+0.25
        (16, 1, 1, -0.28, -0.092, 1.00, 0.16428),  # MatACDC: P=+0.28, Q=+0.092
        (21, 1, 1,  1.20,  0.400, 1.00, 0.16428),  # MatACDC: P=-1.20, Q=-0.40
    ]

    for dc_bus, type_dc, type_ac, p_mw, q_mvar, v_tar, xc in conv_data:
        ac_bus = dc_to_ac.get(dc_bus)
        if ac_bus is None:
            continue

        # Power values are already in MW/MVAr (not per-unit)

        # Determine control mode based on type_dc and type_ac
        # MatACDC convention:
        #   type_dc=1 (DCNOSLACK) = constant P control
        #   type_dc=2 (DCSLACK) = Vdc control
        if type_dc == 2:  # Vdc slack converter (DCSLACK)
            if type_ac == 2:  # Vac control
                control_mode = "vdc_vac"
            else:  # PQ control
                control_mode = "vdc_q"
            v_dc_pu = 1.0
        else:  # P-controlled converter (type_dc=1, DCNOSLACK)
            if type_ac == 2:  # Vac control
                control_mode = "p_vac"
            else:  # PQ control
                control_mode = "p_q"
            v_dc_pu = None

        create_vsc(
            net,
            ac_bus=bus_map[ac_bus],
            dc_bus=dc_bus_map[dc_bus],
            s_mva=100.0,
            control_mode=control_mode,
            p_mw=p_mw,
            q_mvar=q_mvar,
            v_ac_pu=v_tar if type_ac == 2 else None,
            v_dc_pu=v_dc_pu,
            r_pu=0.0001,
            x_pu=xc,
            loss_a=0.0,
            loss_b=0.0,
            loss_c=0.0,
            name=f"VSC DC{dc_bus}-AC{ac_bus}"
        )

    return net