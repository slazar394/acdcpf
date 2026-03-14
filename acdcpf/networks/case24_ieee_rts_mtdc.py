"""
IEEE 24-bus RTS (3 zones) with Multi-Terminal DC grids.

Based on MatACDC case files:
- AC: case24_ieee_rts1996_3zones.m
- DC: case24_ieee_rts1996_MTDC.m

References:
- IEEE Reliability Test System Task Force, "IEEE reliability test system-96",
  IEEE Trans. Power Systems, Vol. 14, No. 3, Aug. 1999, pp. 1010-1020.
- MATPOWER case file case24_ieee_rts.m by Bruce Wollenberg

System composition:
- 50 AC buses across 3 asynchronous zones (1xx, 2xx, 3xx)
- 7 DC buses forming 2 DC grids
- 2 DC grids connecting the asynchronous AC zones:
  - Grid 1: 3-terminal (buses 1,2,3) connecting zones 1, 2, 3
  - Grid 2: 4-terminal meshed (buses 4,5,6,7) connecting zones 1, 2
- Multiple VSC converters with P and Vdc control
"""

from ..network import Network, create_empty_network
from ..create.ac import create_ac_bus, create_ac_line, create_ac_load, create_ac_gen
from ..create.dc import create_dc_bus, create_dc_line
from ..create.converters import create_vsc


