"""
Load and compare MatACDC reference results.

This module loads JSON results exported from MatACDC and compares them
against acdcpf results.

Usage:
    1. Run MatACDC/run_validation_cases.m in MATLAB
    2. Run this comparison: python -m tests.matacdc_reference
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import json

# Path to MatACDC validation results
MATACDC_RESULTS_DIR = Path(__file__).parent.parent / "MatACDC" / "validation_results"


@dataclass
class ComparisonResult:
    """Result of comparing a single value or array."""
    name: str
    matacdc_value: Any
    acdcpf_value: Any
    max_diff: float
    passed: bool
    tolerance: float


def load_matacdc_results(case_name: str) -> Optional[Dict]:
    """Load MatACDC results from JSON file."""
    json_file = MATACDC_RESULTS_DIR / f"{case_name}.json"
    if not json_file.exists():
        print(f"Warning: MatACDC results not found: {json_file}")
        return None

    with open(json_file, 'r') as f:
        return json.load(f)


def compare_arrays(name: str, matacdc: np.ndarray, acdcpf: np.ndarray,
                   tol: float = 1e-4, mapping: Optional[Dict] = None) -> ComparisonResult:
    """
    Compare two arrays with optional index mapping.

    Parameters
    ----------
    name : str
        Name of the quantity being compared
    matacdc : np.ndarray
        MatACDC reference values
    acdcpf : np.ndarray
        acdcpf computed values
    tol : float
        Tolerance for comparison
    mapping : dict, optional
        Mapping from MatACDC indices to acdcpf indices
    """
    matacdc = np.asarray(matacdc)
    acdcpf = np.asarray(acdcpf)

    if mapping is not None:
        # Reorder acdcpf values to match MatACDC ordering
        reordered = np.zeros_like(matacdc)
        for mat_idx, pf_idx in mapping.items():
            if mat_idx < len(matacdc) and pf_idx < len(acdcpf):
                reordered[mat_idx] = acdcpf[pf_idx]
        acdcpf = reordered

    if len(matacdc) != len(acdcpf):
        return ComparisonResult(
            name=name,
            matacdc_value=matacdc,
            acdcpf_value=acdcpf,
            max_diff=float('inf'),
            passed=False,
            tolerance=tol
        )

    diff = np.abs(matacdc - acdcpf)
    max_diff = np.max(diff) if len(diff) > 0 else 0.0
    passed = max_diff <= tol

    return ComparisonResult(
        name=name,
        matacdc_value=matacdc,
        acdcpf_value=acdcpf,
        max_diff=max_diff,
        passed=passed,
        tolerance=tol
    )


def compare_case(case_name: str, net, verbose: bool = True) -> Dict[str, ComparisonResult]:
    """
    Compare acdcpf results against MatACDC reference for a case.

    Parameters
    ----------
    case_name : str
        Name of the test case
    net : Network
        acdcpf network with solved power flow
    verbose : bool
        Print comparison results

    Returns
    -------
    dict
        Dictionary of comparison results
    """
    ref = load_matacdc_results(case_name)
    if ref is None:
        return {}

    results = {}

    if verbose:
        print(f"\n{'='*70}")
        print(f"Comparing: {case_name}")
        print(f"{'='*70}")

    # Build bus index mapping (MatACDC external -> acdcpf internal)
    # MatACDC uses 1-based external bus numbers, acdcpf uses 0-based internal indices
    ac_bus_map = {}  # MatACDC bus_i -> acdcpf index
    matacdc_buses = ref['ac_bus']['bus_i']
    for i, bus_i in enumerate(matacdc_buses):
        # Find corresponding acdcpf bus (by position in sorted order)
        if i < len(net.ac_bus):
            ac_bus_map[i] = i

    # Compare AC bus voltages
    if 'ac_bus' in ref and hasattr(net, 'res_ac_bus'):
        mat_vm = np.array(ref['ac_bus']['vm_pu'])
        pf_vm = net.res_ac_bus['v_pu'].values

        # For now, compare in order (assuming same ordering)
        if len(mat_vm) == len(pf_vm):
            results['ac_vm'] = compare_arrays('AC Voltage Magnitude (pu)', mat_vm, pf_vm, tol=0.01)

        mat_va = np.array(ref['ac_bus']['va_deg'])
        pf_va = np.degrees(net.res_ac_bus['v_angle_rad'].values) if 'v_angle_rad' in net.res_ac_bus.columns else np.zeros_like(mat_va)

        if len(mat_va) == len(pf_va):
            results['ac_va'] = compare_arrays('AC Voltage Angle (deg)', mat_va, pf_va, tol=1.0)

    # Compare DC bus voltages
    if 'dc_bus' in ref and hasattr(net, 'res_dc_bus'):
        mat_vdc = np.array(ref['dc_bus']['vdc_pu'])
        pf_vdc = net.res_dc_bus['v_dc_pu'].values

        if len(mat_vdc) == len(pf_vdc):
            results['dc_v'] = compare_arrays('DC Voltage (pu)', mat_vdc, pf_vdc, tol=0.01)

    # Compare converter powers
    if 'converter' in ref and hasattr(net, 'res_vsc'):
        mat_ps = np.array(ref['converter']['ps_mw'])
        mat_qs = np.array(ref['converter']['qs_mvar'])

        if 'p_ac_mw' in net.res_vsc.columns:
            pf_ps = net.res_vsc['p_ac_mw'].values
            if len(mat_ps) == len(pf_ps):
                results['conv_p'] = compare_arrays('Converter P (MW)', mat_ps, pf_ps, tol=1.0)

        if 'q_ac_mvar' in net.res_vsc.columns:
            pf_qs = net.res_vsc['q_ac_mvar'].values
            if len(mat_qs) == len(pf_qs):
                results['conv_q'] = compare_arrays('Converter Q (MVAr)', mat_qs, pf_qs, tol=1.0)

        # Converter losses
        if 'ploss_mw' in ref['converter'] and 'p_loss_mw' in net.res_vsc.columns:
            mat_loss = np.array(ref['converter']['ploss_mw'])
            pf_loss = net.res_vsc['p_loss_mw'].values
            if len(mat_loss) == len(pf_loss):
                results['conv_loss'] = compare_arrays('Converter Losses (MW)', mat_loss, pf_loss, tol=0.5)

    # Print results
    if verbose:
        all_passed = True
        for name, comp in results.items():
            status = "PASS" if comp.passed else "FAIL"
            all_passed = all_passed and comp.passed
            print(f"  {comp.name:40s} {status:6s} (max diff: {comp.max_diff:.6f}, tol: {comp.tolerance})")

        print(f"\n  Overall: {'PASS' if all_passed else 'FAIL'}")

    return results


def run_all_comparisons():
    """Run comparisons for all available cases."""
    from acdcpf.networks import (
        create_case5_stagg_hvdc_ptp,
        create_case5_stagg_mtdc_slack,
        create_case5_stagg_mtdc_droop,
        create_case24_ieee_rts_mtdc,
    )
    from acdcpf.powerflow import run_pf

    cases = [
        ("case5_stagg_hvdc_ptp", create_case5_stagg_hvdc_ptp),
        ("case5_stagg_mtdc_slack", create_case5_stagg_mtdc_slack),
        ("case5_stagg_mtdc_droop", create_case5_stagg_mtdc_droop),
        ("case24_ieee_rts_mtdc", create_case24_ieee_rts_mtdc),
    ]

    print("="*70)
    print("MatACDC vs acdcpf Comparison")
    print("="*70)

    if not MATACDC_RESULTS_DIR.exists():
        print(f"\nMatACDC results directory not found: {MATACDC_RESULTS_DIR}")
        print("Please run MatACDC/run_validation_cases.m first.")
        return

    all_results = {}
    for case_name, create_func in cases:
        try:
            net = create_func()
            converged = run_pf(net, verbose=False, max_iter_outer=50)

            if converged:
                results = compare_case(case_name, net, verbose=True)
                all_results[case_name] = results
            else:
                print(f"\n{case_name}: Power flow did not converge")
        except Exception as e:
            print(f"\n{case_name}: Error - {e}")

    # Summary
    print("\n" + "="*70)
    print("Summary")
    print("="*70)

    for case_name, results in all_results.items():
        n_pass = sum(1 for r in results.values() if r.passed)
        n_total = len(results)
        status = "PASS" if n_pass == n_total else "FAIL"
        print(f"  {case_name:40s} {status:6s} ({n_pass}/{n_total} checks)")


if __name__ == "__main__":
    run_all_comparisons()
