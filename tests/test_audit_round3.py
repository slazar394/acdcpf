"""
Regression tests for the third-round audit items (Victor, 2026-09-16).

1a. Converter loading, when the full capability limit set is present, is a
    converter-side quantity rather than the grid-side apparent power
    |S_s| / s_mva (which double-counts the transformer/filter reactive
    consumption). Round 3 reported |I_c| / i_max_pu here; round 4 (see
    test_audit_round4.py) moved that physical current ratio to the diagnostic
    column i_c_loading_percent and made loading_percent the current-circle
    utilisation the limiter actually enforces. This test guards that move.
    Grid-side |S_s| / s_mva remains the fallback when only a rating is known.
2.  DC-line topology validation: run_pf warns when an in-service DC line joins
    buses carrying different dc_grid labels, since per-grid slack sharing and
    the per-grid converter-limit rule assume dc_grid matches connectivity.
3.  Opt-in Vdc-slack reactive limiting: run_pf(enforce_slack_q_limits=True)
    bounds the reactive power of a Vdc-slack converter that holds AC voltage
    (dropping voltage control, holding the clamped Q) without curtailing its
    slack active power. Off by default, preserving current behaviour.
"""

import warnings

import numpy as np
import pytest

from acdcpf.networks import create_case5_stagg_mtdc_slack
from acdcpf.powerflow import run_pf


def _slack_q_case():
    """case5 slack MTDC with the Vdc_vac converter (idx 1) driven to a large
    reactive output (raised AC-voltage setpoint) under a tight capability set."""
    net = create_case5_stagg_mtdc_slack()
    s_base = net.s_base
    net.vsc.at[1, "v_ac_pu"] = 1.08
    net.vsc.at[1, "i_max_pu"] = 30.0 / s_base
    net.vsc.at[1, "vc_max_pu"] = 1.10
    net.vsc.at[1, "vc_min_pu"] = 0.90
    return net


def test_loading_is_converter_side_when_full_limit_set():
    """With Icmax/Vcmax/Vcmin defined, loading is a converter-side quantity.

    The physical current ratio |I_c| / i_max_pu (round 3) now lives in the
    i_c_loading_percent diagnostic column; loading_percent is the current-circle
    utilisation (round 4). Both differ from the grid-side |S_s| / s_mva because
    of the transformer/filter reactive consumption.
    """
    net = create_case5_stagg_mtdc_slack()
    s_base = net.s_base
    i_max = 45.0 / s_base
    net.vsc.at[0, "i_max_pu"] = i_max
    net.vsc.at[0, "vc_max_pu"] = 1.2
    net.vsc.at[0, "vc_min_pu"] = 0.85

    assert run_pf(net, max_iter_outer=60)

    # The physical current ratio moved to i_c_loading_percent.
    i_c = abs(net._vsc_internal[0]["i_c"])
    assert net.res_vsc.at[0, "i_c_loading_percent"] == pytest.approx(i_c / i_max * 100.0, abs=1e-9)

    # loading_percent is NOT the grid-side apparent-power number.
    p = float(net.res_vsc.at[0, "p_ac_mw"])
    q = float(net.res_vsc.at[0, "q_ac_mvar"])
    grid_side = np.hypot(p, q) / float(net.res_vsc.at[0, "s_mva"]) * 100.0
    assert abs(net.res_vsc.at[0, "loading_percent"] - grid_side) > 1.0


def test_loading_falls_back_to_apparent_power_without_limit_set():
    """With only a rating (no Icmax/Vcmax/Vcmin), loading = |S_s| / s_mva."""
    net = create_case5_stagg_mtdc_slack()
    assert run_pf(net)

    for idx in net.res_vsc.index:
        p = float(net.res_vsc.at[idx, "p_ac_mw"])
        q = float(net.res_vsc.at[idx, "q_ac_mvar"])
        s_mva = float(net.res_vsc.at[idx, "s_mva"])
        expected = np.hypot(p, q) / s_mva * 100.0 if s_mva > 0 else 0.0
        assert net.res_vsc.at[idx, "loading_percent"] == pytest.approx(expected, abs=1e-9)


