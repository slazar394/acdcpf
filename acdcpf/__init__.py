"""
ACDCPF - Hybrid AC/DC Power Flow Library

A Python library for power flow analysis in hybrid AC/DC networks,
implementing the sequential AC/DC power flow method.

Supports:
- Multi-terminal VSC-HVDC systems
- DC-DC converters
- Various converter control modes (P, Q, Vac, Vdc, droop)
- DC loads and generators
"""

# Numpy 2.x compatibility fix for pypower
# pypower uses numpy.in1d which was removed in numpy 2.0
import numpy as np
if not hasattr(np, 'in1d'):
    np.in1d = np.isin

__version__ = "0.1.0"
__author__ = "ACDCPF Contributors"

from .network import Network, create_empty_network
from .create import (
    create_ac_bus,
    create_ac_line,
    create_ac_load,
    create_ac_gen,
    create_dc_bus,
    create_dc_line,
    create_dc_load,
    create_dc_gen,
    create_vsc,
    create_dcdc,
)
from .powerflow import run_pf
from .networks import create_cigre_b4_dc_test_system, create_2terminal_hvdc

__all__ = [
    "__version__",
    # Network
    "Network",
    "create_empty_network",
    # AC elements
    "create_ac_bus",
    "create_ac_line",
    "create_ac_load",
    "create_ac_gen",
    # DC elements
    "create_dc_bus",
    "create_dc_line",
    "create_dc_load",
    "create_dc_gen",
    # Converters
    "create_vsc",
    "create_dcdc",
    # Power flow
    "run_pf",
    # Test networks
    "create_cigre_b4_dc_test_system",
    "create_2terminal_hvdc",
]
