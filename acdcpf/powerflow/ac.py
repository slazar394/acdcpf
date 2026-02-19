"""
AC power flow using pypower as backend.

Delegates the Newton-Raphson AC power flow to pypower, converting
between our Network format and pypower's case format.
"""

import numpy as np
from scipy import sparse
from typing import Tuple, Dict, List
from ..network import Network

# pypower imports
from pypower.api import runpf, ppoption
from pypower.idx_bus import (
    BUS_I, BUS_TYPE, PD, QD, GS, BS, BUS_AREA, VM, VA,
    BASE_KV, ZONE, VMAX, VMIN, PQ, PV, REF, NONE,
)
from pypower.idx_gen import (
    GEN_BUS, PG, QG, QMAX, QMIN, VG, MBASE, GEN_STATUS,
    PMAX, PMIN,
)
from pypower.idx_brch import (
    F_BUS, T_BUS, BR_R, BR_X, BR_B, RATE_A, RATE_B, RATE_C,
    TAP, SHIFT, BR_STATUS, PF, QF, PT, QT,
)


def _find_ac_islands(net: Network):
    """
    Find connected components (islands) in the AC network.

    Returns a list of lists, where each inner list contains
    the AC bus indices belonging to that island.
    """
    n_bus = len(net.ac_bus)
    if n_bus == 0:
        return []

    bus_indices = net.ac_bus.index.tolist()
    # Build adjacency list
    adj = {b: [] for b in bus_indices}

    lines = net.ac_line[net.ac_line["in_service"] == True]
    for _, line in lines.iterrows():
        fb = int(line["from_bus"])
        tb = int(line["to_bus"])
        if fb in adj and tb in adj:
            adj[fb].append(tb)
            adj[tb].append(fb)

    # BFS to find connected components
    visited = set()
    islands = []
    for bus in bus_indices:
        if bus not in visited:
            component = []
            queue = [bus]
            while queue:
                b = queue.pop(0)
                if b in visited:
                    continue
                visited.add(b)
                component.append(b)
                for nb in adj[b]:
                    if nb not in visited:
                        queue.append(nb)
            islands.append(sorted(component))

    return islands


