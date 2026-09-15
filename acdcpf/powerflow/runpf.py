"""
Main sequential AC/DC power flow solver.

Implements the algorithm from Beerten Chapter 13, Section 13.4 (Figure 13.11).
Iterates between AC power flow (via pypower) and DC power flow (NR)
with converter coupling equations.
"""

from ..results.process import process_ac_results, process_dc_results, process_converter_results
from ..build.dc import build_dc_conductance_matrix, build_dc_bus_data
from ..build.converters import build_converter_data
from ..network import Network
from .ac import run_ac_pf
from .dc import run_dc_pf

import warnings

import numpy as np


def run_pf(
    net: Network,
    max_iter_outer: int = 30,
    max_iter_inner: int = 30,
    tol: float = 1e-8,
    verbose: bool = False,
    enforce_limits: bool = True,
) -> bool:
    """
    Run sequential AC/DC power flow.

    This implements the sequential power flow algorithm from
    Beerten's method, iterating between AC and DC systems
    until convergence.

    Parameters
    ----------
    net : Network
        The network object
    max_iter_outer : int, optional
        Maximum outer iterations (AC/DC loop) (default: 30)
    max_iter_inner : int, optional
        Maximum inner iterations (NR) (default: 30)
    tol : float, optional
        Convergence tolerance (default: 1e-8)
    verbose : bool, optional
        Print iteration info (default: False)
    enforce_limits : bool, optional
        Enforce converter current/voltage limits via the MatACDC
        PQ-capability diagram, switching control modes on violation
        (default: True). Set False to solve without limit enforcement
        (matching MatACDC's ``limac = 0`` option).

    Returns
    -------
    bool
        True if converged, False otherwise
    """
    # Build converter data
    conv_data = build_converter_data(net)
    n_vsc = conv_data["n_vsc"]
    n_dcdc = conv_data["n_dcdc"]

    has_dc = len(net.dc_bus) > 0
    has_ac = len(net.ac_bus) > 0

    # Initialize working arrays for VSC powers
    # P_s, Q_s are AC-side powers at PCC (MW, MVAr)
    p_s = np.zeros(len(net.vsc)) if not net.vsc.empty else np.array([])
    q_s = np.zeros(len(net.vsc)) if not net.vsc.empty else np.array([])
    # P_dc is DC-side power (MW)
    p_dc_vsc = np.zeros(len(net.vsc)) if not net.vsc.empty else np.array([])

    # Voltage arrays
    v_mag = np.ones(net.ac_bus.index.max() + 1) if has_ac else np.array([])
    v_ang = np.zeros(net.ac_bus.index.max() + 1) if has_ac else np.array([])
    v_dc = np.ones(net.dc_bus.index.max() + 1) if has_dc else np.array([])

    # Store converter data on net for use by other functions
    net._conv_data = conv_data
    net._p_s = p_s
    net._q_s = q_s
    net._p_dc_vsc = p_dc_vsc
    net._v_mag = v_mag
    net._v_ang = v_ang
    net._v_dc = v_dc

    # Latches for control-mode switching on converter-limit violations
    # (persist across outer iterations, like MatACDC).
    net._vsc_vcontrol_disabled = set()  # VSCs that dropped AC-voltage control
    net._vsc_droop_disabled = set()     # droop VSCs switched to constant-P

    # Initialize converter powers
    _initialize_converter_powers(net)

    # Main sequential AC/DC iteration loop
    converged = False
    # Track subproblem convergence. Absent subsystems count as converged.
    ac_conv = True
    dc_conv = True
    for outer_iter in range(1, max_iter_outer + 1):
        p_s_old = net._p_s.copy()

        # --- Step 1: AC power flow ---
        if has_ac:
            # Determine which VSCs control AC voltage
            vsc_v_control = _get_vsc_v_control(net)

            v_mag, v_ang, ac_conv, ac_iter = run_ac_pf(
                net, net._p_s, net._q_s, vsc_v_control,
                max_iter=max_iter_inner, tol=tol,
            )
            net._v_mag = v_mag
            net._v_ang = v_ang

            if not ac_conv:
                if verbose:
                    print(f"  AC power flow did not converge at outer iter {outer_iter}")

            # Extract Q from Vac-controlling VSCs (from pypower result)
            _extract_vsc_q_from_ac(net, vsc_v_control)

        # --- Step 1b: Enforce converter limits (PQ-capability diagram) ---
        # Clamps non-slack VSC setpoints onto the converter capability region
        # and switches control modes on violation, so the limited P_s/Q_s
        # propagate into the converter equations and the next AC iteration
        # (matching MatACDC's convlim placement).
        if n_vsc > 0 and enforce_limits:
            _check_converter_limits(net)

        # --- Step 2: Converter calculations ---
        if n_vsc > 0:
            _calculate_converter_equations(net)

        # --- Step 3: DC power flow ---
        if has_dc:
            v_dc, dc_conv, dc_iter = run_dc_pf(
                net, net._p_dc_vsc,
                max_iter=max_iter_inner, tol=tol,
            )
            net._v_dc = v_dc

            if not dc_conv:
                if verbose:
                    print(f"  DC power flow did not converge at outer iter {outer_iter}")

        # --- Step 4: Update slack/droop powers ---
        if n_vsc > 0 and has_dc:
            _update_slack_droop_powers(net)

        # --- Step 5: Convergence check ---
        if len(net._p_s) > 0:
            max_dp = np.max(np.abs(net._p_s - p_s_old))
        else:
            max_dp = 0.0

        if verbose:
            print(
                f"Outer iter {outer_iter}: max|dP_s| = {max_dp:.2e}, "
                f"ac_conv={ac_conv}, dc_conv={dc_conv}"
            )

        # Converged only if the outer loop settled AND both subproblems
        # actually converged this iteration.
        if max_dp < tol and ac_conv and dc_conv:
            converged = True
            break

    # Store results
    net.converged = converged
    _store_results(net)

    # Surface limit-related conditions the solver could not act on silently:
    # converters whose control mode was switched on a violation, and any
    # converter (Vdc-slack included) left loaded above its rating.
    if n_vsc > 0 and enforce_limits:
        _emit_limit_warnings(net)

    return converged


