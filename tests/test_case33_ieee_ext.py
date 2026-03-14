"""
Validation tests for the IEEE 33-bus extended system with DC elements.

Compares acdcpf results against reference values from
'33-bus with DC elements.xlsx'.

Reference sign convention (Excel/PowerFactory):
    P > 0 = inverter (DC->AC), P < 0 = rectifier (AC->DC)
Python (acdcpf) sign convention:
    P_s > 0 = rectifier (AC->DC), P_s < 0 = inverter (DC->AC)
"""

import os
import pytest
import numpy as np
import pandas as pd

from acdcpf.networks import create_case33_ieee_ext
from acdcpf.powerflow import run_pf


# ── Reference data from '33-bus with DC elements.xlsx' ──────────────

# AC bus numbers in order of internal index
AC_BUS_NUMS = [1, 2, 3, 4, 5, 6, 7, 12, 13, 14, 15, 19, 20, 23, 24, 25, 29, 30, 31, 32, 33]

# DC bus numbers in order of internal index
DC_BUS_NUMS = [8, 9, 10, 11, 16, 17, 18, 21, 22, 26, 27, 28, 34, 35, 36]

# DC-DC connected buses (excluded from strict DC voltage check)
DCDC_BUSES = {34, 35, 36}


# Reference AC bus results: {bus_num: (vm_pu, va_degree)}
REF_AC_BUS = {
    1:  (1.050, 0.000),
    2:  (1.047, -0.027),
    3:  (1.038, -0.139),
    4:  (1.034, -0.531),
    5:  (1.030, -0.934),
    6:  (1.000, -0.669),
    7:  (1.030, -1.487),
    12: (0.998, 2.715),
    13: (0.997, 2.663),
    14: (0.997, 2.643),
    15: (0.998, 2.659),
    19: (1.045, -0.077),
    20: (1.029, -0.458),
    23: (1.036, 0.253),
    24: (1.030, 1.068),
    25: (1.024, 1.734),
    29: (1.020, 2.156),
    30: (1.016, 2.369),
    31: (1.005, 2.714),
    32: (1.003, 2.848),
    33: (1.000, 3.020),
}

# Reference DC bus results: {bus_num: vm_pu}
REF_DC_BUS = {
    8: 1.020, 9: 1.016, 10: 1.013, 11: 1.012,
    16: 1.004, 17: 1.002, 18: 1.000,
    21: 1.016, 22: 1.013,
    26: 1.000, 27: 0.999, 28: 0.994,
    34: 1.060, 35: 1.062, 36: 1.093,
}

# Reference VSC results: [(name, p_mw, q_mvar)] in Excel convention
# (inverter-positive for P, generator-positive for Q)
REF_VSC = [
    ("VSC DC8-AC7",   -1.067, 8.527),    # Vdc slack + Vac
    ("VSC DC26-AC6",  -1.359, -11.506),   # Vdc slack + Vac
    ("VSC DC18-AC33",  0.482, -0.883),    # Vdc slack + Vac
    ("VSC DC11-AC12",  0.250, 0.075),     # PQ
    ("VSC DC28-AC29",  0.760, 0.250),     # PQ
    ("VSC DC16-AC15",  0.280, 0.092),     # PQ
    ("VSC DC21-AC20", -1.200, -0.400),    # PQ
]

