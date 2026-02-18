"""
DC element creation functions.
"""

import pandas as pd
from typing import Optional
from ..network import Network
from .ac import _append_row


def create_dc_bus(
    net: Network,
    v_base: float,
    name: str = "",
    dc_grid: int = 0,
    bus_type: str = "p",
    v_dc_pu: float = 1.0,
    v_min: float = 0.95,
    v_max: float = 1.05,
    in_service: bool = True,
) -> int:
    """
    Create a DC bus.

    Parameters
    ----------
    net : Network
        The network to add the bus to
    v_base : float
        Base voltage in kV (pole-to-pole for bipole, pole-to-ground for monopole)
    name : str, optional
        Bus name
    dc_grid : int, optional
        DC grid identifier for multi-grid support (default: 0)
    bus_type : str, optional
        Bus type: 'vdc' (slack), 'p', or 'droop' (default: 'p')
    v_dc_pu : float, optional
        DC voltage in pu (default: 1.0)
    v_min : float, optional
        Minimum voltage in pu (default: 0.95)
    v_max : float, optional
        Maximum voltage in pu (default: 1.05)
    in_service : bool, optional
        Bus status (default: True)

    Returns
    -------
    int
        Index of the created bus
    """
    net.dc_bus, idx = _append_row(net.dc_bus, {
        "name": name,
        "v_base": v_base,
        "dc_grid": dc_grid,
        "bus_type": bus_type,
        "v_dc_pu": v_dc_pu,
        "v_min": v_min,
        "v_max": v_max,
        "in_service": in_service,
    })
    return idx


def create_dc_line(
    net: Network,
    from_bus: int,
    to_bus: int,
    length_km: float,
    r_ohm_per_km: float,
    max_i_ka: Optional[float] = None,
    name: str = "",
    in_service: bool = True,
) -> int:
    """
    Create a DC line.

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
    net.dc_line, idx = _append_row(net.dc_line, {
        "name": name,
        "from_bus": from_bus,
        "to_bus": to_bus,
        "length_km": length_km,
        "r_ohm_per_km": r_ohm_per_km,
        "max_i_ka": max_i_ka,
        "in_service": in_service,
    })
    return idx


def create_dc_load(
    net: Network,
    bus: int,
    p_mw: float = 0.0,
    load_type: str = "constant_power",
    name: str = "",
    in_service: bool = True,
) -> int:
    """
    Create a DC load.

    Parameters
    ----------
    net : Network
        The network to add the load to
    bus : int
        Index of the bus
    p_mw : float, optional
        Active power in MW (default: 0.0)
    load_type : str, optional
        Load type: 'constant_power' or 'constant_impedance' (default: 'constant_power')
    name : str, optional
        Load name
    in_service : bool, optional
        Load status (default: True)

    Returns
    -------
    int
        Index of the created load
    """
    net.dc_load, idx = _append_row(net.dc_load, {
        "name": name,
        "bus": bus,
        "p_mw": p_mw,
        "load_type": load_type,
        "in_service": in_service,
    })
    return idx


def create_dc_gen(
    net: Network,
    bus: int,
    p_mw: float = 0.0,
    name: str = "",
    in_service: bool = True,
) -> int:
    """
    Create a DC generator.

    Parameters
    ----------
    net : Network
        The network to add the generator to
    bus : int
        Index of the bus
    p_mw : float, optional
        Active power in MW (default: 0.0)
    name : str, optional
        Generator name
    in_service : bool, optional
        Generator status (default: True)

    Returns
    -------
    int
        Index of the created generator
    """
    net.dc_gen, idx = _append_row(net.dc_gen, {
        "name": name,
        "bus": bus,
        "p_mw": p_mw,
        "in_service": in_service,
    })
    return idx
