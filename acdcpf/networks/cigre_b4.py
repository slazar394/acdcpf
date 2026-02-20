"""
CIGRE B4 DC Grid Test System.

Based on MatACDC case file: cigre_b4_dc_grid.m
Transcribed by Oscar Damanik (KU Leuven) from [1].

References:
[1] T. K. Vrana, Y. Yang, D. Jovcic, S. Dennetiere, J. Hardini, and H. Saad,
    "The CIGRE B4 DC Grid Test System," ELECTRA No. 270, pp. 10-19, Oct. 2013.

System composition:
- 11 AC buses (2 slack, 7 PV, 2 PQ)
  - Bus 1 (Ba-A0): Onshore A slack, 380 kV
  - Bus 2 (Ba-A1): Onshore A PV, 380 kV
  - Bus 3 (Ba-B0): Onshore B slack, 380 kV
  - Buses 4-6 (Ba-B1..B3): Onshore B PV, 380 kV
  - Buses 7-11: Offshore PV/PQ, 380 kV (Bo-C1, Bo-C2, Bo-D1, Bo-E1, Bo-F1)
- 8 AC branches
- 15 DC buses in 3 DC grids
  - Grid 1: DC buses 1-2, DCS1 monopole, 200 kV base
  - Grid 2: DC buses 3-10, DCS3 bipole, 400 kV base
  - Grid 3: DC buses 11-15, DCS2 monopole, 200 kV base
- 16 DC branches + 1 DC-DC converter (Cd-E1: bus 9→14, 400/200 kV)
- 11 VSC converters (3 Vdc slack, 3 droop, 5 P-controlled)

Global dcpol=2 (bipolar). Monopole branches (dcpoles=1) have their resistance
doubled to give correct power with the global pol=2 multiplier.
Grids 2 and 3 are coupled via DC-DC converter Cd-E1 (d=0.5).
Grid 1 has no DC connection to others (coupled only via AC network).
"""

from ..network import Network, create_empty_network
from ..create.ac import create_ac_bus, create_ac_line, create_ac_load, create_ac_gen
from ..create.dc import create_dc_bus, create_dc_line
from ..create.converters import create_vsc, create_dcdc