# Reference AC branch results: [(from, to, p_from, q_from, p_to, q_to, p_loss, q_loss)]
REF_AC_BRANCH = [
    (1, 2, 4.440, 1.359, -4.428, -1.353, 0.012, 0.006),
    (2, 3, 2.647, 0.654, -2.626, -0.643, 0.021, 0.011),
    (3, 4, 2.927, -1.726, -2.902, 1.739, 0.025, 0.013),
    (4, 5, 2.662, -1.799, -2.640, 1.810, 0.022, 0.011),
    (5, 6, 3.010, 3.532, -2.906, -3.443, 0.104, 0.089),
    (6, 7, 1.347, -8.163, -1.267, 8.427, 0.080, 0.264),
    (12, 13, 0.130, 0.005, -0.130, -0.005, 0.000, 0.000),
    (13, 14, 0.070, -0.015, -0.070, 0.015, 0.000, 0.000),
    (14, 15, -0.330, -0.215, 0.331, 0.216, 0.001, 0.001),
    (2, 19, 1.582, 0.580, -1.579, -0.577, 0.003, 0.003),
    (19, 20, 1.399, 0.497, -1.380, -0.480, 0.019, 0.017),
    (3, 23, -0.481, 2.290, 0.495, -2.280, 0.014, 0.010),
    (23, 24, -0.675, 2.180, 0.702, -2.158, 0.027, 0.022),
    (24, 25, -0.322, 1.943, 0.343, -1.927, 0.021, 0.016),
    (25, 29, -0.643, 1.827, 0.654, -1.816, 0.011, 0.011),
    (29, 30, 0.516, 1.481, -0.509, -1.478, 0.007, 0.003),
    (30, 31, 0.409, 1.418, -0.396, -1.405, 0.013, 0.013),
    (31, 32, -0.087, 1.119, 0.089, -1.117, 0.002, 0.002),
    (31, 15, 0.313, 0.236, -0.311, -0.234, 0.002, 0.002),
    (32, 33, -0.239, 1.047, 0.242, -1.043, 0.003, 0.004),
]

# Reference DC branch results: [(from, to, p_from, p_to, p_loss)]
REF_DC_BRANCH = [
    (8, 9, 0.820, -0.817, 0.003),
    (9, 10, 0.697, -0.695, 0.002),
    (10, 11, 0.670, -0.670, 0.000),
    (16, 17, 0.405, -0.404, 0.001),
    (17, 18, 0.528, -0.527, 0.001),
    (21, 22, 0.900, -0.897, 0.003),
    (26, 27, 1.086, -1.084, 0.002),
    (27, 28, 0.884, -0.880, 0.004),
    (16, 22, -0.895, 0.903, 0.008),
]


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def solved_network():
    """Create and solve the IEEE 33-bus extended network."""
    net = create_case33_ieee_ext()
    converged = run_pf(net, verbose=False, max_iter_outer=50)
    assert converged, "Power flow must converge"
    return net


# ── AC bus voltage tests ─────────────────────────────────────────────

class TestACBusVoltages:
    """Compare AC bus voltage magnitudes against reference."""

    def test_ac_voltage_magnitudes(self, solved_network):
        """AC voltage magnitudes should match within 0.001 pu.

        Larger tolerance accounts for DC-DC model differences that
        affect slack VSC power and propagate to the AC side.
        """
        net = solved_network
        max_diff = 0.0
        for i, bnum in enumerate(AC_BUS_NUMS):
            ref_vm = REF_AC_BUS[bnum][0]
            got_vm = net.res_ac_bus.loc[i, "v_pu"]
            diff = abs(got_vm - ref_vm)
            max_diff = max(max_diff, diff)

        assert max_diff < 0.001, (
            f"AC voltage magnitude max diff = {max_diff:.4f} pu"
        )

# DC bus voltage tests

