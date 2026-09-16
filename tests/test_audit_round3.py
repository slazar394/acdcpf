"""
Regression tests for the third-round audit items (Victor, 2026-09-16).

1a. Converter loading is reported as |I_c| / i_max_pu (the converter-side
    current the limiter actually enforces) when the full capability limit set
    is present, instead of the grid-side apparent power |S_s| / s_mva, which
    double-counts the transformer/filter reactive consumption and flags
    spurious overloads. Grid-side |S_s| / s_mva remains the fallback when only
    a rating is known.
2.  DC-line topology validation: run_pf warns when an in-service DC line joins
    buses carrying different dc_grid labels, since per-grid slack sharing and
    the per-grid converter-limit rule assume dc_grid matches connectivity.
"""

import warnings

import numpy as np
import pytest

from acdcpf.networks import create_case5_stagg_mtdc_slack
from acdcpf.powerflow import run_pf


def test_loading_uses_converter_current_when_full_limit_set():
    """With Icmax/Vcmax/Vcmin defined, loading = |I_c| / i_max_pu."""
    net = create_case5_stagg_mtdc_slack()
    s_base = net.s_base
    i_max = 45.0 / s_base
    net.vsc.at[0, "i_max_pu"] = i_max
    net.vsc.at[0, "vc_max_pu"] = 1.2
    net.vsc.at[0, "vc_min_pu"] = 0.85

    assert run_pf(net, max_iter_outer=60)

    i_c = abs(net._vsc_internal[0]["i_c"])
    expected = i_c / i_max * 100.0
    assert net.res_vsc.at[0, "loading_percent"] == pytest.approx(expected, abs=1e-9)

    # And it is NOT the grid-side apparent-power number (the two quantities
    # genuinely differ because of the transformer/filter reactive consumption).
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
