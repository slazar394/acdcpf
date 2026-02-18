"""
CIGRE B4 DC Grid Test System.

Based on: "The Cigré B4 DC Grid Test System", Vrana et al., October 2013.

System composition:
- 2 onshore AC systems (A: A0,A1; B: B0,B1,B2,B3)
- 4 offshore AC systems (C: C1,C2; D: D1; E: E1; F: F1)
- 2 DC nodes with no AC connection (B4, B5)
- 3 interconnected VSC-DC systems:
    DCS1 (monopole +/-200kV): A1, C1
    DCS2 (monopole +/-200kV): B2, B3, B5, E1, F1
    DCS3 (bipole +/-400kV): A1, C2, D1, E1, B1, B4, B2

Voltages: AC Onshore 380kV, AC Offshore 145kV,
          DC Sym. Monopole +/-200kV, DC Bipole +/-400kV.
"""

from ..network import Network, create_empty_network
from ..create.ac import create_ac_bus, create_ac_line, create_ac_load, create_ac_gen
from ..create.dc import create_dc_bus, create_dc_line, create_dc_load, create_dc_gen
from ..create.converters import create_vsc, create_dcdc


def create_cigre_b4_dc_test_system() -> Network:
    """
    Create the CIGRE B4 DC Grid Test System.

    Returns
    -------
    Network
        The complete CIGRE B4 test network with all AC/DC elements.

    References
    ----------
    T.K. Vrana et al., "The Cigré B4 DC Grid Test System",
    ELECTRA No. 270, October 2013.
    """
    net = create_empty_network(name="CIGRE B4 DC Grid Test System",
                               s_base=100.0, f_hz=50.0)

    # ===================================================================
    # AC BUSES (Table 2)
    # Onshore: 380 kV, Offshore: 145 kV
    # ===================================================================
    # System A (onshore)
    ba_a0 = create_ac_bus(net, vr_kv=380.0, name="Ba-A0")  # Slack bus
    ba_a1 = create_ac_bus(net, vr_kv=380.0, name="Ba-A1")  # PQ

    # System B (onshore)
    ba_b0 = create_ac_bus(net, vr_kv=380.0, name="Ba-B0")  # Slack bus
    ba_b1 = create_ac_bus(net, vr_kv=380.0, name="Ba-B1")  # PQ
    ba_b2 = create_ac_bus(net, vr_kv=380.0, name="Ba-B2")  # PQ
    ba_b3 = create_ac_bus(net, vr_kv=380.0, name="Ba-B3")  # PQ

    # System C (offshore wind)
    ba_c1 = create_ac_bus(net, vr_kv=145.0, name="Ba-C1")  # PQ
    ba_c2 = create_ac_bus(net, vr_kv=145.0, name="Ba-C2")  # PQ

    # System D (offshore wind)
    ba_d1 = create_ac_bus(net, vr_kv=145.0, name="Ba-D1")  # PQ

    # System E (offshore platform)
    ba_e1 = create_ac_bus(net, vr_kv=145.0, name="Ba-E1")  # PQ

    # System F (offshore wind)
    ba_f1 = create_ac_bus(net, vr_kv=145.0, name="Ba-F1")  # PQ

    # ===================================================================
    # AC LINES
    # Onshore (380 kV OHL): R=0.0200 Ohm/km, L=0.8532 mH/km -> X at 50Hz
    # Offshore (145 kV cable): R=0.0843 Ohm/km, L=0.2526 mH/km
    # X = 2*pi*f*L = 2*pi*50*L(H/km)
    # Table 9 line data:
    #   AC OHL 380kV: R=0.0200, X=0.8532*2*pi*50/1000=0.2680 Ohm/km, B=0.0135*2*pi*50=4.2412 uS/km
    #   AC cable 145kV: R=0.0843, X=0.2526*2*pi*50/1000=0.0794 Ohm/km, B=0.1837*2*pi*50=57.73 uS/km
    # More precisely from Table 9 (converting L mH/km to X Ohm/km and C uF/km to B uS/km):
    #   AC OHL 380kV: R=0.0200, X=2*pi*50*0.8532e-3=0.2680, B=2*pi*50*0.0135e-6*1e6=4.2412 uS/km
    #   AC cable 145kV: R=0.0843, X=2*pi*50*0.2526e-3=0.07937, B=2*pi*50*0.1837e-6*1e6=57.73 uS/km
    # ===================================================================
    import math
    omega = 2 * math.pi * 50.0

    # AC OHL 380 kV parameters (Table 9)
    r_ohl_380 = 0.0200    # Ohm/km
    x_ohl_380 = omega * 0.8532e-3   # Ohm/km (from L=0.8532 mH/km)
    b_ohl_380 = omega * 0.0135e-6 * 1e6  # uS/km (from C=0.0135 uF/km)

    # AC cable 145 kV parameters (Table 9)
    r_cab_145 = 0.0843    # Ohm/km
    x_cab_145 = omega * 0.2526e-3   # Ohm/km
    b_cab_145 = omega * 0.1837e-6 * 1e6  # uS/km
    g_cab_145 = 0.041     # uS/km (Table 9)

    # System A
    # A0 -- A1 1 (200 km OHL)
    create_ac_line(net, ba_a0, ba_a1, length_km=200.0,
                   r_ohm_per_km=r_ohl_380, x_ohm_per_km=x_ohl_380,
                   b_us_per_km=b_ohl_380, name="AC-A0-A1-1")
    # A0 -- A1 2 (200 km OHL)
    create_ac_line(net, ba_a0, ba_a1, length_km=200.0,
                   r_ohm_per_km=r_ohl_380, x_ohm_per_km=x_ohl_380,
                   b_us_per_km=b_ohl_380, name="AC-A0-A1-2")
    
    ## System B
    # B0 -- B1 (200 km OHL)
    create_ac_line(net, ba_b0, ba_b1, length_km=200.0,
                   r_ohm_per_km=r_ohl_380, x_ohm_per_km=x_ohl_380,
                   b_us_per_km=b_ohl_380, name="AC-B0-B1")
    # B0 -- B2 (200 km OHL)
    create_ac_line(net, ba_b0, ba_b2, length_km=200.0,
                   r_ohm_per_km=r_ohl_380, x_ohm_per_km=x_ohl_380,
                   b_us_per_km=b_ohl_380, name="AC-B0-B2")
    # B2 -- B3 (200 km OHL)
    create_ac_line(net, ba_b2, ba_b3, length_km=200.0,
                   r_ohm_per_km=r_ohl_380, x_ohm_per_km=x_ohl_380,
                   b_us_per_km=b_ohl_380, name="AC-B2-B3")
    # B0 -- B3 (200 km OHL)
    create_ac_line(net, ba_b0, ba_b3, length_km=200.0,
                   r_ohm_per_km=r_ohl_380, x_ohm_per_km=x_ohl_380,
                   b_us_per_km=b_ohl_380, name="AC-B0-B3")
    # B1 -- B3 (200 km OHL)
    create_ac_line(net, ba_b1, ba_b3, length_km=200.0,
                   r_ohm_per_km=r_ohl_380, x_ohm_per_km=x_ohl_380,
                   b_us_per_km=b_ohl_380, name="AC-B1-B3")

    # System C: C1 -- C2 (50 km cable, from Figure 2)
    create_ac_line(net, ba_c1, ba_c2, length_km=50.0,
                   r_ohm_per_km=r_cab_145, x_ohm_per_km=x_cab_145,
                   b_us_per_km=b_cab_145, g_us_per_km=g_cab_145,
                   name="AC-C1-C2")

    # ===================================================================
    # AC LOADS AND GENERATORS (Table 2)
    # The paper states: "it was decided to not model the AC generators and
    # loads in detail... they are simply represented by constant active
    # power sources and sinks". All non-slack buses are PQ type.
    # AC voltages are maintained by Vac-controlling converters, not gens.
    # Net load = Load - |Generation| (negative = net generation).
    # ===================================================================

    # Ba-A0: Slack bus (absorbs/generates to balance system A)
    create_ac_gen(net, bus=ba_a0, p_mw=0.0, v_pu=1.0, name="Slack-A0")

    # Ba-A1: Gen=-2000, Load=1000 → net = -1000 MW (net generation)
    create_ac_load(net, bus=ba_a1, p_mw=-1000.0, q_mvar=0.0, name="Net-A1")

    # Ba-B0: Slack bus (absorbs/generates to balance system B)
    create_ac_gen(net, bus=ba_b0, p_mw=0.0, v_pu=1.0, name="Slack-B0")

    # Ba-B1: Gen=-1000, Load=2200 → net = 1200 MW (net load)
    create_ac_load(net, bus=ba_b1, p_mw=1200.0, q_mvar=0.0, name="Net-B1")

    # Ba-B2: Gen=-1000, Load=2300 → net = 1300 MW (net load)
    create_ac_load(net, bus=ba_b2, p_mw=1300.0, q_mvar=0.0, name="Net-B2")

    # Ba-B3: Gen=-1000, Load=1900 → net = 900 MW (net load)
    create_ac_load(net, bus=ba_b3, p_mw=900.0, q_mvar=0.0, name="Net-B3")

    # Ba-C1: Gen=-500, Load=0 → net = -500 MW (offshore wind)
    create_ac_load(net, bus=ba_c1, p_mw=-500.0, q_mvar=0.0, name="Net-C1")

    # Ba-C2: Gen=-500, Load=0 → net = -500 MW (offshore wind)
    create_ac_load(net, bus=ba_c2, p_mw=-500.0, q_mvar=0.0, name="Net-C2")

    # Ba-D1: Gen=-1000, Load=0 → net = -1000 MW (offshore wind)
    create_ac_load(net, bus=ba_d1, p_mw=-1000.0, q_mvar=0.0, name="Net-D1")

    # Ba-E1: Gen=0, Load=100 → net = 100 MW (offshore platform)
    create_ac_load(net, bus=ba_e1, p_mw=100.0, q_mvar=0.0, name="Net-E1")

    # Ba-F1: Gen=-500, Load=0 → net = -500 MW (offshore wind)
    create_ac_load(net, bus=ba_f1, p_mw=-500.0, q_mvar=0.0, name="Net-F1")

    # ===================================================================
    # DC BUSES
    # DCS1: Sym. Monopole +/-200kV (v_base=200 per pole, use 400 pole-to-pole)
    # DCS2: Sym. Monopole +/-200kV
    # DCS3: Bipole +/-400kV (v_base=400 per pole, use 800 pole-to-pole)
    # Per CIGRE convention: 200kV and 400kV are nominal = 1pu
    # ===================================================================

    # DCS1 buses (dc_grid=1, monopole 200kV base)
    # Cm-A1 controls Vdc=1.0pu -> Bm-A1 is Vdc slack
    bm_a1 = create_dc_bus(net, v_base=200.0, dc_grid=1, bus_type="vdc",
                          v_dc_pu=1.0, name="Bm-A1")
    bm_c1 = create_dc_bus(net, v_base=200.0, dc_grid=1, bus_type="p",
                          v_dc_pu=1.0, name="Bm-C1")

    # DCS2 buses (dc_grid=2, monopole 200kV base)
    # Cm-B2 has droop control -> Bm-B2 is droop bus
    bm_b2 = create_dc_bus(net, v_base=200.0, dc_grid=2, bus_type="droop",
                          v_dc_pu=0.99, name="Bm-B2")
    bm_b3 = create_dc_bus(net, v_base=200.0, dc_grid=2, bus_type="droop",
                          v_dc_pu=1.0, name="Bm-B3")
    bm_b5 = create_dc_bus(net, v_base=200.0, dc_grid=2, bus_type="p",
                          v_dc_pu=1.0, name="Bm-B5")
    bm_e1 = create_dc_bus(net, v_base=200.0, dc_grid=2, bus_type="p",
                          v_dc_pu=1.0, name="Bm-E1")
    bm_f1 = create_dc_bus(net, v_base=200.0, dc_grid=2, bus_type="p",
                          v_dc_pu=1.0, name="Bm-F1")

    # DCS3 buses (dc_grid=3, bipole 400kV base)
    bb_a1 = create_dc_bus(net, v_base=400.0, dc_grid=3, bus_type="vdc",
                          v_dc_pu=1.01, name="Bb-A1")  # Cb-A1 sets Vdc=1.01pu
    # Cb-B1 has droop control -> Bb-B1 is droop bus
    bb_b1 = create_dc_bus(net, v_base=400.0, dc_grid=3, bus_type="droop",
                          v_dc_pu=1.0, name="Bb-B1")
    bb_b1s = create_dc_bus(net, v_base=400.0, dc_grid=3, bus_type="p",
                           v_dc_pu=1.0, name="Bb-B1s")
    # Cb-B2 has droop control -> Bb-B2 is droop bus
    bb_b2 = create_dc_bus(net, v_base=400.0, dc_grid=3, bus_type="droop",
                          v_dc_pu=1.0, name="Bb-B2")
    bb_b4 = create_dc_bus(net, v_base=400.0, dc_grid=3, bus_type="p",
                          v_dc_pu=1.0, name="Bb-B4")
    bb_c2 = create_dc_bus(net, v_base=400.0, dc_grid=3, bus_type="p",
                          v_dc_pu=1.0, name="Bb-C2")
    bb_d1 = create_dc_bus(net, v_base=400.0, dc_grid=3, bus_type="p",
                          v_dc_pu=1.0, name="Bb-D1")
    bb_e1 = create_dc_bus(net, v_base=400.0, dc_grid=3, bus_type="p",
                          v_dc_pu=1.0, name="Bb-E1")

    # ===================================================================
    # DC LINES (Figure 2, Table 9)
    # Line types from Table 9:
    #   DC OHL +/-400kV: R=0.0114 Ohm/km
    #   DC OHL +/-200kV: R=0.0133 Ohm/km
    #   DC cable +/-400kV: R=0.0095 Ohm/km
    #   DC cable +/-200kV: R=0.0095 Ohm/km
    # Lengths from Figure 2 (in km).
    # ===================================================================

    # --- DCS1 lines (monopole 200kV, cable) ---
    # Bm-A1 -- Bm-C1: 200 km cable
    create_dc_line(net, bm_a1, bm_c1, length_km=200.0,
                   r_ohm_per_km=0.0095, max_i_ka=1.962, name="DC-DCS1-A1-C1")

    # --- DCS2 lines (monopole 200kV, mixed OHL/cable) ---
    # Bm-B2 -- Bm-B3: 200 km cable
    create_dc_line(net, bm_b2, bm_b3, length_km=200.0,
                   r_ohm_per_km=0.0095, max_i_ka=1.962, name="DC-DCS2-B2-B3")

    # Bm-B3 -- Bm-B5: 100 km cable
    create_dc_line(net, bm_b3, bm_b5, length_km=100.0,
                   r_ohm_per_km=0.0133, max_i_ka=3.0, name="DC-DCS2-B3-B5")

    # Bm-B5 -- Bm-F1: 100 km cable
    create_dc_line(net, bm_b5, bm_f1, length_km=100.0,
                   r_ohm_per_km=0.0095, max_i_ka=1.962, name="DC-DCS2-B5-F1")

    # Bm-F1 -- Bm-E1: 200 km cable
    create_dc_line(net, bm_f1, bm_e1, length_km=200.0,
                   r_ohm_per_km=0.0095, max_i_ka=1.962, name="DC-DCS2-F1-E1")

    # --- DCS3 lines (bipole 400kV, mixed OHL/cable) ---
    # Bb-A1 -- Bb-B1: 500 km (from Figure 2, OHL + cable)
    # Split: 200km cable (offshore) + 300km OHL (onshore) per Figure 2
    # Use weighted average or separate segments. For simplicity, one line:
    # Weighted: (200*0.0095 + 300*0.0114)/500 = 0.01064
    create_dc_line(net, bb_a1, bb_b1, length_km=400.0,
                   r_ohm_per_km=0.01064, max_i_ka=3.5, name="DC-DCS3-A1-B1-1")
    create_dc_line(net, bb_a1, bb_b1, length_km=400.0,
                   r_ohm_per_km=0.01064, max_i_ka=3.5, name="DC-DCS3-A1-B1-2")
    create_dc_line(net, bb_a1, bb_b4, length_km=500.0,
                   r_ohm_per_km=0.01064, max_i_ka=3.5, name="DC-DCS3-A1-B4")
    
    # Bb-A1 -- Bb-C2: 200 km cable
    create_dc_line(net, bb_a1, bb_c2, length_km=200.0,
                   r_ohm_per_km=0.0095, max_i_ka=2.265, name="DC-DCS3-A1-C2")

    # Bb-C2 -- Bb-D1: 300 km cable
    create_dc_line(net, bb_c2, bb_d1, length_km=300.0,
                   r_ohm_per_km=0.0095, max_i_ka=2.265, name="DC-DCS3-C2-D1")

    # Bb-D1 -- Bb-E1: 200 km cable
    create_dc_line(net, bb_d1, bb_e1, length_km=200.0,
                   r_ohm_per_km=0.0095, max_i_ka=2.265, name="DC-DCS3-D1-E1")

    # Bb-B1s -- Bb-E1: 200 km (from Figure 2)
    create_dc_line(net, bb_b1s, bb_e1, length_km=200.0,
                   r_ohm_per_km=0.0095, max_i_ka=2.265, name="DC-DCS3-B1s-E1")

    # Bb-B4 -- Bb-B1: 200 km OHL (from Figure 2)
    create_dc_line(net, bb_b4, bb_b1, length_km=200.0,
                   r_ohm_per_km=0.0114, max_i_ka=3.5, name="DC-DCS3-B4-B1")

    # Bb-B2 -- Bb-B4: 300 km OHL (from Figure 2)
    create_dc_line(net, bb_b2, bb_b4, length_km=300.0,
                   r_ohm_per_km=0.0114, max_i_ka=3.5, name="DC-DCS3-B2-B4-1")
    create_dc_line(net, bb_b2, bb_b4, length_km=300.0,
                   r_ohm_per_km=0.0114, max_i_ka=3.5, name="DC-DCS3-B2-B4-2")

    # ===================================================================
    # VSC CONVERTERS (Tables 3-5, 11-13, 7)
    #
    # Converter impedance from Table 7:
    # For 800MVA converters (E1, C2): R=1.00%, X=25.5%+18%=43.5%?
    #   Actually Table 7: R_pu=1.00%, based on converter rating
    #   Need to convert to system base.
    #   Z_conv_pu_sys = Z_conv_pu_conv * (S_conv / S_base)
    #
    # For power flow, use simplified model:
    #   r_pu, x_pu on converter base, then internally scale to system base.
    #   We store on system base in create_vsc for consistency.
    #
    # Table 7 (converter pole data):
    #   200MVA (E1): R=1.00%, L(=X)=25.5%
    #   400MVA (C2): R=1.00%, L=25.5%
    #   800MVA (A1,B2,C1,D1,F1): R=1.00%, L=25.5%
    #   1200MVA (A1,B1,B2,B3): R=1.00%, L=25.5%
    #
    # Simplified: use R=0.01pu, X=0.10pu on converter base
    # Loss coefficients: a=LossA, b=LossB, c=LossC from MatACDC convention
    #   Table 7: G=0.10% (shunt conductance = no-load losses)
    #   Loss model: P_loss = a + b*I + c*I^2
    #   For simplicity, use a=0 (or small), b=0, c=0 as first approximation
    #   since the CIGRE paper doesn't give explicit a,b,c loss coefficients
    #   for power flow.
    # ===================================================================

    # Default converter parameters
    r_pu_conv = 0.01   # pu on converter base
    x_pu_conv = 0.10   # pu on converter base (simplified from Table 7)
    b_filter = 0.05    # pu filter susceptance

    # --- DCS1 Converters (Table 3, Table 11) ---

    # Cm-A1: 800 MVA, Q=0, Vdc=1.0pu (Vdc control)
    create_vsc(net, ac_bus=ba_a1, dc_bus=bm_a1, s_mva=800.0,
               control_mode="vdc_q", q_mvar=0.0, v_dc_pu=1.0,
               loss_a=0.8,
               r_pu=r_pu_conv * net.s_base / 800.0,
               x_pu=x_pu_conv * net.s_base / 800.0,
               b_filter_pu=b_filter * 800.0 / net.s_base,
               name="Cm-A1")

    # Cm-C1: 800 MVA, AC Slack (islanded mode - controls Vac and freq)
    create_vsc(net, ac_bus=ba_c1, dc_bus=bm_c1, s_mva=800.0,
               control_mode="p_vac", p_mw=0.0, v_ac_pu=1.0,
               loss_a=0.8,
               r_pu=r_pu_conv * net.s_base / 800.0,
               x_pu=x_pu_conv * net.s_base / 800.0,
               b_filter_pu=b_filter * 800.0 / net.s_base,
               name="Cm-C1")

    # --- DCS2 Converters (Table 4, Table 12) ---

    # Cm-B2: 800 MVA, Q(Vac) droop + P(Vdc) droop
    # Vdc=0.99pu setpoint, Q=0, Vac droop: 10pu; 21.053 MVAr/kV
    # Vdc droop: 10pu; 40 MW/kV
    create_vsc(net, ac_bus=ba_b2, dc_bus=bm_b2, s_mva=800.0,
               control_mode="droop_q", q_mvar=0.0, v_dc_pu=0.99,
               droop_kv_per_mw=1.0 / 40.0,  # kV/MW: 40 MW per kV
               p_dc_set_mw=0.0, v_dc_set_pu=0.99,
               loss_a=0.8,
               r_pu=r_pu_conv * net.s_base / 800.0,
               x_pu=x_pu_conv * net.s_base / 800.0,
               b_filter_pu=b_filter * 800.0 / net.s_base,
               name="Cm-B2")

    # Cm-B3: 1200 MVA, Q(Vac) droop + P(Vdc) droop
    # Table 12: Vdc droop [10; 60 MW/kV], P_DC_set=-800MW, Vdc=1.0pu
    create_vsc(net, ac_bus=ba_b3, dc_bus=bm_b3, s_mva=1200.0,
               control_mode="droop_vac", v_ac_pu=1.0,
               droop_kv_per_mw=1.0 / 60.0,  # kV/MW: 60 MW per kV
               p_dc_set_mw=-800.0, v_dc_set_pu=1.0,
               loss_a=1.2,
               r_pu=r_pu_conv * net.s_base / 1200.0,
               x_pu=x_pu_conv * net.s_base / 1200.0,
               b_filter_pu=b_filter * 1200.0 / net.s_base,
               name="Cm-B3")

    # Cm-E1: 200 MVA, AC Slack (islanded - offshore platform)
    create_vsc(net, ac_bus=ba_e1, dc_bus=bm_e1, s_mva=200.0,
               control_mode="p_vac", p_mw=0.0, v_ac_pu=1.0,
               loss_a=0.2,
               r_pu=r_pu_conv * net.s_base / 200.0,
               x_pu=x_pu_conv * net.s_base / 200.0,
               b_filter_pu=b_filter * 200.0 / net.s_base,
               name="Cm-E1")

    # Cm-F1: 800 MVA, AC Slack (islanded - offshore wind)
    create_vsc(net, ac_bus=ba_f1, dc_bus=bm_f1, s_mva=800.0,
               control_mode="p_vac", p_mw=0.0, v_ac_pu=1.0,
               loss_a=0.8,
               r_pu=r_pu_conv * net.s_base / 800.0,
               x_pu=x_pu_conv * net.s_base / 800.0,
               b_filter_pu=b_filter * 800.0 / net.s_base,
               name="Cm-F1")

    # --- DCS3 Converters (Table 5, Table 13) ---
    # Bipole converters: rated power is 2*pole_rating

    # Cb-A1: 2*1200 MVA, Q(Vac) droop + P(Vdc) droop, Vac=1pu, Vdc=1.01pu
    create_vsc(net, ac_bus=ba_a1, dc_bus=bb_a1, s_mva=2400.0,
               control_mode="vdc_vac", v_ac_pu=1.0, v_dc_pu=1.01,
               loss_a=2.4,
               r_pu=r_pu_conv * net.s_base / 1200.0,
               x_pu=x_pu_conv * net.s_base / 1200.0,
               b_filter_pu=b_filter * 1200.0 / net.s_base,
               name="Cb-A1")

    # Cb-B1: 2*1200 MVA, Q(Vac) droop + P(Vdc) droop, Vac=1pu, P=-1500MW
    # Inverter mode: delivers 1500 MW from DCS3 to AC bus B1
    create_vsc(net, ac_bus=ba_b1, dc_bus=bb_b1, s_mva=2400.0,
               control_mode="droop_vac", v_ac_pu=1.0,
               droop_kv_per_mw=1.0 / 60.0,  # kV/MW: 60 MW per kV
               p_dc_set_mw=-1500.0, v_dc_set_pu=1.0,
               loss_a=2.4,
               r_pu=r_pu_conv * net.s_base / 1200.0,
               x_pu=x_pu_conv * net.s_base / 1200.0,
               b_filter_pu=b_filter * 1200.0 / net.s_base,
               name="Cb-B1")

    # Cb-B2: 2*1200 MVA, Q(Vac) droop + P(Vdc) droop, Vac=1pu, P=-1700MW
    # Inverter mode: delivers 1700 MW from DCS3 to AC bus B2
    create_vsc(net, ac_bus=ba_b2, dc_bus=bb_b2, s_mva=2400.0,
               control_mode="droop_vac", v_ac_pu=1.0,
               droop_kv_per_mw=1.0 / 60.0,  # kV/MW: 60 MW per kV
               p_dc_set_mw=-1700.0, v_dc_set_pu=1.0,
               loss_a=2.4,
               r_pu=r_pu_conv * net.s_base / 1200.0,
               x_pu=x_pu_conv * net.s_base / 1200.0,
               b_filter_pu=b_filter * 1200.0 / net.s_base,
               name="Cb-B2")

    # Cb-C2: 2*400 MVA, Vac + P=600MW (rectifier: AC wind → DC grid)
    create_vsc(net, ac_bus=ba_c2, dc_bus=bb_c2, s_mva=800.0,
               control_mode="p_vac", p_mw=600.0, v_ac_pu=1.0,
               loss_a=0.8,
               r_pu=r_pu_conv * net.s_base / 400.0,
               x_pu=x_pu_conv * net.s_base / 400.0,
               b_filter_pu=b_filter * 400.0 / net.s_base,
               name="Cb-C2")

    # Cb-D1: 2*800 MVA, AC Slack (islanded)
    create_vsc(net, ac_bus=ba_d1, dc_bus=bb_d1, s_mva=1600.0,
               control_mode="p_vac", p_mw=0.0, v_ac_pu=1.0,
               loss_a=1.6,
               r_pu=r_pu_conv * net.s_base / 800.0,
               x_pu=x_pu_conv * net.s_base / 800.0,
               b_filter_pu=b_filter * 800.0 / net.s_base,
               name="Cb-D1")

    # ===================================================================
    # DC-DC CONVERTERS (Table 6, Table 14)
    # ===================================================================

    # Cd-B1: D=99.595%, R=3.84 Ohm, G=0.78125 uS (Table 8 + Table 14)
    # from_bus = Bb-B1 (V_m, high voltage side), to_bus = Bb-B1s (V_c, low voltage side)
    create_dcdc(net, from_bus=bb_b1, to_bus=bb_b1s, d_ratio=0.99595,
                r_ohm=3.84, g_us=0.78125, name="Cd-B1")

    # Cd-E1: D=50.280%, R=1.92 Ohm, G=0.390625 uS (Table 8 + Table 14)
    # from_bus = Bb-E1 (V_m, 400kV side), to_bus = Bm-E1 (V_c, 200kV side)
    create_dcdc(net, from_bus=bb_e1, to_bus=bm_e1, d_ratio=0.50280,
                r_ohm=1.92, g_us=0.390625, name="Cd-E1")

    return net
