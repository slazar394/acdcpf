"""
DC power flow using Newton-Raphson method.

Implements the DC network power flow from Beerten Chapter 13,
Eq. 13.61-13.70. Handles slack, P-controlled, and droop buses.
"""

from ..build.dc import build_dc_conductance_matrix, build_dc_bus_data
from ..network import Network

from scipy.sparse.linalg import spsolve
from typing import Tuple
from scipy import sparse

import numpy as np


def run_dc_pf(
    net: Network,
    p_dc_vsc: np.ndarray = None,
    max_iter: int = 30,
    tol: float = 1e-8,
) -> Tuple[np.ndarray, bool, int]:
    """
    Run DC power flow using Newton-Raphson method.

    Parameters
    ----------
    net : Network
        The network object with DC data
    p_dc_vsc : np.ndarray, optional
        VSC DC-side power injections (MW)
    max_iter : int, optional
        Maximum number of iterations (default: 30)
    tol : float, optional
        Convergence tolerance (default: 1e-8)

    Returns
    -------
    tuple
        (v_dc, converged, iterations) where v_dc is in per-unit
    """
    n_dc = len(net.dc_bus)
    if n_dc == 0:
        return np.array([]), True, 0

    # Build conductance matrix and bus data
    G_dc = build_dc_conductance_matrix(net)
    v_dc_init, p_spec, slack_mask, droop_mask, p_mask = build_dc_bus_data(
        net, p_dc_vsc
    )

    max_idx = net.dc_bus.index.max()
    n = max_idx + 1

    # Collect active bus indices
    active_buses = []
    for idx in net.dc_bus.index:
        if net.dc_bus.loc[idx, "in_service"]:
            active_buses.append(idx)
    active_buses = np.array(active_buses)

    # Find slack buses (to exclude from NR)
    slack_buses = active_buses[slack_mask[active_buses]]
    non_slack = active_buses[~slack_mask[active_buses]]

    if len(non_slack) == 0:
        # Only slack buses, trivially solved
        return v_dc_init, True, 0

    # Build droop parameters for non-slack droop buses
    droop_params = _build_droop_params(net, non_slack, droop_mask)

    # NR iteration
    v_dc = v_dc_init.copy()
    converged = False
    iteration = 0

    # Number of poles: 2 for symmetric monopole / bipole
    pol = float(net.pol)

    G_dense = G_dc.toarray()

    for iteration in range(1, max_iter + 1):
        # Calculate power mismatch
        mismatch = calc_dc_power_mismatch(
            v_dc, G_dense, p_spec, non_slack, droop_mask, droop_params, pol
        )

        # Check convergence
        max_mis = np.max(np.abs(mismatch))
        if max_mis < tol:
            converged = True
            break

        # Build Jacobian
        J = build_dc_jacobian(
            v_dc, G_dense, non_slack, droop_mask, droop_params, pol
        )

        # Solve for voltage updates: standard NR: dV = -J^{-1} * F
        # where J = dF/dV and F = mismatch
        try:
            dv = np.linalg.solve(J, -mismatch)
        except np.linalg.LinAlgError:
            break

        # Update voltages at non-slack buses
        v_dc[non_slack] += dv

    # Recalculate slack bus power
    for s in slack_buses:
        p_calc = pol * v_dc[s] * np.sum(G_dense[s, :] * v_dc)
        p_spec[s] = p_calc

    return v_dc, converged, iteration


def _build_droop_params(net, non_slack, droop_mask):
    """Build droop parameter dict for droop buses."""
    params = {}
    if not net.vsc.empty:
        vsc_is = net.vsc[net.vsc["in_service"] == True]
        for vsc_idx, vsc_row in vsc_is.iterrows():
            dc_bus = int(vsc_row["dc_bus"])
            if dc_bus in non_slack and droop_mask[dc_bus]:
                control = str(vsc_row["control_mode"])
                if "droop" in control:
                    k_kv_mw = float(vsc_row["droop_kv_per_mw"]) if vsc_row["droop_kv_per_mw"] is not None else 0.0
                    v_base = float(net.dc_bus.loc[dc_bus, "v_base"])
                    # Convert droop from kV/MW to pu/pu
                    # k_pu = k_kv_mw * s_base / v_base
                    if k_kv_mw != 0:
                        k_pu = k_kv_mw * net.s_base / v_base
                    else:
                        k_pu = 0.0

                    p0 = float(vsc_row["p_dc_set_mw"]) / net.s_base if vsc_row["p_dc_set_mw"] is not None else 0.0
                    v0 = float(vsc_row["v_dc_set_pu"]) if vsc_row["v_dc_set_pu"] is not None else 1.0

                    params[dc_bus] = {"k_pu": k_pu, "p0": p0, "v0": v0}
    return params


