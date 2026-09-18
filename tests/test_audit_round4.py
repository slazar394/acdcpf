"""
Regression tests for the fourth-round audit item (Victor, 2026-09-18).

`loading_percent` semantics change again. Round 3 reported the physical
phase-reactor current ratio |I_c| / i_max_pu, which is a current-plane
quantity. The limiter (_convlim) enforces the MatACDC current limit as a
*circle in the (P_s, Q_s) power plane* centred at mpl1 with radius r_l1, so
|I_c| / i_max_pu does not coincide with the enforced boundary: a converged
point the limiter calls feasible (viol == 0) can read |I_c| / i_max_pu > 100 %,
firing a spurious overload warning.

Fix: report loading_percent as the current-circle utilisation

    d_l1 = |s_inj - mpl1| / r_l1 ,   s_inj = -(P_s + jQ_s)

which is exactly the quantity _convlim bounds by 1, so the reported number
never contradicts the limiter's current-circle verdict. The physical current
ratio |I_c| / i_max_pu is retained as a separate diagnostic column
`i_c_loading_percent`. The grid-side |S_s| / s_mva fallback (no full limit
set) is unchanged.
"""

import numpy as np
import pytest

from acdcpf.networks import create_case5_stagg_mtdc_slack
from acdcpf.powerflow import run_pf
from acdcpf.powerflow.runpf import _converter_limit_candidate


def _current_circle_ref(vsm, z_tf, b_f, i_max):
    """Independent re-derivation of the MatACDC current-limit circle
    (centre mpl1, radius r_l1), matching convlim.m -- deliberately NOT the
    production helper, so the test checks the geometry rather than itself."""
    ztf = complex(z_tf)
    bf = float(b_f)
    has_tf = abs(ztf) > 1e-12
    has_bf = abs(bf) > 1e-12
    zf = 1.0 / (1j * bf) if has_bf else np.inf
    ytf = (1.0 / ztf) if has_tf else np.inf
    yf = 1j * bf
    if has_bf:
        mpl1 = complex(-vsm ** 2 * (1.0 / (np.conj(zf) + (np.conj(ztf) if has_tf else 0.0))))
    else:
        mpl1 = 0.0 + 0.0j
    if has_tf:
        r_l1 = vsm * i_max * abs(np.conj(ytf) / (np.conj(yf) + np.conj(ytf)))
    else:
        r_l1 = vsm * i_max
    return mpl1, r_l1


def _case_full_limit_set(i_max_frac=45.0):
    net = create_case5_stagg_mtdc_slack()
    i_max = i_max_frac / net.s_base
    net.vsc.at[0, "i_max_pu"] = i_max
    net.vsc.at[0, "vc_max_pu"] = 1.2
    net.vsc.at[0, "vc_min_pu"] = 0.85
    return net, i_max


def test_loading_is_current_circle_utilisation():
    """With the full limit set, loading_percent = 100 * |s_inj - mpl1| / r_l1."""
    net, i_max = _case_full_limit_set()
    assert run_pf(net, max_iter_outer=60)

    vsm = abs(net._vsc_internal[0]["v_s"])
    z_tf = complex(net.vsc.at[0, "r_tf_pu"], net.vsc.at[0, "x_tf_pu"])
    b_f = net.vsc.at[0, "b_filter_pu"]
    mpl1, r_l1 = _current_circle_ref(vsm, z_tf, b_f, i_max)

    p = float(net.res_vsc.at[0, "p_ac_mw"])
    q = float(net.res_vsc.at[0, "q_ac_mvar"])
    s_inj = -(p + 1j * q) / net.s_base
    expected = abs(s_inj - mpl1) / r_l1 * 100.0

    assert net.res_vsc.at[0, "loading_percent"] == pytest.approx(expected, abs=1e-9)


def test_physical_current_ratio_is_a_separate_diagnostic_column():
    """|I_c| / i_max_pu is retained as i_c_loading_percent, not as loading."""
    net, i_max = _case_full_limit_set()
    assert run_pf(net, max_iter_outer=60)

    i_c = abs(net._vsc_internal[0]["i_c"])
    expected = i_c / i_max * 100.0
    assert "i_c_loading_percent" in net.res_vsc.columns
    assert net.res_vsc.at[0, "i_c_loading_percent"] == pytest.approx(expected, abs=1e-9)


def test_loading_never_contradicts_limiter_verdict():
    """A converged point the limiter deems feasible (viol == 0) reports
    loading_percent <= 100 %, even where the physical current ratio exceeds it.

    This is the whole point of the change: the current-circle utilisation
    agrees with _convlim by construction, so no spurious overload warning
    fires on a converter the limiter considers legal.
    """
    net, _ = _case_full_limit_set()
    assert run_pf(net, max_iter_outer=60)

    viol, _, _ = _converter_limit_candidate(net, net._conv_data, 0)
    assert viol == 0  # limiter calls the converged point feasible

    loading = float(net.res_vsc.at[0, "loading_percent"])
    assert loading <= 100.0 + 1e-6

    # The physical current ratio is the quantity that used to (spuriously)
    # exceed 100 % here; it stays available as the diagnostic column.
    assert net.res_vsc.at[0, "i_c_loading_percent"] > loading


def test_loading_falls_back_to_apparent_power_without_limit_set():
    """With only a rating (no Icmax/Vcmax/Vcmin), loading = |S_s| / s_mva,
    and the diagnostic current column is absent (NaN)."""
    net = create_case5_stagg_mtdc_slack()
    assert run_pf(net)

    for idx in net.res_vsc.index:
        p = float(net.res_vsc.at[idx, "p_ac_mw"])
        q = float(net.res_vsc.at[idx, "q_ac_mvar"])
        s_mva = float(net.res_vsc.at[idx, "s_mva"])
        expected = np.hypot(p, q) / s_mva * 100.0 if s_mva > 0 else 0.0
        assert net.res_vsc.at[idx, "loading_percent"] == pytest.approx(expected, abs=1e-9)
        assert np.isnan(net.res_vsc.at[idx, "i_c_loading_percent"])