def _emit_limit_warnings(net: Network) -> None:
    """
    Warn about clamped/switched converters and residual overloads.

    Emitted once per affected converter after the solve:

    - a converter whose AC-voltage control or droop control was switched off
      when it hit a capability limit (its setpoint was clamped); and
    - any converter still loaded above its rating -- notably Vdc-slack
      converters, which are exempt from curtailment because their power is set
      by the DC power balance, so the limiter cannot reduce their loading.
    """
    vcontrol_disabled = getattr(net, "_vsc_vcontrol_disabled", set())
    droop_disabled = getattr(net, "_vsc_droop_disabled", set())

    if net.vsc.empty or not hasattr(net, "res_vsc") or net.res_vsc.empty:
        switched = vcontrol_disabled | droop_disabled
        for vsc_idx in sorted(switched):
            name = str(net.vsc.at[vsc_idx, "name"]) if vsc_idx in net.vsc.index else str(vsc_idx)
            warnings.warn(
                f"VSC '{name}' hit a converter limit: its control mode was "
                f"switched and its setpoint clamped.",
                stacklevel=2,
            )
        return

    conv_data = getattr(net, "_conv_data", None)
    slack_idx = set()
    if conv_data is not None:
        for i, vsc_idx in enumerate(conv_data["vsc_indices"]):
            if "vdc" in str(conv_data["vsc_control"][i]):
                slack_idx.add(int(vsc_idx))

    for vsc_idx in sorted(vcontrol_disabled | droop_disabled):
        name = str(net.vsc.at[vsc_idx, "name"]) if vsc_idx in net.vsc.index else str(vsc_idx)
        warnings.warn(
            f"VSC '{name}' hit a converter limit: its control mode was "
            f"switched and its setpoint clamped onto the capability region.",
            stacklevel=2,
        )

    for vsc_idx in net.res_vsc.index:
        loading = float(net.res_vsc.at[vsc_idx, "loading_percent"])
        if loading > 100.0 + 1e-3:
            name = str(net.res_vsc.at[vsc_idx, "name"])
            exempt = " (Vdc-slack, exempt from curtailment)" if int(vsc_idx) in slack_idx else ""
            warnings.warn(
                f"VSC '{name}' is loaded at {loading:.2f}% of its rating"
                f"{exempt}.",
                stacklevel=2,
            )


def _get_vsc_v_control(net: Network) -> dict:
    """Get mapping of AC bus -> voltage setpoint for Vac-controlling VSCs.

    Resolves conflicts where a generator already controls voltage at the
    same bus (matching MatACDC behaviour: VSC Vac control is removed and
    Q is set to 0 when a generator is present on the same bus).
    """
    vsc_v_control = {}
    if net.vsc.empty:
        return vsc_v_control

    # Determine which AC buses already have generators controlling voltage
    gen_pv_buses = set()
    if not net.ac_gen.empty:
        for _, gen in net.ac_gen[net.ac_gen["in_service"] == True].iterrows():
            v_pu = gen.get("v_pu")
            if v_pu is not None and not (isinstance(v_pu, float) and np.isnan(v_pu)):
                gen_pv_buses.add(int(gen["bus"]))

    conv_data = net._conv_data
    vcontrol_disabled = getattr(net, "_vsc_vcontrol_disabled", set())
    for i, vsc_idx in enumerate(conv_data["vsc_indices"]):
        control = str(conv_data["vsc_control"][i])
        # A converter whose AC-voltage control was dropped on a limit violation
        # now behaves as PQ, holding its limited reactive power.
        if vsc_idx in vcontrol_disabled:
            continue
        if "vac" in control:
            ac_bus = int(conv_data["vsc_ac_bus"][i])
            v_set = float(conv_data["vsc_v_ac_set"][i])
            if not np.isnan(v_set):
                if ac_bus in gen_pv_buses:
                    # Conflict: generator already controls V at this bus.
                    # Remove VSC Vac control and set Q=0 (MatACDC behaviour).
                    net._q_s[vsc_idx] = 0.0
                else:
                    vsc_v_control[ac_bus] = v_set
    return vsc_v_control


def _extract_vsc_q_from_ac(net: Network, vsc_v_control: dict):
    """After AC PF, extract reactive power for Vac-controlling VSCs."""
    # For Vac-controlling VSCs, Q is determined by the AC power flow.
    # We read the generator reactive power from the pypower solution.
    # The dummy generators added for Vac control have PMAX=0 and PMIN=0.

    if not hasattr(net, '_ppc_results') or not net._ppc_results:
        return

    from pypower.idx_gen import GEN_BUS, QG, PG, PMAX, PMIN

    conv_data = net._conv_data
    if conv_data["n_vsc"] == 0:
        return

    vcontrol_disabled = getattr(net, "_vsc_vcontrol_disabled", set())

    # For each Vac-controlling VSC, find the generator Q in the pypower results
    for i, vsc_idx in enumerate(conv_data["vsc_indices"]):
        control = str(conv_data["vsc_control"][i])
        if "vac" not in control:
            continue
        # Skip converters whose voltage control was dropped on a limit
        # violation: their Q is fixed at the clamped value, not re-extracted.
        if vsc_idx in vcontrol_disabled:
            continue

        ac_bus = int(conv_data["vsc_ac_bus"][i])

        # Find which island this AC bus belongs to
        for island_key, ppc_result in net._ppc_results.items():
            island_buses = list(island_key)
            if ac_bus not in island_buses:
                continue

            # Get internal index within this island
            int_idx = island_buses.index(ac_bus)

            # Find the dummy generator at this bus
            gen_result = ppc_result.get("gen")
            if gen_result is None or len(gen_result) == 0:
                continue

            # Search for the dummy VSC generator at this internal bus index
            # Dummy generators have PMAX=0 AND PMIN=0 (real generators have PMAX > 0)
            found_dummy = False
            for gen_row in gen_result:
                gen_bus = int(gen_row[GEN_BUS])
                pmax = gen_row[PMAX]
                pmin = gen_row[PMIN]
                if gen_bus == int_idx and pmax == 0.0 and pmin == 0.0:
                    # This is the dummy generator for VSC voltage control
                    # QG is in generator convention (positive = injecting Q).
                    # Negate to match acdcpf load convention (positive = consuming Q).
                    q_mvar = gen_row[QG]
                    net._q_s[vsc_idx] = -q_mvar
                    found_dummy = True
                    break

            # If no dummy generator found (shouldn't happen), don't modify Q
            break


