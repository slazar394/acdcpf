"""
Process power flow results into DataFrames.
"""

import pandas as pd
import numpy as np
from ..network import Network


def process_ac_results(net: Network, v_mag: np.ndarray, v_ang: np.ndarray) -> None:
    """
    Process AC power flow results.

    Calculates bus powers, line flows, and losses,
    and stores them in net.res_ac_bus and net.res_ac_line.

    Parameters
    ----------
    net : Network
        The network object
    v_mag : np.ndarray
        Voltage magnitudes from power flow
    v_ang : np.ndarray
        Voltage angles from power flow (radians)
    """
    # --- AC Bus Results ---
    bus_results = []
    for idx in net.ac_bus.index:
        row = net.ac_bus.loc[idx]
        if not row["in_service"]:
            continue

        vm = v_mag[idx] if idx < len(v_mag) else 1.0
        va = v_ang[idx] if idx < len(v_ang) else 0.0

        # Aggregate P, Q at this bus from loads, gens, and VSCs
        p_load = 0.0
        q_load = 0.0
        if not net.ac_load.empty:
            bus_loads = net.ac_load[(net.ac_load["bus"] == idx) & (net.ac_load["in_service"] == True)]
            p_load = bus_loads["p_mw"].astype(float).sum()
            q_load = bus_loads["q_mvar"].astype(float).sum()

        p_gen = 0.0
        q_gen = 0.0
        if not net.ac_gen.empty:
            bus_gens = net.ac_gen[(net.ac_gen["bus"] == idx) & (net.ac_gen["in_service"] == True)]
            p_gen = bus_gens["p_mw"].astype(float).sum()
            q_gen = bus_gens["q_mvar"].astype(float).sum()

        bus_results.append({
            "v_pu": vm,
            "v_angle_deg": np.degrees(va),
            "p_mw": p_gen - p_load,
            "q_mvar": q_gen - q_load,
        })

    if bus_results:
        net.res_ac_bus = pd.DataFrame(bus_results, index=net.ac_bus[net.ac_bus["in_service"] == True].index)
    else:
        net.res_ac_bus = pd.DataFrame(columns=["v_pu", "v_angle_deg", "p_mw", "q_mvar"])

    # --- AC Line Results ---
    line_results = []
    for idx in net.ac_line.index:
        row = net.ac_line.loc[idx]
        if not row["in_service"]:
            continue

        fb = int(row["from_bus"])
        tb = int(row["to_bus"])
        vr_kv = float(net.ac_bus.loc[fb, "vr_kv"])
        z_base = vr_kv ** 2 / net.s_base

        length = float(row["length_km"])
        r = float(row["r_ohm_per_km"]) * length / z_base
        x = float(row["x_ohm_per_km"]) * length / z_base
        b = float(row["b_us_per_km"]) * length * 1e-6 * z_base

        z = complex(r, x)
        y_series = 1.0 / z if abs(z) > 0 else 0.0
        y_shunt = 1j * b / 2

        tap = float(row.get("tap", 1.0))
        if tap == 0.0:
            tap = 1.0  # pypower convention: 0 means no transformer
        shift_rad = np.radians(float(row.get("shift_deg", 0.0)))

        v_f = v_mag[fb] * np.exp(1j * v_ang[fb])
        v_t = v_mag[tb] * np.exp(1j * v_ang[tb])

        # Power flows (MATPOWER transformer model: tap and shift at from bus)
        if tap != 1.0 or shift_rad != 0.0:
            t_exp_neg = tap * np.exp(1j * shift_rad)
            t_exp_pos = tap * np.exp(-1j * shift_rad)
            yff = (y_series + y_shunt) / (tap * tap)
            yft = -y_series / t_exp_neg
            ytf = -y_series / t_exp_pos
            ytt = y_series + y_shunt
            i_ft = yff * v_f + yft * v_t
            i_tf = ytf * v_f + ytt * v_t
        else:
            i_ft = (v_f - v_t) * y_series + v_f * y_shunt
            i_tf = (v_t - v_f) * y_series + v_t * y_shunt

        s_ft = v_f * np.conj(i_ft) * net.s_base  # MVA
        s_tf = v_t * np.conj(i_tf) * net.s_base

        p_from = s_ft.real
        q_from = s_ft.imag
        p_to = s_tf.real
        q_to = s_tf.imag
        p_loss = p_from + p_to
        q_loss = q_from + q_to

        # Current in kA
        i_mag = max(abs(i_ft), abs(i_tf))
        i_ka = i_mag * net.s_base / (vr_kv * np.sqrt(3))

        # Loading percent
        max_i = row.get("max_i_ka")
        if max_i is not None and not (isinstance(max_i, float) and np.isnan(max_i)) and float(max_i) > 0:
            loading = i_ka / float(max_i) * 100
        else:
            loading = 0.0

        line_results.append({
            "p_from_mw": p_from,
            "q_from_mvar": q_from,
            "p_to_mw": p_to,
            "q_to_mvar": q_to,
            "p_loss_mw": p_loss,
            "q_loss_mvar": q_loss,
            "i_ka": i_ka,
            "loading_percent": loading,
        })

    if line_results:
        net.res_ac_line = pd.DataFrame(
            line_results,
            index=net.ac_line[net.ac_line["in_service"] == True].index,
        )
    else:
        net.res_ac_line = pd.DataFrame(
            columns=["p_from_mw", "q_from_mvar", "p_to_mw", "q_to_mvar",
                      "p_loss_mw", "q_loss_mvar", "i_ka", "loading_percent"]
        )


