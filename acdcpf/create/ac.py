"""
AC element creation functions.
"""

from ..network import Network
from typing import Optional

import pandas as pd


def _append_row(df: pd.DataFrame, row: dict) -> tuple:
    """Append a row to a DataFrame, returning (updated_df, index)."""
    if df.empty:
        idx = 0
    else:
        idx = df.index.max() + 1
    new_row = pd.DataFrame([row], index=[idx])
    return pd.concat([df, new_row]), idx


def create_ac_bus(net: Network, vr_kv: float, name: str = "",
                  v_min_pu: float = 0.9, v_max_pu: float = 1.1,
                  in_service: bool = True) -> int:
    """
    This function creates an AC bus based on the given parameters.

    :param net: the network to add the bus to
    :param vr_kv: bus rated voltage in kV
    :param name: bus name
    :param v_min_pu: minimum bus voltage in pu (default: 0.9)
    :param v_max_pu: maximum bus voltage in pu (default: 1.1)
    :param in_service: bus status (default: True)

    :return: index of the created bus
    """
    net.ac_bus, idx = _append_row(net.ac_bus, {
        "name": name,
        "vr_kv": vr_kv,
        "v_min_pu": v_min_pu,
        "v_max_pu": v_max_pu,
        "in_service": in_service,
    })
    return idx


def create_ac_line(
    net: Network,
    from_bus: int,
    to_bus: int,
    length_km: float,
    r_ohm_per_km: float,
    x_ohm_per_km: float,
    b_us_per_km: float = 0.0,
    g_us_per_km: float = 0.0,
    max_i_ka: Optional[float] = None,
    name: str = "",
    in_service: bool = True,
) -> int:
    """
    Create an AC line.

    Parameters
    ----------
    net : Network
        The network to add the line to
    from_bus : int
        Index of the from bus
    to_bus : int
        Index of the to bus
    length_km : float
        Line length in km
    r_ohm_per_km : float
        Resistance in Ohm/km
    x_ohm_per_km : float
        Reactance in Ohm/km
    b_us_per_km : float, optional
        Shunt susceptance in uS/km (default: 0.0)
    g_us_per_km : float, optional
        Shunt conductance in uS/km (default: 0.0)
    max_i_ka : float, optional
        Maximum current in kA
    name : str, optional
        Line name
    in_service : bool, optional
        Line status (default: True)

    Returns
    -------
    int
        Index of the created line
    """
    net.ac_line, idx = _append_row(net.ac_line, {
        "name": name,
        "from_bus": from_bus,
        "to_bus": to_bus,
        "length_km": length_km,
        "r_ohm_per_km": r_ohm_per_km,
        "x_ohm_per_km": x_ohm_per_km,
        "b_us_per_km": b_us_per_km,
        "g_us_per_km": g_us_per_km,
        "max_i_ka": max_i_ka,
        "in_service": in_service,
    })
    return idx


def create_ac_load(
    net: Network,
    bus: int,
    p_mw: float = 0.0,
    q_mvar: float = 0.0,
    name: str = "",
    in_service: bool = True,
) -> int:
    """
    Create an AC load.

    Parameters
    ----------
    net : Network
        The network to add the load to
    bus : int
        Index of the bus
    p_mw : float, optional
        Active power in MW (default: 0.0)
    q_mvar : float, optional
        Reactive power in MVAr (default: 0.0)
    name : str, optional
        Load name
    in_service : bool, optional
        Load status (default: True)

    Returns
    -------
    int
        Index of the created load
    """
    net.ac_load, idx = _append_row(net.ac_load, {
        "name": name,
        "bus": bus,
        "p_mw": p_mw,
        "q_mvar": q_mvar,
        "in_service": in_service,
    })
    return idx


def create_ac_gen(
    net: Network,
    bus: int,
    p_mw: float = 0.0,
    q_mvar: float = 0.0,
    v_pu: Optional[float] = None,
    q_min_mvar: float = float("-inf"),
    q_max_mvar: float = float("inf"),
    name: str = "",
    in_service: bool = True,
) -> int:
    """
    Create an AC generator.

    Parameters
    ----------
    net : Network
        The network to add the generator to
    bus : int
        Index of the bus
    p_mw : float, optional
        Active power in MW (default: 0.0)
    q_mvar : float, optional
        Reactive power in MVAr (default: 0.0)
    v_pu : float, optional
        Voltage setpoint in pu (for PV and SL buses)
    q_min_mvar : float, optional
        Minimum reactive power in MVAr
    q_max_mvar : float, optional
        Maximum reactive power in MVAr
    name : str, optional
        Generator name
    in_service : bool, optional
        Generator status (default: True)

    Returns
    -------
    int
        Index of the created generator
    """
    net.ac_gen, idx = _append_row(net.ac_gen, {
        "name": name,
        "bus": bus,
        "p_mw": p_mw,
        "q_mvar": q_mvar,
        "v_pu": v_pu,
        "q_min_mvar": q_min_mvar,
        "q_max_mvar": q_max_mvar,
        "in_service": in_service,
    })
    return idx