def _initialize_converter_powers(net: Network) -> None:
    """
    Initialize converter power injections.

    P-controlled VSCs: P_s = P_setpoint
    Droop VSCs: P_s = P_dc_set (assume at reference point initially)
    AC slack VSCs (p_vac with P=0): P_s = island power balance
    Vdc slack VSC: P_s = -(sum of other P_s in same DC grid) / n_slack
    """
    conv_data = net._conv_data
    n_vsc = conv_data["n_vsc"]

    if n_vsc == 0:
        return

    # For AC slack converters in isolated islands, compute initial P from
    # the island power balance: P_s = P_gen_island - P_load_island
    island_balance = _compute_island_power_balance(net)

    # Initialize P_s based on control mode
    for i, vsc_idx in enumerate(conv_data["vsc_indices"]):
        control = str(conv_data["vsc_control"][i])
        ac_bus = int(conv_data["vsc_ac_bus"][i])

        if "vdc" in control:
            # Vdc slack -- will be set below
            net._p_s[vsc_idx] = 0.0
        elif "droop" in control:
            # Droop: start at droop reference power
            net._p_s[vsc_idx] = conv_data["vsc_p_dc_set"][i]
        elif control == "p_vac" and conv_data["vsc_p_set"][i] == 0.0:
            # AC slack converter: P determined by island balance
            # P_s > 0 = rectifier; island with excess gen → rectify into DC
            if ac_bus in island_balance:
                net._p_s[vsc_idx] = island_balance[ac_bus]
            else:
                net._p_s[vsc_idx] = 0.0
        else:
            # P-controlled (p_q or p_vac with explicit P setpoint)
            net._p_s[vsc_idx] = conv_data["vsc_p_set"][i]

        # Initialize Q_s
        if "vac" in control:
            net._q_s[vsc_idx] = 0.0  # Will be determined by AC PF
        else:
            net._q_s[vsc_idx] = conv_data["vsc_q_set"][i]

    # Compute slack bus P per DC grid (Eq. 13.46-13.48)
    _init_slack_power_per_grid(net)

    # Initialize P_dc ~ P_s (lossless initial assumption)
    for i, vsc_idx in enumerate(conv_data["vsc_indices"]):
        net._p_dc_vsc[vsc_idx] = net._p_s[vsc_idx]



def _compute_island_power_balance(net: Network) -> dict:
    """
    Compute P_gen - P_load for each AC island.

    Returns a dict mapping AC bus index -> island power balance (MW).
    Only non-trivial for islanded buses (those without AC lines to larger grids).
    Each bus in an island gets the same balance value.
    """
    from .ac import _find_ac_islands
    balance = {}

    islands = _find_ac_islands(net)
    for island_buses in islands:
        bus_set = set(island_buses)
        p_gen_total = 0.0
        p_load_total = 0.0

        if not net.ac_gen.empty:
            for _, gen in net.ac_gen[net.ac_gen["in_service"] == True].iterrows():
                if int(gen["bus"]) in bus_set:
                    p_gen_total += float(gen["p_mw"])

        if not net.ac_load.empty:
            for _, load in net.ac_load[net.ac_load["in_service"] == True].iterrows():
                if int(load["bus"]) in bus_set:
                    p_load_total += float(load["p_mw"])

        # Also account for other VSC P injections already set in this island
        # (e.g., P-controlled converters)
        p_vsc_set = 0.0
        if not net.vsc.empty:
            conv_data = net._conv_data
            for i, vsc_idx in enumerate(conv_data["vsc_indices"]):
                ac_bus = int(conv_data["vsc_ac_bus"][i])
                control = str(conv_data["vsc_control"][i])
                if ac_bus in bus_set:
                    if control not in ("p_vac",) or conv_data["vsc_p_set"][i] != 0.0:
                        # This converter has a fixed P setpoint
                        if "vdc" not in control and "droop" not in control:
                            p_vsc_set += float(conv_data["vsc_p_set"][i])

        # Island balance: positive means excess generation available for rectification
        # Subtract VSC rectifiers (P_s > 0 = load on AC side)
        island_bal = p_gen_total - p_load_total - p_vsc_set
        for bus in island_buses:
            balance[bus] = island_bal

    return balance


