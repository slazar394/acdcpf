"""
Regression tests for the second-round audit items (Victor, 2026-09-15).

1. ICMAX unit consistency: from_matacdc reads Imax as per-unit, so the derived
   apparent-power rating is s_mva = Imax_pu * baseMVA -- consistent with the
   per-unit value the capability-diagram limiter (_convlim) enforces. An
   implausible ICMAX warns.
2. Overload visibility: res_vsc carries a loading_percent column so an
   overloaded Vdc-slack converter (exempt from curtailment) is still visible,
   and a warning is emitted.
3. total_iter: run_ac_pf reports the number of AC island solves, not 0.
4. Voltage-control dummy generators carry a finite, rating-based reactive
   bound rather than a magic +-9999.
"""

import warnings

import numpy as np
import pytest

import acdcpf as pf
from acdcpf.powerflow import run_pf
from acdcpf.powerflow.ac import run_ac_pf, _vsc_reactive_limit_at_bus
from acdcpf.networks import create_case5_stagg_mtdc_slack


def _minimal_matacdc_case(imax=1.10):
    baseMVA = 100.0
    basekVac = 345.0
    ppc = {
        "baseMVA": baseMVA,
        "bus": np.array([
            [1, 3, 0.0, 0.0, 0, 0, 1, 1.0, 0.0, basekVac, 1, 1.1, 0.9],
            [2, 1, 50.0, 20.0, 0, 0, 1, 1.0, 0.0, basekVac, 1, 1.1, 0.9],
        ], dtype=float),
        "gen": np.array([
            [1, 0.0, 0.0, 999.0, -999.0, 1.0, baseMVA, 1, 999.0, -999.0],
        ], dtype=float),
        "branch": np.array([
            [1, 2, 0.01, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1],
        ], dtype=float),
    }
    busdc = np.array([
        [1, 1, 1, 0.0, 1.0, 345.0, 1.1, 0.9, 0.0],
        [2, 2, 1, 0.0, 1.0, 345.0, 1.1, 0.9, 0.0],
    ], dtype=float)
    convdc = np.array([
        [1, 1, 1, -60.0, -40.0, 1.0, 0.001, 0.05, 0.0, 0.0, 0.0,
         basekVac, 1.20, 0.85, imax, 1, 0.0, 0.0, 0.0, 0.0],
        [2, 2, 1, 0.0, 0.0, 1.0, 0.001, 0.05, 0.0, 0.0, 0.0,
         basekVac, 1.30, 0.80, 1.05, 1, 0.0, 0.0, 0.0, 0.0],
    ], dtype=float)
    branchdc = np.array([[1, 2, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 1, 1]], dtype=float)
    pdc = {
        "baseMVAac": baseMVA, "baseMVAdc": baseMVA, "pol": 1,
        "busdc": busdc, "convdc": convdc, "branchdc": branchdc,
    }
    return ppc, pdc, baseMVA


# --- Issue 1: ICMAX unit consistency ---------------------------------------

def test_icmax_rating_is_consistent_with_per_unit_limit():
    """s_mva / baseMVA must equal the per-unit ICMAX fed to the limiter."""
    ppc, pdc, baseMVA = _minimal_matacdc_case(imax=1.10)
    net = pf.from_matacdc(ppc, pdc)

    vsc0 = net.vsc.index[0]
    assert net.vsc.at[vsc0, "i_max_pu"] == pytest.approx(1.10)
    assert net.vsc.at[vsc0, "s_mva"] == pytest.approx(1.10 * baseMVA)
    # The two representations of the current limit must now agree.
    assert net.vsc.at[vsc0, "s_mva"] / baseMVA == pytest.approx(
        net.vsc.at[vsc0, "i_max_pu"]
    )


def test_implausible_icmax_warns():
    """A kA-magnitude ICMAX (unit mistake) triggers a plausibility warning."""
    ppc, pdc, _ = _minimal_matacdc_case(imax=300.0)
    with pytest.warns(UserWarning, match="ICMAX"):
        pf.from_matacdc(ppc, pdc)


def test_plausible_icmax_does_not_warn():
    ppc, pdc, _ = _minimal_matacdc_case(imax=1.10)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        pf.from_matacdc(ppc, pdc)  # must not raise


# --- Issue 2 / 5a: loading_percent + overloaded-slack visibility -----------

def test_res_vsc_has_loading_percent():
    net = create_case5_stagg_mtdc_slack()
    run_pf(net)
    assert "loading_percent" in net.res_vsc.columns
    assert "s_mva" in net.res_vsc.columns
    for idx in net.res_vsc.index:
        p = float(net.res_vsc.at[idx, "p_ac_mw"])
        q = float(net.res_vsc.at[idx, "q_ac_mvar"])
        s_rated = float(net.res_vsc.at[idx, "s_mva"])
        expected = np.hypot(p, q) / s_rated * 100.0
        assert net.res_vsc.at[idx, "loading_percent"] == pytest.approx(expected)


def test_overloaded_slack_is_visible_and_warns():
    """An overloaded Vdc-slack converter is exempt from curtailment but must be
    reported via loading_percent and a warning."""
    net = create_case5_stagg_mtdc_slack()
    cd = pf.build.converters.build_converter_data(net)
    slack = [int(cd["vsc_indices"][i]) for i in range(cd["n_vsc"])
             if "vdc" in str(cd["vsc_control"][i])]
    assert slack, "case must contain a Vdc-slack converter"
    net.vsc.loc[slack[0], "s_mva"] = 5.0  # tiny rating -> forced overload

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert run_pf(net)
        messages = [str(x.message) for x in w]

    assert net.res_vsc.at[slack[0], "loading_percent"] > 100.0
    assert any("exempt from curtailment" in m for m in messages)


# --- Issue 5b: total_iter counts AC solves ---------------------------------

def test_run_ac_pf_reports_nonzero_solve_count():
    net = create_case5_stagg_mtdc_slack()
    run_pf(net)
    _, _, _, n_solves = run_ac_pf(net, net._p_s, net._q_s, {})
    assert n_solves >= 1


# --- Issue 5d: finite, rating-based reactive bound for dummy gens ----------

def test_vac_dummy_generator_reactive_bound_is_rating_based():
    net = create_case5_stagg_mtdc_slack()
    vsc0 = net.vsc.index[0]
    ac_bus = int(net.vsc.at[vsc0, "ac_bus"])
    s_mva = float(net.vsc.at[vsc0, "s_mva"])
    q_lim = _vsc_reactive_limit_at_bus(net, ac_bus)
    assert np.isfinite(q_lim)
    assert q_lim == pytest.approx(s_mva)
    assert q_lim != 9999.0