def _net_to_ppc(net: Network, island_buses: List[int],
                p_vsc: np.ndarray, q_vsc: np.ndarray,
                vsc_v_control: Dict[int, float]) -> dict:
    """
    Convert Network DataFrames to pypower case format for a single AC island.

    Parameters
    ----------
    net : Network
        The network object
    island_buses : list of int
        AC bus indices belonging to this island
    p_vsc : np.ndarray
        VSC active power injections at AC buses (MW), indexed by VSC index
    q_vsc : np.ndarray
        VSC reactive power injections at AC buses (MVAr), indexed by VSC index
    vsc_v_control : dict
        Mapping from AC bus index to voltage setpoint for Vac-controlling VSCs

    Returns
    -------
    dict
        pypower case dict with "bus", "gen", "branch", "baseMVA", "version"
    """
    island_set = set(island_buses)
    n_bus = len(island_buses)

    # Create mapping from external bus index to internal (0-based) index
    ext2int = {ext: i for i, ext in enumerate(island_buses)}

    # --- Build bus matrix ---
    bus_data = np.zeros((n_bus, 13))
    for i, ext_idx in enumerate(island_buses):
        row = net.ac_bus.loc[ext_idx]
        bus_data[i, BUS_I] = i
        bus_data[i, BUS_TYPE] = PQ  # default PQ, updated below
        bus_data[i, PD] = 0.0
        bus_data[i, QD] = 0.0
        bus_data[i, GS] = 0.0
        bus_data[i, BS] = 0.0
        bus_data[i, BUS_AREA] = 1
        bus_data[i, VM] = 1.0
        bus_data[i, VA] = 0.0
        bus_data[i, BASE_KV] = float(row["vr_kv"])
        bus_data[i, ZONE] = 1
        bus_data[i, VMAX] = float(row["v_max_pu"])
        bus_data[i, VMIN] = float(row["v_min_pu"])

    # Aggregate loads at buses
    if not net.ac_load.empty:
        loads = net.ac_load[net.ac_load["in_service"] == True]
        for _, load in loads.iterrows():
            bus_ext = int(load["bus"])
            if bus_ext in ext2int:
                i = ext2int[bus_ext]
                bus_data[i, PD] += float(load["p_mw"])
                bus_data[i, QD] += float(load["q_mvar"])

    # Add VSC injections as negative loads at PCC buses
    if not net.vsc.empty:
        vsc_is = net.vsc[net.vsc["in_service"] == True]
        for vsc_idx, vsc_row in vsc_is.iterrows():
            ac_bus_ext = int(vsc_row["ac_bus"])
            if ac_bus_ext in ext2int:
                i = ext2int[ac_bus_ext]
                # VSC convention: P_s > 0 = rectifier (AC→DC) = load on AC side
                bus_data[i, PD] += p_vsc[vsc_idx]
                # For Vac-controlling VSCs, Q is handled by the dummy generator
                # Don't add Q as load to avoid double-counting
                if ac_bus_ext not in vsc_v_control:
                    bus_data[i, QD] += q_vsc[vsc_idx]

    # --- Build generator matrix ---
    gen_list = []
    if not net.ac_gen.empty:
        gens = net.ac_gen[net.ac_gen["in_service"] == True]
        for _, gen in gens.iterrows():
            bus_ext = int(gen["bus"])
            if bus_ext not in ext2int:
                continue
            i = ext2int[bus_ext]
            g = np.zeros(21)
            g[GEN_BUS] = i
            g[PG] = float(gen["p_mw"])
            g[QG] = float(gen["q_mvar"])
            g[QMAX] = float(gen["q_max_mvar"])
            g[QMIN] = float(gen["q_min_mvar"])
            v_pu = gen.get("v_pu")
            if v_pu is not None and not (isinstance(v_pu, float) and np.isnan(v_pu)):
                g[VG] = float(v_pu)
                bus_data[i, BUS_TYPE] = PV
                bus_data[i, VM] = float(v_pu)
            else:
                g[VG] = 1.0
            g[MBASE] = net.s_base
            g[GEN_STATUS] = 1
            g[PMAX] = 9999.0
            g[PMIN] = -9999.0
            gen_list.append(g)

    # Add dummy generators for Vac-controlling VSCs
    for ac_bus_ext, v_set in vsc_v_control.items():
        if ac_bus_ext not in ext2int:
            continue
        i = ext2int[ac_bus_ext]
        # Only add dummy gen if this bus isn't already a PV/REF bus
        if bus_data[i, BUS_TYPE] == PQ:
            bus_data[i, BUS_TYPE] = PV
            bus_data[i, VM] = v_set
        g = np.zeros(21)
        g[GEN_BUS] = i
        g[PG] = 0.0  # P already handled via load injection
        g[QG] = 0.0
        g[QMAX] = 9999.0
        g[QMIN] = -9999.0
        g[VG] = v_set
        g[MBASE] = net.s_base
        g[GEN_STATUS] = 1
        g[PMAX] = 0.0  # Zero P - only for voltage control
        g[PMIN] = 0.0
        gen_list.append(g)

    # Ensure at least one slack bus (first generator's bus becomes REF)
    has_ref = False
    for i in range(n_bus):
        if bus_data[i, BUS_TYPE] == REF:
            has_ref = True
            break

    if not has_ref and gen_list:
        ref_bus_int = int(gen_list[0][GEN_BUS])
        bus_data[ref_bus_int, BUS_TYPE] = REF

    # If no generators at all, make first bus a REF with dummy gen
    if not gen_list:
        bus_data[0, BUS_TYPE] = REF
        g = np.zeros(21)
        g[GEN_BUS] = 0
        g[PG] = 0.0
        g[QG] = 0.0
        g[QMAX] = 9999.0
        g[QMIN] = -9999.0
        g[VG] = 1.0
        g[MBASE] = net.s_base
        g[GEN_STATUS] = 1
        g[PMAX] = 9999.0
        g[PMIN] = -9999.0
        gen_list.append(g)

    gen_data = np.array(gen_list)

    # --- Build branch matrix ---
    branch_list = []
    if not net.ac_line.empty:
        lines = net.ac_line[net.ac_line["in_service"] == True]
        for _, line in lines.iterrows():
            fb_ext = int(line["from_bus"])
            tb_ext = int(line["to_bus"])
            if fb_ext not in ext2int or tb_ext not in ext2int:
                continue
            fb_int = ext2int[fb_ext]
            tb_int = ext2int[tb_ext]

            # Convert line parameters to per-unit
            vr_kv = float(net.ac_bus.loc[fb_ext, "vr_kv"])
            z_base = vr_kv ** 2 / net.s_base  # Ohm
            y_base = 1.0 / z_base  # Siemens

            length = float(line["length_km"])
            r_pu = float(line["r_ohm_per_km"]) * length / z_base
            x_pu = float(line["x_ohm_per_km"]) * length / z_base
            b_pu = float(line["b_us_per_km"]) * length * 1e-6 / y_base

            br = np.zeros(21)
            br[F_BUS] = fb_int
            br[T_BUS] = tb_int
            br[BR_R] = r_pu
            br[BR_X] = x_pu
            br[BR_B] = b_pu
            br[RATE_A] = 0.0  # No limit
            br[RATE_B] = 0.0
            br[RATE_C] = 0.0
            max_i = line.get("max_i_ka")
            if max_i is not None and not (isinstance(max_i, float) and np.isnan(max_i)):
                br[RATE_A] = float(max_i) * vr_kv * np.sqrt(3)  # MVA rating
            br[TAP] = 0.0  # No transformer
            br[SHIFT] = 0.0
            br[BR_STATUS] = 1
            branch_list.append(br)

    if not branch_list:
        # pypower needs at least one branch; create dummy if single-bus island
        br = np.zeros(21)
        br[F_BUS] = 0
        br[T_BUS] = 0
        br[BR_R] = 0.0
        br[BR_X] = 1e10  # Very high reactance (virtually open)
        br[BR_B] = 0.0
        br[BR_STATUS] = 0  # Out of service
        branch_list.append(br)

    branch_data = np.array(branch_list)

    ppc = {
        "version": "2",
        "baseMVA": net.s_base,
        "bus": bus_data,
        "gen": gen_data,
        "branch": branch_data,
    }

    return ppc