def _init_slack_power_per_grid(net: Network):
    """Initialize slack VSC power to balance each DC grid."""
    conv_data = net._conv_data
    n_vsc = conv_data["n_vsc"]

    if n_vsc == 0 or net.dc_bus.empty:
        return

    # Group VSCs by DC grid
    dc_grids = {}
    for i, vsc_idx in enumerate(conv_data["vsc_indices"]):
        dc_bus = int(conv_data["vsc_dc_bus"][i])
        if dc_bus in net.dc_bus.index:
            grid_id = int(net.dc_bus.loc[dc_bus, "dc_grid"])
        else:
            grid_id = 0
        if grid_id not in dc_grids:
            dc_grids[grid_id] = {"slack": [], "non_slack": [], "p_sum": 0.0}

        control = str(conv_data["vsc_control"][i])
        if "vdc" in control:
            dc_grids[grid_id]["slack"].append(vsc_idx)
        else:
            dc_grids[grid_id]["non_slack"].append(vsc_idx)
            dc_grids[grid_id]["p_sum"] += net._p_s[vsc_idx]

    # Also account for DC loads and generators in each grid
    for grid_id in dc_grids:
        grid_buses = set()
        for idx, row in net.dc_bus.iterrows():
            if int(row["dc_grid"]) == grid_id and row["in_service"]:
                grid_buses.add(idx)

        # DC loads (consumption) -- only constant-power loads affect the
        # explicit power sum; constant-impedance loads are inside G_dc.
        if not net.dc_load.empty:
            for _, load in net.dc_load[net.dc_load["in_service"] == True].iterrows():
                if int(load["bus"]) in grid_buses:
                    if str(load.get("load_type", "constant_power")) == "constant_impedance":
                        continue
                    dc_grids[grid_id]["p_sum"] -= float(load["p_mw"])

        # DC generators (injection)
        if not net.dc_gen.empty:
            for _, gen in net.dc_gen[net.dc_gen["in_service"] == True].iterrows():
                if int(gen["bus"]) in grid_buses:
                    dc_grids[grid_id]["p_sum"] += float(gen["p_mw"])

    # Set slack power to balance each grid
    for grid_id, info in dc_grids.items():
        n_slack = len(info["slack"])
        if n_slack > 0:
            p_slack_each = -info["p_sum"] / n_slack
            for vsc_idx in info["slack"]:
                net._p_s[vsc_idx] = p_slack_each


def _calculate_converter_equations(net: Network) -> None:
    """
    Calculate VSC converter equations (Eq. 13.11-13.23).

    Given V_s from AC solution and P_s, Q_s setpoints,
    compute the converter operating point and losses,
    then determine P_DC.
    """
    conv_data = net._conv_data
    n_vsc = conv_data["n_vsc"]

    for i in range(n_vsc):
        vsc_idx = conv_data["vsc_indices"][i]
        ac_bus = int(conv_data["vsc_ac_bus"][i])

        # Get AC voltage at PCC
        if ac_bus < len(net._v_mag):
            v_s_mag = net._v_mag[ac_bus]
            v_s_ang = net._v_ang[ac_bus]
        else:
            v_s_mag = 1.0
            v_s_ang = 0.0

        v_s = v_s_mag * np.exp(1j * v_s_ang)

        # Converter AC-side power
        p_s = net._p_s[vsc_idx] / net.s_base  # pu
        q_s = net._q_s[vsc_idx] / net.s_base  # pu
        s_s = complex(p_s, q_s)

        # Converter impedance parameters (separate transformer and phase reactor)
        r_tf = conv_data["vsc_r_tf"][i]
        x_tf = conv_data["vsc_x_tf"][i]
        r_c = conv_data["vsc_r_c"][i]
        x_c = conv_data["vsc_x_c"][i]
        b_f = conv_data["vsc_b_filter"][i]

        # Loss coefficients (per-unit conversion matching MatACDC)
        # LossA in MW, LossB in kV, LossC in Ohm
        loss_base_kv = conv_data["vsc_loss_base_kv"][i]
        base_kv_ac = loss_base_kv if loss_base_kv > 0 else float(net.ac_bus.loc[ac_bus, "vr_kv"])

        # Impedances are already in per-unit on the system base (baseMVA).
        # MatACDC does NOT scale impedances by voltage ratio; basekVac is
        # used only for loss coefficient conversion.
        z_tf = complex(r_tf, x_tf)
        z_c = complex(r_c, x_c)
        base_ka = net.s_base / (np.sqrt(3) * base_kv_ac)
        loss_a = conv_data["vsc_loss_a"][i] / net.s_base  # MW -> pu
        loss_b = conv_data["vsc_loss_b"][i] * base_ka / net.s_base  # kV -> pu
        loss_c_rec = conv_data["vsc_loss_c"][i] * base_ka ** 2 / net.s_base  # Ohm -> pu
        loss_c_inv = conv_data["vsc_loss_c_inv"][i] * base_ka ** 2 / net.s_base

        # Transformer current (Eq. 13.11)
        if abs(v_s) > 1e-10:
            i_tf = np.conj(s_s / v_s)
        else:
            i_tf = 0.0

        # Filter bus voltage (Eq. 13.26: U_f = U_s + Z_tf * I_s_beerten)
        # Code's I_tf = -I_s_beerten (opposite convention), so V_f = V_s - I_tf * Z_tf
        v_f = v_s - i_tf * z_tf

        # Filter-side transformer power
        s_sf = v_f * np.conj(i_tf)

        # Filter reactive power (Eq. 13.13)
        q_f = -b_f * abs(v_f) ** 2

        # Converter-side apparent power at filter bus (Eq. 13.14)
        s_cf = s_sf + 1j * q_f

        # Converter (phase reactor) current (Eq. 13.15)
        if abs(v_f) > 1e-10:
            i_c = np.conj(s_cf / v_f)
        else:
            i_c = 0.0

        # Converter voltage (across phase reactor), same sign convention
        v_c = v_f - i_c * z_c

        # Converter-side power (for loss calculation)
        s_c = v_c * np.conj(i_c)
        p_c = s_c.real
        q_c = s_c.imag

        # Converter losses (Eq. 13.9) using converter-side current
        # Sign-dependent quadratic coefficient (MatACDC: LossCrec when Pc>0, LossCinv when Pc<0)
        # In acdcpf load convention signs are opposite, so:
        #   p_c > 0 (acdcpf rectifier) → MatACDC Pc < 0 → LossCinv
        #   p_c < 0 (acdcpf inverter) → MatACDC Pc > 0 → LossCrec
        i_c_mag = np.sqrt(p_c ** 2 + q_c ** 2) / abs(v_c) if abs(v_c) > 1e-10 else abs(i_c)
        loss_c_used = loss_c_inv if p_c > 0 else loss_c_rec
        p_loss = loss_a + loss_b * i_c_mag + loss_c_used * i_c_mag ** 2

        # DC-side power (Eq. 13.10)
        p_dc = p_c - p_loss  # Convention: positive P_s = rectifier, P_dc positive into DC grid

        # Store in MW
        net._p_dc_vsc[vsc_idx] = p_dc * net.s_base

        # Store converter internal state for results
        if not hasattr(net, '_vsc_internal'):
            net._vsc_internal = {}
        net._vsc_internal[vsc_idx] = {
            'v_s': v_s, 'v_f': v_f, 'v_c': v_c, 'i_c': i_c,
            'p_loss': p_loss * net.s_base,  # MW
            'p_dc': p_dc * net.s_base,
            'p_c': p_c * net.s_base,
        }


