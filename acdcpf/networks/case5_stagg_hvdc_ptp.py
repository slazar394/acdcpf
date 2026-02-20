"""
5-bus Stagg system with point-to-point HVDC link.

Based on MatACDC case files:
- AC: case5_stagg.m
- DC: case5_stagg_HVDCptp.m

References:
- G.W. Stagg, A.H. El-Abiad, "Computer methods in power system analysis",
  McGraw-Hill, 1968.
- J. Beerten, D. Van Hertem, R. Belmans, "VSC MTDC systems with a
  distributed DC voltage control - a power flow approach", IEEE Powertech 2011.

System composition:
- 5 AC buses (bus 1 is slack, bus 2 is PV)
- 2 DC buses forming a point-to-point HVDC link
- 7 AC branches
- 1 DC branch
- 2 VSC converters (one Vdc slack, one P-controlled)
"""

from ..create.ac import create_ac_bus, create_ac_line, create_ac_load, create_ac_gen
from ..create.dc import create_dc_bus, create_dc_line
from ..network import Network, create_empty_network
from ..create.converters import create_vsc


def create_case5_stagg_hvdc_ptp() -> Network:
    """
    Create the 5-bus Stagg system with point-to-point HVDC link.

    Returns
    -------
    Network
        The 5-bus AC system with 2-terminal HVDC link.
    """
    net = create_empty_network(
        name="Case5 Stagg HVDC PtP",
        s_base=100.0,
        f_hz=50.0,
        pol=2  # Bipolar DC grid
    )

    base_kv_ac = 345.0  # kV
    base_kv_dc = 345.0  # kV

    # ===================================================================
    # AC BUSES
    # From case5_stagg.m:
    # bus_i  type  Pd   Qd   Gs  Bs  area  Vm    Va  baseKV zone Vmax Vmin
    # 1      3     0    0    0   0   1     1.06  0   345    1    1.1  0.9  (Slack)
    # 2      2     20   10   0   0   1     1     0   345    1    1.1  0.9  (PV)
    # 3      1     45   15   0   0   1     1     0   345    1    1.1  0.9  (PQ)
    # 4      1     40   5    0   0   1     1     0   345    1    1.1  0.9  (PQ)
    # 5      1     60   10   0   0   1     1     0   345    1    1.1  0.9  (PQ)
    # ===================================================================

    bus_map = {}

    ac_bus_data = [
        # (bus_num, type, Pd_MW, Qd_MVAr, Vm_pu)
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
    # From case5_stagg.m:
    # bus  Pg    Qg  Qmax  Qmin  Vg    mBase  status Pmax Pmin
    # 1    0     0   500   -500  1.06  100    1      250  10   (Slack)
    # 2    40    0   300   -300  1.00  100    1      300  10   (PV)
    # ===================================================================

    create_ac_gen(net, bus=bus_map[1], p_mw=0.0, v_pu=1.06,
                  q_min_mvar=-500.0, q_max_mvar=500.0, name="Gen 1 (Slack)")
    create_ac_gen(net, bus=bus_map[2], p_mw=40.0, v_pu=1.00,
                  q_min_mvar=-300.0, q_max_mvar=300.0, name="Gen 2")

    # ===================================================================
    # AC BRANCHES
    # From case5_stagg.m (r, x, b in pu on 100 MVA base):
    # fbus tbus  r     x     b     rateA rateB rateC ratio angle status
    # 1    2     0.02  0.06  0.06  100   100   100   0     0     1
    # 1    3     0.08  0.24  0.05  100   100   100   0     0     1
    # 2    3     0.06  0.18  0.04  100   100   100   0     0     1
    # 2    4     0.06  0.18  0.04  100   100   100   0     0     1
    # 2    5     0.04  0.12  0.03  100   100   100   0     0     1
    # 3    4     0.01  0.03  0.02  100   100   100   0     0     1
    # 4    5     0.08  0.24  0.05  100   100   100   0     0     1
    # ===================================================================

    z_base = base_kv_ac**2 / net.s_base  # ohm

    ac_branch_data = [
        # (fbus, tbus, r_pu, x_pu, b_pu)
        (1, 2, 0.02, 0.06, 0.06),
        (1, 3, 0.08, 0.24, 0.05),
        (2, 3, 0.06, 0.18, 0.04),
        (2, 4, 0.06, 0.18, 0.04),
        (2, 5, 0.04, 0.12, 0.03),
        (3, 4, 0.01, 0.03, 0.02),
        (4, 5, 0.08, 0.24, 0.05),
    ]

    y_base = 1.0 / z_base  # Siemens

    for fbus, tbus, r_pu, x_pu, b_pu in ac_branch_data:
        r_ohm = r_pu * z_base
        x_ohm = x_pu * z_base
        b_us = b_pu * y_base * 1e6  # Convert to micro-Siemens
        create_ac_line(net, from_bus=bus_map[fbus], to_bus=bus_map[tbus],
                       length_km=1.0, r_ohm_per_km=r_ohm, x_ohm_per_km=x_ohm,
                       b_us_per_km=b_us, name=f"Line {fbus}-{tbus}")

    # ===================================================================
    # DC BUSES
    # From case5_stagg_HVDCptp.m:
    # busdc_i busac_i grid Pdc  Vdc basekVdc Vdcmax Vdcmin Cdc
    # 1       2       1    0    1   345      1.1    0.9    0
    # 2       3       1    0    1   345      1.1    0.9    0
    # ===================================================================

    dc_bus_map = {}

    dc_bus_data = [
        # (dc_bus, ac_bus, grid, Vdc_pu)
        (1, 2, 1, 1.0),
        (2, 3, 1, 1.0),
    ]

    for dc_bus, ac_bus, grid, vdc_pu in dc_bus_data:
        # MatACDC: converter 1 (type_dc=1) controls DC voltage, converter 2 (type_dc=2) is P-controlled
        # But the DC voltage REFERENCE is at bus 2 (V=1.0 pu), with bus 1 higher due to power flow
        # So in acdcpf: bus 2 is the Vdc slack (reference), bus 1 is P-controlled
        bus_type = "p" if dc_bus == 1 else "vdc"
        idx = create_dc_bus(net, v_base=base_kv_dc, dc_grid=grid, v_dc_pu=vdc_pu,
                            bus_type=bus_type, name=f"DC Bus {dc_bus}")
        dc_bus_map[dc_bus] = idx

    # ===================================================================
    # DC BRANCHES
    # From case5_stagg_HVDCptp.m:
    # fbusdc tbusdc r      l   c   rateA rateB rateC status
    # 1      2      0.052  0   0   100   100   100   1
    # ===================================================================

    z_base_dc = base_kv_dc**2 / net.s_base  # ohm

    dc_branch_data = [
        # (fbus, tbus, r_pu)
        (1, 2, 0.052),
    ]

    for fbus, tbus, r_pu in dc_branch_data:
        r_ohm = r_pu * z_base_dc
        create_dc_line(net, from_bus=dc_bus_map[fbus], to_bus=dc_bus_map[tbus],
                       length_km=1.0, r_ohm_per_km=r_ohm,
                       name=f"DC Line {fbus}-{tbus}")

    # ===================================================================
    # VSC CONVERTERS
    # From case5_stagg_HVDCptp.m:
    # busdc_i type_dc type_ac P_g   Q_g  Vtar  rtf    xtf    bf     rc     xc       basekVac Vmmax Vmmin Imax status LossA LossB LossCrec LossCinv
    # 1       1       1       -60   -40  1     0.0015 0.1121 0.0887 0.0001 0.16428  345      1.1   0.9   1.2  1      1.103 0.887 2.885    4.371
    # 2       2       2       0     0    1     0.0015 0.1121 0.0887 0.0001 0.16428  345      1.1   0.9   1.2  1      1.103 0.887 2.885    4.371
    #
    # MatACDC type_dc: 1=Vdc slack, 2=P-controlled
    # MatACDC type_ac: 1=PQ, 2=PV (Vac control)
    # P_g, Q_g are in MW, MVAr (power injected into AC grid, positive = inverter)
    # ===================================================================

    # Mapping DC bus to AC bus
    dc_to_ac = {1: 2, 2: 3}

    # Converter 1: type_dc=1 with PQ control (type_ac=1)
    # P=-60 MW, Q=-40 MVAr from MatACDC
    # MatACDC convention: P<0 = rectifier (absorbing from AC)
    # acdcpf convention: P_s>0 = rectifier (absorbing from AC)
    # So P_s = -P_matacdc = 60 MW
    create_vsc(
        net,
        ac_bus=bus_map[dc_to_ac[1]],
        dc_bus=dc_bus_map[1],
        s_mva=120.0,  # Based on Imax=1.2 pu
        control_mode="p_q",  # P,Q fixed on AC side
        p_mw=60.0,     # Rectifier: absorbing 60 MW from AC
        q_mvar=40.0,   # Absorbing 40 MVAr from AC
        r_tf_pu=0.0015, x_tf_pu=0.1121,
        r_c_pu=0.0001, x_c_pu=0.16428,
        b_filter_pu=0.0887,
        loss_a=1.103,
        loss_b=0.887,
        loss_c=2.885,  # Using LossCrec
        name="VSC DC1-AC2"
    )

    # Converter 2: type_dc=2 with Vac control (type_ac=2)
    # At Vdc slack bus - P determined by DC power balance, Vac controlled on AC side
    # P_s will be negative (inverter: injecting into AC)
    create_vsc(
        net,
        ac_bus=bus_map[dc_to_ac[2]],
        dc_bus=dc_bus_map[2],
        s_mva=120.0,
        control_mode="vdc_vac",  # Vdc slack with Vac control
        p_mw=0.0,  # Not used - determined by DC balance
        q_mvar=0.0,  # Not used - determined by Vac control
        v_ac_pu=1.0,
        v_dc_pu=1.0,  # DC voltage setpoint
        r_tf_pu=0.0015, x_tf_pu=0.1121,
        r_c_pu=0.0001, x_c_pu=0.16428,
        b_filter_pu=0.0887,
        loss_a=1.103,
        loss_b=0.887,
        loss_c=2.885,
        name="VSC DC2-AC3"
    )

    return net