def _ppc_to_results(ppc: dict, island_buses: List[int],
                    v_mag: np.ndarray, v_ang: np.ndarray):
    """
    Extract voltage results from solved pypower case back into full arrays.

    Parameters
    ----------
    ppc : dict
        Solved pypower case
    island_buses : list of int
        AC bus indices belonging to this island
    v_mag : np.ndarray
        Full voltage magnitude array (modified in-place)
    v_ang : np.ndarray
        Full voltage angle array in radians (modified in-place)
    """
    bus_result = ppc["bus"]
    for i, ext_idx in enumerate(island_buses):
        v_mag[ext_idx] = bus_result[i, VM]
        v_ang[ext_idx] = bus_result[i, VA] * np.pi / 180.0  # deg -> rad


def run_ac_pf(
    net: Network,
    p_vsc: np.ndarray = None,
    q_vsc: np.ndarray = None,
    vsc_v_control: Dict[int, float] = None,
    max_iter: int = 30,
    tol: float = 1e-8,
) -> Tuple[np.ndarray, np.ndarray, bool, int]:
    """
    Run AC power flow using pypower as backend.

    Handles multiple AC islands by solving each independently.

    Parameters
    ----------
    net : Network
        The network object with AC data
    p_vsc : np.ndarray, optional
        VSC active power injections (MW), indexed by VSC index
    q_vsc : np.ndarray, optional
        VSC reactive power injections (MVAr), indexed by VSC index
    vsc_v_control : dict, optional
        Mapping from AC bus index to voltage setpoint for Vac-controlling VSCs
    max_iter : int, optional
        Maximum number of iterations (default: 30)
    tol : float, optional
        Convergence tolerance (default: 1e-8)

    Returns
    -------
    tuple
        (v_mag, v_ang, converged, iterations)
    """
    n_bus = len(net.ac_bus)
    if n_bus == 0:
        return np.array([]), np.array([]), True, 0

    if p_vsc is None:
        n_vsc = len(net.vsc) if not net.vsc.empty else 0
        p_vsc = np.zeros(n_vsc)
    if q_vsc is None:
        n_vsc = len(net.vsc) if not net.vsc.empty else 0
        q_vsc = np.zeros(n_vsc)
    if vsc_v_control is None:
        vsc_v_control = {}

    # Initialize full result arrays
    max_bus_idx = net.ac_bus.index.max()
    v_mag = np.ones(max_bus_idx + 1)
    v_ang = np.zeros(max_bus_idx + 1)

    # Find AC islands
    islands = _find_ac_islands(net)

    all_converged = True
    total_iter = 0

    # Pypower options: suppress output
    ppopt = ppoption(
        PF_ALG=1,  # Newton's method
        PF_MAX_IT=max_iter,
        PF_TOL=tol,
        VERBOSE=0,
        OUT_ALL=0,
    )

    for island_buses in islands:
        # Build pypower case for this island
        ppc = _net_to_ppc(net, island_buses, p_vsc, q_vsc, vsc_v_control)

        # Run pypower power flow
        result, success = runpf(ppc, ppopt)

        if not success:
            all_converged = False

        # Extract results
        _ppc_to_results(result, island_buses, v_mag, v_ang)

    # Store the solved ppc for later result extraction
    # (last island's result; for multi-island we store per-island)
    net._ppc_results = {}
    for island_buses in islands:
        ppc = _net_to_ppc(net, island_buses, p_vsc, q_vsc, vsc_v_control)
        result, success = runpf(ppc, ppopt)
        net._ppc_results[tuple(island_buses)] = result

    return v_mag, v_ang, all_converged, total_iter