def create_cigre_b4_dc_test_system() -> Network:
    """
    Create the CIGRE B4 DC Grid Test System from MatACDC case file.

    Returns
    -------
    Network
        The complete CIGRE B4 test network.
    """
    net = create_empty_network(
        name="CIGRE B4 DC Grid Test System",
        s_base=100.0,
        f_hz=50.0,
        pol=2,  # Bipolar (global)
    )

    base_kv_ac = 380.0  # All AC buses at 380 kV (matching .m file)

    # ===================================================================
    # AC BUSES (mpc.bus)
    # All at 380 kV per the MatACDC case file.
    # bus_i  type  Pd     Qd  baseKV
    # 1      3     0      0   380   Ba-A0 (Slack onshore A)
    # 2      2     1000   0   380   Ba-A1 (PV onshore A)
    # 3      3     0      0   380   Ba-B0 (Slack onshore B)
    # 4      2     2200   0   380   Ba-B1 (PV onshore B)
    # 5      2     2300   0   380   Ba-B2 (PV onshore B)
    # 6      2     1900   0   380   Ba-B3 (PV onshore B)
    # 7      2     0      0   380   Bo-C1 (Offshore wind)
    # 8      2     0      0   380   Bo-C2 (Offshore wind)
    # 9      2     0      0   380   Bo-D1 (Offshore wind)
    # 10     2     100    0   380   Bo-E1 (Offshore platform)
    # 11     2     0      0   380   Bo-F1 (Offshore wind)
    # ===================================================================

    bus_map = {}
    ac_bus_data = [
        # (bus_num, type, Pd_MW, Qd_MVAr)
        (1,  3, 0.0,    0.0),
        (2,  2, 1000.0, 0.0),
        (3,  3, 0.0,    0.0),
        (4,  2, 2200.0, 0.0),
        (5,  2, 2300.0, 0.0),
        (6,  2, 1900.0, 0.0),
        (7,  2, 0.0,    0.0),
        (8,  2, 0.0,    0.0),
        (9,  2, 0.0,    0.0),
        (10, 2, 100.0,  0.0),
        (11, 2, 0.0,    0.0),
    ]

    for bus_num, bus_type, pd, qd in ac_bus_data:
        idx = create_ac_bus(net, vr_kv=base_kv_ac, name=f"Bus {bus_num}")
        bus_map[bus_num] = idx
        if pd != 0.0 or qd != 0.0:
            create_ac_load(net, bus=idx, p_mw=pd, q_mvar=qd,
                           name=f"Load {bus_num}")

    # ===================================================================
    # AC GENERATORS (mpc.gen)
    # bus  Pg    Qmax  Vg    Pmax
    # 2    2000  720   1.05  4000   (onshore A, dispatchable)
    # 4    1000  360   1.05  2000   (onshore B)
    # 5    1000  360   1.05  2000   (onshore B)
    # 6    1000  360   1.05  2000   (onshore B)
    # 7    500   180   1.05  500    (offshore wind C1)
    # 8    500   180   1.05  500    (offshore wind C2)
    # 9    1000  360   1.05  1000   (offshore wind D1)
    # 11   500   180   1.05  500    (offshore wind F1)
    # Bus 10 (Bo-E1) has no generator — pure load bus.
    # ===================================================================

    # Slack generators
    create_ac_gen(net, bus=bus_map[1], p_mw=0.0, v_pu=1.0,
                  q_min_mvar=-1000.0, q_max_mvar=1000.0,
                  name="Slack-A0")
    create_ac_gen(net, bus=bus_map[3], p_mw=0.0, v_pu=1.0,
                  q_min_mvar=-1000.0, q_max_mvar=1000.0,
                  name="Slack-B0")

    # PV generators (from mpc.gen)
    gen_data = [
        (2,  2000.0, 1.05, 720.0),
        (4,  1000.0, 1.05, 360.0),
        (5,  1000.0, 1.05, 360.0),
        (6,  1000.0, 1.05, 360.0),
        (7,  500.0,  1.05, 180.0),
        (8,  500.0,  1.05, 180.0),
        (9,  1000.0, 1.05, 360.0),
        (11, 500.0,  1.05, 180.0),
    ]

    for bus_num, pg, vg, qmax in gen_data:
        create_ac_gen(net, bus=bus_map[bus_num], p_mw=pg, v_pu=vg,
                      q_min_mvar=0.0, q_max_mvar=qmax,
                      name=f"Gen {bus_num}")

    # ===================================================================
    # AC BRANCHES (mpc.branch)
    # All in per-unit on 100 MVA / 380 kV base.
    # z_base = 380^2 / 100 = 1444.0 ohm
    # fbus tbus  r_pu          x_pu          b_pu
    # 1    2     0.002770083   0.037124749   0.612422072  (x2 parallel)
    # 3    4     0.002770083   0.037124749   0.612422072
    # 3    5     0.002770083   0.037124749   0.612422072
    # 3    6     0.002770083   0.037124749   0.612422072
    # 4    6     0.002770083   0.037124749   0.612422072
    # 5    6     0.002770083   0.037124749   0.612422072
    # 7    8     0.020047562   0.018871969   0.303343744
    # ===================================================================

    z_base = base_kv_ac ** 2 / net.s_base  # 1444.0 ohm
    y_base = 1.0 / z_base

    ac_branch_data = [
        # (fbus, tbus, r_pu, x_pu, b_pu)
        (1, 2, 0.002770083, 0.037124749, 0.612422072),
        (1, 2, 0.002770083, 0.037124749, 0.612422072),  # parallel
        (3, 4, 0.002770083, 0.037124749, 0.612422072),
        (3, 5, 0.002770083, 0.037124749, 0.612422072),
        (3, 6, 0.002770083, 0.037124749, 0.612422072),
        (4, 6, 0.002770083, 0.037124749, 0.612422072),
        (5, 6, 0.002770083, 0.037124749, 0.612422072),
        (7, 8, 0.020047562, 0.018871969, 0.303343744),
    ]

    for fbus, tbus, r_pu, x_pu, b_pu in ac_branch_data:
        r_ohm = r_pu * z_base
        x_ohm = x_pu * z_base
        b_us = b_pu * y_base * 1e6
        create_ac_line(net, from_bus=bus_map[fbus], to_bus=bus_map[tbus],
                       length_km=1.0, r_ohm_per_km=r_ohm,
                       x_ohm_per_km=x_ohm, b_us_per_km=b_us,
                       name=f"Line {fbus}-{tbus}")

    # ===================================================================
    # DC BUSES (mpc.busdc)
    # All in one DC grid (grid=1).
    # busdc  grid  basekVdc
    # 1      1     200   Bm-A1  (DCS1 monopole)
    # 2      1     200   Bm-C1  (DCS1 monopole)
    # 3      1     400   Bb-A1  (DCS3 bipole)
    # 4      1     400   Bb-C2  (DCS3 bipole)
    # 5      1     400   Bb-D1  (DCS3 bipole)
    # 6      1     400   Bb-B4  (DCS3 bipole)
    # 7      1     400   Bb-B1  (DCS3 bipole)
    # 8      1     400   Bb-B1s (DCS3 bipole)
    # 9      1     400   Bb-E1  (DCS3 bipole)
    # 10     1     400   Bb-B2  (DCS3 bipole)
    # 11     1     200   Bm-B2  (DCS2 monopole)
    # 12     1     200   Bm-B3  (DCS2 monopole)
    # 13     1     200   Bm-B5  (DCS2 monopole)
    # 14     1     200   Bm-E1  (DCS2 monopole)
    # 15     1     200   Bm-F1  (DCS2 monopole)
    # ===================================================================

    dc_bus_map = {}

    # Three separate DC grids (no DC branch connects across voltage levels):
    #   Grid 1: DCS1 monopole {1, 2} at 200 kV
    #   Grid 2: DCS3 bipole {3-10} at 400 kV
    #   Grid 3: DCS2 monopole {11-15} at 200 kV
    # Grid 2 ↔ Grid 3 connected via DC-DC converter (bus 9 → bus 14).
    # Grid 1 has no DC branch to other grids (coupled only via AC network).

    dc_bus_data = [
        # (dc_bus, basekVdc, dc_grid, name)
        (1,  200, 1, "Bm-A1"),
        (2,  200, 1, "Bm-C1"),
        (3,  400, 2, "Bb-A1"),
        (4,  400, 2, "Bb-C2"),
        (5,  400, 2, "Bb-D1"),
        (6,  400, 2, "Bb-B4"),
        (7,  400, 2, "Bb-B1"),
        (8,  400, 2, "Bb-B1s"),
        (9,  400, 2, "Bb-E1"),
        (10, 400, 2, "Bb-B2"),
        (11, 200, 3, "Bm-B2"),
        (12, 200, 3, "Bm-B3"),
        (13, 200, 3, "Bm-B5"),
        (14, 200, 3, "Bm-E1"),
        (15, 200, 3, "Bm-F1"),
    ]

    # Vdc slack buses (one per grid, required for NR reference):
    #   Grid 1: bus 1 (Conv 1, control_vdc_mode=3 in MatACDC)
    #   Grid 2: bus 3 (Conv 7 Cb-A1, promoted from droop to Vdc slack)
    #   Grid 3: bus 11 (Conv 3 Cm-B2, promoted from droop to Vdc slack)
    # Remaining droop converters: buses 7, 10, 12 (Conv 8, 9, 4)
    vdc_slack_buses = {1, 3, 11}
    droop_dc_buses = {7, 10, 12}  # Remaining droop converters

    for dc_bus, base_kv_dc, dc_grid, name in dc_bus_data:
        if dc_bus in vdc_slack_buses:
            bus_type = "vdc"
        elif dc_bus in droop_dc_buses:
            bus_type = "droop"
        else:
            bus_type = "p"
        idx = create_dc_bus(net, v_base=base_kv_dc, dc_grid=dc_grid, v_dc_pu=1.0,
                            bus_type=bus_type, name=name)
        dc_bus_map[dc_bus] = idx

    # ===================================================================
    # DC BRANCHES (mpc.branchdc)
    # r is in per-unit on the from-bus base. Convert to ohms.
    #
    # Monopole branches (dcpoles=1) in a bipole system (dcpol=2):
    # Double the resistance so that P = pol * V * G * V gives correct
    # power (effectively: G_eff = dcpoles / (dcpol * r) = 1/(2*r)).
    #
    # Branch 9→14 crosses voltage levels (400→200 kV) and is modeled
    # as a DC-DC converter instead of a DC line.
    # Branch 7→8 is within the 400 kV grid (both sides same base).
    #
    # fbusdc tbusdc r_pu     dcpoles
    # 1      2      0.00475  1   DCS1 monopole
    # 3      4      0.00475  2   DCS3 bipole
    # 3      6      0.01425  2
    # 3      7      0.0114   2   (x2 parallel)
    # 4      5      0.007125 2
    # 6      7      0.0057   2
    # 8      9      0.00475  2
    # 5      9      0.00475  2
    # 6      10     0.007125 2   (x2 parallel)
    # 11     12     0.00475  1   DCS2 monopole
    # 12     13     0.002375 1
    # 13     15     0.002375 1
    # 14     15     0.00475  1
    # 7      8      0.00012  1   DC-DC link Cd-B1 (same base, as DC line)
    # 9      14     0.00012  1   DC-DC link Cd-E1 (cross-voltage, as dcdc)
    # ===================================================================

    base_kv_lookup = {b[0]: b[1] for b in dc_bus_data}

    dc_branch_data = [
        # (fbus, tbus, r_pu, dcpoles)
        (1,  2,  0.00475,   1),
        (3,  4,  0.00475,   2),
        (3,  6,  0.01425,   2),
        (3,  7,  0.0114,    2),
        (3,  7,  0.0114,    2),  # parallel
        (4,  5,  0.007125,  2),
        (6,  7,  0.0057,    2),
        (8,  9,  0.00475,   2),
        (5,  9,  0.00475,   2),
        (6,  10, 0.007125,  2),
        (6,  10, 0.007125,  2),  # parallel
        (11, 12, 0.00475,   1),
        (12, 13, 0.002375,  1),
        (13, 15, 0.002375,  1),
        (14, 15, 0.00475,   1),
        (7,  8,  0.00012,   1),  # DC-DC link Cd-B1 (same 400 kV base)
    ]

    for fbus, tbus, r_pu, dcpoles in dc_branch_data:
        fb_base_kv = base_kv_lookup[fbus]
        z_base_dc = fb_base_kv ** 2 / net.s_base
        r_ohm = r_pu * z_base_dc

        # For monopole branches in bipole system: double R
        if dcpoles == 1:
            r_ohm *= 2.0

        create_dc_line(net, from_bus=dc_bus_map[fbus], to_bus=dc_bus_map[tbus],
                       length_km=1.0, r_ohm_per_km=r_ohm,
                       name=f"DC {fbus}-{tbus}")

    # DC-DC converter link Cd-E1: bus 9 (400 kV, grid 2) → bus 14 (200 kV, grid 3)
    # d_ratio = V_to / V_from = 200/400 = 0.5 (voltage step-down)
    # r_pu = 0.00012 on 400 kV base → r_ohm = 0.00012 * (400^2/100) = 0.192
    # Monopole in bipole: double R → 0.384 ohm
    dcdc_r_ohm = 0.00012 * (400.0 ** 2 / net.s_base) * 2.0
    create_dcdc(net, from_bus=dc_bus_map[9], to_bus=dc_bus_map[14],
                d_ratio=0.5, r_ohm=dcdc_r_ohm, name="Cd-E1")

    # ===================================================================
    # VSC CONVERTERS (mpc.convdc)
    #
    # From the .m file (key columns):
    # busdc busac  Pacrated  basekVac  rtf         xtf        bf        rc          xc          LossA  LossB  LossC  droop  Pdcset  Vdcset  control_pdc  control_vdc  control_vdc_mode
    # 1     2      800       380       7.14e-5     0.00250    13.609    4.16e-5     0.00125     1.103  0.887  2.885  0.005  800     1       0            1            3   → Vdc slack
    # 2     7      800       145       7.14e-5     0.00250    13.609    4.16e-5     0.00125     1.103  0.887  2.885  0.005  800     1       1            0            2   → P-ctrl
    # 11    5      800       380       7.14e-5     0.00250    13.609    4.16e-5     0.00125     1.103  0.887  2.885  10     800     1       1            1            1   → Droop
    # 12    6      1200      380       7.14e-5     0.00250    13.609    4.16e-5     0.00125     1.103  0.887  2.885  10     1200    1       1            1            1   → Droop
    # 14    10     200       145       7.14e-5     0.00250    13.609    4.16e-5     0.00125     1.103  0.887  2.885  0.005  200     1       1            0            2   → P-ctrl
    # 15    11     800       145       7.14e-5     0.00250    13.609    4.16e-5     0.00125     1.103  0.887  2.885  0.005  800     1       1            0            2   → P-ctrl
    # 3     2      2400      380       7.14e-5     0.00250    13.609    4.16e-5     0.00125     1.103  0.887  2.885  10     2400    1       1            1            1   → Droop
    # 7     4      2400      380       7.14e-5     0.00250    13.609    4.16e-5     0.00125     1.103  0.887  2.885  10     2400    1       1            1            1   → Droop
    # 10    5      2400      145       7.14e-5     0.00250    13.609    4.16e-5     0.00125     1.103  0.887  2.885  10     2400    1       1            1            1   → Droop
    # 4     8      800       380       7.14e-5     0.00250    13.609    4.16e-5     0.00125     1.103  0.887  2.885  0.005  800     1       1            0            2   → P-ctrl
    # 5     9      1600      145       7.14e-5     0.00250    13.609    4.16e-5     0.00125     1.103  0.887  2.885  0.005  1600    1       1            0            2   → P-ctrl
    #
    # All converters share the same impedance and loss coefficients.
    # Impedance is in per-unit on system base (not converter base).
    #
    # Control mapping:
    #   control_vdc_mode=3 → Vdc slack (constant Vdc)
    #   control_vdc_mode=1 → Vdc droop (droop from .m file)
    #   control_vdc_mode=2 → P-controlled (constant P from AC side)
    #
    # For P-controlled offshore converters at isolated AC buses (9, 10, 11)
    # or islanded AC grids (7-8): use p_vac so the converter acts as AC slack.
    # For P-controlled at non-isolated buses (bus 8 in C1-C2 island): use p_q.
    #
    # Droop converters: use droop_q. The .m file sets Pdcset=Pacrated for all,
    # which represents the droop reference operating point at Vdc=1.0 pu.
    # ===================================================================

    # Common converter impedance parameters (system pu, from .m file)
    rtf = 7.13994e-05
    xtf = 0.00249898
    bf  = 13.608978
    rc  = 4.16435e-05
    xc  = 0.001249306

    # Common loss coefficients
    loss_a = 1.103   # MW
    loss_b = 0.887   # kV
    loss_c = 2.885   # Ohm

    # Converter data from .m file:
    # (dc_bus, ac_bus, s_mva, basekVac, control, droop_kv_per_mw,
    #  p_dc_set_mw, v_dc_set_pu, p_mw, q_mvar, v_ac_pu, v_dc_pu, name)
    #
    # For droop converters: Pdcset from .m file = rated power = droop ref at V=1.0
    # For P-controlled: P determined by AC island balance (p_vac) or setpoint (p_q)

    conv_data = [
        # Conv 1: Cm-A1 (DC1→AC2) — Vdc slack, Q=0
        # control_vdc_mode=3, Vdcset=1.0
        {
            "dc_bus": 1, "ac_bus": 2, "s_mva": 800.0, "basekVac": 380,
            "control_mode": "vdc_q", "q_mvar": 0.0, "v_dc_pu": 1.0,
            "name": "Cm-A1",
        },
        # Conv 2: Cm-C1 (DC2→AC7) — P-controlled, AC slack for C1-C2 island
        # control_vdc_mode=2 (P-ctrl)
        {
            "dc_bus": 2, "ac_bus": 7, "s_mva": 800.0, "basekVac": 145,
            "control_mode": "p_vac", "p_mw": 0.0, "v_ac_pu": 1.05,
            "name": "Cm-C1",
        },
        # Conv 3: Cm-B2 (DC11→AC5) — Vdc slack for grid 3 (promoted from droop)
        # MatACDC: control_vdc_mode=1, droop=10 kV/MW. Here: Vdc slack at 1.0 pu.
        {
            "dc_bus": 11, "ac_bus": 5, "s_mva": 800.0, "basekVac": 380,
            "control_mode": "vdc_q", "q_mvar": 0.0, "v_dc_pu": 1.0,
            "name": "Cm-B2",
        },
        # Conv 4: Cm-B3 (DC12→AC6) — Droop, Q=0
        # control_vdc_mode=1, droop=10 kV/MW, Pdcset=1200
        {
            "dc_bus": 12, "ac_bus": 6, "s_mva": 1200.0, "basekVac": 380,
            "control_mode": "droop_q", "q_mvar": 0.0,
            "droop_kv_per_mw": 10.0, "p_dc_set_mw": 1200.0, "v_dc_set_pu": 1.0,
            "name": "Cm-B3",
        },
        # Conv 5: Cm-E1 (DC14→AC10) — P-controlled, AC slack for isolated bus 10
        # control_vdc_mode=2
        {
            "dc_bus": 14, "ac_bus": 10, "s_mva": 200.0, "basekVac": 145,
            "control_mode": "p_vac", "p_mw": 0.0, "v_ac_pu": 1.0,
            "name": "Cm-E1",
        },
        # Conv 6: Cm-F1 (DC15→AC11) — P-controlled, AC slack for isolated bus 11
        # control_vdc_mode=2
        {
            "dc_bus": 15, "ac_bus": 11, "s_mva": 800.0, "basekVac": 145,
            "control_mode": "p_vac", "p_mw": 0.0, "v_ac_pu": 1.05,
            "name": "Cm-F1",
        },
        # Conv 7: Cb-A1 (DC3→AC2) — Vdc slack for grid 2 (promoted from droop)
        # MatACDC: control_vdc_mode=1, droop=10 kV/MW. Here: Vdc slack at 1.0 pu.
        {
            "dc_bus": 3, "ac_bus": 2, "s_mva": 2400.0, "basekVac": 380,
            "control_mode": "vdc_q", "q_mvar": 0.0, "v_dc_pu": 1.0,
            "name": "Cb-A1",
        },
        # Conv 8: Cb-B1 (DC7→AC4) — Droop, Q=0
        # control_vdc_mode=1, droop=10 kV/MW, Pdcset=2400
        {
            "dc_bus": 7, "ac_bus": 4, "s_mva": 2400.0, "basekVac": 380,
            "control_mode": "droop_q", "q_mvar": 0.0,
            "droop_kv_per_mw": 10.0, "p_dc_set_mw": 2400.0, "v_dc_set_pu": 1.0,
            "name": "Cb-B1",
        },
        # Conv 9: Cb-B2 (DC10→AC5) — Droop, Q=0
        # control_vdc_mode=1, droop=10 kV/MW, Pdcset=2400
        # NOTE: .m file has basekVac=145 for this onshore converter (likely error)
        {
            "dc_bus": 10, "ac_bus": 5, "s_mva": 2400.0, "basekVac": 145,
            "control_mode": "droop_q", "q_mvar": 0.0,
            "droop_kv_per_mw": 10.0, "p_dc_set_mw": 2400.0, "v_dc_set_pu": 1.0,
            "name": "Cb-B2",
        },
        # Conv 10: Cb-C2 (DC4→AC8) — P-controlled, PQ (C1-C2 island has AC slack at bus 7)
        # control_vdc_mode=2
        # NOTE: .m file has basekVac=380 for this offshore converter (likely error)
        {
            "dc_bus": 4, "ac_bus": 8, "s_mva": 800.0, "basekVac": 380,
            "control_mode": "p_q", "p_mw": 500.0, "q_mvar": 0.0,
            "name": "Cb-C2",
        },
        # Conv 11: Cb-D1 (DC5→AC9) — P-controlled, AC slack for isolated bus 9
        # control_vdc_mode=2
        {
            "dc_bus": 5, "ac_bus": 9, "s_mva": 1600.0, "basekVac": 145,
            "control_mode": "p_vac", "p_mw": 0.0, "v_ac_pu": 1.05,
            "name": "Cb-D1",
        },
    ]

    for c in conv_data:
        # Build kwargs
        kwargs = {
            "ac_bus": bus_map[c["ac_bus"]],
            "dc_bus": dc_bus_map[c["dc_bus"]],
            "s_mva": c["s_mva"],
            "control_mode": c["control_mode"],
            "r_tf_pu": rtf,
            "x_tf_pu": xtf,
            "r_c_pu": rc,
            "x_c_pu": xc,
            "b_filter_pu": bf,
            "loss_a": loss_a,
            "loss_b": loss_b,
            "loss_c": loss_c,
            "loss_base_kv": float(c["basekVac"]),
            "name": c["name"],
        }

        # Optional fields
        for key in ("p_mw", "q_mvar", "v_ac_pu", "v_dc_pu",
                     "droop_kv_per_mw", "p_dc_set_mw", "v_dc_set_pu"):
            if key in c:
                kwargs[key] = c[key]

        create_vsc(net, **kwargs)

    return net
