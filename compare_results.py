#!/usr/bin/env python3
"""
Compare AC/DC power flow results between MATLAB (MatACDC) and Python (acdcpf).

Usage:
    python compare_results.py

Prerequisites:
    1. Run MATLAB simulation first: run_case33_ieee.m (generates MatACDC/results/*.csv)
    2. Run Python simulation: python run_case33_ieee.py (generates acdcpf/results/case33_ieee/*.csv)
"""

import numpy as np
if not hasattr(np, 'in1d'):
    np.in1d = np.isin

import pandas as pd
from pathlib import Path


def load_matlab_results(results_dir: Path) -> dict:
    """Load MATLAB results from CSV files."""
    results = {}

    ac_bus_file = results_dir / "res_ac_bus.csv"
    if ac_bus_file.exists():
        results["ac_bus"] = pd.read_csv(ac_bus_file)

    dc_bus_file = results_dir / "res_dc_bus.csv"
    if dc_bus_file.exists():
        results["dc_bus"] = pd.read_csv(dc_bus_file)

    vsc_file = results_dir / "res_vsc.csv"
    if vsc_file.exists():
        results["vsc"] = pd.read_csv(vsc_file)

    dc_line_file = results_dir / "res_dc_line.csv"
    if dc_line_file.exists():
        results["dc_line"] = pd.read_csv(dc_line_file)

    return results


def load_python_results(results_dir: Path) -> dict:
    """Load Python results from CSV files."""
    results = {}

    ac_bus_file = results_dir / "res_ac_bus.csv"
    if ac_bus_file.exists():
        results["ac_bus"] = pd.read_csv(ac_bus_file, index_col=0)

    dc_bus_file = results_dir / "res_dc_bus.csv"
    if dc_bus_file.exists():
        results["dc_bus"] = pd.read_csv(dc_bus_file, index_col=0)

    vsc_file = results_dir / "res_vsc.csv"
    if vsc_file.exists():
        results["vsc"] = pd.read_csv(vsc_file, index_col=0)

    dc_line_file = results_dir / "res_dc_line.csv"
    if dc_line_file.exists():
        results["dc_line"] = pd.read_csv(dc_line_file, index_col=0)

    return results


def compare_ac_bus_results(matlab: pd.DataFrame, python: pd.DataFrame) -> dict:
    """Compare AC bus voltage results."""
    print("\n" + "=" * 70)
    print("AC BUS VOLTAGE COMPARISON")
    print("=" * 70)

    # Bus mapping: MATLAB bus_id -> Python index
    # Based on case33_ieee.py ac_bus_data order
    matlab_bus_order = [1, 2, 3, 4, 5, 6, 7, 12, 13, 14, 15, 19, 20, 23, 24, 25, 29, 30, 31, 32, 33]
    bus_map = {bus_id: idx for idx, bus_id in enumerate(matlab_bus_order)}

    print(f"\nMATLAB buses: {len(matlab)}")
    print(f"Python buses: {len(python)}")

    # Detailed bus-by-bus comparison
    print("\nBus-by-bus voltage comparison:")
    print("-" * 80)
    print(f"{'Bus':<8}{'MATLAB V':<12}{'Python V':<12}{'Diff V':<12}{'MATLAB Ang':<12}{'Python Ang':<12}{'Diff Ang':<10}")
    print("-" * 80)

    v_diffs = []
    a_diffs = []
    for _, m_row in matlab.iterrows():
        bus_id = int(m_row["bus_id"])
        if bus_id in bus_map:
            py_idx = bus_map[bus_id]
            if py_idx in python.index:
                p_row = python.loc[py_idx]
                v_diff = abs(m_row["v_pu"] - p_row["v_pu"])
                a_diff = abs(m_row["v_angle_deg"] - p_row["v_angle_deg"])
                v_diffs.append(v_diff)
                a_diffs.append(a_diff)
                print(f"{bus_id:<8}{m_row['v_pu']:<12.6f}{p_row['v_pu']:<12.6f}{v_diff:<12.6f}"
                      f"{m_row['v_angle_deg']:<12.4f}{p_row['v_angle_deg']:<12.4f}{a_diff:<10.4f}")

    print("-" * 80)

    # Summary statistics
    if v_diffs:
        print(f"\nMax voltage diff: {max(v_diffs):.6f} p.u.")
        print(f"Max angle diff: {max(a_diffs):.4f} deg")
        print(f"Mean voltage diff: {np.mean(v_diffs):.6f} p.u.")
        print(f"Mean angle diff: {np.mean(a_diffs):.4f} deg")

    return {
        "vm_diff_max": max(v_diffs) if v_diffs else 0,
        "va_diff_max": max(a_diffs) if a_diffs else 0,
    }