class TestDCBusVoltages:
    """Compare DC bus voltages against reference."""

    def test_dc_voltage_original_buses(self, solved_network):
        """Original 12 DC bus voltages should match within 0.002 pu."""
        net = solved_network
        max_diff = 0.0
        for i, bnum in enumerate(DC_BUS_NUMS):
            if bnum in DCDC_BUSES:
                continue
            ref_v = REF_DC_BUS[bnum]
            got_v = net.res_dc_bus.loc[i, "v_dc_pu"]
            diff = abs(got_v - ref_v)
            max_diff = max(max_diff, diff)

        assert max_diff < 0.002, (
            f"DC voltage max diff (excl. DCDC buses) = {max_diff:.4f} pu"
        )

    def test_dc_voltage_dcdc_buses(self, solved_network):
        """DC-DC connected bus voltages (34,35,36) should match within 0.003 pu."""
        net = solved_network
        max_diff = 0.0
        for i, bnum in enumerate(DC_BUS_NUMS):
            if bnum not in DCDC_BUSES:
                continue
            ref_v = REF_DC_BUS[bnum]
            got_v = net.res_dc_bus.loc[i, "v_dc_pu"]
            diff = abs(got_v - ref_v)
            max_diff = max(max_diff, diff)

        assert max_diff < 0.003, (
            f"DC voltage max diff (DCDC buses) = {max_diff:.4f} pu"
        )

    def test_dc_slack_buses(self, solved_network):
        """Vdc slack buses must hold their setpoints."""
        net = solved_network
        slack_setpoints = {8: 1.02, 18: 1.0, 26: 1.0}
        for bnum, v_set in slack_setpoints.items():
            idx = DC_BUS_NUMS.index(bnum)
            got_v = net.res_dc_bus.loc[idx, "v_dc_pu"]
            assert abs(got_v - v_set) < 1e-6, (
                f"DC Bus {bnum}: Vdc={got_v:.6f}, expected {v_set}"
            )

    def test_dc_voltages_in_bounds(self, solved_network):
        """All DC voltages should be within [0.90, 1.15]."""
        v_dc = solved_network.res_dc_bus["v_dc_pu"].values
        assert np.all(v_dc >= 0.90), f"Min DC voltage: {v_dc.min():.4f}"
        assert np.all(v_dc <= 1.15), f"Max DC voltage: {v_dc.max():.4f}"


# ── VSC converter tests ──────────────────────────────────────────────

class TestVSCResults:
    """Compare VSC converter results against reference."""

    def test_pq_converters_match_setpoints(self, solved_network):
        """P-Q controlled converters must match their setpoints exactly.

        PQ converters (indices 3-6) have fixed P and Q.
        Python convention: P > 0 = rectifier (opposite to Excel).
        """
        net = solved_network
        # PQ VSCs: indices 3,4,5,6 in our ordering
        pq_indices = [3, 4, 5, 6]
        for i in pq_indices:
            ref_name, ref_p, ref_q = REF_VSC[i]
            # Convert reference (inverter-positive) to Python (rectifier-positive)
            expected_p = -ref_p
            expected_q = -ref_q
            got_p = net.res_vsc.loc[i, "p_ac_mw"]
            got_q = net.res_vsc.loc[i, "q_ac_mvar"]
            assert abs(got_p - expected_p) < 1e-6, (
                f"{ref_name}: P={got_p:.4f}, expected {expected_p:.4f}"
            )
            assert abs(got_q - expected_q) < 1e-6, (
                f"{ref_name}: Q={got_q:.4f}, expected {expected_q:.4f}"
            )

    def test_slack_vsc_power_direction(self, solved_network):
        """Slack VSCs should transfer power in the expected direction."""
        net = solved_network
        # vsc_1 (DC8-AC7): reference P=-1.067 (rectifier in Excel convention)
        # -> Python P should be positive (rectifier)
        p_vsc1 = net.res_vsc.loc[0, "p_ac_mw"]
        assert p_vsc1 > 0, f"VSC1 should be rectifying, got P={p_vsc1:.3f}"

        # vsc_2 (DC26-AC6): reference P=-1.359 (rectifier)
        p_vsc2 = net.res_vsc.loc[1, "p_ac_mw"]
        assert p_vsc2 > 0, f"VSC2 should be rectifying, got P={p_vsc2:.3f}"


# ── DC branch flow tests ─────────────────────────────────────────────

class TestDCBranchFlows:
    """Compare DC branch flows against reference."""

    def test_dc_branch_flow_directions(self, solved_network):
        """DC branch power should flow in the correct direction."""
        net = solved_network
        for i, (fb, tb, ref_pf, ref_pt, ref_pl) in enumerate(REF_DC_BRANCH):
            got_pf = net.res_dc_line.loc[i, "p_from_mw"]
            # Power direction should match (same sign)
            if ref_pf != 0:
                assert np.sign(got_pf) == np.sign(ref_pf), (
                    f"DC Line {fb}-{tb}: flow direction mismatch "
                    f"(ref={ref_pf:.3f}, got={got_pf:.3f})"
                )

    def test_dc_branch_losses_nonnegative(self, solved_network):
        """DC branch losses should be non-negative."""
        net = solved_network
        for i in range(len(net.res_dc_line)):
            p_loss = net.res_dc_line.loc[i, "p_loss_mw"]
            assert p_loss >= -1e-6, f"DC line {i}: negative loss {p_loss:.6f}"