def test_dc_grid_label_crossing_warns():
    """A DC line joining two different dc_grid labels raises a warning."""
    net = create_case5_stagg_mtdc_slack()
    # Relabel one DC bus so the incident DC lines cross the grid boundary.
    crossed_bus = int(net.dc_line.iloc[0]["to_bus"])
    net.dc_bus.at[crossed_bus, "dc_grid"] = 999

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert run_pf(net)

    msgs = [str(w.message) for w in caught if "dc_grid" in str(w.message)]
    assert msgs, "expected a dc_grid topology-mismatch warning"
    assert any("different dc_grid labels" in m for m in msgs)


def test_dc_grid_labels_consistent_no_warning():
    """A consistent labelling emits no dc_grid topology warning."""
    net = create_case5_stagg_mtdc_slack()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert run_pf(net)

    assert not [w for w in caught if "different dc_grid labels" in str(w.message)]


def test_slack_q_limit_enforced_when_flag_on():
    """enforce_slack_q_limits=True bounds a Vdc-slack converter's reactive power.

    The Vdc_vac converter is driven to a large reactive output. With the flag on
    its Q is clamped onto the capability region and AC-voltage control is dropped,
    while its slack active power (set by the DC balance) is preserved and the
    solve still converges.
    """
    off = _slack_q_case()
    assert run_pf(off, max_iter_outer=60)
    q_off = off._q_s[1]
    p_off = off._p_s[1]
    # Baseline: the slack holds voltage with a large (uncurtailed) reactive draw.
    assert abs(q_off) > 100.0
    assert not off._vsc_vcontrol_disabled

    on = _slack_q_case()
    assert run_pf(on, max_iter_outer=60, enforce_slack_q_limits=True)
    q_on = on._q_s[1]

    # Reactive power bounded well below the uncurtailed value, and V-control
    # dropped (the converter now holds the clamped Q).
    assert abs(q_on) < abs(q_off) - 100.0
    assert 1 in on._vsc_vcontrol_disabled

    # Active power is NOT curtailed: it remains the DC-balance slack, close to
    # the unlimited slack power (it shifts only slightly because dropping AC
    # voltage control perturbs the AC solution, not because P was clamped).
    assert on._p_s[1] == pytest.approx(p_off, abs=2.0)

    # The clamped operating point respects the reactive capability at its fixed
    # active power: re-running the limiter finds no further reactive violation.
    from acdcpf.powerflow.runpf import _converter_limit_candidate
    viol, _, _ = _converter_limit_candidate(on, on._conv_data, 1)
    assert viol != 1


def test_slack_q_limit_off_by_default_preserves_behavior():
    """The flag defaults off: the slack keeps holding voltage with free Q."""
    default = _slack_q_case()
    assert run_pf(default, max_iter_outer=60)

    explicit_off = _slack_q_case()
    assert run_pf(explicit_off, max_iter_outer=60, enforce_slack_q_limits=False)

    # Default == explicit-off, and neither latches or clamps the slack.
    assert not default._vsc_vcontrol_disabled
    assert not explicit_off._vsc_vcontrol_disabled
    np.testing.assert_allclose(default._q_s, explicit_off._q_s, atol=1e-9)
    assert abs(default._q_s[1]) > 100.0


def test_slack_q_limit_noop_when_within_rating():
    """Flag on is a no-op when the slack's reactive power is already feasible."""
    off = create_case5_stagg_mtdc_slack()
    assert run_pf(off)

    on = create_case5_stagg_mtdc_slack()
    assert run_pf(on, enforce_slack_q_limits=True)

    assert not on._vsc_vcontrol_disabled
    np.testing.assert_allclose(on._q_s, off._q_s, atol=1e-6)
    np.testing.assert_allclose(on._p_s, off._p_s, atol=1e-6)
