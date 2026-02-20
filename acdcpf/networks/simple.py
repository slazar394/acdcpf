"""
Simple test networks for basic validation.
"""

from ..network import Network, create_empty_network
from ..create.ac import create_ac_bus, create_ac_line, create_ac_load, create_ac_gen
from ..create.dc import create_dc_bus, create_dc_line
from ..create.converters import create_vsc


def create_2terminal_hvdc() -> Network:
    """
    Create a simple 2-terminal HVDC test system.

    Two AC buses connected via a point-to-point HVDC link:
    - AC Bus 0 (slack, 380 kV) with generator
    - AC Bus 1 (PQ, 380 kV) with load
    - DC Bus 0 (Vdc slack, 400 kV)
    - DC Bus 1 (P-controlled, 400 kV)
    - DC Line connecting DC buses (100 km)
    - VSC 0: Vdc control at DC Bus 0
    - VSC 1: P control, injecting 500 MW into DC grid

    Returns
    -------
    Network
        The 2-terminal HVDC test network
    """
    net = create_empty_network(name="2-Terminal HVDC", s_base=100.0, f_hz=50.0)

    # AC buses
    ac_b0 = create_ac_bus(net, vr_kv=380.0, name="AC-Slack")
    ac_b1 = create_ac_bus(net, vr_kv=380.0, name="AC-Load")

    # AC line between buses
    # X = 2*pi*50*0.8532e-3 = 0.268 Ohm/km (from L=0.8532 mH/km)
    # B = 2*pi*50*0.0135e-6*1e6 = 4.24 uS/km (from C=0.0135 uF/km)
    create_ac_line(net, from_bus=ac_b0, to_bus=ac_b1, length_km=100.0,
                   r_ohm_per_km=0.02, x_ohm_per_km=0.268,
                   b_us_per_km=4.24, name="AC Line 1")

    # Generator at slack bus
    create_ac_gen(net, bus=ac_b0, p_mw=0.0, v_pu=1.0, name="Gen Slack")

    # Load at bus 1
    create_ac_load(net, bus=ac_b1, p_mw=500.0, q_mvar=100.0, name="Load 1")

    # DC buses
    dc_b0 = create_dc_bus(net, v_base=400.0, dc_grid=0, bus_type="vdc",
                          v_dc_pu=1.0, name="DC-Slack")
    dc_b1 = create_dc_bus(net, v_base=400.0, dc_grid=0, bus_type="p",
                          v_dc_pu=1.0, name="DC-P")

    # DC line
    create_dc_line(net, from_bus=dc_b0, to_bus=dc_b1, length_km=100.0,
                   r_ohm_per_km=0.0114, name="DC Line 1")

    # VSC converters
    # VSC 0: Vdc control + Q control at DC bus 0
    create_vsc(net, ac_bus=ac_b0, dc_bus=dc_b0, s_mva=600.0,
               control_mode="vdc_q", q_mvar=0.0, v_dc_pu=1.0,
               loss_a=1.1033, loss_b=0.0, loss_c=0.0,
               r_tf_pu=0.005, x_tf_pu=0.05,
               r_c_pu=0.005, x_c_pu=0.05, name="VSC-Slack")

    # VSC 1: P + Q control at DC bus 1
    create_vsc(net, ac_bus=ac_b1, dc_bus=dc_b1, s_mva=600.0,
               control_mode="p_q", p_mw=500.0, q_mvar=0.0,
               loss_a=1.1033, loss_b=0.0, loss_c=0.0,
               r_tf_pu=0.005, x_tf_pu=0.05,
               r_c_pu=0.005, x_c_pu=0.05, name="VSC-P")

    return net
