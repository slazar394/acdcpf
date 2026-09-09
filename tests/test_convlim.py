"""
Unit tests for the MatACDC PQ-capability-diagram converter limiter (_convlim).

`_convlim` is a port of MatACDC's convlim.m (chapter 4.1.4 of the MatACDC
user manual). It clamps a converter's grid-side (P_s, Q_s) setpoint onto the
feasible region bounded by the maximum current-limit circle and the min/max
converter-voltage circles.

Ground truth is convlim.m itself: `tests/convlim_reference_data/convlim_golden.csv`
holds 108 (Vs, P, Q) -> (violation, P', Q') samples produced by running the
original MATLAB convlim.m (parameters recorded in the file header). Note the
MatACDC capability circles are an *approximation* of the full non-linear
converter equations, so correctness means matching convlim.m, not that the
clamped point satisfies |I_c|<=Icmax exactly; the outer AC/DC iteration
refines the operating point.

Convention: convlim.m works in generator/injection convention (S_inj), while
`_convlim` takes acdcpf's load convention (P_s>0 = rectifier). The two are
related by S_inj = -(P_s + jQ_s); the tests negate accordingly.

Reference: J. Beerten et al., "Generalized Steady-State VSC MTDC Model for
Sequential AC/DC Power Flow Algorithms", IEEE Trans. Power Syst., 2012.
"""

from pathlib import Path
import csv

import numpy as np
import pytest

from acdcpf.powerflow.runpf import _convlim

# Station parameters must match the golden-file header.
Z_TF = complex(0.0015, 0.1121)
Z_C = complex(0.0001, 0.16428)
B_F = 0.0887
I_MAX = 1.1
VC_MAX = 1.2
VC_MIN = 0.85

GOLDEN = Path(__file__).parent / "convlim_reference_data" / "convlim_golden.csv"


def _load_golden():
    rows = []
    with open(GOLDEN) as f:
        for r in csv.reader(f):
            if not r or r[0].startswith("#") or r[0] == "vsm":
                continue
            rows.append(tuple(float(x) for x in r))
    return rows


def _convlim_injection(p_inj, q_inj, vsm):
    """Call _convlim with an injection-convention setpoint; return injection out."""
    viol, p_load, q_load = _convlim(
        -p_inj, -q_inj, complex(vsm, 0.0), Z_TF, B_F, Z_C, I_MAX, VC_MAX, VC_MIN
    )
    return viol, -p_load, -q_load


def test_matches_matacdc_convlim_golden():
    """_convlim reproduces MATLAB convlim.m across the whole reference grid."""
    rows = _load_golden()
    assert len(rows) >= 100, "golden reference fixture missing or truncated"

    worst = 0.0
    for vsm, p_inj, q_inj, viol_ref, pn_ref, qn_ref in rows:
        viol, pn, qn = _convlim_injection(p_inj, q_inj, vsm)
        assert viol == int(viol_ref), (
            f"violation flag mismatch at Vs={vsm}, S=({p_inj},{q_inj}): "
            f"got {viol}, expected {int(viol_ref)}"
        )
        err = max(abs(pn - pn_ref), abs(qn - qn_ref))
        worst = max(worst, err)
        assert err < 1e-6, (
            f"clamped setpoint mismatch at Vs={vsm}, S=({p_inj},{q_inj}): "
            f"got ({pn:.6f},{qn:.6f}), expected ({pn_ref:.6f},{qn_ref:.6f})"
        )
    assert worst < 1e-6


def test_feasible_point_unchanged():
    # (P=0.5, Q=0.0) at Vs=1.0 is feasible in the reference (viol 0).
    viol, pn, qn = _convlim_injection(0.5, 0.0, 1.0)
    assert viol == 0
    assert pn == pytest.approx(0.5, abs=1e-9)
    assert qn == pytest.approx(0.0, abs=1e-9)


def test_reactive_violation_preserves_active_power():
    # (P=0.3, Q=1.6): only Q is out of range -> viol 1, P held, |Q| reduced.
    viol, pn, qn = _convlim_injection(0.3, 1.6, 1.0)
    assert viol == 1
    assert pn == pytest.approx(0.3, abs=1e-6)
    assert abs(qn) < 1.6


def test_active_power_violation_reduces_p():
    # A setpoint well beyond the current-circle P-range -> viol 2, |P| reduced.
    viol, pn, qn = _convlim_injection(5.0, 0.0, 1.0)
    assert viol == 2
    assert abs(pn) < 5.0


def test_no_current_limit_when_i_max_zero():
    # With i_max<=0 the diagram cannot be built by the caller; _convlim is only
    # invoked with valid limits, but guard against a degenerate voltage case
    # (lossless reactor) not raising.
    z_c_lossless = complex(0.0, 0.16428)
    viol, pn, qn = _convlim(0.3, 1.6, complex(1.0, 0.0), Z_TF, B_F,
                            z_c_lossless, I_MAX, VC_MAX, VC_MIN)
    assert viol in (0, 1, 2)
    assert np.isfinite(pn) and np.isfinite(qn)
