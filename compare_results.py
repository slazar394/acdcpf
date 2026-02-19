#!/usr/bin/env python3
"""
Compare AC/DC power flow results between MATLAB (MatACDC) and Python (acdcpf).
Generates a multi-sheet Excel report with side-by-side comparisons.
"""

import numpy as np

if not hasattr(np, 'in1d'):
    np.in1d = np.isin

import pandas as pd
from pathlib import Path


def load_matlab_results(results_dir: Path) -> dict:
    """Load MATLAB results from CSV files."""
    results = {}
    files = {
        "ac_bus": "res_ac_bus.csv",
        "dc_bus": "res_dc_bus.csv",
        "vsc": "res_vsc.csv",
        "dc_line": "res_dc_line.csv"
    }
    for key, name in files.items():
        path = results_dir / name
        if path.exists():
            results[key] = pd.read_csv(path)
    return results


def load_python_results(results_dir: Path) -> dict:
    """Load Python results from CSV files."""
    results = {}
    files = {
        "ac_bus": "res_ac_bus.csv",
        "dc_bus": "res_dc_bus.csv",
        "vsc": "res_vsc.csv",
        "dc_line": "res_dc_line.csv"
    }
    for key, name in files.items():
        path = results_dir / name
        if path.exists():
            results[key] = pd.read_csv(path, index_col=0)
    return results


def compare_ac_bus(matlab: pd.DataFrame, python: pd.DataFrame) -> pd.DataFrame:
    """Create side-by-side comparison for AC buses."""
    matlab_bus_order = [1, 2, 3, 4, 5, 6, 7, 12, 13, 14, 15, 19, 20, 23, 24, 25, 29, 30, 31, 32, 33]
    bus_map = {bus_id: idx for idx, bus_id in enumerate(matlab_bus_order)}

    rows = []
    for _, m_row in matlab.iterrows():
        bus_id = int(m_row["bus_id"])
        if bus_id in bus_map:
            py_idx = bus_map[bus_id]
            if py_idx in python.index:
                p_row = python.loc[py_idx]
                rows.append({
                    "Bus ID": bus_id,
                    "MATLAB V (pu)": m_row["v_pu"],
                    "Python V (pu)": p_row["v_pu"],
                    "V Diff (pu)": abs(m_row["v_pu"] - p_row["v_pu"]),
                    "MATLAB Angle (deg)": m_row["v_angle_deg"],
                    "Python Angle (deg)": p_row["v_angle_deg"],
                    "Angle Diff (deg)": abs(m_row["v_angle_deg"] - p_row["v_angle_deg"])
                })
    return pd.DataFrame(rows)


def compare_dc_bus(matlab: pd.DataFrame, python: pd.DataFrame) -> pd.DataFrame:
    """Create side-by-side comparison for DC buses."""
    rows = []
    for i in range(min(len(matlab), len(python))):
        m_row = matlab.iloc[i]
        p_row = python.iloc[i]
        rows.append({
            "DC Bus Index": i + 1,
            "MATLAB Vdc (pu)": m_row["v_dc_pu"],
            "Python Vdc (pu)": p_row["v_dc_pu"],
            "Vdc Diff (pu)": abs(m_row["v_dc_pu"] - p_row["v_dc_pu"]),
            "MATLAB P (MW)": m_row["p_mw"],
            "Python P (MW)": -p_row["p_mw"],
            "P Diff (MW)": abs(m_row["p_mw"] - (-p_row["p_mw"]))
        })
    return pd.DataFrame(rows)


def compare_vsc(matlab: pd.DataFrame, python: pd.DataFrame) -> pd.DataFrame:
    """Create side-by-side comparison for VSC converters."""
    rows = []
    for i in range(min(len(matlab), len(python))):
        m_row = matlab.iloc[i]
        p_row = python.iloc[i]
        rows.append({
            "VSC Index": i + 1,
            "MATLAB Pac (MW)": m_row["p_ac_mw"],
            "Python Pac (MW)": -p_row["p_ac_mw"],
            "Pac Diff (MW)": abs(m_row["p_ac_mw"] - (-p_row["p_ac_mw"])),
            "MATLAB Qac (MVAr)": m_row["q_ac_mvar"],
            "Python Qac (MVAr)": p_row["q_ac_mvar"],
            "Qac Diff (MVAr)": abs(m_row["q_ac_mvar"] - p_row["q_ac_mvar"]),
            "MATLAB Loss (MW)": m_row["p_loss_mw"],
            "Python Loss (MW)": p_row["p_loss_mw"],
            "Loss Diff (MW)": abs(m_row["p_loss_mw"] - p_row["p_loss_mw"])
        })
    return pd.DataFrame(rows)


def main():
    project_dir = Path(__file__).parent
    matlab_dir = project_dir / "MatACDC" / "results"
    python_dir = project_dir / "acdcpf" / "results" / "case33_ieee"

    if not matlab_dir.exists() or not python_dir.exists():
        print("Error: Ensure both MATLAB and Python results folders exist.")
        return

    matlab = load_matlab_results(matlab_dir)
    python = load_python_results(python_dir)

    report_path = project_dir / "comparison_report.xlsx"

    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        # AC Bus Sheet
        if "ac_bus" in matlab and "ac_bus" in python:
            df_ac = compare_ac_bus(matlab["ac_bus"], python["ac_bus"])
            df_ac.to_excel(writer, sheet_name="AC Bus Comparison", index=False)

        # DC Bus Sheet
        if "dc_bus" in matlab and "dc_bus" in python:
            df_dc = compare_dc_bus(matlab["dc_bus"], python["dc_bus"])
            df_dc.to_excel(writer, sheet_name="DC Bus Comparison", index=False)

        # VSC Sheet
        if "vsc" in matlab and "vsc" in python:
            df_vsc = compare_vsc(matlab["vsc"], python["vsc"])
            df_vsc.to_excel(writer, sheet_name="VSC Comparison", index=False)

        # Summary Sheet
        summary_rows = []
        if "ac_bus" in matlab and "ac_bus" in python:
            summary_rows.append({"Metric": "Max AC Voltage Diff (pu)", "Value": df_ac["V Diff (pu)"].max()})
            summary_rows.append({"Metric": "Max AC Angle Diff (deg)", "Value": df_ac["Angle Diff (deg)"].max()})
        if "dc_bus" in matlab and "dc_bus" in python:
            summary_rows.append({"Metric": "Max DC Voltage Diff (pu)", "Value": df_dc["Vdc Diff (pu)"].max()})
        if "vsc" in matlab and "vsc" in python:
            summary_rows.append({"Metric": "Total Loss Difference (MW)",
                                 "Value": abs(df_vsc["MATLAB Loss (MW)"].sum() - df_vsc["Python Loss (MW)"].sum())})

        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

    print(f"Report successfully generated at: {report_path}")


if __name__ == '__main__':
    main()