def _circle_circle_intersect(c1: complex, r1: float, c2: complex, r2: float):
    """
    Intersection points of two circles in the complex (P, Q) plane.

    Returns a list of 0, 1 or 2 complex points. Infinite radii (a
    degenerate limit circle) yield no intersection.
    """
    if not (np.isfinite(r1) and np.isfinite(r2)):
        return []
    d = abs(c2 - c1)
    if d < 1e-15:
        return []
    if d > r1 + r2 + 1e-12 or d < abs(r1 - r2) - 1e-12:
        return []  # separate or one contained in the other
    a = (r1 ** 2 - r2 ** 2 + d ** 2) / (2.0 * d)
    h2 = r1 ** 2 - a ** 2
    h = np.sqrt(h2) if h2 > 0 else 0.0
    ux = (c2 - c1).real / d
    uy = (c2 - c1).imag / d
    mid = complex(c1.real + a * ux, c1.imag + a * uy)
    if h < 1e-12:
        return [mid]
    return [
        complex(mid.real - h * uy, mid.imag + h * ux),
        complex(mid.real + h * uy, mid.imag - h * ux),
    ]


def _voltage_limit_q(ps, vsm, vc, g2, b2, g12, b12):
    """
    Reactive power on a converter-voltage limit circle at active power ``ps``.

    Ports the sin(delta) formulation from MatACDC convlim.m (upper arc).
    Returns +inf when the formulation is degenerate (lossless reactor,
    G2 ~ 0), so the voltage limit is treated as non-binding.
    """
    if abs(g2) < 1e-9:
        return np.inf
    ratio = (ps + vsm ** 2 * g12) / (vsm * vc * g2)
    a = 1.0 + (b2 / g2) ** 2
    b = -2.0 * (b2 / g2) * ratio
    c = ratio ** 2 - 1.0
    disc = b ** 2 - 4.0 * a * c
    if disc < 0.0:
        disc = 0.0
    sin_dd = (-b + np.sqrt(disc)) / (2.0 * a)
    sin_dd = float(np.clip(sin_dd, -1.0, 1.0))
    cos_dd = np.cos(np.arcsin(sin_dd))
    return vsm ** 2 * b12 + vsm * vc * (g2 * sin_dd - b2 * cos_dd)


