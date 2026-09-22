"""
Tests locking the DC per-unit voltage convention.

``v_base`` on a DC bus is the pole-to-ground (per-pole) voltage for every
value of ``net.pol``, and ``r_ohm_per_km`` on a DC line is the resistance of a
single conductor. This follows from the DC power flow equation actually
solved, which is MatACDC Eq. (14),

    P_dc,i = p * U_dc,i * sum_j Y_dc,ij * (U_dc,i - U_dc,j)

with ``p = net.pol``. The equation is written in per-pole voltages and
per-conductor resistances, so the ``pol`` factor is what accounts for the
second conductor. Three observable consequences are checked here:

1. The reported triple satisfies ``P = pol * U * I``.
2. ``I`` is the current in one conductor, so it does not scale with ``pol``.
3. Line losses are ``pol * I**2 * R``, one ``I**2 * R`` per conductor.

Each case is a minimal two-bus DC network with no AC side and no converters,
so nothing but the DC equations is under test.

Reference:
- MatACDC User Manual, Eq. (14) and the ``pol`` variable in the casedc files.
- J. Beerten, S. Cole, R. Belmans, "Generalized Steady-State VSC MTDC Model
  for Sequential AC/DC Power Flow Algorithms", IEEE Trans. Power Syst., 2012.
"""

import math

import pytest

import acdcpf as pf


def _two_bus_dc(pol, v_base, r_ohm, p_load_mw, s_base=100.0):
    """Slack bus, P bus, one line, one constant-power load. No AC, no VSC."""
    net = pf.create_empty_network(name="dc-convention", s_base=s_base, pol=pol)
    b0 = pf.create_dc_bus(net, v_base=v_base, bus_type="vdc", v_dc_pu=1.0,
                          name="DC-Slack")
    b1 = pf.create_dc_bus(net, v_base=v_base, bus_type="p", v_dc_pu=1.0,
                          name="DC-Load")
    line = pf.create_dc_line(net, b0, b1, length_km=1.0, r_ohm_per_km=r_ohm)
    pf.create_dc_load(net, bus=b1, p_mw=p_load_mw)

    assert pf.run_pf(net), "two-bus DC case failed to converge"

    return {
        "net": net,
        "u_kv": float(net.res_dc_bus.loc[b1, "v_dc_kv"]),
        # the load bus injection is negative, so flip it to get the load
        "p_mw": -float(net.res_dc_bus.loc[b1, "p_mw"]),
        "i_ka": float(net.res_dc_line.loc[line, "i_ka"]),
        "p_loss_mw": float(net.res_dc_line.loc[line, "p_loss_mw"]),
    }


def _u_closed_form(pol, v_base, r_ohm, p_load_mw):
    """
    Solve P = pol * U * (V - U) / R for the load-bus voltage, taking U and V
    as pole-to-ground voltages and R as the resistance of one conductor.
    """
    disc = (pol * v_base) ** 2 - 4.0 * pol * p_load_mw * r_ohm
    assert disc > 0, "test case has no real operating point"
    return (pol * v_base + math.sqrt(disc)) / (2.0 * pol)


# (pol, v_base_kv, r_ohm, p_load_mw)
CASES = [
    (2, 20.0, 1.0, 10.0),
    (1, 20.0, 1.0, 10.0),
    (2, 10.0, 1.0, 10.0),
    (1, 20.0, 2.0, 10.0),
    (2, 20.0, 1.0, 25.0),
]


@pytest.mark.parametrize("pol,v_base,r_ohm,p_load", CASES)
def test_reported_power_is_pol_times_u_times_i(pol, v_base, r_ohm, p_load):
    """P = pol * U * I, so U is per-pole and I is per-conductor."""
    r = _two_bus_dc(pol, v_base, r_ohm, p_load)
    assert r["p_mw"] / (r["u_kv"] * r["i_ka"]) == pytest.approx(pol, rel=1e-6)


@pytest.mark.parametrize("pol,v_base,r_ohm,p_load", CASES)
def test_line_losses_are_pol_times_i_squared_r(pol, v_base, r_ohm, p_load):
    """One I^2*R per conductor, which is pol conductors in total."""
    r = _two_bus_dc(pol, v_base, r_ohm, p_load)
    assert r["p_loss_mw"] == pytest.approx(pol * r["i_ka"] ** 2 * r_ohm, rel=1e-6)


@pytest.mark.parametrize("pol,v_base,r_ohm,p_load", CASES)
def test_voltage_matches_per_pole_closed_form(pol, v_base, r_ohm, p_load):
    """The solved voltage matches P = pol * U * (V - U) / R exactly."""
    r = _two_bus_dc(pol, v_base, r_ohm, p_load)
    assert r["u_kv"] == pytest.approx(
        _u_closed_form(pol, v_base, r_ohm, p_load), abs=1e-6
    )


def test_v_base_is_not_pole_to_pole():
    """
    The regression this file exists for. If v_base were the pole-to-pole
    voltage under pol=2, then a +/-20 kV bipole would have to be entered as
    v_base=40, and doing so would reproduce the pole-to-ground answer. It does
    not: entering 40 doubles the transmitted power for the same current, so
    the two are not interchangeable.
    """
    per_pole = _two_bus_dc(2, 20.0, 1.0, 10.0)
    pole_to_pole = _two_bus_dc(2, 40.0, 1.0, 10.0)

    assert per_pole["u_kv"] == pytest.approx(19.746794, abs=1e-5)
    assert pole_to_pole["u_kv"] != pytest.approx(per_pole["u_kv"], abs=1e-3)

    # Both still obey P = pol*U*I, which is the point: the equation is fixed
    # and it is v_base that has to be supplied per pole.
    for r in (per_pole, pole_to_pole):
        assert r["p_mw"] / (r["u_kv"] * r["i_ka"]) == pytest.approx(2.0, rel=1e-6)


def test_current_is_per_conductor_not_summed_over_poles():
    """
    Same per-pole voltage and same per-conductor resistance, only pol differs.
    A bipole moves twice the power at the same conductor current, so i_ka must
    be unchanged while p_mw doubles.
    """
    mono = _two_bus_dc(1, 20.0, 1.0, 10.0)
    bi = _two_bus_dc(2, 20.0, 1.0, 20.0)

    assert bi["u_kv"] == pytest.approx(mono["u_kv"], rel=1e-6)
    assert bi["i_ka"] == pytest.approx(mono["i_ka"], rel=1e-6)
    assert bi["p_mw"] == pytest.approx(2.0 * mono["p_mw"], rel=1e-6)
    assert bi["p_loss_mw"] == pytest.approx(2.0 * mono["p_loss_mw"], rel=1e-6)