def process_dc_results(net: Network, v_dc: np.ndarray) -> None:
    """
    Process DC power flow results.

    Calculates bus powers, line flows, and losses,
    and stores them in net.res_dc_bus and net.res_dc_line.

    Parameters
    ----------
    net : Network
        The network object
    v_dc : np.ndarray
        DC voltages from power flow (pu)
    """
    # --- DC Bus Results ---
    bus_results = []
    for idx in net.dc_bus.index:
        row = net.dc_bus.loc[idx]
        if not row["in_service"]:
            continue

        v_pu = v_dc[idx] if idx < len(v_dc) else 1.0
        v_base = float(row["v_base"])
        v_kv = v_pu * v_base

        # Power injection at this bus (sum of all sources)
        p_mw = 0.0

        # VSC injections
        if not net.vsc.empty and hasattr(net, '_p_dc_vsc'):
            vsc_at_bus = net.vsc[(net.vsc["dc_bus"] == idx) & (net.vsc["in_service"] == True)]
            for vsc_idx in vsc_at_bus.index:
                if vsc_idx < len(net._p_dc_vsc):
                    p_mw += net._p_dc_vsc[vsc_idx]

        # DC loads
        if not net.dc_load.empty:
            for _, ld in net.dc_load[(net.dc_load["bus"] == idx) & (net.dc_load["in_service"] == True)].iterrows():
                if str(ld.get("load_type", "constant_power")) == "constant_impedance":
                    p_mw -= float(ld["p_mw"]) * v_pu ** 2
                else:
                    p_mw -= float(ld["p_mw"])

        # DC generators
        if not net.dc_gen.empty:
            gens = net.dc_gen[(net.dc_gen["bus"] == idx) & (net.dc_gen["in_service"] == True)]
            p_mw += gens["p_mw"].astype(float).sum()

        bus_results.append({
            "v_dc_pu": v_pu,
            "v_dc_kv": v_kv,
            "p_mw": p_mw,
        })

    if bus_results:
        net.res_dc_bus = pd.DataFrame(bus_results, index=net.dc_bus[net.dc_bus["in_service"] == True].index)
    else:
        net.res_dc_bus = pd.DataFrame(columns=["v_dc_pu", "v_dc_kv", "p_mw"])

    # --- DC Line Results ---
    line_results = []
    for idx in net.dc_line.index:
        row = net.dc_line.loc[idx]
        if not row["in_service"]:
            continue

        fb = int(row["from_bus"])
        tb = int(row["to_bus"])

        v_from_pu = v_dc[fb] if fb < len(v_dc) else 1.0
        v_to_pu = v_dc[tb] if tb < len(v_dc) else 1.0

        v_base = float(net.dc_bus.loc[fb, "v_base"])
        r_total = float(row["r_ohm_per_km"]) * float(row["length_km"])
        z_base = v_base ** 2 / net.s_base

        r_pu = r_total / z_base if z_base > 0 else 0.0
        g_pu = 1.0 / r_pu if r_pu > 0 else 0.0

        # Current flow (from -> to) per conductor
        i_pu = (v_from_pu - v_to_pu) * g_pu

        # Powers (total for all poles)
        pol = float(net.pol)
        p_from = pol * v_from_pu * i_pu * net.s_base  # MW
        p_to = pol * -v_to_pu * i_pu * net.s_base  # MW (negative if receiving)
        p_loss = p_from + p_to  # MW

        # Current in kA (per conductor)
        i_base = net.s_base / v_base  # kA base
        i_ka = abs(i_pu) * i_base

        line_results.append({
            "p_from_mw": p_from,
            "p_to_mw": p_to,
            "p_loss_mw": p_loss,
            "i_ka": i_ka,
        })

    if line_results:
        net.res_dc_line = pd.DataFrame(
            line_results,
            index=net.dc_line[net.dc_line["in_service"] == True].index,
        )
    else:
        net.res_dc_line = pd.DataFrame(columns=["p_from_mw", "p_to_mw", "p_loss_mw", "i_ka"])