def _convlim(p_s_pu, q_s_pu, v_s, z_tf, b_f, z_c, i_max, vc_max, vc_min,
             eps_lim: float = 1e-4):
    """
    MatACDC PQ-capability-diagram limiter (port of convlim.m).

    Clamp a grid-side converter setpoint onto its feasible region, defined by
    the maximum current-limit circle (``|I_c| <= i_max``) and the min/max
    converter-voltage circles (``vc_min <= |V_c| <= vc_max``).

    Parameters
    ----------
    p_s_pu, q_s_pu : float
        Grid-side active/reactive power in per-unit, acdcpf **load**
        convention (``P_s > 0`` = rectifier).
    v_s : complex
        Grid-side (PCC) voltage phasor in per-unit.
    z_tf, z_c : complex
        Transformer and phase-reactor impedances (per-unit).
    b_f : float
        Filter susceptance (per-unit).
    i_max, vc_max, vc_min : float
        Converter current and voltage limits (per-unit).
    eps_lim : float, optional
        Deadband: a correction smaller than this (per-unit) is treated as no
        violation (default 1e-4).

    Returns
    -------
    tuple
        ``(viol, p_new_pu, q_new_pu)`` in load convention, where ``viol`` is
        0 (feasible), 1 (reactive-power limit hit, P preserved) or 2
        (active-power limit hit, P and Q adjusted).

    Notes
    -----
    Internally the setpoint is converted to MatACDC's injection convention
    (``S_inj = -(P_s + jQ_s)``); the two converter models coincide exactly
    under this mapping, so the ported geometry applies unchanged. The caller
    must exclude Vdc-slack converters. Reference: MatACDC convlim.m;
    J. Beerten et al., IEEE Trans. Power Syst., 2012.
    """
    # --- convention bridge: acdcpf load convention -> MatACDC injection ---
    ps = -float(p_s_pu)
    qs = -float(q_s_pu)
    ss_old = complex(ps, qs)

    vsm = abs(v_s)
    if vsm < 1e-12:
        return 0, p_s_pu, q_s_pu

    ztf = complex(z_tf)
    zc = complex(z_c)
    bf = float(b_f)

    has_tf = abs(ztf) > 1e-12
    has_bf = abs(bf) > 1e-12
    zf = 1.0 / (1j * bf) if has_bf else np.inf
    ytf = (1.0 / ztf) if has_tf else np.inf
    yf = 1j * bf

    # pi-equivalent of the converter station (transformer / filter / reactor)
    if has_tf and has_bf:
        num = ztf * zc + zc * zf + zf * ztf
        z1 = num / zc
        z2 = num / zf
    elif not has_tf and has_bf:
        z1 = zf
        z2 = zc
    elif has_tf and not has_bf:
        z1 = np.inf
        z2 = ztf + zc
    else:
        z1 = np.inf
        z2 = zc

    y1 = 0.0 if (isinstance(z1, float) and z1 == np.inf) else 1.0 / z1
    y2 = 1.0 / z2
    g2 = y2.real
    b2 = y2.imag
    y12 = y1 + y2
    g12 = complex(y12).real
    b12 = complex(y12).imag

    # --- maximum current-limit circle (L1) ---
    if has_bf:
        mpl1 = complex(-vsm ** 2 * (1.0 / (np.conj(zf) + (np.conj(ztf) if has_tf else 0.0))))
    else:
        mpl1 = 0.0 + 0.0j
    if has_tf:
        r_l1 = vsm * i_max * abs(np.conj(ytf) / (np.conj(yf) + np.conj(ytf)))
    else:
        r_l1 = vsm * i_max
    qc = mpl1.imag
    pmax_l1 = mpl1.real + r_l1
    pmin_l1 = mpl1.real - r_l1

    # --- min/max converter-voltage circles (L2) ---
    mpl2 = complex(-vsm ** 2 * np.conj(y1 + y2))
    r_l2_min = vsm * vc_min * abs(y2)
    r_l2_max = vsm * vc_max * abs(y2)

    # --- feasible active-power range [pmin, pmax] with matching Q ---
    pmin, qp_min = pmin_l1, qc
    pmax, qp_max = pmax_l1, qc

    pts = _circle_circle_intersect(mpl1, r_l1, mpl2, r_l2_min)
    if len(pts) == 2:
        lo, hi = sorted(pts, key=lambda z: z.real)
        if lo.imag > qc:
            pmin, qp_min = lo.real, lo.imag
        if hi.imag > qc:
            pmax, qp_max = hi.real, hi.imag
    pts = _circle_circle_intersect(mpl1, r_l1, mpl2, r_l2_max)
    if len(pts) == 2:
        lo, hi = sorted(pts, key=lambda z: z.real)
        if lo.imag < qc:
            pmin, qp_min = lo.real, lo.imag
        if hi.imag < qc:
            pmax, qp_max = hi.real, hi.imag

    # --- limit check ---
    if pmin < ps < pmax:
        disc1 = r_l1 ** 2 - (ps - mpl1.real) ** 2
        if disc1 < 0.0:
            disc1 = 0.0
        qs1 = qc + np.sqrt(disc1) if qc < qs else qc - np.sqrt(disc1)

        qs2_min = _voltage_limit_q(ps, vsm, vc_min, g2, b2, g12, b12)
        qs2_max = _voltage_limit_q(ps, vsm, vc_max, g2, b2, g12, b12)

        if qs > qc:
            upper = min(qs1, qs2_max)
            lower = qs2_min
            if qs > upper:
                viol, qs = 1, upper
            elif qs < lower:
                viol, qs = 1, lower
            else:
                viol = 0
        else:
            lower = max(qs1, qs2_min)
            upper = qs2_max
            if qs < lower:
                viol, qs = 1, lower
            elif qs > upper:
                viol, qs = 1, upper
            else:
                viol = 0
    elif ps <= pmin:
        viol, ps, qs = 2, pmin, qp_min
    else:
        viol, ps, qs = 2, pmax, qp_max

    ss_new = complex(ps, qs)
    if abs(ss_old - ss_new) < eps_lim:
        viol = 0

    # back to load convention
    return viol, -ss_new.real, -ss_new.imag


def _apparent_power_clamp(p_s, q_s, s_rated):
    """
    Fallback limiter: clamp (P, Q) onto the apparent-power circle S <= s_rated.

    Used when full capability-diagram limits (Icmax/Vcmax/Vcmin) are not
    available for a converter. Reduces Q first, then P (P-priority).
    Returns (viol, p_new, q_new).
    """
    if not (s_rated > 0):
        return 0, p_s, q_s
    s_actual = np.sqrt(p_s ** 2 + q_s ** 2)
    if s_actual <= s_rated:
        return 0, p_s, q_s
    viol = 1
    q_max = np.sqrt(max(s_rated ** 2 - p_s ** 2, 0.0))
    if abs(q_s) > q_max:
        q_s = np.sign(q_s) * q_max
    s_actual = np.sqrt(p_s ** 2 + q_s ** 2)
    if s_actual > s_rated:
        scale = s_rated / s_actual
        p_s *= scale
        q_s *= scale
        viol = 2
    return viol, p_s, q_s


def _converter_limit_candidate(net, conv_data, i):
    """
    Evaluate the limiter for one non-slack converter without applying it.

    Returns ``(viol, p_new, q_new)`` in MW (load convention). Uses the full
    MatACDC PQ-capability diagram (:func:`_convlim`) when the converter
    defines the complete limit set (Icmax, Vcmax, Vcmin), otherwise the
    apparent-power fallback (:func:`_apparent_power_clamp`).
    """
    s_base = net.s_base
    vsc_idx = conv_data["vsc_indices"][i]
    p_s = net._p_s[vsc_idx]
    q_s = net._q_s[vsc_idx]

    i_max = conv_data["vsc_i_max"][i]
    vc_max = conv_data["vsc_vc_max"][i]
    vc_min = conv_data["vsc_vc_min"][i]

    if i_max > 0 and vc_max > vc_min > 0:
        ac_bus = int(conv_data["vsc_ac_bus"][i])
        if ac_bus < len(net._v_mag):
            v_s = net._v_mag[ac_bus] * np.exp(1j * net._v_ang[ac_bus])
        else:
            v_s = complex(1.0, 0.0)
        z_tf = complex(conv_data["vsc_r_tf"][i], conv_data["vsc_x_tf"][i])
        z_c = complex(conv_data["vsc_r_c"][i], conv_data["vsc_x_c"][i])
        b_f = conv_data["vsc_b_filter"][i]
        viol, p_new_pu, q_new_pu = _convlim(
            p_s / s_base, q_s / s_base, v_s, z_tf, b_f, z_c,
            i_max, vc_max, vc_min,
        )
        return viol, p_new_pu * s_base, q_new_pu * s_base

    return _apparent_power_clamp(p_s, q_s, conv_data["vsc_s_mva"][i])


