"""
Network container for hybrid AC/DC power systems.
"""

import pandas as pd
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Network:
    """
    Hybrid AC/DC network container.

    This class holds all network element data in pandas DataFrames
    and stores results after power flow calculation.

    Attributes
    ----------
    name : str
        Network name
    s_base : float
        System base power in MVA
    f_hz : float
        System frequency in Hz

    ac_bus : pd.DataFrame
        AC bus data
    ac_line : pd.DataFrame
        AC line data
    ac_load : pd.DataFrame
        AC load data
    ac_gen : pd.DataFrame
        AC generator data

    dc_bus : pd.DataFrame
        DC bus data
    dc_line : pd.DataFrame
        DC line data
    dc_load : pd.DataFrame
        DC load data
    dc_gen : pd.DataFrame
        DC generator data

    vsc : pd.DataFrame
        VSC (AC-DC) converter data
    dcdc : pd.DataFrame
        DC-DC converter data

    res_ac_bus : pd.DataFrame
        AC bus results
    res_ac_line : pd.DataFrame
        AC line results
    res_dc_bus : pd.DataFrame
        DC bus results
    res_dc_line : pd.DataFrame
        DC line results
    res_vsc : pd.DataFrame
        VSC converter results
    res_dcdc : pd.DataFrame
        DC-DC converter results

    converged : bool
        Power flow convergence status
    """

    # Network identification
    name: str = ""
    s_base: float = 100.0  # MVA
    f_hz: float = 50.0  # Hz
    pol: int = 2  # Number of poles (1=asymmetric monopole, 2=symmetric monopole or bipole)

    # AC element data
    ac_bus: pd.DataFrame = field(default_factory=pd.DataFrame)
    ac_line: pd.DataFrame = field(default_factory=pd.DataFrame)
    ac_load: pd.DataFrame = field(default_factory=pd.DataFrame)
    ac_gen: pd.DataFrame = field(default_factory=pd.DataFrame)

    # DC element data
    dc_bus: pd.DataFrame = field(default_factory=pd.DataFrame)
    dc_line: pd.DataFrame = field(default_factory=pd.DataFrame)
    dc_load: pd.DataFrame = field(default_factory=pd.DataFrame)
    dc_gen: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Converter data
    vsc: pd.DataFrame = field(default_factory=pd.DataFrame)
    dcdc: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Results (populated after power flow)
    res_ac_bus: pd.DataFrame = field(default_factory=pd.DataFrame)
    res_ac_line: pd.DataFrame = field(default_factory=pd.DataFrame)
    res_dc_bus: pd.DataFrame = field(default_factory=pd.DataFrame)
    res_dc_line: pd.DataFrame = field(default_factory=pd.DataFrame)
    res_vsc: pd.DataFrame = field(default_factory=pd.DataFrame)
    res_dcdc: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Convergence status
    converged: bool = False


def create_empty_network(name: str = "", s_base: float = 100.0, f_hz: float = 50.0, pol: int = 2) -> Network:
    """
    Create an empty hybrid AC/DC network.

    Parameters
    ----------
    name : str, optional
        Network name
    s_base : float, optional
        System base power in MVA (default: 100.0)
    f_hz : float, optional
        System frequency in Hz (default: 50.0)
    pol : int, optional
        Number of poles (default: 2).
        1 = asymmetric monopole (single conductor + ground return)
        2 = symmetric monopole or bipole (two conductors)

    Returns
    -------
    Network
        Empty network object

    Examples
    --------
    >>> import acdcpf as pf
    >>> net = pf.create_empty_network(name="My Network", s_base=100)
    """
    return Network(name=name, s_base=s_base, f_hz=f_hz, pol=pol)