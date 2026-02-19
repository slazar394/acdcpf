"""
Pre-built test networks for hybrid AC/DC power flow.

Available networks:
- Simple test cases:
  - create_2terminal_hvdc: Simple 2-terminal HVDC test system

- IEEE/CIGRE standard cases:
  - create_case33_ieee: IEEE 33-bus distribution system with MTDC
  - create_cigre_b4_dc_test_system: CIGRE B4 DC Grid Test System

- MatACDC compatible cases (for validation):
  - create_case5_stagg_hvdc_ptp: 5-bus Stagg with point-to-point HVDC
  - create_case5_stagg_mtdc_slack: 5-bus Stagg with MTDC (slack control)
  - create_case5_stagg_mtdc_droop: 5-bus Stagg with MTDC (droop control)
  - create_case24_ieee_rts_mtdc: IEEE 24-bus RTS (3 zones) with MTDC
"""

from .cigre_b4 import create_cigre_b4_dc_test_system
from .simple import create_2terminal_hvdc
from .case33_ieee import create_case33_ieee
from .case5_stagg_hvdc_ptp import create_case5_stagg_hvdc_ptp
from .case5_stagg_mtdc_slack import create_case5_stagg_mtdc_slack
from .case5_stagg_mtdc_droop import create_case5_stagg_mtdc_droop
from .case24_ieee_rts_mtdc import create_case24_ieee_rts_mtdc

__all__ = [
    # Simple test cases
    "create_2terminal_hvdc",
    # IEEE/CIGRE standard cases
    "create_case33_ieee",
    "create_cigre_b4_dc_test_system",
    # MatACDC compatible cases
    "create_case5_stagg_hvdc_ptp",
    "create_case5_stagg_mtdc_slack",
    "create_case5_stagg_mtdc_droop",
    "create_case24_ieee_rts_mtdc",
]