def _check_converter_limits(net: Network) -> bool:
    """
    Check and enforce converter limits, and switch control modes on violation.

    Each non-slack VSC setpoint (P_s, Q_s) is clamped onto its feasible region.
    When the converter defines the full MatACDC limit set (Icmax, Vcmax, Vcmin)
    the complete PQ-capability diagram (:func:`_convlim`) is used; otherwise it
    falls back to the apparent-power circle (:func:`_apparent_power_clamp`).

    **One correction per DC grid per call**, matching MatACDC's ``runacdcpf``:
    all non-slack converters are evaluated, then within each DC grid a single
    converter is corrected -- the largest active-power violation (viol == 2,
    ranked by |dP|) if any exists, otherwise the largest reactive-power
    violation (viol == 1, ranked by |dQ|). Correcting one at a time (rather
    than all simultaneously) avoids spuriously latching a control-mode switch
    on a converter whose violation would clear once a coupled converter in the
    same grid is corrected. Remaining violations are handled on later outer
    iterations. For a system with a single DC grid this reduces to exactly one
    correction per outer iteration; grids are corrected independently because
    they are only coupled through DC-DC converters, not a shared power balance.

    This function is invoked once per outer iteration, after the AC power flow
    (so ``V_s`` is available) and before the converter equations and DC power
    flow, so the clamped setpoints propagate into the converter model and the
    next AC solve -- matching the placement of ``convlim`` in MatACDC's
    ``runacdcpf`` sequential loop.

    On the corrected converter the control mode is switched, matching MatACDC:
    a voltage-controlling (Vac) converter that hits a reactive-power limit
    drops AC-voltage control (held at the limited Q via
    ``net._vsc_vcontrol_disabled``), and a droop converter switches to
    constant active power (``net._vsc_droop_disabled``). These latches persist
    for the remainder of the solve.

    Vdc-slack converters are exempt: their power is fixed by the DC grid power
    balance, not a setpoint, so it cannot be curtailed (MatACDC removes slack
    converters from the convlim check).

    Returns True if any converter was corrected.
    """
    conv_data = net._conv_data
    n_vsc = conv_data["n_vsc"]

    vcontrol_disabled = net._vsc_vcontrol_disabled
    droop_disabled = net._vsc_droop_disabled

    # 1) Evaluate every non-slack converter; collect violations per DC grid.
    by_grid = {}
    for i in range(n_vsc):
        control = str(conv_data["vsc_control"][i])
        if "vdc" in control:  # slack converters are exempt
            continue

        viol, p_new, q_new = _converter_limit_candidate(net, conv_data, i)
        if viol == 0:
            continue

        vsc_idx = conv_data["vsc_indices"][i]
        dc_bus = int(conv_data["vsc_dc_bus"][i])
        grid = int(net.dc_bus.loc[dc_bus, "dc_grid"]) if dc_bus in net.dc_bus.index else 0
        d_p = abs(p_new - net._p_s[vsc_idx])
        d_q = abs(q_new - net._q_s[vsc_idx])
        by_grid.setdefault(grid, []).append(
            {"vsc_idx": vsc_idx, "control": control, "viol": viol,
             "p_new": p_new, "q_new": q_new, "d_p": d_p, "d_q": d_q}
        )

    if not by_grid:
        return False

    # 2) Correct exactly one converter per DC grid (P-violations take priority).
    limit_hit = False
    for cands in by_grid.values():
        p_viol = [c for c in cands if c["viol"] == 2]
        if p_viol:
            sel = max(p_viol, key=lambda c: c["d_p"])
        else:
            sel = max(cands, key=lambda c: c["d_q"])

        vsc_idx = sel["vsc_idx"]
        net._p_s[vsc_idx] = sel["p_new"]
        net._q_s[vsc_idx] = sel["q_new"]
        limit_hit = True

        if "vac" in sel["control"]:
            vcontrol_disabled.add(vsc_idx)
        if "droop" in sel["control"]:
            droop_disabled.add(vsc_idx)

    return limit_hit


def _update_slack_droop_powers(net: Network) -> None:
    """
    Update DC slack and droop bus powers after DC power flow.

    For slack/droop VSCs, the DC power flow determines the new P_DC.
    We then solve the converter equations backward to find new P_s.
    (Eq. 13.71-13.76, Figure 13.12 in Beerten)
    """
    conv_data = net._conv_data
    n_vsc = conv_data["n_vsc"]
    droop_disabled = getattr(net, "_vsc_droop_disabled", set())

    for i in range(n_vsc):
        vsc_idx = conv_data["vsc_indices"][i]
        control = str(conv_data["vsc_control"][i])

        if "vdc" not in control and "droop" not in control:
            continue

        # A droop converter whose control was disabled on a limit violation
        # becomes constant active power: keep its clamped P_s, no droop update.
        if "droop" in control and vsc_idx in droop_disabled:
            continue

        dc_bus = int(conv_data["vsc_dc_bus"][i])
        ac_bus = int(conv_data["vsc_ac_bus"][i])

        # Get V_dc from DC power flow
        if dc_bus < len(net._v_dc):
            v_dc_pu = net._v_dc[dc_bus]
        else:
            v_dc_pu = 1.0

        # For droop buses, compute P_DC from droop equation
        if "droop" in control:
            k_kv_mw = conv_data["vsc_droop_k"][i]
            v_base = float(net.dc_bus.loc[dc_bus, "v_base"])
            p0 = conv_data["vsc_p_dc_set"][i]
            v0 = conv_data["vsc_v_dc_droop_set"][i]
            # P_DC = P0 - (V_dc - V0) * V_base / k  (minus for stability)
            if k_kv_mw != 0:
                p_dc_new = p0 - (v_dc_pu - v0) * v_base / k_kv_mw
            else:
                p_dc_new = p0
            net._p_dc_vsc[vsc_idx] = p_dc_new

        # For Vdc slack, compute P_DC from DC voltage solution
        if "vdc" in control:
            G_dc = build_dc_conductance_matrix(net)
            G_dense = G_dc.toarray()
            v_dc_arr = net._v_dc
            pol = float(net.pol)
            p_calc_pu = pol * v_dc_arr[dc_bus] * np.dot(G_dense[dc_bus, :], v_dc_arr)
            # p_calc is the total net injection: p_vsc + gen - load.
            # Extract the VSC portion: p_vsc = p_calc + load - gen
            p_load_mw = 0.0
            p_gen_mw = 0.0
            if not net.dc_load.empty:
                bus_loads = net.dc_load[(net.dc_load["bus"] == dc_bus) & (net.dc_load["in_service"] == True)]
                for _, ld in bus_loads.iterrows():
                    if str(ld.get("load_type", "constant_power")) == "constant_impedance":
                        continue
                    p_load_mw += float(ld["p_mw"])
            if not net.dc_gen.empty:
                bus_gens = net.dc_gen[(net.dc_gen["bus"] == dc_bus) & (net.dc_gen["in_service"] == True)]
                p_gen_mw = bus_gens["p_mw"].astype(float).sum()
            net._p_dc_vsc[vsc_idx] = p_calc_pu * net.s_base + p_load_mw - p_gen_mw

        # Backward solve: given P_DC, find P_s
        # Inner NR iteration (Eq. 13.71-13.76)
        p_dc = net._p_dc_vsc[vsc_idx]
        _backward_converter_solve(net, i, vsc_idx, p_dc)