def compare_dc_bus_results(matlab: pd.DataFrame, python: pd.DataFrame) -> dict:
    """Compare DC bus voltage results."""
    print("\n" + "=" * 70)
    print("DC BUS VOLTAGE COMPARISON")
    print("=" * 70)

    print(f"\nMATLAB DC buses: {len(matlab)}")
    print(f"Python DC buses: {len(python)}")

    print(f"\n{'Metric':<25}{'MATLAB':<20}{'Python':<20}{'Diff':<15}")
    print("-" * 70)

    # DC Voltage
    m_vdc_min = matlab["v_dc_pu"].min()
    m_vdc_max = matlab["v_dc_pu"].max()
    p_vdc_min = python["v_dc_pu"].min()
    p_vdc_max = python["v_dc_pu"].max()

    print(f"{'V_dc_min (p.u.)':<25}{m_vdc_min:<20.6f}{p_vdc_min:<20.6f}{abs(m_vdc_min - p_vdc_min):<15.6f}")
    print(f"{'V_dc_max (p.u.)':<25}{m_vdc_max:<20.6f}{p_vdc_max:<20.6f}{abs(m_vdc_max - p_vdc_max):<15.6f}")

    # DC Power (negate Python to match MATLAB sign convention)
    m_p_total = matlab["p_mw"].sum()
    p_p_total = -python["p_mw"].sum()  # Negate for convention

    print(f"{'Total P_dc (MW)':<25}{m_p_total:<20.4f}{p_p_total:<20.4f}{abs(m_p_total - p_p_total):<15.4f}")

    return {
        "vdc_diff_min": abs(m_vdc_min - p_vdc_min),
        "vdc_diff_max": abs(m_vdc_max - p_vdc_max),
        "p_total_diff": abs(m_p_total - p_p_total),
    }


def compare_vsc_results(matlab: pd.DataFrame, python: pd.DataFrame) -> dict:
    """Compare VSC converter results."""
    print("\n" + "=" * 70)
    print("VSC CONVERTER COMPARISON")
    print("=" * 70)

    print(f"\nMATLAB VSCs: {len(matlab)}")
    print(f"Python VSCs: {len(python)}")

    # Note: Sign conventions differ between MATLAB and Python
    # MATLAB: P_g > 0 = inverter (power INTO AC grid)
    # Python: P_s > 0 = rectifier (power FROM AC grid)
    # So we negate Python P values for comparison

    print(f"\n{'Metric':<25}{'MATLAB':<20}{'Python':<20}{'Diff':<15}")
    print("-" * 70)

    # Total AC power (negate Python to match MATLAB convention)
    m_pac_total = matlab["p_ac_mw"].sum()
    p_pac_total = -python["p_ac_mw"].sum()  # Negate for convention
    print(f"{'Total P_ac (MW)':<25}{m_pac_total:<20.4f}{p_pac_total:<20.4f}{abs(m_pac_total - p_pac_total):<15.4f}")

    # Total Q (same sign convention for Q)
    m_qac_total = matlab["q_ac_mvar"].sum()
    p_qac_total = python["q_ac_mvar"].sum()
    print(f"{'Total Q_ac (MVAr)':<25}{m_qac_total:<20.4f}{p_qac_total:<20.4f}{abs(m_qac_total - p_qac_total):<15.4f}")

    # Total losses
    m_loss_total = matlab["p_loss_mw"].sum()
    p_loss_total = python["p_loss_mw"].sum()
    print(f"{'Total losses (MW)':<25}{m_loss_total:<20.4f}{p_loss_total:<20.4f}{abs(m_loss_total - p_loss_total):<15.4f}")

    return {
        "pac_diff": abs(m_pac_total - p_pac_total),
        "qac_diff": abs(m_qac_total - p_qac_total),
        "loss_diff": abs(m_loss_total - p_loss_total),
    }


def main():
    print("=" * 70)
    print("COMPARING MATLAB (MatACDC) vs PYTHON (acdcpf) RESULTS")
    print("=" * 70)

    # Paths
    project_dir = Path(__file__).parent
    matlab_results_dir = project_dir / "MatACDC" / "results"
    python_results_dir = project_dir / "acdcpf" / "results" / "case33_ieee"

    # Check if results exist
    if not matlab_results_dir.exists():
        print(f"\nMATLAB results not found at: {matlab_results_dir}")
        print("Please run the MATLAB simulation first:")
        print("  >> cd MatACDC")
        print("  >> run_case33_ieee")
        return

    if not python_results_dir.exists():
        print(f"\nPython results not found at: {python_results_dir}")
        print("Please run the Python simulation first:")
        print("  $ python run_case33_ieee.py")
        return

    print(f"\nMATLAB results: {matlab_results_dir}")
    print(f"Python results: {python_results_dir}")

    # Load results
    matlab = load_matlab_results(matlab_results_dir)
    python = load_python_results(python_results_dir)

    # Compare AC bus results
    if "ac_bus" in matlab and "ac_bus" in python:
        ac_diff = compare_ac_bus_results(matlab["ac_bus"], python["ac_bus"])
    else:
        print("\nAC bus results not available for comparison.")
        ac_diff = {}

    # Compare DC bus results
    if "dc_bus" in matlab and "dc_bus" in python:
        dc_diff = compare_dc_bus_results(matlab["dc_bus"], python["dc_bus"])
    else:
        print("\nDC bus results not available for comparison.")
        dc_diff = {}

    # Compare VSC results
    if "vsc" in matlab and "vsc" in python:
        vsc_diff = compare_vsc_results(matlab["vsc"], python["vsc"])
    else:
        print("\nVSC results not available for comparison.")
        vsc_diff = {}

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    all_diffs = list(ac_diff.values()) + list(dc_diff.values()) + list(vsc_diff.values())

    if all_diffs:
        max_diff = max(all_diffs)
        if max_diff < 1e-4:
            print("\n[EXCELLENT] Results match within 0.0001")
        elif max_diff < 1e-2:
            print("\n[GOOD] Results match within 0.01")
        elif max_diff < 0.1:
            print("\n[ACCEPTABLE] Results match within 0.1")
        else:
            print("\n[WARNING] Significant differences found")

        print(f"Maximum difference: {max_diff:.6f}")
    else:
        print("\nNo results available for comparison.")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()