"""
IEEE 33-bus distribution system with extended DC elements.

System composition:
- 21 AC buses (nodes 1-7, 12-15, 19-20, 23-25, 29-33)
- 15 DC buses: 12 original + 3 generator buses (34, 35, 36)
- 3 DC grids:
    - Grid 1 (buses 8,9,10,11,35): Connected via VSCs at DC buses 8 and 11
    - Grid 2 (buses 26,27,28): Connected via VSCs at DC buses 26 and 28
    - Grid 3 (buses 16,17,18,21,22,34,36): Connected via VSCs at DC buses 16, 18, and 21
- 7 VSC converters connecting AC and DC systems
- 9 DC lines
- 3 DC-DC converters connecting generator buses to main grids
- 12 DC loads on original DC buses
- 3 DC generators on buses 34, 35, 36

AC System:
- Bus 1: Slack bus (reference, Vm=1.05 pu)
- Buses 5, 24, 29: PV buses with generators
- All other buses: PQ load buses

"""

from ..network import Network, create_empty_network
from ..create.ac import create_ac_bus, create_ac_line, create_ac_load, create_ac_gen
from ..create.dc import create_dc_bus, create_dc_line, create_dc_load, create_dc_gen
from ..create.converters import create_vsc, create_dcdc


def create_case33_ieee_ext() -> Network:
    """
    Create the IEEE 33-bus distribution system with extended DC elements.

    This variant includes DC loads, DC generators, and DC-DC converters
    in addition to the standard VSC-connected DC grids.

    Returns
    -------
    Network
        The complete hybrid AC/DC network.
    """
    net = create_empty_network(
        name="IEEE 33-bus with DC (Extended)",
        s_base=100.0,
        f_hz=50.0,
        pol=1 
    )

    base_kv_ac = 12.66 

    # AC BUSES

    bus_map = {} 

    # Bus data: (bus_number, type, Vm_pu)
    # type 3=slack, 2=PV, 1=PQ
    ac_bus_data = [
        (1,  3, 1.05),
        (2,  1, 1.00),
        (3,  1, 1.00),
        (4,  1, 1.00),
        (5,  2, 1.03),
        (6,  1, 1.00),
        (7,  1, 1.00),
        (12, 1, 1.00),
        (13, 1, 1.00),
        (14, 1, 1.00),
        (15, 1, 1.00),
        (19, 1, 1.00),
        (20, 1, 1.00),
        (23, 1, 1.00),
        (24, 2, 1.03),
        (25, 1, 1.00),
        (29, 2, 1.02),
        (30, 1, 1.00),
        (31, 1, 1.00),
        (32, 1, 1.00),
        (33, 1, 1.00),
    ]

    for bus_num, bus_type, vm in ac_bus_data:
        idx = create_ac_bus(net, vr_kv=base_kv_ac, name=f"Bus {bus_num}")
        bus_map[bus_num] = idx

    # AC LOADS 

    ac_load_data = [
        (2,  0.20, 0.12),
        (3,  0.18, 0.08),
        (4,  0.24, 0.06),
        (5,  0.13, 0.06),
        (6,  0.20, 0.10),
        (7,  0.20, 0.10),
        (12, 0.12, 0.07),
        (13, 0.06, 0.02),
        (14, 0.40, 0.20),
        (15, 0.26, 0.11),
        (19, 0.18, 0.08),
        (20, 0.18, 0.08),
        (23, 0.18, 0.10),
        (24, 0.12, 0.06),
        (25, 0.30, 0.10),
        (29, 0.09, 0.04),
        (30, 0.10, 0.06),
        (31, 0.17, 0.05),
        (32, 0.15, 0.07),
        (33, 0.24, 0.16),
    ]

    for bus_num, pd, qd in ac_load_data:
        create_ac_load(net, bus=bus_map[bus_num], p_mw=pd, q_mvar=qd,
                       name=f"Load {bus_num}")

    # AC GENERATORS
    # Q limits widened: PowerFactory results show G2 Q=4.22 MVAr (bus 5),
    # far exceeding the 0.25 MVAr from the Excel.

    create_ac_gen(net, bus=bus_map[1], p_mw=0.5, v_pu=1.05,
                  q_min_mvar=-50.0, q_max_mvar=50.0, name="Gen 1 (Slack)")

    create_ac_gen(net, bus=bus_map[5], p_mw=0.5, v_pu=1.03,
                  q_min_mvar=-50.0, q_max_mvar=50.0, name="Gen 5")

    create_ac_gen(net, bus=bus_map[24], p_mw=0.5, v_pu=1.03,
                  q_min_mvar=-50.0, q_max_mvar=50.0, name="Gen 24")

    create_ac_gen(net, bus=bus_map[29], p_mw=0.5, v_pu=1.02,
                  q_min_mvar=-50.0, q_max_mvar=50.0, name="Gen 29")

    # AC LINES

    ac_branch_data = [
        (1,  2,  0.0922, 0.047),
        (2,  3,  0.493,  0.2511),
        (3,  4,  0.366,  0.1864),
        (4,  5,  0.3811, 0.1941),
        (5,  6,  0.819,  0.707),
        (6,  7,  0.1872, 0.6188),
        (12, 13, 1.468,  1.155),
        (13, 14, 0.5416, 0.7129),
        (14, 15, 0.591,  0.526),
        (2,  19, 0.164,  0.1565),
        (19, 20, 1.5042, 1.3554),
        (3,  23, 0.4512, 0.3083),
        (23, 24, 0.898,  0.7091),
        (24, 25, 0.896,  0.7011),
        (25, 29, 0.500,  0.500),
        (29, 30, 0.5075, 0.2585),
        (30, 31, 0.9744, 0.963),
        (31, 32, 0.3105, 0.3619),
        (32, 33, 0.341,  0.5302),
        (31, 15, 2.000,  2.000),
    ]

    for fbus, tbus, r_ohm, x_ohm in ac_branch_data:
        create_ac_line(net, from_bus=bus_map[fbus], to_bus=bus_map[tbus],
                       length_km=1.0, r_ohm_per_km=r_ohm, x_ohm_per_km=x_ohm,
                       b_us_per_km=0.0, name=f"Line {fbus}-{tbus}")

    # DC BUSES

    base_kv_dc = 20.67
    base_kv_dc_gen = 1.0  # DC generator buses 34, 35, 36

    dc_bus_map = {}  # DC bus number -> internal index

    # Vdc slack buses with their voltage setpoints
    vdc_slack_setpoints = {8: 1.02, 26: 1.0, 18: 1.0}

    # DC buses: (dc_bus_num, grid, v_dc_pu_init, v_base_kv)
    dc_bus_data = [
        (8,  1, 1.02, base_kv_dc),
        (9,  1, 1.00, base_kv_dc),
        (10, 1, 1.00, base_kv_dc),
        (11, 1, 1.00, base_kv_dc),
        (16, 3, 1.00, base_kv_dc),
        (17, 3, 1.00, base_kv_dc),
        (18, 3, 1.00, base_kv_dc),
        (21, 3, 1.00, base_kv_dc),
        (22, 3, 1.00, base_kv_dc),
        (26, 2, 1.00, base_kv_dc),
        (27, 2, 1.00, base_kv_dc),
        (28, 2, 1.00, base_kv_dc),
        # DC generator buses at 1 kV (connected via DC-DC boost converters)
        (34, 3, 1.00, base_kv_dc_gen),  # connects to bus 22 (grid 3)
        (35, 1, 1.00, base_kv_dc_gen),  # connects to bus 10 (grid 1)
        (36, 3, 1.00, base_kv_dc_gen),  # connects to bus 17 (grid 3)
    ]

    for dc_bus_num, grid, v_init, v_base in dc_bus_data:
        if dc_bus_num in vdc_slack_setpoints:
            bus_type = "vdc"
            v_dc = vdc_slack_setpoints[dc_bus_num]
        else:
            bus_type = "p"
            v_dc = v_init
        idx = create_dc_bus(net, v_base=v_base, dc_grid=grid, v_dc_pu=v_dc,
                            bus_type=bus_type, name=f"DC Bus {dc_bus_num}")
        dc_bus_map[dc_bus_num] = idx

    # DC LINES

    dc_branch_data = [
        (8,  9,  2.06),
        (9,  10, 2.08),
        (10, 11, 0.3932),
        (16, 17, 2.578),
        (17, 18, 1.464),
        (21, 22, 1.4178),
        (26, 27, 0.5684),
        (27, 28, 2.118),
        (16, 22, 4.0),
    ]

    for fbus, tbus, r_ohm in dc_branch_data:
        create_dc_line(net, from_bus=dc_bus_map[fbus], to_bus=dc_bus_map[tbus],
                       length_km=1.0, r_ohm_per_km=r_ohm,
                       name=f"DC Line {fbus}-{tbus}")

    # DC LOADS

    dc_load_data = [
        (8,  0.24),
        (9,  0.12),
        (10, 0.12),
        (11, 0.42),
        (16, 0.21),
        (17, 0.06),
        (18, 0.045),
        (21, 0.3),
        (22, 0.09),
        (26, 0.26),
        (27, 0.2),
        (28, 0.12),
    ]

    for dc_bus_num, p_mw in dc_load_data:
        create_dc_load(net, bus=dc_bus_map[dc_bus_num], p_mw=p_mw,
                       name=f"DC Load {dc_bus_num}")

    # DC GENERATORS

    dc_gen_data = [
        (34, 0.1),
        (35, 0.1), 
        (36, 0.2),
    ]

    for dc_bus_num, p_mw in dc_gen_data:
        create_dc_gen(net, bus=dc_bus_map[dc_bus_num], p_mw=p_mw,
                      name=f"DC Gen {dc_bus_num}")

    # DC-DC CONVERTERS
    # Boost converters: 1 kV → 20.61 kV (ratio = 20.61)
    # Convention: from_bus = V_m (high voltage side, 20.67 kV grid)
    #             to_bus   = V_c (low voltage side, 1 kV, series R side)
    #             d_ratio  = V_c / V_m (actual voltage ratio)

    boost_ratio = 20.61  # From CASE 3 update: 1 kV → 20.61 kV
    d_ratio = 1.0 / boost_ratio  # V_c / V_m ≈ 0.04852

    dcdc_data = [
        (22, 34, 0.5),
        (10, 35, 0.5),
        (17, 36, 0.5),
    ]

    for fbus, tbus, r_ohm in dcdc_data:
        create_dcdc(net, from_bus=dc_bus_map[fbus], to_bus=dc_bus_map[tbus],
                    d_ratio=d_ratio, r_ohm=r_ohm,
                    name=f"DCDC {fbus}-{tbus}")

    # VSC CONVERTERS
    # Excel convention: positive P = inverter (DC→AC)
    # Python convention: positive P_s = rectifier (AC→DC)
    # So P and Q values are negated from Excel for PQ converters.
    # Slack converters have P=Q=0 (determined by solver).

    dc_to_ac = {8: 7, 11: 12, 16: 15, 18: 33, 21: 20, 26: 6, 28: 29}

    # P/Q already in Python convention
    vsc_data = [
        (8,  "vdc_vac", 0.0,   0.0,   1.03),
        (26, "vdc_vac", 0.0,   0.0,   1.00),
        (18, "vdc_vac", 0.0,   0.0,   1.00),
        (11, "p_q", -0.25,  -0.075, None),
        (28, "p_q", -0.76,  -0.25,  None),
        (16, "p_q", -0.28,  -0.092, None),
        (21, "p_q",  1.20,   0.40,  None),
    ]

    for dc_bus, control_mode, p_mw, q_mvar, v_ac_pu in vsc_data:
        ac_bus = dc_to_ac[dc_bus]
        v_dc_pu = 1.0 if "vdc" in control_mode else None

        create_vsc(
            net,
            ac_bus=bus_map[ac_bus],
            dc_bus=dc_bus_map[dc_bus],
            s_mva=100.0,
            control_mode=control_mode,
            p_mw=p_mw,
            q_mvar=q_mvar,
            v_ac_pu=v_ac_pu,
            v_dc_pu=v_dc_pu,
            r_tf_pu=0.0, x_tf_pu=0.0,
            r_c_pu=0.01, x_c_pu=1.6428,
            loss_a=0.0,
            loss_b=0.0,
            loss_c=0.0,
            name=f"VSC DC{dc_bus}-AC{ac_bus}"
        )

    return net