def calc_ac_power_mismatch(
    v_mag: np.ndarray,
    v_ang: np.ndarray,
    y_bus: sparse.csr_matrix,
    p_spec: np.ndarray,
    q_spec: np.ndarray,
    pv_idx: np.ndarray,
    pq_idx: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate AC power mismatch (kept as utility, not used in pypower path).
    """
    n = len(v_mag)
    v = v_mag * np.exp(1j * v_ang)
    s_calc = v * np.conj(y_bus @ v)
    p_calc = s_calc.real
    q_calc = s_calc.imag

    all_non_slack = np.concatenate([pv_idx, pq_idx])
    all_non_slack = np.sort(all_non_slack)
    delta_p = p_spec[all_non_slack] - p_calc[all_non_slack]
    delta_q = q_spec[pq_idx] - q_calc[pq_idx]

    return delta_p, delta_q


def build_ac_jacobian(
    v_mag: np.ndarray,
    v_ang: np.ndarray,
    y_bus: sparse.csr_matrix,
    pv_idx: np.ndarray,
    pq_idx: np.ndarray,
) -> sparse.csr_matrix:
    """
    Build the AC Jacobian matrix (kept as utility, not used in pypower path).
    """
    n = len(v_mag)
    v = v_mag * np.exp(1j * v_ang)
    Y = y_bus.toarray()

    non_slack = np.sort(np.concatenate([pv_idx, pq_idx]))
    n_ns = len(non_slack)
    n_pq = len(pq_idx)

    # H = dP/dtheta, N = dP/dV, M = dQ/dtheta, L = dQ/dV
    H = np.zeros((n_ns, n_ns))
    N = np.zeros((n_ns, n_pq))
    M = np.zeros((n_pq, n_ns))
    L = np.zeros((n_pq, n_pq))

    for ii, i in enumerate(non_slack):
        for jj, j in enumerate(non_slack):
            if i == j:
                for k in range(n):
                    if k != i:
                        H[ii, ii] -= v_mag[i] * v_mag[k] * (
                            Y[i, k].real * np.sin(v_ang[i] - v_ang[k])
                            - Y[i, k].imag * np.cos(v_ang[i] - v_ang[k])
                        )
            else:
                H[ii, jj] = v_mag[i] * v_mag[j] * (
                    Y[i, j].real * np.sin(v_ang[i] - v_ang[j])
                    - Y[i, j].imag * np.cos(v_ang[i] - v_ang[j])
                )

    J = sparse.bmat([
        [sparse.csr_matrix(H), sparse.csr_matrix(N)],
        [sparse.csr_matrix(M), sparse.csr_matrix(L)],
    ], format="csr")

    return J