# ── Comprehensive comparison (informational) ─────────────────────────

class TestFullComparison:
    """
    Full comparison with reference."""

    def test_all_ac_voltages_close(self, solved_network):
        """All AC bus voltages within tolerance of reference."""
        net = solved_network
        diffs = []
        for i, bnum in enumerate(AC_BUS_NUMS):
            ref_vm = REF_AC_BUS[bnum][0]
            got_vm = net.res_ac_bus.loc[i, "v_pu"]
            diffs.append(abs(got_vm - ref_vm))
        max_diff = max(diffs)
        mean_diff = sum(diffs) / len(diffs)
        assert max_diff < 0.001, f"Max AC voltage diff: {max_diff:.4f}"
        assert mean_diff < 0.001, f"Mean AC voltage diff: {mean_diff:.4f}"

    def test_dc_branch_magnitudes(self, solved_network):
        """
        DC branch power magnitudes within 0.001 of reference.
        """
        net = solved_network
        for i, (fb, tb, ref_pf, ref_pt, ref_pl) in enumerate(REF_DC_BRANCH):
            got_pf = net.res_dc_line.loc[i, "p_from_mw"]
            if abs(ref_pf) > 0.01:
                rel_err = abs(got_pf - ref_pf) / abs(ref_pf)
                assert rel_err < 0.001, (
                    f"DC Line {fb}-{tb}: p_from ref={ref_pf:.3f}, "
                    f"got={got_pf:.3f}, rel_err={rel_err:.1%}"
                )


# Excel report generation

class TestExcelReport:
    """
    Generate an Excel comparison report (PowerFactory vs acdcpf).
    """

    def test_generate_comparison_excel(self, solved_network):
        """Generate comparison_report.xlsx with side-by-side results."""
        net = solved_network
        output_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "comparison_report.xlsx",
        )

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            _write_ac_bus_sheet(writer, net)
            _write_dc_bus_sheet(writer, net)
            _write_vsc_sheet(writer, net)
            _write_ac_branch_sheet(writer, net)
            _write_dc_branch_sheet(writer, net)
            _write_summary_sheet(writer, net)

        assert os.path.exists(output_path)


# Sheet builders (module-level helpers)

def _write_ac_bus_sheet(writer, net):
    """AC Bus Voltages: PowerFactory vs acdcpf."""
    rows = []
    for i, bnum in enumerate(AC_BUS_NUMS):
        ref_vm, ref_va = REF_AC_BUS[bnum]
        got_vm = net.res_ac_bus.loc[i, "v_pu"]
        got_va = net.res_ac_bus.loc[i, "v_angle_deg"]
        rows.append({
            "Bus": bnum,
            "Vm PF [pu]": ref_vm,
            "Vm acdcpf [pu]": round(got_vm, 4),
            "Vm Diff [pu]": round(got_vm - ref_vm, 4),
            "Va PF [deg]": ref_va,
            "Va acdcpf [deg]": round(got_va, 3),
            "Va Diff [deg]": round(got_va - ref_va, 3),
        })
    df = pd.DataFrame(rows)
    df.to_excel(writer, sheet_name="AC Bus Voltages", index=False)


def _write_dc_bus_sheet(writer, net):
    """DC Bus Voltages: PowerFactory vs acdcpf."""
    rows = []
    for i, bnum in enumerate(DC_BUS_NUMS):
        ref_v = REF_DC_BUS[bnum]
        got_v = net.res_dc_bus.loc[i, "v_dc_pu"]
        rows.append({
            "DC Bus": bnum,
            "Vdc PF [pu]": ref_v,
            "Vdc acdcpf [pu]": round(got_v, 4),
            "Vdc Diff [pu]": round(got_v - ref_v, 4),
        })
    df = pd.DataFrame(rows)
    df.to_excel(writer, sheet_name="DC Bus Voltages", index=False)


