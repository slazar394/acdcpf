"""
Build converter data for power flow.
"""

import numpy as np
from typing import Dict, Any
from ..network import Network


def build_converter_data(net: Network) -> Dict[str, Any]:
    """
    Build converter data structures for power flow.

    Processes VSC and DC-DC converter data and prepares
    them for the sequential power flow algorithm.

    Parameters
    ----------
    net : Network
        The network object

    Returns
    -------
    dict
        Converter data including:
        - 'n_vsc': number of in-service VSCs
        - 'vsc_ac_bus': AC bus indices
        - 'vsc_dc_bus': DC bus indices
        - 'vsc_control': control mode strings
        - 'vsc_p_set': P setpoints (MW)
        - 'vsc_q_set': Q setpoints (MVAr)
        - 'vsc_v_ac_set': Vac setpoints (pu)
        - 'vsc_v_dc_set': Vdc setpoints (pu)
        - 'vsc_droop_k': droop constants (kV/MW)
        - 'vsc_p_dc_set': droop P setpoints (MW)
        - 'vsc_v_dc_droop_set': droop Vdc setpoints (pu)
        - 'vsc_loss_a/b/c': loss coefficients
        - 'vsc_r/x/b_filter': impedance parameters (pu)
        - 'vsc_s_mva': rated power (MVA)
        - 'n_dcdc': number of in-service DC-DC converters
        - 'dcdc_indices': indices of in-service DC-DC converters
    """
    data = {}

    # --- VSC converters ---
    if not net.vsc.empty:
        vsc_is = net.vsc[net.vsc["in_service"] == True]
    else:
        vsc_is = net.vsc

    n_vsc = len(vsc_is)
    data["n_vsc"] = n_vsc
    data["vsc_indices"] = vsc_is.index.to_numpy()

    if n_vsc > 0:
        data["vsc_ac_bus"] = vsc_is["ac_bus"].astype(int).to_numpy()
        data["vsc_dc_bus"] = vsc_is["dc_bus"].astype(int).to_numpy()
        data["vsc_control"] = vsc_is["control_mode"].to_numpy()
        data["vsc_p_set"] = vsc_is["p_mw"].astype(float).to_numpy()
        data["vsc_q_set"] = vsc_is["q_mvar"].astype(float).to_numpy()
        data["vsc_v_ac_set"] = vsc_is["v_ac_pu"].to_numpy(dtype=float, na_value=1.0)
        data["vsc_v_dc_set"] = vsc_is["v_dc_pu"].to_numpy(dtype=float, na_value=1.0)
        data["vsc_droop_k"] = vsc_is["droop_kv_per_mw"].to_numpy(dtype=float, na_value=0.0)
        data["vsc_p_dc_set"] = vsc_is["p_dc_set_mw"].to_numpy(dtype=float, na_value=0.0)
        data["vsc_v_dc_droop_set"] = vsc_is["v_dc_set_pu"].to_numpy(dtype=float, na_value=1.0)
        data["vsc_loss_a"] = vsc_is["loss_a"].astype(float).to_numpy()
        data["vsc_loss_b"] = vsc_is["loss_b"].astype(float).to_numpy()
        data["vsc_loss_c"] = vsc_is["loss_c"].astype(float).to_numpy()
        data["vsc_r"] = vsc_is["r_pu"].astype(float).to_numpy()
        data["vsc_x"] = vsc_is["x_pu"].astype(float).to_numpy()
        data["vsc_b_filter"] = vsc_is["b_filter_pu"].astype(float).to_numpy()
        data["vsc_s_mva"] = vsc_is["s_mva"].astype(float).to_numpy()
    else:
        for key in ["vsc_ac_bus", "vsc_dc_bus", "vsc_p_set", "vsc_q_set",
                     "vsc_v_ac_set", "vsc_v_dc_set", "vsc_droop_k",
                     "vsc_p_dc_set", "vsc_v_dc_droop_set",
                     "vsc_loss_a", "vsc_loss_b", "vsc_loss_c",
                     "vsc_r", "vsc_x", "vsc_b_filter", "vsc_s_mva"]:
            data[key] = np.array([])
        data["vsc_control"] = np.array([], dtype=str)

    # --- DC-DC converters ---
    if not net.dcdc.empty:
        dcdc_is = net.dcdc[net.dcdc["in_service"] == True]
    else:
        dcdc_is = net.dcdc

    n_dcdc = len(dcdc_is)
    data["n_dcdc"] = n_dcdc
    data["dcdc_indices"] = dcdc_is.index.to_numpy()

    return data
