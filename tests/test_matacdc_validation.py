"""
Validation tests comparing acdcpf results against MatACDC reference values.

Each test case runs the AC/DC power flow and compares numerical results
(voltages, power flows, converter variables) against MatACDC MATLAB output
stored in tests/matacdc_reference_data/*.json.

Sign conventions:
- acdcpf uses load convention for VSC: P_s > 0 = rectifier (AC->DC)
- MatACDC uses generator convention: P_s > 0 = inverter (DC->AC)
- AC bus voltages, line flows, DC voltages, DC line flows use the same
  convention in both implementations.

Reference:
- J. Beerten, S. Cole, R. Belmans, "Generalized Steady-State VSC MTDC Model
  for Sequential AC/DC Power Flow Algorithms", IEEE Trans. Power Syst., 2012.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from acdcpf.networks import (
    create_case5_stagg_hvdc_ptp,
    create_case5_stagg_mtdc_slack,
    create_case5_stagg_mtdc_droop,
    create_case24_ieee_rts_mtdc,
)
from acdcpf.powerflow import run_pf

REFERENCE_DIR = Path(__file__).parent / "matacdc_reference_data"

# Default tolerances
VM_ATOL = 1e-4       # AC voltage magnitude (pu)
VA_ATOL = 1e-2       # AC voltage angle (degrees)
VDC_ATOL = 1e-4      # DC voltage (pu)
P_AC_ATOL = 0.1      # AC line active power (MW)
Q_AC_ATOL = 0.1      # AC line reactive power (MVAr)
P_DC_ATOL = 0.1      # DC line active power (MW)
VSC_P_ATOL = 0.1     # VSC active power (MW)
VSC_Q_ATOL = 0.1     # VSC reactive power (MVAr)

# Per-case relaxed tolerances (solver/rounding differences)
CASE_TOLERANCES = {
    "case24_ieee_rts_mtdc": {
        "VA_ATOL": 0.03,
        "P_AC_ATOL": 0.3,
        "VSC_P_ATOL": 0.3,
    },
    "case5_stagg_mtdc_droop": {
        "VSC_P_ATOL": 0.15,
    },
}


def _tol(case_name: str, key: str, default: float) -> float:
    """Per-case tolerance; fallback to default."""
    return CASE_TOLERANCES.get(case_name, {}).get(key, default)


def _load_reference(case_name: str) -> dict:
    json_file = REFERENCE_DIR / f"{case_name}.json"
    with open(json_file, "r") as f:
        return json.load(f)


def _as_array(val):
    """Ensure value is a numpy array (handles scalar JSON fields)."""
    return np.atleast_1d(np.asarray(val, dtype=float))


# ---------------------------------------------------------------------------
# Fixtures: run power flow once per case (module scope)
# ---------------------------------------------------------------------------

CASES = [
    ("case5_stagg_hvdc_ptp", create_case5_stagg_hvdc_ptp),
    ("case5_stagg_mtdc_slack", create_case5_stagg_mtdc_slack),
    ("case5_stagg_mtdc_droop", create_case5_stagg_mtdc_droop),
    ("case24_ieee_rts_mtdc", create_case24_ieee_rts_mtdc),
]


@pytest.fixture(params=CASES, ids=[c[0] for c in CASES], scope="module")
def solved_case(request):
    """Run power flow and return (case_name, network, reference_data)."""
    case_name, create_func = request.param
    net = create_func()
    converged = run_pf(net, verbose=False, max_iter_outer=50)
    assert converged, f"{case_name} did not converge"
    ref = _load_reference(case_name)
    return case_name, net, ref


# ---------------------------------------------------------------------------
# AC Bus Voltages
# ---------------------------------------------------------------------------

class TestACBusVoltages:

    def test_voltage_magnitude(self, solved_case):
        case_name, net, ref = solved_case
        expected = np.array(ref["ac_bus"]["vm_pu"])
        actual = net.res_ac_bus["v_pu"].values
        np.testing.assert_allclose(
            actual, expected, atol=VM_ATOL,
            err_msg=f"{case_name}: AC voltage magnitude mismatch",
        )

    def test_voltage_angle(self, solved_case):
        case_name, net, ref = solved_case
        expected = np.array(ref["ac_bus"]["va_deg"])
        actual = net.res_ac_bus["v_angle_deg"].values
        np.testing.assert_allclose(
            actual, expected, atol=_tol(case_name, "VA_ATOL", VA_ATOL),
            err_msg=f"{case_name}: AC voltage angle mismatch",
        )


# ---------------------------------------------------------------------------
# DC Bus Voltages
# ---------------------------------------------------------------------------

class TestDCBusVoltages:

    def test_dc_voltage(self, solved_case):
        case_name, net, ref = solved_case
        expected = np.array(ref["dc_bus"]["vdc_pu"])
        actual = net.res_dc_bus["v_dc_pu"].values
        np.testing.assert_allclose(
            actual, expected, atol=_tol(case_name, "VDC_ATOL", VDC_ATOL),
            err_msg=f"{case_name}: DC voltage mismatch",
        )


# ---------------------------------------------------------------------------
# AC Line Flows
# ---------------------------------------------------------------------------

class TestACLineFlows:

    def test_p_from(self, solved_case):
        case_name, net, ref = solved_case
        expected = np.array(ref["ac_branch"]["pf_mw"])
        actual = net.res_ac_line["p_from_mw"].values
        np.testing.assert_allclose(
            actual, expected, atol=_tol(case_name, "P_AC_ATOL", P_AC_ATOL),
            err_msg=f"{case_name}: AC line P_from mismatch",
        )

    def test_q_from(self, solved_case):
        case_name, net, ref = solved_case
        expected = np.array(ref["ac_branch"]["qf_mvar"])
        actual = net.res_ac_line["q_from_mvar"].values
        np.testing.assert_allclose(
            actual, expected, atol=Q_AC_ATOL,
            err_msg=f"{case_name}: AC line Q_from mismatch",
        )

    def test_p_to(self, solved_case):
        case_name, net, ref = solved_case
        expected = np.array(ref["ac_branch"]["pt_mw"])
        actual = net.res_ac_line["p_to_mw"].values
        np.testing.assert_allclose(
            actual, expected, atol=_tol(case_name, "P_AC_ATOL", P_AC_ATOL),
            err_msg=f"{case_name}: AC line P_to mismatch",
        )

    def test_q_to(self, solved_case):
        case_name, net, ref = solved_case
        expected = np.array(ref["ac_branch"]["qt_mvar"])
        actual = net.res_ac_line["q_to_mvar"].values
        np.testing.assert_allclose(
            actual, expected, atol=Q_AC_ATOL,
            err_msg=f"{case_name}: AC line Q_to mismatch",
        )


# ---------------------------------------------------------------------------
# DC Line Flows
# ---------------------------------------------------------------------------

class TestDCLineFlows:

    def test_p_from(self, solved_case):
        case_name, net, ref = solved_case
        expected = _as_array(ref["dc_branch"]["pf_mw"])
        actual = net.res_dc_line["p_from_mw"].values
        np.testing.assert_allclose(
            actual, expected, atol=_tol(case_name, "P_DC_ATOL", P_DC_ATOL),
            err_msg=f"{case_name}: DC line P_from mismatch",
        )

    def test_p_to(self, solved_case):
        case_name, net, ref = solved_case
        expected = _as_array(ref["dc_branch"]["pt_mw"])
        actual = net.res_dc_line["p_to_mw"].values
        np.testing.assert_allclose(
            actual, expected, atol=_tol(case_name, "P_DC_ATOL", P_DC_ATOL),
            err_msg=f"{case_name}: DC line P_to mismatch",
        )


# ---------------------------------------------------------------------------
# VSC Converter Variables
# ---------------------------------------------------------------------------

class TestVSCVariables:
    """Compare VSC converter operating points.

    acdcpf uses load convention (P_s > 0 = rectifier), while MatACDC
    uses generator convention (P_s > 0 = inverter). The comparison
    negates the MatACDC reference to match acdcpf's convention.
    """

    def test_p_ac(self, solved_case):
        case_name, net, ref = solved_case
        expected = -np.array(ref["converter"]["ps_mw"])
        actual = net.res_vsc["p_ac_mw"].values
        np.testing.assert_allclose(
            actual, expected, atol=_tol(case_name, "VSC_P_ATOL", VSC_P_ATOL),
            err_msg=f"{case_name}: VSC P_ac mismatch",
        )

    def test_q_ac(self, solved_case):
        case_name, net, ref = solved_case
        expected = -np.array(ref["converter"]["qs_mvar"])
        actual = net.res_vsc["q_ac_mvar"].values
        np.testing.assert_allclose(
            actual, expected, atol=_tol(case_name, "VSC_Q_ATOL", VSC_Q_ATOL),
            err_msg=f"{case_name}: VSC Q_ac mismatch",
        )

    def test_p_dc(self, solved_case):
        case_name, net, ref = solved_case
        expected = -np.array(ref["dc_bus"]["pdc_mw"])
        actual = net.res_vsc["p_dc_mw"].values
        np.testing.assert_allclose(
            actual, expected, atol=_tol(case_name, "VSC_P_ATOL", VSC_P_ATOL),
            err_msg=f"{case_name}: VSC P_dc mismatch",
        )