def _write_vsc_sheet(writer, net):
    """VSC Converter Results: PowerFactory vs acdcpf.

    P reported in PowerFactory convention (P > 0 = inverter, DC->AC).
    Q reported in load convention (Q > 0 = absorbing reactive power).

    For P: negate Python values (rectifier-positive -> inverter-positive).
    For Q: solver uses load convention matching PowerFactory; PQ converter
    Q was negated at setup so negate back; slack Q is already correct.
    """
    rows = []
    for i, (name, ref_p, ref_q) in enumerate(REF_VSC):
        mode = net.vsc.loc[i, "control_mode"]
        # P: always negate (Python rectifier+ -> PF inverter+)
        got_p = -net.res_vsc.loc[i, "p_ac_mw"]
        # Q: for PQ converters, Q was negated at network setup so negate
        # back; for slack/vdc converters, solver Q is already in PF sign
        if mode == "p_q":
            got_q = -net.res_vsc.loc[i, "q_ac_mvar"]
        else:
            got_q = net.res_vsc.loc[i, "q_ac_mvar"]
        rows.append({
            "Converter": name,
            "Control": mode,
            "P PF [MW]": ref_p,
            "P acdcpf [MW]": round(got_p, 3),
            "P Diff [MW]": round(got_p - ref_p, 3),
            "Q PF [MVAr]": ref_q,
            "Q acdcpf [MVAr]": round(got_q, 3),
            "Q Diff [MVAr]": round(got_q - ref_q, 3),
        })
    df = pd.DataFrame(rows)
    df.to_excel(writer, sheet_name="VSC Converters", index=False)


def _write_ac_branch_sheet(writer, net):
    """AC Branch Flows: PowerFactory vs acdcpf."""
    rows = []
    for i, (fb, tb, ref_pf, ref_qf, ref_pt, ref_qt, ref_pl, ref_ql) in enumerate(REF_AC_BRANCH):
        got_pf = net.res_ac_line.loc[i, "p_from_mw"]
        got_qf = net.res_ac_line.loc[i, "q_from_mvar"]
        got_pt = net.res_ac_line.loc[i, "p_to_mw"]
        got_qt = net.res_ac_line.loc[i, "q_to_mvar"]
        got_pl = net.res_ac_line.loc[i, "p_loss_mw"]
        got_ql = net.res_ac_line.loc[i, "q_loss_mvar"]
        rows.append({
            "From": fb,
            "To": tb,
            "Pf PF [MW]": ref_pf,
            "Pf acdcpf [MW]": round(got_pf, 3),
            "Pf Diff [MW]": round(got_pf - ref_pf, 3),
            "Qf PF [MVAr]": ref_qf,
            "Qf acdcpf [MVAr]": round(got_qf, 3),
            "Qf Diff [MVAr]": round(got_qf - ref_qf, 3),
            "Pt PF [MW]": ref_pt,
            "Pt acdcpf [MW]": round(got_pt, 3),
            "Pt Diff [MW]": round(got_pt - ref_pt, 3),
            "Qt PF [MVAr]": ref_qt,
            "Qt acdcpf [MVAr]": round(got_qt, 3),
            "Qt Diff [MVAr]": round(got_qt - ref_qt, 3),
            "Ploss PF [MW]": ref_pl,
            "Ploss acdcpf [MW]": round(got_pl, 3),
            "Ploss Diff [MW]": round(got_pl - ref_pl, 3),
            "Qloss PF [MVAr]": ref_ql,
            "Qloss acdcpf [MVAr]": round(got_ql, 3),
            "Qloss Diff [MVAr]": round(got_ql - ref_ql, 3),
        })
    df = pd.DataFrame(rows)
    df.to_excel(writer, sheet_name="AC Branches", index=False)