def _backward_converter_solve(net: Network, conv_i: int, vsc_idx: int, p_dc_mw: float):
    """
    Given P_DC, solve converter equations backward to find P_s.

    Uses iterative approach:
    1. Estimate P_c = P_DC (initially, assume zero losses)
    2. Given P_c and V_s, solve for converter current
    3. Calculate losses
    4. Update P_c = P_DC + P_loss
    5. Iterate until P_c converges
    """
    conv_data = net._conv_data
    ac_bus = int(conv_data["vsc_ac_bus"][conv_i])

    if ac_bus < len(net._v_mag):
        v_s_mag = net._v_mag[ac_bus]
        v_s_ang = net._v_ang[ac_bus]
    else:
        v_s_mag = 1.0
        v_s_ang = 0.0

    v_s = v_s_mag * np.exp(1j * v_s_ang)

    r_tf = conv_data["vsc_r_tf"][conv_i]
    x_tf = conv_data["vsc_x_tf"][conv_i]
    r_c = conv_data["vsc_r_c"][conv_i]
    x_c = conv_data["vsc_x_c"][conv_i]
    b_f = conv_data["vsc_b_filter"][conv_i]

    # Loss coefficients (per-unit conversion matching MatACDC)
    loss_base_kv = conv_data["vsc_loss_base_kv"][conv_i]
    base_kv_ac = loss_base_kv if loss_base_kv > 0 else float(net.ac_bus.loc[ac_bus, "vr_kv"])

    z_tf = complex(r_tf, x_tf)
    z_c = complex(r_c, x_c)
    base_ka = net.s_base / (np.sqrt(3) * base_kv_ac)
    loss_a = conv_data["vsc_loss_a"][conv_i] / net.s_base
    loss_b = conv_data["vsc_loss_b"][conv_i] * base_ka / net.s_base
    loss_c_rec = conv_data["vsc_loss_c"][conv_i] * base_ka ** 2 / net.s_base
    loss_c_inv = conv_data["vsc_loss_c_inv"][conv_i] * base_ka ** 2 / net.s_base

    q_s = net._q_s[vsc_idx] / net.s_base
    p_dc_pu = p_dc_mw / net.s_base

    # Inner iteration
    p_s_pu = p_dc_pu  # Initial estimate (lossless)
    for _ in range(20):
        s_s = complex(p_s_pu, q_s)

        if abs(v_s) > 1e-10:
            i_tf = np.conj(s_s / v_s)
        else:
            i_tf = 0.0

        v_f = v_s - i_tf * z_tf
        s_sf = v_f * np.conj(i_tf)
        q_f = -b_f * abs(v_f) ** 2
        s_cf = s_sf + 1j * q_f

        if abs(v_f) > 1e-10:
            i_c = np.conj(s_cf / v_f)
        else:
            i_c = 0.0

        # Converter voltage and power (2-impedance model)
        v_c = v_f - i_c * z_c
        s_c = v_c * np.conj(i_c)
        p_c = s_c.real
        q_c = s_c.imag

        # Converter losses using converter-side current
        i_c_mag = np.sqrt(p_c ** 2 + q_c ** 2) / abs(v_c) if abs(v_c) > 1e-10 else abs(i_c)
        loss_c_used = loss_c_inv if p_c > 0 else loss_c_rec
        p_loss = loss_a + loss_b * i_c_mag + loss_c_used * i_c_mag ** 2

        # P_DC = P_c - P_loss => P_c = P_DC + P_loss
        p_c_target = p_dc_pu + p_loss

        # With corrected V signs: P_c = P_s - R_tf*|I_tf|² - R_c*|I_c|²
        # So P_s = P_c + R losses (add back impedance losses)
        p_s_new = p_c_target + r_c * abs(i_c) ** 2 + r_tf * abs(i_tf) ** 2

        if abs(p_s_new - p_s_pu) < 1e-10:
            break
        p_s_pu = p_s_new

    net._p_s[vsc_idx] = p_s_pu * net.s_base


def _store_results(net: Network) -> None:
    """Store power flow results in net.res_* DataFrames."""
    has_ac = len(net.ac_bus) > 0
    has_dc = len(net.dc_bus) > 0

    if has_ac:
        process_ac_results(net, net._v_mag, net._v_ang)

    if has_dc:
        process_dc_results(net, net._v_dc)

    process_converter_results(net)
