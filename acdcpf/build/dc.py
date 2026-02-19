"""
Build DC bus-branch model.
"""

from ..network import Network
from scipy import sparse
from typing import Tuple

import numpy as np


def build_dc_conductance_matrix(net: Network) -> sparse.csr_matrix:
    """
    Build the DC bus conductance matrix (G_dc).

    Constructs the conductance matrix from DC line resistances.
    G_ij = -1/R_ij for off-diagonal, G_ii = sum(1/R_ij) for diagonal.
    (Eq. 13.38-13.40 in Beerten)

    Parameters
    ----------
    net : Network
        The network object

    Returns
    -------
    scipy.sparse.csr_matrix
        The bus conductance matrix G_dc
    """
    n_bus = len(net.dc_bus)
    if n_bus == 0:
        return sparse.csr_matrix((0, 0))

    max_idx = net.dc_bus.index.max()
    n = max_idx + 1
    G = sparse.lil_matrix((n, n))

    if not net.dc_line.empty:
        lines = net.dc_line[net.dc_line["in_service"] == True]
        for _, line in lines.iterrows():
            fb = int(line["from_bus"])
            tb = int(line["to_bus"])
            r_total = float(line["r_ohm_per_km"]) * float(line["length_km"])

            # Convert to per-unit conductance
            v_base_fb = float(net.dc_bus.loc[fb, "v_base"])  # kV
            z_base = v_base_fb ** 2 / net.s_base  # Ohm (using system MVA base)
            g_pu = z_base / r_total if r_total > 0 else 0.0

            G[fb, fb] += g_pu
            G[tb, tb] += g_pu
            G[fb, tb] -= g_pu
            G[tb, fb] -= g_pu

    # Add DC-DC converter branches (transformer model)
    if not net.dcdc.empty:
        dcdcs = net.dcdc[net.dcdc["in_service"] == True]
        for _, dcdc in dcdcs.iterrows():
            m = int(dcdc["from_bus"])   # V_m side (high voltage)
            c = int(dcdc["to_bus"])     # V_c side (low voltage)
            d_ratio = float(dcdc["d_ratio"])
            r_ohm = float(dcdc["r_ohm"])
            g_us_val = float(dcdc["g_us"])

            # Per-unit turns ratio
            v_m_base = float(net.dc_bus.loc[m, "v_base"])  # kV
            v_c_base = float(net.dc_bus.loc[c, "v_base"])  # kV
            d_pu = d_ratio * v_m_base / v_c_base

            # Series conductance in system pu (on V_c base)
            z_base_c = v_c_base ** 2 / net.s_base
            g_series = z_base_c / r_ohm if r_ohm > 0 else 0.0

            # Shunt conductance in system pu (on V_m base)
            g_shunt = g_us_val * 1e-6 * v_m_base ** 2 / net.s_base

            # Transformer branch contributions
            G[m, m] += d_pu ** 2 * g_series + g_shunt
            G[m, c] -= d_pu * g_series
            G[c, m] -= d_pu * g_series
            G[c, c] += g_series

    return G.tocsr()


def build_dc_bus_data(
    net: Network,
    p_dc_vsc: np.ndarray = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Build DC bus data arrays for power flow.

    Aggregates power injections from VSC converters,
    DC loads, and DC generators at each DC bus.

    Parameters
    ----------
    net : Network
        The network object
    p_dc_vsc : np.ndarray, optional
        VSC DC-side power injections (MW), indexed by VSC index.
        Positive = injecting into DC grid.

    Returns
    -------
    tuple
        (v_dc_init, p_spec, slack_mask, droop_mask, p_mask)
        - v_dc_init: initial DC voltages (pu)
        - p_spec: specified power at each bus (pu, on system base)
        - slack_mask: boolean mask for slack buses
        - droop_mask: boolean mask for droop buses
        - p_mask: boolean mask for P-controlled buses
    """
    n_bus = len(net.dc_bus)
    if n_bus == 0:
        empty = np.array([])
        return empty, empty, np.array([], dtype=bool), np.array([], dtype=bool), np.array([], dtype=bool)

    max_idx = net.dc_bus.index.max()
    n = max_idx + 1

    v_dc_init = np.ones(n)
    p_spec = np.zeros(n)  # MW
    slack_mask = np.zeros(n, dtype=bool)
    droop_mask = np.zeros(n, dtype=bool)
    p_mask = np.zeros(n, dtype=bool)

    # Set bus types and initial voltages from dc_bus data
    for idx, row in net.dc_bus.iterrows():
        if not row["in_service"]:
            continue
        v_dc_init[idx] = float(row["v_dc_pu"])
        btype = str(row["bus_type"]).lower()
        if btype == "vdc":
            slack_mask[idx] = True
        elif btype == "droop":
            droop_mask[idx] = True
        else:
            p_mask[idx] = True

    # Add VSC DC-side power injections
    # Convention: P_dc_vsc > 0 = rectifier = power INTO DC bus (positive injection)
    if p_dc_vsc is not None and not net.vsc.empty:
        vsc_is = net.vsc[net.vsc["in_service"] == True]
        for vsc_idx, vsc_row in vsc_is.iterrows():
            dc_bus = int(vsc_row["dc_bus"])
            if vsc_idx < len(p_dc_vsc):
                p_spec[dc_bus] += p_dc_vsc[vsc_idx]

    # Subtract DC loads (load = positive consumption = negative injection)
    if not net.dc_load.empty:
        loads = net.dc_load[net.dc_load["in_service"] == True]
        for _, load in loads.iterrows():
            bus = int(load["bus"])
            p_spec[bus] -= float(load["p_mw"])

    # Add DC generators (positive injection)
    if not net.dc_gen.empty:
        gens = net.dc_gen[net.dc_gen["in_service"] == True]
        for _, gen in gens.iterrows():
            bus = int(gen["bus"])
            p_spec[bus] += float(gen["p_mw"])

    # Convert MW to per-unit
    p_spec /= net.s_base

    return v_dc_init, p_spec, slack_mask, droop_mask, p_mask
