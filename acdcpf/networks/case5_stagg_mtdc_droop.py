"""
5-bus Stagg system with 3-terminal MTDC grid (droop control).

Based on MatACDC case files:
- AC: case5_stagg.m
- DC: case5_stagg_MTDCdroop.m

References:
- G.W. Stagg, A.H. El-Abiad, "Computer methods in power system analysis",
  McGraw-Hill, 1968.
- J. Beerten, D. Van Hertem, R. Belmans, "VSC MTDC systems with a
  distributed DC voltage control - a power flow approach", IEEE Powertech 2011.

System composition:
- 5 AC buses (bus 1 is slack, bus 2 is PV)
- 3 DC buses forming a multi-terminal DC grid
- 7 AC branches
- 3 DC branches (meshed DC grid)
- 3 VSC converters (all with droop control)
"""

from ..network import Network, create_empty_network
from ..create.ac import create_ac_bus, create_ac_line, create_ac_load, create_ac_gen
from ..create.dc import create_dc_bus, create_dc_line
from ..create.converters import create_vsc


def create_case5_stagg_mtdc_droop() -> Network:
    """
    Create the 5-bus Stagg system with 3-terminal MTDC grid (droop control).

    Returns
    -------
    Network
        The 5-bus AC system with 3-terminal MTDC grid using droop control.
    """
    net = create_empty_network(
        name="Case5 Stagg MTDC Droop",
        s_base=100.0,
        f_hz=50.0,
        pol=2  # Bipolar DC grid
    )

    base_kv_ac = 345.0  # kV
    base_kv_dc = 345.0  # kV

    # ===================================================================
    # AC BUSES (same as other case5_stagg variants)
    # ===================================================================

    bus_map = {}

    ac_bus_data = [
        (1, 3, 0.0, 0.0, 1.06),    # Slack
        (2, 2, 20.0, 10.0, 1.00),  # PV
        (3, 1, 45.0, 15.0, 1.00),  # PQ
        (4, 1, 40.0, 5.0, 1.00),   # PQ
        (5, 1, 60.0, 10.0, 1.00),  # PQ
    ]

    for bus_num, bus_type, pd, qd, vm in ac_bus_data:
        idx = create_ac_bus(net, vr_kv=base_kv_ac, name=f"Bus {bus_num}")
        bus_map[bus_num] = idx
        if pd != 0.0 or qd != 0.0:
            create_ac_load(net, bus=idx, p_mw=pd, q_mvar=qd, name=f"Load {bus_num}")

    # ===================================================================
    # AC GENERATORS
    # ===================================================================

    create_ac_gen(net, bus=bus_map[1], p_mw=0.0, v_pu=1.06,
                  q_min_mvar=-500.0, q_max_mvar=500.0, name="Gen 1 (Slack)")
    create_ac_gen(net, bus=bus_map[2], p_mw=40.0, v_pu=1.00,
                  q_min_mvar=-300.0, q_max_mvar=300.0, name="Gen 2")

    # ===================================================================
    # AC BRANCHES
    # ===================================================================

    z_base = base_kv_ac**2 / net.s_base
    y_base = 1.0 / z_base

    ac_branch_data = [
        (1, 2, 0.02, 0.06, 0.06),
        (1, 3, 0.08, 0.24, 0.05),
        (2, 3, 0.06, 0.18, 0.04),
        (2, 4, 0.06, 0.18, 0.04),
        (2, 5, 0.04, 0.12, 0.03),
        (3, 4, 0.01, 0.03, 0.02),
        (4, 5, 0.08, 0.24, 0.05),
    ]

    for fbus, tbus, r_pu, x_pu, b_pu in ac_branch_data:
        r_ohm = r_pu * z_base
        x_ohm = x_pu * z_base
        b_us = b_pu * y_base * 1e6
        create_ac_line(net, from_bus=bus_map[fbus], to_bus=bus_map[tbus],
                       length_km=1.0, r_ohm_per_km=r_ohm, x_ohm_per_km=x_ohm,
                       b_us_per_km=b_us, name=f"Line {fbus}-{tbus}")

    # ===================================================================
    # DC BUSES (same topology as MTDCslack)
    # ===================================================================

    dc_bus_map = {}

    dc_bus_data = [
        (1, 2, 1, 1.0),
        (2, 3, 1, 1.0),
        (3, 5, 1, 1.0),
    ]

    for dc_bus, ac_bus, grid, vdc_pu in dc_bus_data:
        # All droop buses need a reference for initial voltage
        bus_type = "droop"
        idx = create_dc_bus(net, v_base=base_kv_dc, dc_grid=grid, v_dc_pu=vdc_pu,
                            bus_type=bus_type, name=f"DC Bus {dc_bus}")
        dc_bus_map[dc_bus] = idx

    # ===================================================================
    # DC BRANCHES (same as MTDCslack)
    # ===================================================================

    z_base_dc = base_kv_dc**2 / net.s_base

    dc_branch_data = [
        (1, 2, 0.052),
        (2, 3, 0.052),
        (1, 3, 0.073),
    ]

    for fbus, tbus, r_pu in dc_branch_data:
        r_ohm = r_pu * z_base_dc
        create_dc_line(net, from_bus=dc_bus_map[fbus], to_bus=dc_bus_map[tbus],
                       length_km=1.0, r_ohm_per_km=r_ohm,
                       name=f"DC Line {fbus}-{tbus}")

    # ===================================================================
    # VSC CONVERTERS
    # From case5_stagg_MTDCdroop.m:
    # busdc_i type_dc type_ac P_g   Q_g  Vtar  rtf    xtf    bf     rc     xc       basekVac Vmmax Vmmin Imax status LossA LossB LossCrec LossCinv droop   Pdcset   Vdcset dVdcset
    # 1       3       1       -60   -40  1     0.0015 0.1121 0.0887 0.0001 0.16428  345      1.1   0.9   1.1  1      1.103 0.887 2.885    4.371    0.0050  -58.6274 1.0079 0
    # 2       3       2       0     0    1     0.0015 0.1121 0.0887 0.0001 0.16428  345      1.1   0.9   1.1  1      1.103 0.887 2.885    4.371    0.0070  21.9013  1.0000 0
    # 3       3       1       35    5    1     0.0015 0.1121 0.0887 0.0001 0.16428  345      1.1   0.9   1.1  1      1.103 0.887 2.885    4.371    0.0050  36.1856  0.9978 0
    #
    # type_dc=3 means droop control
    # droop is in pu (kV per MW)
    # Pdcset is DC power setpoint in MW
    # Vdcset is DC voltage setpoint in pu
    # ===================================================================

    dc_to_ac = {1: 2, 2: 3, 3: 5}

    # Converter 1: Droop control (type_dc=3) with PQ control (type_ac=1)
    # P=-60 MW, Q=-40 MVAr (inverter)
    # Droop: 0.0050 pu (kV/MW), Pdcset=-58.6274 MW, Vdcset=1.0079 pu
    create_vsc(
        net,
        ac_bus=bus_map[dc_to_ac[1]],
        dc_bus=dc_bus_map[1],
        s_mva=110.0,
        control_mode="droop_q",
        p_mw=60.0,      # Negated
        q_mvar=40.0,    # Negated
        droop_kv_per_mw=0.0050,   # kV/MW
        p_dc_set_mw=-58.6274,     # DC power setpoint
        v_dc_set_pu=1.0079,       # DC voltage setpoint
        r_tf_pu=0.0015, x_tf_pu=0.1121,
        r_c_pu=0.0001, x_c_pu=0.16428,
        b_filter_pu=0.0887,
        loss_a=1.103,
        loss_b=0.887,
        loss_c=2.885,
        name="VSC DC1-AC2"
    )

    # Converter 2: Droop control (type_dc=3) with Vac control (type_ac=2)
    # P=0, Q=0
    # Droop: 0.0070 pu (kV/MW), Pdcset=21.9013 MW, Vdcset=1.0000 pu
    create_vsc(
        net,
        ac_bus=bus_map[dc_to_ac[2]],
        dc_bus=dc_bus_map[2],
        s_mva=110.0,
        control_mode="droop_vac",
        p_mw=0.0,
        q_mvar=0.0,
        v_ac_pu=1.0,
        droop_kv_per_mw=0.0070,
        p_dc_set_mw=21.9013,
        v_dc_set_pu=1.0000,
        r_tf_pu=0.0015, x_tf_pu=0.1121,
        r_c_pu=0.0001, x_c_pu=0.16428,
        b_filter_pu=0.0887,
        loss_a=1.103,
        loss_b=0.887,
        loss_c=2.885,
        name="VSC DC2-AC3"
    )

    # Converter 3: Droop control (type_dc=3) with PQ control (type_ac=1)
    # P=35 MW, Q=5 MVAr (inverter)
    # Droop: 0.0050 pu (kV/MW), Pdcset=36.1856 MW, Vdcset=0.9978 pu
    create_vsc(
        net,
        ac_bus=bus_map[dc_to_ac[3]],
        dc_bus=dc_bus_map[3],
        s_mva=110.0,
        control_mode="droop_q",
        p_mw=-35.0,     # Negated (inverter)
        q_mvar=-5.0,    # Negated
        droop_kv_per_mw=0.0050,
        p_dc_set_mw=36.1856,
        v_dc_set_pu=0.9978,
        r_tf_pu=0.0015, x_tf_pu=0.1121,
        r_c_pu=0.0001, x_c_pu=0.16428,
        b_filter_pu=0.0887,
        loss_a=1.103,
        loss_b=0.887,
        loss_c=2.885,
        name="VSC DC3-AC5"
    )

    return net
