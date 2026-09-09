"""
Integration tests for converter-limit enforcement inside run_pf.

Covers the full MatACDC PQ-capability-diagram limiter wired into the
sequential AC/DC solver, the control-mode switching it triggers on a
violation (dropping AC-voltage control / disabling droop), and the
`enforce_limits` opt-out flag.
"""

import numpy as np
import pytest

from acdcpf.networks import (
    create_case5_stagg_mtdc_slack,
    create_case5_stagg_mtdc_droop,
)
from acdcpf.powerflow import run_pf
from acdcpf.powerflow.runpf import _convlim, _check_converter_limits


def _apparent_power(net, idx):
    p = float(net.res_vsc.at[idx, "p_ac_mw"])
    q = float(net.res_vsc.at[idx, "q_ac_mvar"])
    return np.hypot(p, q)


def test_full_diagram_limits_reduce_loading_and_converge():
    """Tight Icmax/Vcmax/Vcmin clamp a converter onto its capability region."""
    base = create_case5_stagg_mtdc_slack()
    assert run_pf(base)
    s_unlimited = _apparent_power(base, 0)

    net = create_case5_stagg_mtdc_slack()
    s_base = net.s_base
    i_max = 45.0 / s_base                  # rating well below the ~72 MVA point
    net.vsc.at[0, "i_max_pu"] = i_max
    net.vsc.at[0, "vc_max_pu"] = 1.2
    net.vsc.at[0, "vc_min_pu"] = 0.85

    assert run_pf(net, max_iter_outer=60)
    s_limited = _apparent_power(net, 0)
    assert s_limited < s_unlimited - 1.0, "full-diagram limit did not reduce loading"

    # The converged operating point must respect the capability diagram: the
    # limiter is a fixed point there (no further violation).
    ac = int(net.vsc.at[0, "ac_bus"])
    v_s = net._v_mag[ac] * np.exp(1j * net._v_ang[ac])
    z_tf = complex(net.vsc.at[0, "r_tf_pu"], net.vsc.at[0, "x_tf_pu"])
    z_c = complex(net.vsc.at[0, "r_c_pu"], net.vsc.at[0, "x_c_pu"])
    b_f = float(net.vsc.at[0, "b_filter_pu"])
    p = float(net.res_vsc.at[0, "p_ac_mw"]) / s_base
    q = float(net.res_vsc.at[0, "q_ac_mvar"]) / s_base
    viol, _, _ = _convlim(p, q, v_s, z_tf, b_f, z_c, i_max, 1.2, 0.85)
    assert viol == 0, "converged operating point violates the capability diagram"


def test_droop_and_vac_control_switching_on_violation():
    """A violated droop_vac converter drops V-control AND droop control."""
    net = create_case5_stagg_mtdc_droop()
    # Rate two droop converters below their operating points.
    net.vsc.at[0, "s_mva"] = 40.0   # droop_q  (~72 MVA)  -> droop disabled
    net.vsc.at[1, "s_mva"] = 15.0   # droop_vac (~22 MVA) -> droop + V-control

    assert run_pf(net, max_iter_outer=80)

    # droop_vac converter (idx 1) latched on both control paths.
    assert 1 in net._vsc_vcontrol_disabled
    assert 1 in net._vsc_droop_disabled
    # droop_q converter (idx 0) latched only on droop.
    assert 0 in net._vsc_droop_disabled
    assert 0 not in net._vsc_vcontrol_disabled

    # Both clamped onto their apparent-power ratings.
    assert _apparent_power(net, 0) <= 40.0 + 1e-3
    assert _apparent_power(net, 1) <= 15.0 + 1e-3


def test_one_correction_per_grid_per_call():
    """A single _check_converter_limits call corrects one converter per grid.

    Two converters in the same DC grid are forced over their ratings; only the
    larger active-power violation is corrected (and mode-switched), the other
    is left for a later iteration. This is MatACDC's one-at-a-time behaviour,
    which avoids spuriously latching a control switch on a coupled violation.
    """
    net = create_case5_stagg_mtdc_droop()
    assert run_pf(net)  # populate _conv_data / _p_s / latch sets

    cd = net._conv_data
    # vsc 0 and 2 are droop_q converters in the same DC grid (grid 1).
    cd["vsc_s_mva"] = np.array(cd["vsc_s_mva"], dtype=float)  # writable copy
    cd["vsc_s_mva"][0] = 10.0
    cd["vsc_s_mva"][2] = 10.0
    net._p_s[0], net._q_s[0] = 60.0, 0.0   # |dP| = 50 after clamp to 10
    net._p_s[2], net._q_s[2] = 40.0, 0.0   # |dP| = 30 after clamp to 10
    net._vsc_vcontrol_disabled.clear()
    net._vsc_droop_disabled.clear()

    hit = _check_converter_limits(net)
    assert hit
    # Only the larger violation (vsc 0) is corrected this call.
    assert net._p_s[0] == pytest.approx(10.0, abs=1e-6)
    assert net._p_s[2] == pytest.approx(40.0, abs=1e-6)  # untouched
    # Its droop control is switched; the untouched one is not latched.
    assert net._vsc_droop_disabled == {0}
    assert net._vsc_vcontrol_disabled == set()


def test_enforce_limits_flag_disables_enforcement():
    """enforce_limits=False leaves setpoints unclamped and latches empty."""
    net = create_case5_stagg_mtdc_droop()
    net.vsc.at[0, "s_mva"] = 40.0
    net.vsc.at[1, "s_mva"] = 15.0

    assert run_pf(net, enforce_limits=False, max_iter_outer=80)

    assert not net._vsc_vcontrol_disabled
    assert not net._vsc_droop_disabled
    # Converter 0 runs above the artificial 40 MVA rating (limit ignored).
    assert _apparent_power(net, 0) > 40.0 + 1.0


def test_within_rating_solution_is_unchanged_by_enforcement():
    """Enforcement is a no-op for a solution already within limits."""
    ref = create_case5_stagg_mtdc_slack()
    run_pf(ref, enforce_limits=False)

    net = create_case5_stagg_mtdc_slack()
    run_pf(net, enforce_limits=True)

    np.testing.assert_allclose(
        net.res_vsc["p_ac_mw"].values,
        ref.res_vsc["p_ac_mw"].values,
        atol=1e-6,
    )
    np.testing.assert_allclose(
        net.res_vsc["q_ac_mvar"].values,
        ref.res_vsc["q_ac_mvar"].values,
        atol=1e-6,
    )
    assert not net._vsc_vcontrol_disabled and not net._vsc_droop_disabled
