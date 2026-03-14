"""
Pre-built test networks for hybrid AC/DC power flow.

Available networks:
- Simple test cases:
  - create_2terminal_hvdc: Simple 2-terminal HVDC test system

- IEEE standard cases:
  - create_case33_ieee: IEEE 33-bus distribution system with MTDC
  - create_case33_ieee_ext: IEEE 33-bus extended with DC-DC converters

- MatACDC compatible cases (for validation):
  - create_case5_stagg_hvdc_ptp: 5-bus Stagg with point-to-point HVDC
  - create_case5_stagg_mtdc_slack: 5-bus Stagg with MTDC (slack control)
  - create_case5_stagg_mtdc_droop: 5-bus Stagg with MTDC (droop control)
  - create_case24_ieee_rts_mtdc: IEEE 24-bus RTS (3 zones) with MTDC
"""

from .simple import create_2terminal_hvdc
from .case33_ieee import create_case33_ieee
from .case33_ieee_ext import create_case33_ieee_ext
from .case5_stagg_hvdc_ptp import create_case5_stagg_hvdc_ptp
from .case5_stagg_mtdc_slack import create_case5_stagg_mtdc_slack
from .case5_stagg_mtdc_droop import create_case5_stagg_mtdc_droop
from .case24_ieee_rts_mtdc import create_case24_ieee_rts_mtdc

__all__ = [
    # Simple test cases
    "create_2terminal_hvdc",
    # IEEE standard cases
    "create_case33_ieee",
    "create_case33_ieee_ext",
    # MatACDC compatible cases
    "create_case5_stagg_hvdc_ptp",
    "create_case5_stagg_mtdc_slack",
    "create_case5_stagg_mtdc_droop",
    "create_case24_ieee_rts_mtdc",
]