def _write_dc_branch_sheet(writer, net):
    """DC Branch Flows: PowerFactory vs acdcpf."""
    rows = []
    for i, (fb, tb, ref_pf, ref_pt, ref_pl) in enumerate(REF_DC_BRANCH):
        got_pf = net.res_dc_line.loc[i, "p_from_mw"]
        got_pt = net.res_dc_line.loc[i, "p_to_mw"]
        got_pl = net.res_dc_line.loc[i, "p_loss_mw"]
        rows.append({
            "From": fb,
            "To": tb,
            "Pf PF [MW]": ref_pf,
            "Pf acdcpf [MW]": round(got_pf, 3),
            "Pf Diff [MW]": round(got_pf - ref_pf, 3),
            "Pt PF [MW]": ref_pt,
            "Pt acdcpf [MW]": round(got_pt, 3),
            "Pt Diff [MW]": round(got_pt - ref_pt, 3),
            "Ploss PF [MW]": ref_pl,
            "Ploss acdcpf [MW]": round(got_pl, 3),
            "Ploss Diff [MW]": round(got_pl - ref_pl, 3),
        })
    df = pd.DataFrame(rows)
    df.to_excel(writer, sheet_name="DC Branches", index=False)


def _write_summary_sheet(writer, net):
    """Summary statistics of the comparison."""
    # AC voltage magnitude stats
    ac_vm_diffs = []
    for i, bnum in enumerate(AC_BUS_NUMS):
        ref_vm = REF_AC_BUS[bnum][0]
        got_vm = net.res_ac_bus.loc[i, "v_pu"]
        ac_vm_diffs.append(abs(got_vm - ref_vm))

    # DC voltage stats (all buses)
    dc_v_diffs_all = []
    dc_v_diffs_grid = []
    dc_v_diffs_dcdc = []
    for i, bnum in enumerate(DC_BUS_NUMS):
        ref_v = REF_DC_BUS[bnum]
        got_v = net.res_dc_bus.loc[i, "v_dc_pu"]
        d = abs(got_v - ref_v)
        dc_v_diffs_all.append(d)
        if bnum in DCDC_BUSES:
            dc_v_diffs_dcdc.append(d)
        else:
            dc_v_diffs_grid.append(d)

    # VSC P differences (slack converters only, indices 0-2)
    vsc_p_diffs = []
    for i in range(3):
        ref_p = REF_VSC[i][1]
        got_p = -net.res_vsc.loc[i, "p_ac_mw"]
        vsc_p_diffs.append(abs(got_p - ref_p))

    # DC branch P_from differences
    dc_br_diffs = []
    for i, (fb, tb, ref_pf, ref_pt, ref_pl) in enumerate(REF_DC_BRANCH):
        got_pf = net.res_dc_line.loc[i, "p_from_mw"]
        dc_br_diffs.append(abs(got_pf - ref_pf))

    rows = [
        {"Metric": "AC Bus Vm",
         "Max Abs Diff": round(max(ac_vm_diffs), 4),
         "Mean Abs Diff": round(np.mean(ac_vm_diffs), 4),
         "Unit": "pu"},
        {"Metric": "DC Bus Vdc (grid buses)",
         "Max Abs Diff": round(max(dc_v_diffs_grid), 4),
         "Mean Abs Diff": round(np.mean(dc_v_diffs_grid), 4),
         "Unit": "pu"},
        {"Metric": "DC Bus Vdc (DC-DC buses 34,35,36)",
         "Max Abs Diff": round(max(dc_v_diffs_dcdc), 4),
         "Mean Abs Diff": round(np.mean(dc_v_diffs_dcdc), 4),
         "Unit": "pu"},
        {"Metric": "DC Bus Vdc (all buses)",
         "Max Abs Diff": round(max(dc_v_diffs_all), 4),
         "Mean Abs Diff": round(np.mean(dc_v_diffs_all), 4),
         "Unit": "pu"},
        {"Metric": "VSC Slack P (converters 1-3)",
         "Max Abs Diff": round(max(vsc_p_diffs), 3),
         "Mean Abs Diff": round(np.mean(vsc_p_diffs), 3),
         "Unit": "MW"},
        {"Metric": "DC Branch Pf",
         "Max Abs Diff": round(max(dc_br_diffs), 3),
         "Mean Abs Diff": round(np.mean(dc_br_diffs), 3),
         "Unit": "MW"},
    ]
    df = pd.DataFrame(rows)
    df.to_excel(writer, sheet_name="Summary", index=False)
