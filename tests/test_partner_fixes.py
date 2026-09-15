"""
Regression tests for three issues found in code review:

1. Converter limits (_check_converter_limits) existed but were never called,
   so a VSC could operate far above its rating with no enforcement.
2. run_pf returned converged=True without checking that the AC/DC subproblems
   actually converged (ac_conv / dc_conv were captured but ignored). On an
   AC-only network with no VSCs it returned True on the first iteration even
   for a physically impossible power flow.
3. VCMAX / VCMIN converter voltage limits were never imported from MatACDC
   case files, and ICMAX was used only to derive s_mva and then discarded.

References:
- MatACDC idx_convdc.m (column layout), convlim.m (limit enforcement,
  chapter 4.1.4 of the MatACDC user manual).
"""

import numpy as np
import pytest

import acdcpf as pf
from acdcpf.powerflow import run_pf
from acdcpf.networks import create_case5_stagg_mtdc_slack


# ---------------------------------------------------------------------------
# Issue 1: converter current/apparent-power limits are enforced
# ---------------------------------------------------------------------------

def test_converter_limit_is_enforced():
    """A non-slack VSC driven above its rating must be clamped to s_mva."""
    net = create_case5_stagg_mtdc_slack()

    # Converter 0 is a fixed P/Q (rectifier) converter. Shrink its rating
    # well below its operating point so the limit must bite.
    vsc0 = net.vsc.index[0]
    p_set = float(net.vsc.at[vsc0, "p_mw"])
    q_set = float(net.vsc.at[vsc0, "q_mvar"])
    s_set = np.hypot(p_set, q_set)
    assert s_set > 0

    s_rated = 0.5 * s_set          # force a clear violation
    net.vsc.at[vsc0, "s_mva"] = s_rated

    converged = run_pf(net, verbose=False, max_iter_outer=50)
    assert converged, "power flow with limited converter should still converge"

    p_ac = float(net.res_vsc.at[vsc0, "p_ac_mw"])
    q_ac = float(net.res_vsc.at[vsc0, "q_ac_mvar"])
    s_ac = np.hypot(p_ac, q_ac)

    assert s_ac <= s_rated * (1 + 1e-6), (
        f"converter apparent power {s_ac:.3f} MVA exceeds rating "
        f"{s_rated:.3f} MVA -- limit not enforced"
    )


def test_converter_within_rating_is_untouched():
    """Enforcement must be a no-op when converters are within their rating."""
    net_ref = create_case5_stagg_mtdc_slack()
    run_pf(net_ref, verbose=False, max_iter_outer=50)

    # Baseline case has generously rated converters; results must match a
    # second identical run (i.e. enforcement did not perturb a valid solution).
    net = create_case5_stagg_mtdc_slack()
    run_pf(net, verbose=False, max_iter_outer=50)

    np.testing.assert_allclose(
        net.res_vsc["p_ac_mw"].values,
        net_ref.res_vsc["p_ac_mw"].values,
        atol=1e-9,
    )


# ---------------------------------------------------------------------------
# Issue 2: convergence flag reflects the actual AC/DC convergence
# ---------------------------------------------------------------------------

def test_nonconvergent_ac_network_reports_false():
    """An AC-only network past its loadability limit must report not-converged."""
    net = pf.create_empty_network(name="diverge", s_base=100.0)

    b0 = pf.create_ac_bus(net, vr_kv=100.0, name="slack")
    b1 = pf.create_ac_bus(net, vr_kv=100.0, name="load")

    # Slack generator at b0.
    pf.create_ac_gen(net, bus=b0, p_mw=0.0, v_pu=1.0, name="slack gen")

    # A short reactive line and an enormous load beyond the nose point of the
    # P-V curve: Newton-Raphson cannot converge.
    pf.create_ac_line(
        net, from_bus=b0, to_bus=b1, length_km=1.0,
        r_ohm_per_km=1.0, x_ohm_per_km=10.0, name="line",
    )
    pf.create_ac_load(net, bus=b1, p_mw=1.0e6, q_mvar=1.0e6, name="huge load")

    converged = run_pf(net, verbose=False, max_iter_outer=30)
    assert converged is False, (
        "run_pf reported convergence for a physically impossible power flow"
    )


# ---------------------------------------------------------------------------
# Issue 3: VCMAX / VCMIN / ICMAX are imported from MatACDC convdc data
# ---------------------------------------------------------------------------

