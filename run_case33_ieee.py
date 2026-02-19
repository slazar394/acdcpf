#!/usr/bin/env python3
"""
Run AC/DC power flow for the IEEE 33-bus network.

This script runs the sequential AC/DC power flow using the acdcpf tool
for the case33_ieee network and exports voltage results for comparison
with the MATLAB MatACDC tool.

Usage:
    python run_case33_ieee.py
"""

import sys
from pathlib import Path

# Fix for NumPy 2.0+ compatibility with pypower
import numpy as np
if not hasattr(np, 'in1d'):
    np.in1d = np.isin

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from acdcpf.networks.case33_ieee import create_case33_ieee
from acdcpf.powerflow.runpf import run_pf
from acdcpf.results.export import export_results_to_csv, export_results_to_json


def main():
    print("=" * 50)
    print("Running AC/DC Power Flow: case33_ieee (Python)")
    print("=" * 50)
    print()

    # Create the network
    print("Creating IEEE 33-bus network with MTDC...")
    net = create_case33_ieee()

    print(f"  Network name: {net.name}")
    print(f"  Base MVA: {net.s_base}")
    print(f"  Number of poles: {net.pol}")
    print(f"  AC buses: {len(net.ac_bus)}")
    print(f"  AC lines: {len(net.ac_line)}")
    print(f"  AC loads: {len(net.ac_load)}")
    print(f"  AC generators: {len(net.ac_gen)}")
    print(f"  DC buses: {len(net.dc_bus)}")
    print(f"  DC lines: {len(net.dc_line)}")
    print(f"  VSC converters: {len(net.vsc)}")
    print()

    # Run power flow
    print("Running sequential AC/DC power flow...")
    converged = run_pf(net, max_iter_outer=30, max_iter_inner=30, tol=1e-8, verbose=True)
    print()

    # Print convergence status
    print("=" * 50)
    if converged:
        print("Power flow CONVERGED")
    else:
        print("Power flow DID NOT CONVERGE")
    print("=" * 50)
    print()

    # Export results
    results_dir = Path(__file__).parent / "acdcpf" / "results" / "case33_ieee"
    print(f"Exporting results to: {results_dir}")

    export_results_to_csv(net, results_dir)
    export_results_to_json(net, results_dir / "results.json")

    print("  Results exported successfully.")
    print()

    # Print summary
    print("=" * 50)
    print("RESULTS SUMMARY")
    print("=" * 50)

    print("\nAC Bus Results:")
    if not net.res_ac_bus.empty:
        print(f"  Voltage range: {net.res_ac_bus['v_pu'].min():.4f} - {net.res_ac_bus['v_pu'].max():.4f} p.u.")
        print(f"  Angle range: {net.res_ac_bus['v_angle_deg'].min():.2f} - {net.res_ac_bus['v_angle_deg'].max():.2f} deg")
        print("\n  First 10 AC buses:")
        print("  " + "-" * 50)
        print(f"  {'Bus':<8}{'V (p.u.)':<12}{'Angle (deg)':<12}{'P (MW)':<12}{'Q (MVAr)':<12}")
        print("  " + "-" * 50)
        for idx in list(net.res_ac_bus.index)[:10]:
            row = net.res_ac_bus.loc[idx]
            print(f"  {idx:<8}{row['v_pu']:<12.6f}{row['v_angle_deg']:<12.4f}{row['p_mw']:<12.4f}{row['q_mvar']:<12.4f}")
    else:
        print("  No AC bus results available.")

    print("\nDC Bus Results:")
    if not net.res_dc_bus.empty:
        print(f"  DC voltage range: {net.res_dc_bus['v_dc_pu'].min():.4f} - {net.res_dc_bus['v_dc_pu'].max():.4f} p.u.")
        print("\n  All DC buses:")
        print("  " + "-" * 40)
        print(f"  {'Bus':<8}{'V_dc (p.u.)':<15}{'V_dc (kV)':<12}{'P (MW)':<12}")
        print("  " + "-" * 40)
        for idx in net.res_dc_bus.index:
            row = net.res_dc_bus.loc[idx]
            print(f"  {idx:<8}{row['v_dc_pu']:<15.6f}{row['v_dc_kv']:<12.4f}{row['p_mw']:<12.4f}")
    else:
        print("  No DC bus results available.")

    print("\nVSC Converter Results:")
    if not net.res_vsc.empty:
        total_p_ac = net.res_vsc['p_ac_mw'].sum()
        total_q_ac = net.res_vsc['q_ac_mvar'].sum()
        total_loss = net.res_vsc['p_loss_mw'].sum()
        print(f"  Total P_AC injection: {total_p_ac:.4f} MW")
        print(f"  Total Q_AC injection: {total_q_ac:.4f} MVAr")
        print(f"  Total converter losses: {total_loss:.4f} MW")
        print("\n  All VSC converters:")
        print("  " + "-" * 70)
        print(f"  {'VSC':<8}{'P_ac (MW)':<12}{'Q_ac (MVAr)':<14}{'P_dc (MW)':<12}{'P_loss (MW)':<12}{'V_ac':<8}{'V_dc':<8}")
        print("  " + "-" * 70)
        for idx in net.res_vsc.index:
            row = net.res_vsc.loc[idx]
            print(f"  {idx:<8}{row['p_ac_mw']:<12.4f}{row['q_ac_mvar']:<14.4f}{row['p_dc_mw']:<12.4f}{row['p_loss_mw']:<12.4f}{row['v_ac_pu']:<8.4f}{row['v_dc_pu']:<8.4f}")
    else:
        print("  No VSC results available.")

    print("\nDC Line Results:")
    if not net.res_dc_line.empty:
        total_dc_loss = net.res_dc_line['p_loss_mw'].sum()
        print(f"  Total DC line losses: {total_dc_loss:.4f} MW")
    else:
        print("  No DC line results available.")

    print()
    print("=" * 50)
    print("Power flow complete.")
    print("=" * 50)

    return converged


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)