def calc_dc_power_mismatch(
    v_dc: np.ndarray,
    G_dc: np.ndarray,
    p_spec: np.ndarray,
    non_slack: np.ndarray,
    droop_mask: np.ndarray,
    droop_params: dict,
    pol: float = 1.0,
) -> np.ndarray:
    """
    Calculate DC power mismatch at non-slack buses.

    For P-controlled buses (Eq. 13.61-13.62):
        mismatch = P_spec - P_calc
    For droop buses (Eq. 13.66-13.68):
        mismatch = P_dc0 + (1/k)*(V - V0) - P_calc

    Parameters
    ----------
    v_dc : np.ndarray
        DC voltages (pu)
    G_dc : np.ndarray
        DC conductance matrix (dense)
    p_spec : np.ndarray
        Specified power injections (pu)
    non_slack : np.ndarray
        Non-slack bus indices
    droop_mask : np.ndarray
        Boolean mask for droop buses
    droop_params : dict
        Droop parameters per bus
    pol : float
        Polarity (default: 1.0)

    Returns
    -------
    np.ndarray
        Power mismatch vector for non-slack buses
    """
    n_ns = len(non_slack)
    mismatch = np.zeros(n_ns)

    for ii, i in enumerate(non_slack):
        # P_calc = pol * V_i * sum(G_ij * V_j)
        p_calc = pol * v_dc[i] * np.dot(G_dc[i, :], v_dc)

        if droop_mask[i] and i in droop_params:
            dp = droop_params[i]
            k_pu = dp["k_pu"]
            p0 = dp["p0"]
            v0 = dp["v0"]
            # Droop equation: P = P0 - (1/k)*(V - V0)
            # Minus sign for stability: higher V → less injection → V drops
            if k_pu != 0:
                p_droop = p0 - (1.0 / k_pu) * (v_dc[i] - v0)
            else:
                p_droop = p0
            mismatch[ii] = p_droop - p_calc
        else:
            mismatch[ii] = p_spec[i] - p_calc

    return mismatch


def build_dc_jacobian(
    v_dc: np.ndarray,
    G_dc: np.ndarray,
    non_slack: np.ndarray,
    droop_mask: np.ndarray,
    droop_params: dict,
    pol: float = 1.0,
) -> np.ndarray:
    """
    Build the DC Jacobian matrix for non-slack buses.

    Off-diagonal (Eq. 13.63-13.64):
        J_ij = -pol * V_i * G_ij
    Diagonal (Eq. 13.63-13.64):
        J_ii = -(P_calc_i / V_i + pol * V_i * G_ii)
    For droop buses (Eq. 13.69-13.70):
        Add -(1/k) to diagonal

    Parameters
    ----------
    v_dc : np.ndarray
        DC voltages (pu)
    G_dc : np.ndarray
        DC conductance matrix (dense)
    non_slack : np.ndarray
        Non-slack bus indices
    droop_mask : np.ndarray
        Boolean mask for droop buses
    droop_params : dict
        Droop parameters per bus
    pol : float
        Polarity (default: 1.0)

    Returns
    -------
    np.ndarray
        Jacobian matrix (n_ns x n_ns)
    """
    n_ns = len(non_slack)
    J = np.zeros((n_ns, n_ns))

    for ii, i in enumerate(non_slack):
        p_calc = pol * v_dc[i] * np.dot(G_dc[i, :], v_dc)

        for jj, j in enumerate(non_slack):
            if ii == jj:
                # Diagonal: -(P_calc/V_i + pol * V_i * G_ii)
                # = -(pol * sum(G_ij * V_j) + pol * V_i * G_ii)
                # Simplified: derivative of mismatch w.r.t. V_i
                J[ii, ii] = -(p_calc / v_dc[i] + pol * v_dc[i] * G_dc[i, i])

                # Droop contribution: dF/dV includes -1/k from droop term
                if droop_mask[i] and i in droop_params:
                    k_pu = droop_params[i]["k_pu"]
                    if k_pu != 0:
                        J[ii, ii] -= 1.0 / k_pu
            else:
                # Off-diagonal
                J[ii, jj] = -pol * v_dc[i] * G_dc[i, j]

    # The Jacobian is for mismatch = P_spec - P_calc, so dMismatch/dV
    # We need -J for NR: J * dV = mismatch => dV = J^-1 * mismatch
    # Since we defined J as the negative of the derivative, we solve J*dV = mismatch
    return J