def process_converter_results(net: Network) -> None:
    """
    Process converter results.

    Stores converter powers, losses, and operating points
    in net.res_vsc and net.res_dcdc.

    Parameters
    ----------
    net : Network
        The network object
    """
    # --- VSC Results ---
    vsc_results = []
    if not net.vsc.empty:
        for idx in net.vsc.index:
            row = net.vsc.loc[idx]
            if not row["in_service"]:
                continue

            p_ac = net._p_s[idx] if hasattr(net, '_p_s') and idx < len(net._p_s) else 0.0
            q_ac = net._q_s[idx] if hasattr(net, '_q_s') and idx < len(net._q_s) else 0.0
            p_dc = net._p_dc_vsc[idx] if hasattr(net, '_p_dc_vsc') and idx < len(net._p_dc_vsc) else 0.0
            p_loss = p_ac - p_dc  # Simplified

            ac_bus = int(row["ac_bus"])
            dc_bus = int(row["dc_bus"])
            v_ac = net._v_mag[ac_bus] if hasattr(net, '_v_mag') and ac_bus < len(net._v_mag) else 1.0
            v_dc_pu = net._v_dc[dc_bus] if hasattr(net, '_v_dc') and dc_bus < len(net._v_dc) else 1.0

            # Converter internal voltage
            v_conv = 1.0
            if hasattr(net, '_vsc_internal') and idx in net._vsc_internal:
                p_loss = net._vsc_internal[idx]['p_loss']
                v_conv = abs(net._vsc_internal[idx].get('v_c', 1.0))

            # AC current
            vr_kv = float(net.ac_bus.loc[ac_bus, "vr_kv"])
            s_ac = np.sqrt(p_ac ** 2 + q_ac ** 2)
            i_ac_ka = s_ac / (np.sqrt(3) * vr_kv * v_ac) if vr_kv * v_ac > 0 else 0.0

            vsc_results.append({
                "p_ac_mw": p_ac,
                "q_ac_mvar": q_ac,
                "p_dc_mw": p_dc,
                "p_loss_mw": p_loss,
                "v_ac_pu": v_ac,
                "v_dc_pu": v_dc_pu,
                "v_converter_pu": v_conv,
                "i_ac_ka": i_ac_ka,
            })

    if vsc_results:
        net.res_vsc = pd.DataFrame(
            vsc_results,
            index=net.vsc[net.vsc["in_service"] == True].index,
        )
    else:
        net.res_vsc = pd.DataFrame(
            columns=["p_ac_mw", "q_ac_mvar", "p_dc_mw", "p_loss_mw",
                      "v_ac_pu", "v_dc_pu", "v_converter_pu", "i_ac_ka"]
        )

    # --- DC-DC Results (transformer model) ---
    dcdc_results = []
    if not net.dcdc.empty and hasattr(net, '_v_dc'):
        v_dc = net._v_dc
        for idx in net.dcdc.index:
            row = net.dcdc.loc[idx]
            if not row["in_service"]:
                continue

            m = int(row["from_bus"])   # V_m side (high voltage)
            c = int(row["to_bus"])     # V_c side (low voltage)
            d_ratio = float(row["d_ratio"])
            r_ohm = float(row["r_ohm"])
            g_us_val = float(row["g_us"])

            v_m = v_dc[m] if m < len(v_dc) else 1.0
            v_c = v_dc[c] if c < len(v_dc) else 1.0

            # Per-unit parameters
            v_m_base = float(net.dc_bus.loc[m, "v_base"])
            v_c_base = float(net.dc_bus.loc[c, "v_base"])
            d_pu = d_ratio * v_m_base / v_c_base

            z_base_c = v_c_base ** 2 / net.s_base
            g_series = z_base_c / r_ohm if r_ohm > 0 else 0.0
            g_shunt = g_us_val * 1e-6 * v_m_base ** 2 / net.s_base

            # Power at each side (pu), then convert to MW
            p_m_pu = v_m * (d_pu ** 2 * g_series * v_m - d_pu * g_series * v_c + g_shunt * v_m)
            p_c_pu = v_c * (-d_pu * g_series * v_m + g_series * v_c)

            # Same convention as DC lines: positive = power leaving bus through branch
            pol = float(net.pol)
            p_from_mw = pol * p_m_pu * net.s_base
            p_to_mw = pol * p_c_pu * net.s_base
            p_loss_mw = p_from_mw + p_to_mw

            dcdc_results.append({
                "p_from_mw": p_from_mw,
                "p_to_mw": p_to_mw,
                "p_loss_mw": p_loss_mw,
            })

    if dcdc_results:
        net.res_dcdc = pd.DataFrame(
            dcdc_results,
            index=net.dcdc[net.dcdc["in_service"] == True].index,
        )
    else:
        net.res_dcdc = pd.DataFrame(columns=["p_from_mw", "p_to_mw", "p_loss_mw"])
