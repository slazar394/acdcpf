"""Final comprehensive test of acdcpf."""
import warnings
warnings.filterwarnings("ignore")
import numpy as np

print("=" * 60)
print("TEST 1: 2-Terminal HVDC")
print("=" * 60)
from acdcpf.networks.simple import create_2terminal_hvdc
from acdcpf.powerflow.runpf import run_pf

net = create_2terminal_hvdc()
converged = run_pf(net, verbose=True, tol=1e-6)
print(f"Converged: {converged}")
assert converged, "2-terminal HVDC did not converge!"

# Check basic power balance
p_s0 = net._p_s[0]  # VSC-Slack (should be negative = inverter)
print(net._p_s)
p_s1 = net._p_s[1]  # VSC-P (should be 500 MW rectifier)
print(f"VSC-Slack P_s = {p_s0:.2f} MW (inverter)")
print(f"VSC-P     P_s = {p_s1:.2f} MW (rectifier)")
assert p_s0 < 0, "VSC-Slack should be inverter (P_s < 0)"
assert abs(p_s1 - 500.0) < 1.0, "VSC-P should be ~500 MW"

# DC voltages should be close to 1.0
assert abs(net._v_dc[0] - 1.0) < 0.001, "DC slack voltage should be 1.0"
assert abs(net._v_dc[1] - 1.0) < 0.05, "DC-P voltage should be near 1.0"
print("PASSED!\n")


print("=" * 60)
print("TEST 2: CIGRE B4 DC Grid Test System")
print("=" * 60)
from acdcpf.networks.cigre_b4 import create_cigre_b4_dc_test_system

net = create_cigre_b4_dc_test_system()
converged = run_pf(net, verbose=True, tol=1e-6)
print(net.res_dcdc)
print(f"Converged: {converged}")
assert converged, "CIGRE B4 did not converge!"

# Check DC voltage ranges
for idx, row in net.dc_bus.iterrows():
    v_pu = net._v_dc[idx]
    name = row["name"]
    assert 0.90 < v_pu < 1.10, f"Bus {name} voltage {v_pu:.4f} out of range!"

# Check power flow directions
vsc_data = {}
for vsc_idx, vsc_row in net.vsc.iterrows():
    vsc_data[vsc_row["name"]] = {
        "p_s": net._p_s[vsc_idx],
        "p_dc": net._p_dc_vsc[vsc_idx],
        "control": vsc_row["control_mode"],
    }

# Offshore wind converters should rectify (P_s > 0)
assert vsc_data["Cm-C1"]["p_s"] > 0, "Cm-C1 (wind) should rectify"
assert vsc_data["Cm-F1"]["p_s"] > 0, "Cm-F1 (wind) should rectify"
assert vsc_data["Cb-C2"]["p_s"] > 0, "Cb-C2 (wind) should rectify"
assert vsc_data["Cb-D1"]["p_s"] > 0, "Cb-D1 (wind) should rectify"

# Onshore load converters should invert (P_s < 0, delivering to AC loads)
assert vsc_data["Cm-B3"]["p_s"] < 0, "Cm-B3 (onshore load) should invert"
assert vsc_data["Cb-B1"]["p_s"] < 0, "Cb-B1 (onshore load) should invert"
assert vsc_data["Cb-B2"]["p_s"] < 0, "Cb-B2 (onshore load) should invert"

# Platform E1 should be supplied (inverter)
assert vsc_data["Cm-E1"]["p_s"] < 0, "Cm-E1 (platform) should invert"

# DCS1 slack should balance (inverter, exporting wind to AC)
assert vsc_data["Cm-A1"]["p_s"] < 0, "Cm-A1 (DCS1 slack) should invert"

# DCS3 slack should balance (depends on overall flow, likely rectifier from large AC gen)
# Cb-A1 at bus A1 has 2000MW gen, 1000MW load, so excess gen → rectify into DC
assert vsc_data["Cb-A1"]["p_s"] > 0, "Cb-A1 (DCS3 slack) should rectify"

print("\nAll power flow directions correct!")

# Check DCS1 power balance
dcs1_vsc = vsc_data["Cm-A1"]["p_dc"] + vsc_data["Cm-C1"]["p_dc"]
print(f"\nDCS1 balance (losses): {dcs1_vsc:.1f} MW")
assert 0 < dcs1_vsc < 50, "DCS1 losses should be small positive"

# Check converter internal voltages
for vsc_idx, d in net._vsc_internal.items():
    name = net.vsc.loc[vsc_idx, "name"]
    v_f = abs(d["v_f"])
    assert 0.9 < v_f < 1.1, f"{name} V_f={v_f:.3f} out of range!"

print("\nAll converter internal voltages reasonable!")

# Check results DataFrames exist
for attr in ['res_ac_bus', 'res_dc_bus', 'res_dc_line', 'res_vsc', 'res_dcdc']:
    df = getattr(net, attr, None)
    assert df is not None and not df.empty, f"{attr} should not be empty!"

print("\nAll result DataFrames populated!")

# Summary
print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
print(f"DCS1: Bm-A1={net._v_dc[0]:.4f} pu, Bm-C1={net._v_dc[1]:.4f} pu")
grid2_buses = [(idx, row) for idx, row in net.dc_bus.iterrows() if int(row["dc_grid"]) == 2]
print(f"DCS2: " + ", ".join(f"{r['name']}={net._v_dc[i]:.4f}" for i, r in grid2_buses))
grid3_buses = [(idx, row) for idx, row in net.dc_bus.iterrows() if int(row["dc_grid"]) == 3]
print(f"DCS3: " + ", ".join(f"{r['name']}={net._v_dc[i]:.4f}" for i, r in grid3_buses))

print(f"\nAll tests PASSED!")
