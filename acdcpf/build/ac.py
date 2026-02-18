"""
Build AC bus-branch model.

With pypower backend, Y_bus construction is handled internally by pypower.
These functions are kept as optional utilities.
"""

import numpy as np
from scipy import sparse
from typing import Tuple
from ..network import Network


def build_ac_admittance_matrix(net: Network) -> sparse.csr_matrix:
    """
    Build the AC bus admittance matrix (Y_bus).

    Parameters
    ----------
    net : Network
        The network object

    Returns
    -------
    scipy.sparse.csr_matrix
        The bus admittance matrix Y_bus
    """
    n_bus = len(net.ac_bus)
    if n_bus == 0:
        return sparse.csr_matrix((0, 0), dtype=complex)

    max_idx = net.ac_bus.index.max()
    n = max_idx + 1
    Y = sparse.lil_matrix((n, n), dtype=complex)

    if not net.ac_line.empty:
        lines = net.ac_line[net.ac_line["in_service"] == True]
        for _, line in lines.iterrows():
            fb = int(line["from_bus"])
            tb = int(line["to_bus"])
            vr_kv = float(net.ac_bus.loc[fb, "vr_kv"])
            z_base = vr_kv ** 2 / net.s_base

            length = float(line["length_km"])
            r = float(line["r_ohm_per_km"]) * length
            x = float(line["x_ohm_per_km"]) * length
            b = float(line["b_us_per_km"]) * length * 1e-6
            g = float(line["g_us_per_km"]) * length * 1e-6

            z = complex(r, x) / z_base
            y_series = 1.0 / z if abs(z) > 0 else 0.0
            y_shunt = complex(g, b) / (1.0 / z_base)

            Y[fb, fb] += y_series + y_shunt / 2
            Y[tb, tb] += y_series + y_shunt / 2
            Y[fb, tb] -= y_series
            Y[tb, fb] -= y_series

    return Y.tocsr()


def build_ac_bus_data(net: Network) -> Tuple[np.ndarray, ...]:
    """
    Build AC bus data arrays for power flow.

    Aggregates loads and generators at each bus.

    Parameters
    ----------
    net : Network
        The network object

    Returns
    -------
    tuple
        (p_load, q_load, p_gen, q_gen, v_setpoint)
        All arrays indexed by bus index.
    """
    n_bus = len(net.ac_bus)
    if n_bus == 0:
        return (np.array([]),) * 5

    max_idx = net.ac_bus.index.max()
    n = max_idx + 1

    p_load = np.zeros(n)
    q_load = np.zeros(n)
    p_gen = np.zeros(n)
    q_gen = np.zeros(n)
    v_setpoint = np.ones(n)

    if not net.ac_load.empty:
        loads = net.ac_load[net.ac_load["in_service"] == True]
        for _, load in loads.iterrows():
            bus = int(load["bus"])
            p_load[bus] += float(load["p_mw"])
            q_load[bus] += float(load["q_mvar"])

    if not net.ac_gen.empty:
        gens = net.ac_gen[net.ac_gen["in_service"] == True]
        for _, gen in gens.iterrows():
            bus = int(gen["bus"])
            p_gen[bus] += float(gen["p_mw"])
            q_gen[bus] += float(gen["q_mvar"])
            v_pu = gen.get("v_pu")
            if v_pu is not None and not (isinstance(v_pu, float) and np.isnan(v_pu)):
                v_setpoint[bus] = float(v_pu)

    return p_load, q_load, p_gen, q_gen, v_setpoint
