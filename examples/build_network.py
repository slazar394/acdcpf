"""
Example: Building a network from scratch

Recreates the 5-bus Stagg system with a 3-terminal MTDC grid (Vdc slack control)
step by step, matching the MatACDC case5_stagg_MTDCslack validation case.

System overview:
- 5 AC buses (345 kV), 7 AC lines, 2 generators, 4 loads
- 3 DC buses (345 kV), 3 DC lines (meshed topology)
- 3 VSC converters:
    VSC 1 (AC bus 2 <-> DC bus 1): P-Q control, rectifier at 60 MW
    VSC 2 (AC bus 3 <-> DC bus 2): Vdc-Vac control (DC slack)
    VSC 3 (AC bus 5 <-> DC bus 3): P-Q control, inverter at 35 MW
"""
import acdcpf as pf

# --- Create empty network ---
net = pf.create_empty_network(
    name="Case5 Stagg MTDC Slack",
    s_base=100.0,   # System base power (MVA)
    f_hz=50.0,      # System frequency (Hz)
    pol=2,          # Bipolar DC (multiplies DC power by 2)
)

base_kv_ac = 345.0  # AC base voltage (kV)
base_kv_dc = 345.0  # DC base voltage (kV)

# --- AC Buses ---
# All buses at 345 kV. Bus types are determined automatically:
#   - A bus with a generator that has v_pu set becomes a PV bus
#   - The first PV bus becomes the slack (reference) bus
#   - All other buses are PQ buses
b1 = pf.create_ac_bus(net, vr_kv=base_kv_ac, name="Bus 1")  # Will be slack
b2 = pf.create_ac_bus(net, vr_kv=base_kv_ac, name="Bus 2")  # Will be PV
b3 = pf.create_ac_bus(net, vr_kv=base_kv_ac, name="Bus 3")
b4 = pf.create_ac_bus(net, vr_kv=base_kv_ac, name="Bus 4")
b5 = pf.create_ac_bus(net, vr_kv=base_kv_ac, name="Bus 5")

# --- AC Loads ---
# Positive p_mw = power consumption
pf.create_ac_load(net, bus=b2, p_mw=20.0,  q_mvar=10.0, name="Load 2")
pf.create_ac_load(net, bus=b3, p_mw=45.0,  q_mvar=15.0, name="Load 3")
pf.create_ac_load(net, bus=b4, p_mw=40.0,  q_mvar=5.0,  name="Load 4")
pf.create_ac_load(net, bus=b5, p_mw=60.0,  q_mvar=10.0, name="Load 5")

# --- AC Generators ---
# Setting v_pu makes the bus a PV (voltage-controlled) bus.
# The first PV generator automatically becomes the slack bus.
pf.create_ac_gen(net, bus=b1, p_mw=0.0,  v_pu=1.06, name="Gen 1 (Slack)")
pf.create_ac_gen(net, bus=b2, p_mw=40.0, v_pu=1.00, name="Gen 2")

# --- AC Lines ---
# The Stagg system uses per-unit impedances. We convert to physical units
# (Ohm/km, uS/km) since acdcpf works in physical units with length_km.
# Using length_km=1.0 makes the per-km values equal to the total values.
z_base = base_kv_ac**2 / net.s_base   # Ohm
y_base = 1.0 / z_base                 # Siemens

# (from_bus, to_bus, r_pu, x_pu, b_pu)
ac_branches = [
    (b1, b2, 0.02, 0.06, 0.06),
    (b1, b3, 0.08, 0.24, 0.05),
    (b2, b3, 0.06, 0.18, 0.04),
    (b2, b4, 0.06, 0.18, 0.04),
    (b2, b5, 0.04, 0.12, 0.03),
    (b3, b4, 0.01, 0.03, 0.02),
    (b4, b5, 0.08, 0.24, 0.05),
]

for fbus, tbus, r_pu, x_pu, b_pu in ac_branches:
    pf.create_ac_line(
        net, from_bus=fbus, to_bus=tbus,
        length_km=1.0,
        r_ohm_per_km=r_pu * z_base,
        x_ohm_per_km=x_pu * z_base,
        b_us_per_km=b_pu * y_base * 1e6,
        name=f"Line {fbus}-{tbus}",
    )

