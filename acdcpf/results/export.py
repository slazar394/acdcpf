"""
Export power flow results.
"""

import json
import pandas as pd
from pathlib import Path
from typing import Union
from ..network import Network


def export_results_to_csv(net: Network, directory: Union[str, Path]) -> None:
    """
    Export all results to CSV files.

    Creates separate CSV files for each result DataFrame.

    Parameters
    ----------
    net : Network
        The network object with results
    directory : str or Path
        Output directory path
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    result_dfs = {
        "res_ac_bus": net.res_ac_bus,
        "res_ac_line": net.res_ac_line,
        "res_ac_gen": net.res_ac_gen,
        "res_dc_bus": net.res_dc_bus,
        "res_dc_line": net.res_dc_line,
        "res_dc_gen": net.res_dc_gen,
        "res_vsc": net.res_vsc,
        "res_dcdc": net.res_dcdc,
    }

    for name, df in result_dfs.items():
        if not df.empty:
            df.to_csv(directory / f"{name}.csv")


def export_results_to_json(net: Network, filepath: Union[str, Path]) -> None:
    """
    Export all results to a single JSON file.

    Parameters
    ----------
    net : Network
        The network object with results
    filepath : str or Path
        Output file path
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    results = {
        "converged": net.converged,
        "network_name": net.name,
    }

    result_dfs = {
        "res_ac_bus": net.res_ac_bus,
        "res_ac_line": net.res_ac_line,
        "res_ac_gen": net.res_ac_gen,
        "res_dc_bus": net.res_dc_bus,
        "res_dc_line": net.res_dc_line,
        "res_dc_gen": net.res_dc_gen,
        "res_vsc": net.res_vsc,
        "res_dcdc": net.res_dcdc,
    }

    for name, df in result_dfs.items():
        if not df.empty:
            results[name] = json.loads(df.to_json(orient="index"))
        else:
            results[name] = {}

    with open(filepath, "w") as f:
        json.dump(results, f, indent=2)