def create_case24_ieee_rts_mtdc() -> Network:
    """
    Create the IEEE 24-bus RTS (3 zones) with MTDC grids.

    Returns
    -------
    Network
        The 50-bus AC system with 7-terminal DC system (2 DC grids).
    """
    net = create_empty_network(
        name="IEEE 24-bus RTS 3-Zones with MTDC",
        s_base=100.0,
        f_hz=60.0,  # IEEE RTS uses 60 Hz
        pol=2  # Bipolar DC grid
    )

    # ===================================================================
    # AC BUSES
    # From case24_ieee_rts1996_3zones.m
    # 50 buses: 24 in zone 1 (101-124), 24 in zone 2 (201-224), 2 in zone 3 (301-302)
    # ===================================================================

    bus_map = {}

    # Zone 1 buses (101-124) - matches case24_ieee_rts1996_3zones.m
    # Vmin=0.95, Vmax=1.05 per MATLAB; bus 106 has Bs=1.00 (shunt susceptance)
    zone1_bus_data = [
        # (bus_num, type, Pd, Qd, Vm, baseKV, bs_pu)
        (101, 2, 108, 22, 1.0, 138, 0.0),
        (102, 2, 97, 20, 1.0, 138, 0.0),
        (103, 1, 180, 37, 1.0, 138, 0.0),
        (104, 1, 74, 15, 1.0, 138, 0.0),
        (105, 1, 71, 14, 1.0, 138, 0.0),
        (106, 1, 136, 28, 1.0, 138, 1.0),   # Bs=1.00 in MATLAB
        (107, 2, 125, 25, 1.0, 138, 0.0),
        (108, 1, 171, 35, 1.0, 138, 0.0),
        (109, 1, 175, 36, 1.0, 138, 0.0),
        (110, 1, 195, 40, 1.0, 138, 0.0),
        (111, 1, 0, 0, 1.0, 230, 0.0),
        (112, 1, 0, 0, 1.0, 230, 0.0),
        (113, 3, 265, 54, 1.0, 230, 0.0),   # Slack for zone 1
        (114, 2, 194, 39, 1.0, 230, 0.0),
        (115, 2, 317, 64, 1.0, 230, 0.0),
        (116, 2, 100, 20, 1.0, 230, 0.0),
        (117, 1, 0, 0, 1.0, 230, 0.0),
        (118, 2, 333, 68, 1.0, 230, 0.0),
        (119, 1, 181, 37, 1.0, 230, 0.0),
        (120, 1, 128, 26, 1.0, 230, 0.0),
        (121, 2, 0, 0, 1.0, 230, 0.0),
        (122, 2, 0, 0, 1.0, 230, 0.0),
        (123, 2, 0, 0, 1.0, 230, 0.0),
        (124, 1, 0, 0, 1.0, 230, 0.0),
    ]

    # Zone 2 buses (201-224)
    zone2_bus_data = [
        (201, 2, 108, 22, 1.0, 138, 0.0),
        (202, 2, 97, 20, 1.0, 138, 0.0),
        (203, 1, 180, 37, 1.0, 138, 0.0),
        (204, 1, 74, 15, 1.0, 138, 0.0),
        (205, 1, 71, 14, 1.0, 138, 0.0),
        (206, 1, 136, 28, 1.0, 138, 1.0),   # Bs=1.00 in MATLAB
        (207, 2, 125, 25, 1.0, 138, 0.0),
        (208, 1, 171, 35, 1.0, 138, 0.0),
        (209, 1, 175, 36, 1.0, 138, 0.0),
        (210, 1, 195, 40, 1.0, 138, 0.0),
        (211, 1, 0, 0, 1.0, 230, 0.0),
        (212, 1, 0, 0, 1.0, 230, 0.0),
        (213, 3, 265, 54, 1.0, 230, 0.0),   # Slack for zone 2
        (214, 2, 194, 39, 1.0, 230, 0.0),
        (215, 2, 317, 64, 1.0, 230, 0.0),
        (216, 2, 100, 20, 1.0, 230, 0.0),
        (217, 1, 0, 0, 1.0, 230, 0.0),
        (218, 2, 333, 68, 1.0, 230, 0.0),
        (219, 1, 181, 37, 1.0, 230, 0.0),
        (220, 1, 128, 26, 1.0, 230, 0.0),
        (221, 2, 0, 0, 1.0, 230, 0.0),
        (222, 2, 0, 0, 1.0, 230, 0.0),
        (223, 2, 0, 0, 1.0, 230, 0.0),
        (224, 1, 0, 0, 1.0, 230, 0.0),
    ]

    # Zone 3 buses (301-302)
    zone3_bus_data = [
        (301, 1, 0, 0, 1.0, 230, 0.0),
        (302, 3, 0, 0, 1.05, 230, 0.0),  # Slack for zone 3
    ]

    all_bus_data = zone1_bus_data + zone2_bus_data + zone3_bus_data

    for bus_num, bus_type, pd, qd, vm, base_kv, bs_pu in all_bus_data:
        idx = create_ac_bus(
            net, vr_kv=base_kv, name=f"Bus {bus_num}",
            v_min_pu=0.95, v_max_pu=1.05, bs_pu=bs_pu
        )
        bus_map[bus_num] = idx
        if pd != 0.0 or qd != 0.0:
            create_ac_load(net, bus=idx, p_mw=pd, q_mvar=qd, name=f"Load {bus_num}")

    # ===================================================================
    # AC GENERATORS
    # From case24_ieee_rts1996_3zones.m. Slack buses (type 3) are 113, 213, 302.
    # Order generators so slack-bus gens are first per zone (power flow uses
    # first gen's bus as REF to match MatACDC).
    # ===================================================================

    # Zone 1: put slack bus 113 first, then rest
    gen_data_zone1 = [
        (113, 95.1, 1.020, 80, 0),   # Slack (type 3) - must be first in zone 1
        (113, 95.1, 1.020, 80, 0),
        (113, 95.1, 1.020, 80, 0),
        (114, 0, 0.980, 200, -50),   # Synchronous condenser
        (115, 12, 1.014, 6, 0),
        (115, 12, 1.014, 6, 0),
        (115, 12, 1.014, 6, 0),
        (115, 12, 1.014, 6, 0),
        (115, 12, 1.014, 6, 0),
        (115, 155, 1.014, 80, -50),
        (116, 155, 1.017, 80, -50),
        (118, 400, 1.05, 200, -50),
        (121, 400, 1.05, 200, -50),
        (122, 50, 1.05, 16, -10),
        (122, 50, 1.05, 16, -10),
        (122, 50, 1.05, 16, -10),
        (122, 50, 1.05, 16, -10),
        (122, 50, 1.05, 16, -10),
        (122, 50, 1.05, 16, -10),
        (123, 155, 1.05, 80, -50),
        (123, 155, 1.05, 80, -50),
        (123, 350, 1.05, 150, -25),
        (101, 10, 1.035, 10, 0),
        (101, 10, 1.035, 10, 0),
        (101, 76, 1.035, 30, -25),
        (101, 76, 1.035, 30, -25),
        (102, 10, 1.035, 10, 0),
        (102, 10, 1.035, 10, 0),
        (102, 76, 1.035, 30, -25),
        (102, 76, 1.035, 30, -25),
        (107, 80, 1.025, 60, 0),
        (107, 80, 1.025, 60, 0),
    ]

    # Zone 2: put slack bus 213 first, then rest
    gen_data_zone2 = [
        (213, 95.1, 1.020, 80, 0),   # Slack (type 3) - must be first in zone 2
        (213, 95.1, 1.020, 80, 0),
        (213, 95.1, 1.020, 80, 0),
        (214, 0, 0.980, 200, -50),
        (215, 12, 1.014, 6, 0),
        (215, 12, 1.014, 6, 0),
        (215, 12, 1.014, 6, 0),
        (215, 12, 1.014, 6, 0),
        (215, 12, 1.014, 6, 0),
        (215, 155, 1.014, 80, -50),
        (216, 155, 1.017, 80, -50),
        (218, 400, 1.05, 200, -50),
        (221, 400, 1.05, 200, -50),
        (222, 50, 1.05, 16, -10),
        (222, 50, 1.05, 16, -10),
        (222, 50, 1.05, 16, -10),
        (222, 50, 1.05, 16, -10),
        (222, 50, 1.05, 16, -10),
        (222, 50, 1.05, 16, -10),
        (223, 155, 1.05, 80, -50),
        (223, 155, 1.05, 80, -50),
        (223, 350, 1.05, 150, -25),
        (201, 10, 1.035, 10, 0),
        (201, 10, 1.035, 10, 0),
        (201, 76, 1.035, 30, -25),
        (202, 10, 1.035, 10, 0),
        (202, 10, 1.035, 10, 0),
        (202, 76, 1.035, 30, -25),
        (202, 76, 1.035, 30, -25),
        (207, 80, 1.025, 60, 0),
        (207, 80, 1.025, 60, 0),
        (207, 80, 1.025, 60, 0),
    ]

    # Zone 3 generator
    gen_data_zone3 = [
        (302, 150, 1.05, 150, -25),
    ]

    all_gen_data = gen_data_zone1 + gen_data_zone2 + gen_data_zone3

    for bus_num, pg, vg, qmax, qmin in all_gen_data:
        create_ac_gen(net, bus=bus_map[bus_num], p_mw=pg, v_pu=vg,
                      q_min_mvar=qmin, q_max_mvar=qmax, name=f"Gen at {bus_num}")

    # ===================================================================
    # AC BRANCHES
    # Simplified branch data from case24_ieee_rts1996_3zones.m
    # ===================================================================

    # Zone 1 branches (r, x, b in pu; tap=1.0 for lines, 1.015/1.03 for transformers per MATLAB)
    # Format: (fbus, tbus, r_pu, x_pu, b_pu, base_kv, tap)
    branch_data_zone1 = [
        (101, 102, 0.003, 0.014, 0.461, 138, 1.0),
        (101, 103, 0.055, 0.211, 0.057, 138, 1.0),
        (101, 105, 0.022, 0.085, 0.023, 138, 1.0),
        (102, 104, 0.033, 0.127, 0.034, 138, 1.0),
        (102, 106, 0.050, 0.192, 0.052, 138, 1.0),
        (103, 109, 0.031, 0.119, 0.032, 138, 1.0),
        (103, 124, 0.002, 0.084, 0.0, 138, 1.015),   # Transformer ratio 1.015
        (104, 109, 0.027, 0.104, 0.028, 138, 1.0),
        (105, 110, 0.022, 0.088, 0.024, 138, 1.0),
        (106, 110, 0.014, 0.061, 2.459, 138, 1.0),
        (107, 108, 0.016, 0.061, 0.017, 138, 1.0),
        (108, 109, 0.043, 0.165, 0.045, 138, 1.0),
        (108, 110, 0.043, 0.165, 0.045, 138, 1.0),
        (109, 111, 0.002, 0.084, 0.0, 138, 1.03),    # Transformer ratio 1.03
        (109, 112, 0.002, 0.084, 0.0, 138, 1.03),
        (110, 111, 0.002, 0.084, 0.0, 138, 1.015),
        (110, 112, 0.002, 0.084, 0.0, 138, 1.015),
        (111, 113, 0.006, 0.048, 0.100, 230, 1.0),
        (111, 114, 0.005, 0.042, 0.088, 230, 1.0),
        (112, 113, 0.006, 0.048, 0.100, 230, 1.0),
        (112, 123, 0.012, 0.097, 0.203, 230, 1.0),
        (113, 123, 0.011, 0.087, 0.182, 230, 1.0),
        (114, 116, 0.005, 0.059, 0.082, 230, 1.0),
        (115, 116, 0.002, 0.017, 0.036, 230, 1.0),
        (115, 121, 0.006, 0.049, 0.103, 230, 1.0),
        (115, 121, 0.006, 0.049, 0.103, 230, 1.0),   # Parallel line
        (115, 124, 0.007, 0.052, 0.109, 230, 1.0),
        (116, 117, 0.003, 0.026, 0.055, 230, 1.0),
        (116, 119, 0.003, 0.023, 0.049, 230, 1.0),
        (117, 118, 0.002, 0.014, 0.030, 230, 1.0),
        (117, 122, 0.014, 0.105, 0.221, 230, 1.0),
        (118, 121, 0.003, 0.026, 0.055, 230, 1.0),
        (118, 121, 0.003, 0.026, 0.055, 230, 1.0),   # Parallel line
        (119, 120, 0.005, 0.040, 0.083, 230, 1.0),
        (119, 120, 0.005, 0.040, 0.083, 230, 1.0),   # Parallel line
        (120, 123, 0.003, 0.022, 0.046, 230, 1.0),
        (120, 123, 0.003, 0.022, 0.046, 230, 1.0),   # Parallel line
        (121, 122, 0.009, 0.068, 0.142, 230, 1.0),
    ]

    # Zone 2 branches (same tap pattern as zone 1)
    branch_data_zone2 = [
        (201, 202, 0.003, 0.014, 0.461, 138, 1.0),
        (201, 203, 0.055, 0.211, 0.057, 138, 1.0),
        (201, 205, 0.022, 0.085, 0.023, 138, 1.0),
        (202, 204, 0.033, 0.127, 0.034, 138, 1.0),
        (202, 206, 0.050, 0.192, 0.052, 138, 1.0),
        (203, 209, 0.031, 0.119, 0.032, 138, 1.0),
        (203, 224, 0.002, 0.084, 0.0, 138, 1.015),
        (204, 209, 0.027, 0.104, 0.028, 138, 1.0),
        (205, 210, 0.022, 0.088, 0.024, 138, 1.0),
        (206, 210, 0.014, 0.061, 2.459, 138, 1.0),
        (207, 208, 0.016, 0.061, 0.017, 138, 1.0),
        (208, 209, 0.043, 0.165, 0.045, 138, 1.0),
        (208, 210, 0.043, 0.165, 0.045, 138, 1.0),
        (209, 211, 0.002, 0.084, 0.0, 138, 1.03),
        (209, 212, 0.002, 0.084, 0.0, 138, 1.03),
        (210, 211, 0.002, 0.084, 0.0, 138, 1.015),
        (210, 212, 0.002, 0.084, 0.0, 138, 1.015),
        (211, 213, 0.006, 0.048, 0.100, 230, 1.0),
        (211, 214, 0.005, 0.042, 0.088, 230, 1.0),
        (212, 213, 0.006, 0.048, 0.100, 230, 1.0),
        (212, 223, 0.012, 0.097, 0.203, 230, 1.0),
        (213, 223, 0.011, 0.087, 0.182, 230, 1.0),
        (214, 216, 0.005, 0.059, 0.082, 230, 1.0),
        (215, 216, 0.002, 0.017, 0.036, 230, 1.0),
        (215, 221, 0.006, 0.049, 0.103, 230, 1.0),
        (215, 221, 0.006, 0.049, 0.103, 230, 1.0),
        (215, 224, 0.007, 0.052, 0.109, 230, 1.0),
        (216, 217, 0.003, 0.026, 0.055, 230, 1.0),
        (216, 219, 0.003, 0.023, 0.049, 230, 1.0),
        (217, 218, 0.002, 0.014, 0.030, 230, 1.0),
        (217, 222, 0.014, 0.105, 0.221, 230, 1.0),
        (218, 221, 0.003, 0.026, 0.055, 230, 1.0),
        (218, 221, 0.003, 0.026, 0.055, 230, 1.0),
        (219, 220, 0.005, 0.040, 0.083, 230, 1.0),
        (219, 220, 0.005, 0.040, 0.083, 230, 1.0),
        (220, 223, 0.003, 0.022, 0.046, 230, 1.0),
        (220, 223, 0.003, 0.022, 0.046, 230, 1.0),
        (221, 222, 0.009, 0.068, 0.142, 230, 1.0),
    ]

    # Zone 3 branch
    branch_data_zone3 = [
        (301, 302, 0.000, 0.001, 0.0, 230, 1.0),
    ]

    all_branch_data = branch_data_zone1 + branch_data_zone2 + branch_data_zone3

    for fbus, tbus, r_pu, x_pu, b_pu, base_kv, tap in all_branch_data:
        z_base = base_kv**2 / net.s_base
        y_base = 1.0 / z_base
        r_ohm = r_pu * z_base
        x_ohm = x_pu * z_base
        b_us = b_pu * y_base * 1e6
        create_ac_line(net, from_bus=bus_map[fbus], to_bus=bus_map[tbus],
                       length_km=1.0, r_ohm_per_km=r_ohm, x_ohm_per_km=x_ohm,
                       b_us_per_km=b_us, tap=tap, name=f"Line {fbus}-{tbus}")

    # ===================================================================
    # DC BUSES
    # From case24_ieee_rts1996_MTDC.m:
    # Grid 1: DC buses 1-3 (connecting zones 1, 2, 3) - 150 kV DC
    # Grid 2: DC buses 4-7 (connecting zones 1, 2) - 300 kV DC
    # ===================================================================

    dc_bus_map = {}

    # DC bus data: (dc_bus, ac_bus, grid, Vdc_pu, basekVdc)
    dc_bus_data = [
        (1, 107, 1, 1.0, 150),
        (2, 204, 1, 1.0, 150),
        (3, 301, 1, 1.0, 150),
        (4, 113, 2, 1.0, 300),
        (5, 123, 2, 1.0, 300),
        (6, 215, 2, 1.0, 300),
        (7, 217, 2, 1.0, 300),
    ]

    # Vdc slack: DC buses 1 and 4 (one per grid)
    vdc_slack_buses = {1, 4}

    for dc_bus, ac_bus, grid, vdc_pu, base_kv_dc in dc_bus_data:
        bus_type = "vdc" if dc_bus in vdc_slack_buses else "p"
        idx = create_dc_bus(net, v_base=base_kv_dc, dc_grid=grid, v_dc_pu=vdc_pu,
                            bus_type=bus_type, name=f"DC Bus {dc_bus}")
        dc_bus_map[dc_bus] = idx

    # ===================================================================
    # DC BRANCHES
    # From case24_ieee_rts1996_MTDC.m
    # Grid 1: lines 1-3, 2-3 (radial)
    # Grid 2: lines 4-5, 4-7, 4-6, 5-7, 6-7 (meshed)
    # ===================================================================

    dc_branch_data = [
        # (fbus, tbus, r_pu, basekVdc)
        (1, 3, 0.0352, 150),
        (2, 3, 0.0352, 150),
        (4, 5, 0.0828, 300),
        (4, 7, 0.0704, 300),
        (4, 6, 0.0718, 300),
        (5, 7, 0.0760, 300),
        (6, 7, 0.0248, 300),
    ]

    for fbus, tbus, r_pu, base_kv_dc in dc_branch_data:
        z_base_dc = base_kv_dc**2 / net.s_base
        r_ohm = r_pu * z_base_dc
        create_dc_line(net, from_bus=dc_bus_map[fbus], to_bus=dc_bus_map[tbus],
                       length_km=1.0, r_ohm_per_km=r_ohm,
                       name=f"DC Line {fbus}-{tbus}")

    # ===================================================================
    # VSC CONVERTERS
    # From case24_ieee_rts1996_MTDC.m
    # ===================================================================

    dc_to_ac = {1: 107, 2: 204, 3: 301, 4: 113, 5: 123, 6: 215, 7: 217}

    # Per-converter data matching case24_ieee_rts1996_MTDC.m exactly:
    # (dc_bus, type_dc, type_ac, P_mw, Q_mvar, basekVac,
    #  rtf, xtf, bf, rc, xc, Imax, LossA, LossB, LossCrec, LossCinv)
    conv_data = [
        # Grid 1 converters (150 kV DC, 138 kV AC)
        (1, 2, 1,      0,   50, 138,
         0.001, 0.10, 0.09,   0.0001, 0.16, 1.1,  1.103, 0.887, 2.885, 4.371),
        (2, 1, 2,   75.3,  -50, 138,
         0.001, 0.10, 0.09,   0.0001, 0.16, 1.1,  1.103, 0.887, 2.885, 4.371),
        (3, 1, 1, -141.9,  130, 138,
         0.001, 0.05, 0.045,  0.0001, 0.08, 2.2,  2.206, 0.887, 1.442, 2.185),
        # Grid 2 converters (300 kV DC, 345 kV AC)
        (4, 2, 1,  131.5, 75.9, 345,
         0.0005, 0.05, 0.0,  0.0001, 0.08, 2.2,  2.206, 1.8,   5.94,  9.0),
        (5, 1, 1,  -61.7,    0, 345,
         0.001,  0.10, 0.0,  0.0001, 0.16, 1.1,  1.103, 1.8,  11.88, 18.0),
        (6, 1, 2, -123.4,  -10, 345,
         0.0005, 0.05, 0.0,  0.0001, 0.08, 2.2,  2.206, 1.8,   5.94,  9.0),
        (7, 1, 1,     50,   20, 345,
         0.001,  0.10, 0.0,  0.0001, 0.16, 1.1,  1.103, 1.8,  11.88, 18.0),
    ]

    for (dc_bus, type_dc, type_ac, p_mw, q_mvar, base_kv_ac,
         rtf, xtf, bf, rc, xc, imax, lossa, lossb, lossc_rec, lossc_inv) in conv_data:
        ac_bus = dc_to_ac[dc_bus]

        # Determine control mode
        if type_dc == 2:  # Vdc slack
            if type_ac == 2:
                control_mode = "vdc_vac"
            else:
                control_mode = "vdc_q"
        else:  # P-controlled
            if type_ac == 2:
                control_mode = "p_vac"
            else:
                control_mode = "p_q"

        s_mva = imax * 100.0  # Imax in pu * baseMVA

        # Power convention: MatACDC P>0 = inverter, Python P_s>0 = rectifier
        # So we need to negate P and Q
        create_vsc(
            net,
            ac_bus=bus_map[ac_bus],
            dc_bus=dc_bus_map[dc_bus],
            s_mva=s_mva,
            control_mode=control_mode,
            p_mw=-p_mw,      # Negated
            q_mvar=-q_mvar,  # Negated
            v_dc_pu=1.0 if type_dc == 2 else None,
            v_ac_pu=1.0 if type_ac == 2 else None,
            r_tf_pu=rtf, x_tf_pu=xtf,
            r_c_pu=rc, x_c_pu=xc,
            b_filter_pu=bf,
            loss_a=lossa,
            loss_b=lossb,
            loss_c=lossc_rec,
            loss_c_inv=lossc_inv,
            loss_base_kv=base_kv_ac,
            name=f"VSC DC{dc_bus}-AC{ac_bus}"
        )

    return net
