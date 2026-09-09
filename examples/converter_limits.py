"""
Example: Converter limit enforcement (PQ-capability diagram)

acdcpf enforces VSC converter limits every outer iteration, clamping the
converter setpoint onto the MatACDC PQ-capability diagram -- the maximum
current-limit circle (Icmax) and the min/max converter-voltage circles
(Vcmax/Vcmin). On a violation the converter's control mode is switched:
a voltage-controlling converter drops AC-voltage control, a droop converter
switches to constant active power.

Enforcement is on by default and is a no-op when converters stay within their
ratings; pass ``enforce_limits=False`` to disable it (MatACDC's ``limac = 0``).

The limit data (``i_max_pu`` / ``vc_max_pu`` / ``vc_min_pu``, and the
apparent-power rating ``s_mva``) is imported automatically from MatACDC
``convdc`` case files; here we set it by hand on built-in networks.

Run:
    python examples/converter_limits.py
"""
import numpy as np
import acdcpf as pf
from acdcpf.networks import (
    create_case5_stagg_mtdc_slack,
    create_case5_stagg_mtdc_droop,
)

S_BASE = 100.0  # MVA, system base of these test cases


def loading(net, idx):
    p = float(net.res_vsc.at[idx, "p_ac_mw"])
    q = float(net.res_vsc.at[idx, "q_ac_mvar"])
    return p, q, np.hypot(p, q)


# ---------------------------------------------------------------------------
# 1) Full PQ-capability diagram: clamp a converter onto its current limit
# ---------------------------------------------------------------------------
# Give converter 0 a tight current limit (~45 MVA rating) plus voltage limits.
def build_limited():
    net = create_case5_stagg_mtdc_slack()
    net.vsc.at[0, "i_max_pu"] = 45.0 / S_BASE   # Icmax (pu)  -> ~45 MVA
    net.vsc.at[0, "vc_max_pu"] = 1.2            # Vcmax (pu)
    net.vsc.at[0, "vc_min_pu"] = 0.85           # Vcmin (pu)
    return net

# Solve without enforcement...
net_off = build_limited()
pf.run_pf(net_off, enforce_limits=False)
p_off, q_off, s_off = loading(net_off, 0)

# ...and with the full capability diagram (default).
net_on = build_limited()
pf.run_pf(net_on, enforce_limits=True)
p_on, q_on, s_on = loading(net_on, 0)

print("=" * 64)
print("1) PQ-capability diagram clamp (converter 0, p_q control)")
print("=" * 64)
print(f"  current rating   : {net_on.vsc.at[0, 'i_max_pu'] * S_BASE:.1f} MVA (at 1 pu)")
print(f"  limits ignored   : P={p_off:7.2f} MW  Q={q_off:7.2f} MVAr  S={s_off:6.2f} MVA")
print(f"  limits enforced  : P={p_on:7.2f} MW  Q={q_on:7.2f} MVAr  S={s_on:6.2f} MVA")
print("\n  VSC results (limits enforced):")
print(net_on.res_vsc)

# ---------------------------------------------------------------------------
# 2) Control-mode switching on violation
# ---------------------------------------------------------------------------
# The 3-terminal droop case: rate two droop converters below their operating
# points. Converter 1 is droop_vac (droop + AC-voltage control), so hitting its
# limit drops BOTH its voltage control and its droop control.
net = create_case5_stagg_mtdc_droop()
net.vsc.at[0, "s_mva"] = 40.0   # droop_q   (~72 MVA operating point)
net.vsc.at[1, "s_mva"] = 15.0   # droop_vac (~22 MVA operating point)
pf.run_pf(net, max_iter_outer=80)

print("\n" + "=" * 64)
print("2) Control-mode switching (3-terminal droop grid)")
print("=" * 64)
for idx in net.res_vsc.index:
    _, _, s = loading(net, idx)
    mode = net.vsc.at[idx, "control_mode"]
    rating = float(net.vsc.at[idx, "s_mva"])
    print(f"  converter {idx} ({mode:9s}): S={s:6.2f} MVA  rating={rating:5.1f} MVA")

# The latch sets record which converters had their control mode switched.
vcontrol = sorted(int(i) for i in net._vsc_vcontrol_disabled)
droop = sorted(int(i) for i in net._vsc_droop_disabled)
print(f"\n  dropped AC-voltage control (-> PQ)        : {vcontrol}")
print(f"  droop control disabled (-> constant power): {droop}")
