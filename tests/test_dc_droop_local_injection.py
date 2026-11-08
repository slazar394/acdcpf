"""
Regression tests: DC loads and generators on droop-controlled DC buses.

At a droop bus the converter's DC power follows the droop law, but the bus
power balance must still include any local constant-power DC load or DC
generator. A former bug compared the droop power alone with the bus's total
net injection, so local loads/generators silently dropped out of the DC power
balance (the solver still reported convergence).

The checks are physical and self-contained (no external reference):
- DC power conservation: the sum of all DC bus injections equals the DC line
  losses;
- at the droop bus, converter DC power + generation - load equals the bus's
  net injection;
- the droop converter's DC power satisfies its droop characteristic.
"""

import warnings

import numpy as np
import pytest

import acdcpf as pf
from acdcpf.powerflow import run_pf

S_BASE = 100.0
V_DC = 10.0      # kV, per pole
K_DROOP = 0.5    # kV/MW
P0 = 2.0         # MW, droop power set-point (into the DC grid)
V0 = 1.0         # pu, droop voltage set-point
P_LOAD = 3.0     # MW, constant-power DC load at the droop bus
P_GEN = 1.2      # MW, DC generator at the droop bus


def _build(load_mw=P_LOAD, gen_mw=P_GEN):
    net = pf.create_empty_network(name="droop local injection", s_base=S_BASE, pol=2)
    a0 = pf.create_ac_bus(net, vr_kv=20.0, name="AC0")
    a1 = pf.create_ac_bus(net, vr_kv=20.0, name="AC1")
    pf.create_ac_line(net, a0, a1, length_km=5.0, r_ohm_per_km=0.16, x_ohm_per_km=0.11)
    pf.create_ac_gen(net, bus=a0, p_mw=0.0, v_pu=1.0, name="slack")
    pf.create_ac_load(net, bus=a1, p_mw=1.0, q_mvar=0.3)

    d0 = pf.create_dc_bus(net, v_base=V_DC, dc_grid=0, bus_type="vdc", v_dc_pu=1.0, name="DC0")
    d1 = pf.create_dc_bus(net, v_base=V_DC, dc_grid=0, bus_type="droop", v_dc_pu=1.0, name="DC1")
    d2 = pf.create_dc_bus(net, v_base=V_DC, dc_grid=0, bus_type="p", v_dc_pu=1.0, name="DC2")
    pf.create_dc_line(net, d0, d1, length_km=8.0, r_ohm_per_km=0.1)
    pf.create_dc_line(net, d1, d2, length_km=4.0, r_ohm_per_km=0.1)
    pf.create_dc_load(net, bus=d2, p_mw=1.5)
    if load_mw:
        pf.create_dc_load(net, bus=d1, p_mw=load_mw)
    if gen_mw:
        pf.create_dc_gen(net, bus=d1, p_mw=gen_mw)

    pf.create_vsc(net, ac_bus=a0, dc_bus=d0, s_mva=10.0, control_mode="vdc_q", v_dc_pu=1.0, name="slack VSC")
    pf.create_vsc(net, ac_bus=a1, dc_bus=d1, s_mva=10.0, control_mode="droop_q",
                  droop_kv_per_mw=K_DROOP, p_dc_set_mw=P0, v_dc_set_pu=V0, name="droop VSC")
    return net


@pytest.fixture(scope="module")
def solved():
    net = _build()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert run_pf(net), "power flow must converge"
    return net


def test_dc_power_is_conserved(solved):
    net = solved
    inj = net.res_dc_bus["p_mw"].sum()
    losses = net.res_dc_line["p_loss_mw"].sum()
    assert inj == pytest.approx(losses, abs=1e-6)


def test_droop_bus_balance_includes_local_load_and_gen(solved):
    net = solved
    p_conv = float(net.res_vsc.loc[net.res_vsc["name"] == "droop VSC", "p_dc_mw"].iloc[0])
    p_bus = float(net.res_dc_bus.loc[net.res_dc_bus["name"] == "DC1", "p_mw"].iloc[0])
    assert p_bus == pytest.approx(p_conv + P_GEN - P_LOAD, abs=1e-6)


def test_droop_characteristic_holds(solved):
    net = solved
    v = float(net.res_dc_bus.loc[net.res_dc_bus["name"] == "DC1", "v_dc_pu"].iloc[0])
    p_conv = float(net.res_vsc.loc[net.res_vsc["name"] == "droop VSC", "p_dc_mw"].iloc[0])
    expected = P0 - (v - V0) * V_DC / K_DROOP
    assert p_conv == pytest.approx(expected, abs=1e-6)


def test_local_load_changes_the_solution():
    """With the load moved off the droop bus the slack must supply less power."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with_load = _build(); run_pf(with_load)
        no_load = _build(load_mw=0.0, gen_mw=0.0); run_pf(no_load)
    p_slack_with = float(with_load.res_vsc["p_ac_mw"].iloc[0])
    p_slack_without = float(no_load.res_vsc["p_ac_mw"].iloc[0])
    # Net local demand of P_LOAD - P_GEN = 1.8 MW must be supplied by the
    # converters (shared between slack and droop), so the slack's rectified
    # power has to increase.
    assert p_slack_with - p_slack_without > 0.5
