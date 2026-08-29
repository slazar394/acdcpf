"""
ACDCPF - Hybrid AC/DC Power Flow Library ⚡

A powerful and efficient Python library for power flow analysis in hybrid AC/DC networks,
implementing the sequential AC/DC power flow method.

Supports:
- Multi-terminal VSC-HVDC systems 🔄
- DC-DC converters 🔌
- Various converter control modes (P, Q, Vac, Vdc, droop) 🎛️
- DC loads and generators ⚡
- Comprehensive logging for better observability 📝
"""

import logging
import sys

# Configure logging for the library
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Numpy 2.x compatibility fix for pypower
# pypower uses numpy.in1d which was removed in numpy 2.0
import numpy as np

if not hasattr(np, "in1d"):
    np.in1d = np.isin
    logger.debug("Applied NumPy 2.x compatibility patch for np.in1d ✅")

__version__ = "0.1.0"
__author__ = "ACDCPF Contributors"

# Welcome banner
print("=" * 60)
print("⚡ ACDCPF v{} - Hybrid AC/DC Power Flow Library ⚡".format(__version__))
print("=" * 60)
print("📖 Docs: https://github.com/slazar394/acdcpf")
print("🐛 Issues: https://github.com/slazar394/acdcpf/issues")
print("⭐ Star us on GitHub if you find this useful!")
print("=" * 60)
print()

logger.info("ACDCPF library v%s loaded successfully! ✅", __version__)

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
from .io import from_pypower, from_matacdc
from .powerflow import run_pf
from .networks import create_2terminal_hvdc

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
    # I/O (import from external formats)
    "from_pypower",
    "from_matacdc",
    # Power flow
    "run_pf",
    # Test networks
    "create_2terminal_hvdc",
]
