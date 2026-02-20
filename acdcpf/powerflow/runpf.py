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

import numpy as np


def run_pf(
    net: Network,
    max_iter_outer: int = 30,
    max_iter_inner: int = 30,
    tol: float = 1e-8,
    verbose: bool = False,
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

    # Initialize converter powers
    _initialize_converter_powers(net)

    # Main sequential AC/DC iteration loop
    converged = False
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
            print(f"Outer iter {outer_iter}: max|dP_s| = {max_dp:.2e}")

        if max_dp < tol:
            converged = True
            break

    # Store results
    net.converged = converged
    _store_results(net)

    return converged


def _get_vsc_v_control(net: Network) -> dict:
    """Get mapping of AC bus -> voltage setpoint for Vac-controlling VSCs."""
    vsc_v_control = {}
    if net.vsc.empty:
        return vsc_v_control

    conv_data = net._conv_data
    for i, vsc_idx in enumerate(conv_data["vsc_indices"]):
        control = str(conv_data["vsc_control"][i])
        if "vac" in control:
            ac_bus = int(conv_data["vsc_ac_bus"][i])
            v_set = float(conv_data["vsc_v_ac_set"][i])
            if not np.isnan(v_set):
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

    # For each Vac-controlling VSC, find the generator Q in the pypower results
    for i, vsc_idx in enumerate(conv_data["vsc_indices"]):
        control = str(conv_data["vsc_control"][i])
        if "vac" not in control:
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
                    q_mvar = gen_row[QG]
                    net._q_s[vsc_idx] = q_mvar
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

        # DC loads (consumption)
        if not net.dc_load.empty:
            for _, load in net.dc_load[net.dc_load["in_service"] == True].iterrows():
                if int(load["bus"]) in grid_buses:
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
        z_tf = complex(r_tf, x_tf)
        r_c = conv_data["vsc_r_c"][i]
        x_c = conv_data["vsc_x_c"][i]
        z_c = complex(r_c, x_c)
        b_f = conv_data["vsc_b_filter"][i]

        # Loss coefficients (per-unit conversion matching MatACDC)
        # LossA in MW, LossB in kV, LossC in Ohm
        s_mva = conv_data["vsc_s_mva"][i]
        loss_base_kv = conv_data["vsc_loss_base_kv"][i]
        base_kv_ac = loss_base_kv if loss_base_kv > 0 else float(net.ac_bus.loc[ac_bus, "vr_kv"])
        base_ka = net.s_base / (np.sqrt(3) * base_kv_ac)
        loss_a = conv_data["vsc_loss_a"][i] / net.s_base  # MW -> pu
        loss_b = conv_data["vsc_loss_b"][i] * base_ka / net.s_base  # kV -> pu
        loss_c = conv_data["vsc_loss_c"][i] * base_ka ** 2 / net.s_base  # Ohm -> pu

        # Transformer current (Eq. 13.11)
        if abs(v_s) > 1e-10:
            i_tf = np.conj(s_s / v_s)
        else:
            i_tf = 0.0

        # Filter bus voltage using only Z_tf (Eq. 13.12)
        v_f = v_s + i_tf * z_tf

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

        # Converter voltage (across phase reactor)
        v_c = v_f + i_c * z_c

        # Converter-side power (for loss calculation)
        s_c = v_c * np.conj(i_c)
        p_c = s_c.real
        q_c = s_c.imag

        # Converter losses (Eq. 13.9) using converter-side current
        i_c_mag = np.sqrt(p_c ** 2 + q_c ** 2) / abs(v_c) if abs(v_c) > 1e-10 else abs(i_c)
        p_loss = loss_a + loss_b * i_c_mag + loss_c * i_c_mag ** 2

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


def _calculate_converter_losses(net: Network) -> np.ndarray:
    """Calculate converter losses (called as part of converter equations)."""
    conv_data = net._conv_data
    n_vsc = conv_data["n_vsc"]
    losses = np.zeros(len(net.vsc)) if not net.vsc.empty else np.array([])

    if hasattr(net, '_vsc_internal'):
        for vsc_idx, internal in net._vsc_internal.items():
            losses[vsc_idx] = internal['p_loss']

    return losses


def _check_converter_limits(net: Network) -> bool:
    """
    Check and enforce converter limits.

    Checks current limits (PQ capability circle) and voltage limits.
    Returns True if any limit was hit and setpoints were adjusted.
    """
    conv_data = net._conv_data
    n_vsc = conv_data["n_vsc"]
    limit_hit = False

    for i in range(n_vsc):
        vsc_idx = conv_data["vsc_indices"][i]
        s_rated = conv_data["vsc_s_mva"][i]

        p_s = net._p_s[vsc_idx]
        q_s = net._q_s[vsc_idx]
        s_actual = np.sqrt(p_s ** 2 + q_s ** 2)

        # Check current limit (Eq. 13.28-13.30)
        if s_rated > 0 and s_actual > s_rated:
            # Reduce Q first (priority: P > Q)
            q_max = np.sqrt(max(s_rated ** 2 - p_s ** 2, 0))
            if abs(q_s) > q_max:
                net._q_s[vsc_idx] = np.sign(q_s) * q_max
                limit_hit = True

            # If still over, reduce P
            s_actual = np.sqrt(net._p_s[vsc_idx] ** 2 + net._q_s[vsc_idx] ** 2)
            if s_actual > s_rated:
                scale = s_rated / s_actual
                net._p_s[vsc_idx] *= scale
                net._q_s[vsc_idx] *= scale
                limit_hit = True

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

    for i in range(n_vsc):
        vsc_idx = conv_data["vsc_indices"][i]
        control = str(conv_data["vsc_control"][i])

        if "vdc" not in control and "droop" not in control:
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
            net._p_dc_vsc[vsc_idx] = p_calc_pu * net.s_base

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
    z_tf = complex(r_tf, x_tf)
    r_c = conv_data["vsc_r_c"][conv_i]
    x_c = conv_data["vsc_x_c"][conv_i]
    z_c = complex(r_c, x_c)
    b_f = conv_data["vsc_b_filter"][conv_i]

    # Loss coefficients (per-unit conversion matching MatACDC)
    loss_base_kv = conv_data["vsc_loss_base_kv"][conv_i]
    base_kv_ac = loss_base_kv if loss_base_kv > 0 else float(net.ac_bus.loc[ac_bus, "vr_kv"])
    base_ka = net.s_base / (np.sqrt(3) * base_kv_ac)
    loss_a = conv_data["vsc_loss_a"][conv_i] / net.s_base
    loss_b = conv_data["vsc_loss_b"][conv_i] * base_ka / net.s_base
    loss_c = conv_data["vsc_loss_c"][conv_i] * base_ka ** 2 / net.s_base

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

        v_f = v_s + i_tf * z_tf
        s_sf = v_f * np.conj(i_tf)
        q_f = -b_f * abs(v_f) ** 2
        s_cf = s_sf + 1j * q_f

        if abs(v_f) > 1e-10:
            i_c = np.conj(s_cf / v_f)
        else:
            i_c = 0.0

        # Converter voltage and power (2-impedance model)
        v_c = v_f + i_c * z_c
        s_c = v_c * np.conj(i_c)
        p_c = s_c.real
        q_c = s_c.imag

        # Converter losses using converter-side current
        i_c_mag = np.sqrt(p_c ** 2 + q_c ** 2) / abs(v_c) if abs(v_c) > 1e-10 else abs(i_c)
        p_loss = loss_a + loss_b * i_c_mag + loss_c * i_c_mag ** 2

        # P_DC = P_c - P_loss => P_c = P_DC + P_loss
        p_c_target = p_dc_pu + p_loss

        # Update P_s: account for losses through both impedances
        # P_s ≈ p_c_target + R_c * |I_c|² + R_tf * |I_tf|²
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
