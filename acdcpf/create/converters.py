"""
Converter creation functions (VSC and DC-DC).
"""

from ..network import Network
from .ac import _append_row
from typing import Optional


def create_vsc(
    net: Network,
    ac_bus: int,
    dc_bus: int,
    s_mva: float,
    control_mode: str = "p_q",
    p_mw: float = 0.0,
    q_mvar: float = 0.0,
    v_ac_pu: Optional[float] = None,
    v_dc_pu: Optional[float] = None,
    droop_kv_per_mw: Optional[float] = None,
    p_dc_set_mw: Optional[float] = None,
    v_dc_set_pu: Optional[float] = None,
    loss_a: float = 0.0,
    loss_b: float = 0.0,
    loss_c: float = 0.0,
    r_pu: float = 0.01,
    x_pu: float = 0.1,
    b_filter_pu: float = 0.0,
    name: str = "",
    in_service: bool = True,
) -> int:
    """
    Create a VSC (Voltage Source Converter) AC-DC converter.

    Parameters
    ----------
    net : Network
        The network to add the converter to
    ac_bus : int
        Index of the AC bus
    dc_bus : int
        Index of the DC bus
    s_mva : float
        Rated apparent power in MVA
    control_mode : str, optional
        Control mode (default: 'p_q'):
        - 'p_q': Constant P and Q
        - 'p_vac': Constant P and AC voltage
        - 'vdc_q': Constant DC voltage and Q
        - 'vdc_vac': Constant DC voltage and AC voltage
        - 'droop_q': P-Vdc droop and constant Q
        - 'droop_vac': P-Vdc droop and AC voltage
    p_mw : float, optional
        Active power setpoint in MW (default: 0.0)
    q_mvar : float, optional
        Reactive power setpoint in MVAr (default: 0.0)
    v_ac_pu : float, optional
        AC voltage setpoint in pu
    v_dc_pu : float, optional
        DC voltage setpoint in pu
    droop_kv_per_mw : float, optional
        Droop constant in kV/MW
    p_dc_set_mw : float, optional
        P setpoint for droop control in MW
    v_dc_set_pu : float, optional
        Vdc setpoint for droop control in pu
    loss_a : float, optional
        Constant (no-load) loss coefficient in MW (default: 0.0)
    loss_b : float, optional
        Linear loss coefficient in kV (default: 0.0)
    loss_c : float, optional
        Quadratic loss coefficient in Ohm (default: 0.0)
    r_pu : float, optional
        Converter resistance in pu (default: 0.01)
    x_pu : float, optional
        Converter reactance in pu (default: 0.1)
    b_filter_pu : float, optional
        Filter susceptance in pu (default: 0.0)
    name : str, optional
        Converter name
    in_service : bool, optional
        Converter status (default: True)

    Returns
    -------
    int
        Index of the created converter
    """
    net.vsc, idx = _append_row(net.vsc, {
        "name": name,
        "ac_bus": ac_bus,
        "dc_bus": dc_bus,
        "s_mva": s_mva,
        "control_mode": control_mode,
        "p_mw": p_mw,
        "q_mvar": q_mvar,
        "v_ac_pu": v_ac_pu,
        "v_dc_pu": v_dc_pu,
        "droop_kv_per_mw": droop_kv_per_mw,
        "p_dc_set_mw": p_dc_set_mw,
        "v_dc_set_pu": v_dc_set_pu,
        "loss_a": loss_a,
        "loss_b": loss_b,
        "loss_c": loss_c,
        "r_pu": r_pu,
        "x_pu": x_pu,
        "b_filter_pu": b_filter_pu,
        "in_service": in_service,
    })
    return idx


def create_dcdc(
    net: Network,
    from_bus: int,
    to_bus: int,
    d_ratio: float,
    r_ohm: float = 0.0,
    g_us: float = 0.0,
    name: str = "",
    in_service: bool = True,
) -> int:
    """
    Create a DC-DC converter (constant voltage ratio model).

    Models the converter as an ideal transformer with turns ratio D,
    a series resistance on the to-bus (low voltage) side, and a shunt
    conductance on the from-bus (high voltage) side.

    Parameters
    ----------
    net : Network
        The network to add the converter to
    from_bus : int
        Index of the from DC bus (V_m, high voltage side, shunt G side)
    to_bus : int
        Index of the to DC bus (V_c, low voltage side, series R side)
    d_ratio : float
        Voltage ratio D = V_c / V_m (e.g. 0.99595 or 0.50280)
    r_ohm : float, optional
        Total series resistance in ohms (default: 0.0)
    g_us : float, optional
        Shunt conductance in micro-siemens (default: 0.0)
    name : str, optional
        Converter name
    in_service : bool, optional
        Converter status (default: True)

    Returns
    -------
    int
        Index of the created converter
    """
    net.dcdc, idx = _append_row(net.dcdc, {
        "name": name,
        "from_bus": from_bus,
        "to_bus": to_bus,
        "d_ratio": d_ratio,
        "r_ohm": r_ohm,
        "g_us": g_us,
        "in_service": in_service,
    })
    return idx