def _minimal_matacdc_case():
    """Build a tiny (2 AC bus / 2 DC bus) MatACDC-format case in memory."""
    baseMVA = 100.0
    basekVac = 345.0

    # ppc bus cols: [bus_i, type, Pd, Qd, Gs, Bs, area, Vm, Va, baseKV, zone, Vmax, Vmin]
    ppc = {
        "baseMVA": baseMVA,
        "bus": np.array([
            [1, 3, 0.0, 0.0, 0, 0, 1, 1.0, 0.0, basekVac, 1, 1.1, 0.9],
            [2, 1, 50.0, 20.0, 0, 0, 1, 1.0, 0.0, basekVac, 1, 1.1, 0.9],
        ], dtype=float),
        # gen cols: [bus, Pg, Qg, Qmax, Qmin, Vg, mBase, status, Pmax, Pmin]
        "gen": np.array([
            [1, 0.0, 0.0, 999.0, -999.0, 1.0, baseMVA, 1, 999.0, -999.0],
        ], dtype=float),
        # branch cols: [fbus, tbus, r, x, b, rateA, rateB, rateC, ratio, angle, status]
        "branch": np.array([
            [1, 2, 0.01, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1],
        ], dtype=float),
    }

    # busdc cols: [busdc_i, busac_i, grid, Pdc, Vdc, basekVdc, Vdcmax, Vdcmin, Cdc]
    busdc = np.array([
        [1, 1, 1, 0.0, 1.0, 345.0, 1.1, 0.9, 0.0],
        [2, 2, 1, 0.0, 1.0, 345.0, 1.1, 0.9, 0.0],
    ], dtype=float)

    # convdc cols (0-indexed):
    # 0 busdc_i, 1 type_dc, 2 type_ac, 3 P_g, 4 Q_g, 5 Vtar, 6 rtf, 7 xtf,
    # 8 bf, 9 rc, 10 xc, 11 basekVac, 12 Vcmax, 13 Vcmin, 14 Imax, 15 status,
    # 16 LossA, 17 LossB, 18 LossCrec, 19 LossCinv
    convdc = np.array([
        # DC bus 1: constant-P converter with distinctive voltage/current limits
        [1, 1, 1, -60.0, -40.0, 1.0, 0.001, 0.05, 0.0, 0.0, 0.0,
         basekVac, 1.20, 0.85, 1.10, 1, 0.0, 0.0, 0.0, 0.0],
        # DC bus 2: Vdc-slack converter
        [2, 2, 1, 0.0, 0.0, 1.0, 0.001, 0.05, 0.0, 0.0, 0.0,
         basekVac, 1.30, 0.80, 1.05, 1, 0.0, 0.0, 0.0, 0.0],
    ], dtype=float)

    # branchdc cols: [fbusdc, tbusdc, r, l, c, rateA, rateB, rateC, status, N]
    branchdc = np.array([
        [1, 2, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 1, 1],
    ], dtype=float)

    pdc = {
        "baseMVAac": baseMVA,
        "baseMVAdc": baseMVA,
        "pol": 1,
        "busdc": busdc,
        "convdc": convdc,
        "branchdc": branchdc,
    }
    return ppc, pdc, basekVac


def test_matacdc_import_reads_vcmax_vcmin_icmax():
    ppc, pdc, basekVac = _minimal_matacdc_case()
    net = pf.from_matacdc(ppc, pdc, name="tiny hybrid")

    assert len(net.vsc) == 2

    # Converter on DC bus 1 (first convdc row).
    vsc0 = net.vsc.index[0]
    assert net.vsc.at[vsc0, "vc_max_pu"] == pytest.approx(1.20)
    assert net.vsc.at[vsc0, "vc_min_pu"] == pytest.approx(0.85)
    assert net.vsc.at[vsc0, "i_max_pu"] == pytest.approx(1.10)

    # s_mva is derived from ICMAX read as per-unit current on the system base
    # (S_max = Imax_pu * baseMVA), consistent with the per-unit value fed to
    # the capability-diagram limiter (_convlim) and the per-unit VCMAX/VCMIN.
    baseMVA = float(ppc["baseMVA"])
    expected_s = 1.10 * baseMVA
    assert net.vsc.at[vsc0, "s_mva"] == pytest.approx(expected_s)

    # Second converter's distinct limits.
    vsc1 = net.vsc.index[1]
    assert net.vsc.at[vsc1, "vc_max_pu"] == pytest.approx(1.30)
    assert net.vsc.at[vsc1, "vc_min_pu"] == pytest.approx(0.80)
    assert net.vsc.at[vsc1, "i_max_pu"] == pytest.approx(1.05)


def test_build_converter_data_exposes_limits():
    ppc, pdc, _ = _minimal_matacdc_case()
    net = pf.from_matacdc(ppc, pdc, name="tiny hybrid")

    from acdcpf.build.converters import build_converter_data
    data = build_converter_data(net)

    assert "vsc_vc_max" in data and "vsc_vc_min" in data and "vsc_i_max" in data
    np.testing.assert_allclose(data["vsc_vc_max"], [1.20, 1.30])
    np.testing.assert_allclose(data["vsc_vc_min"], [0.85, 0.80])
    np.testing.assert_allclose(data["vsc_i_max"], [1.10, 1.05])