# --- DC Buses ---
# bus_type controls what is specified vs. solved:
#   "vdc"   = DC voltage is fixed (slack), power is calculated
#   "p"     = power is fixed by VSC, voltage is calculated
#   "droop" = power follows P-Vdc droop curve, voltage is calculated
# Each DC grid needs exactly one "vdc" bus.
z_base_dc = base_kv_dc**2 / net.s_base

dc1 = pf.create_dc_bus(net, v_base=base_kv_dc, dc_grid=1,
                        bus_type="p",   v_dc_pu=1.0, name="DC Bus 1")
dc2 = pf.create_dc_bus(net, v_base=base_kv_dc, dc_grid=1,
                        bus_type="vdc", v_dc_pu=1.0, name="DC Bus 2")  # Slack
dc3 = pf.create_dc_bus(net, v_base=base_kv_dc, dc_grid=1,
                        bus_type="p",   v_dc_pu=1.0, name="DC Bus 3")

# --- DC Lines ---
# DC lines are purely resistive (no reactance for steady-state DC).
# Same per-unit to physical conversion as AC.
dc_branches = [
    (dc1, dc2, 0.052),
    (dc2, dc3, 0.052),
    (dc1, dc3, 0.073),
]

for fbus, tbus, r_pu in dc_branches:
    pf.create_dc_line(
        net, from_bus=fbus, to_bus=tbus,
        length_km=1.0,
        r_ohm_per_km=r_pu * z_base_dc,
        name=f"DC Line {fbus}-{tbus}",
    )

# --- VSC Converters ---
# Power sign convention:
#   p_mw > 0 = rectifier (AC -> DC, acts as load on the AC side)
#   p_mw < 0 = inverter  (DC -> AC, acts as generation on the AC side)
#
# Loss model: P_loss = a + b*|Ic| + c*|Ic|^2
#   loss_a in MW, loss_b in kV, loss_c/loss_c_inv in Ohm

# VSC 1: P-Q control, rectifier absorbing 60 MW from AC bus 2
pf.create_vsc(
    net, ac_bus=b2, dc_bus=dc1, s_mva=120.0,
    control_mode="p_q",
    p_mw=60.0, q_mvar=40.0,
    r_tf_pu=0.0015, x_tf_pu=0.1121,
    r_c_pu=0.0001,  x_c_pu=0.16428,
    b_filter_pu=0.0887,
    loss_a=1.103, loss_b=0.887, loss_c=2.885, loss_c_inv=4.371,
    name="VSC DC1-AC2",
)

# VSC 2: Vdc-Vac control (DC slack bus + AC voltage control)
# Power is determined by DC network balance, not specified.
pf.create_vsc(
    net, ac_bus=b3, dc_bus=dc2, s_mva=120.0,
    control_mode="vdc_vac",
    v_dc_pu=1.0, v_ac_pu=1.0,
    r_tf_pu=0.0015, x_tf_pu=0.1121,
    r_c_pu=0.0001,  x_c_pu=0.16428,
    b_filter_pu=0.0887,
    loss_a=1.103, loss_b=0.887, loss_c=2.885, loss_c_inv=4.371,
    name="VSC DC2-AC3",
)

# VSC 3: P-Q control, inverter injecting 35 MW into AC bus 5
pf.create_vsc(
    net, ac_bus=b5, dc_bus=dc3, s_mva=120.0,
    control_mode="p_q",
    p_mw=-35.0, q_mvar=-5.0,
    r_tf_pu=0.0015, x_tf_pu=0.1121,
    r_c_pu=0.0001,  x_c_pu=0.16428,
    b_filter_pu=0.0887,
    loss_a=1.103, loss_b=0.887, loss_c=2.885, loss_c_inv=4.371,
    name="VSC DC3-AC5",
)

# --- Run Power Flow ---
converged = pf.run_pf(net, verbose=True)

# --- Display Results ---
print(f"\nConverged: {converged}")
print("\n=== AC Bus Results ===")
print(net.res_ac_bus)
print("\n=== DC Bus Results ===")
print(net.res_dc_bus)
print("\n=== VSC Converter Results ===")
print(net.res_vsc)
print("\n=== DC Line Results ===")
print(net.res_dc_line)
