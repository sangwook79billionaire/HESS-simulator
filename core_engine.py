import numpy as np
import pandas as pd
import requests

# Constants
PRICE_PV = 1200   # $/kWp
PRICE_BESS = 450  # $/kWh
PRICE_EL = 1500  # $/kW (Electrolyzer)
PRICE_FC = 3000  # $/kW (Fuel Cell)
BESS_EFF = 0.90
H2_EL_EFF = 0.70
H2_FC_EFF = 0.50
INV_EFF = 0.95

def get_nasa_data(lat, lon):
    url_h = f"https://power.larc.nasa.gov/api/temporal/hourly/point?parameters=ALLSKY_SFC_SW_DWN,T2M&community=RE&longitude={lon}&latitude={lat}&format=JSON&start=20230101&end=20231231"
    try:
        res_h = requests.get(url_h, timeout=20).json()
        ins_h = res_h['properties']['parameter']['ALLSKY_SFC_SW_DWN']
        tmp_h = res_h['properties']['parameter']['T2M']
        df_h = pd.DataFrame({
            'Timestamp': pd.to_datetime(list(ins_h.keys()), format='%Y%m%d%H'),
            'Insolation': list(ins_h.values()),
            'Temp': list(tmp_h.values())
        })
        return df_h
    except Exception as e:
        print(f"Error fetching NASA data for {lat}, {lon}: {e}")
        return None

def simulate(lat, lon, total_d, load_profile, hh):
    df_h = get_nasa_data(lat, lon)
    if df_h is None: return None
    
    annual_demand = total_d * 365
    df_h['Gen_1kW'] = (df_h['Insolation'] * (0.85 * (1 - 0.004 * (df_h['Temp'] - 25))) * INV_EFF) / 1000
    annual_yield_1kW = df_h['Gen_1kW'].sum()
    pv_ideal = annual_demand / (annual_yield_1kW * 0.98)
    
    profile_sum = sum(load_profile)
    norm_profile = [(v / profile_sum) * 24 for v in load_profile]
    
    # Scenario A: BESS Only
    df_a = df_h.copy()
    df_a['Gen'] = df_a['Gen_1kW'] * pv_ideal
    df_a['Load'] = [(total_d / 24) * norm_profile[h] for h in df_a['Timestamp'].dt.hour]
    
    soc, bess_a_cap = 50.0, total_d * 5
    soc_trace = []
    for i, row in df_a.iterrows():
        bal = row['Gen'] - row['Load']
        if bal > 0:
            ch = min(bal, (95 - soc) * bess_a_cap / 100)
            soc += (ch * np.sqrt(BESS_EFF) / bess_a_cap) * 100
        else:Dis = min(abs(bal), (soc - 20) * bess_a_cap / 100 / np.sqrt(BESS_EFF))
            soc -= (Dis * np.sqrt(BESS_EFF) / bess_a_cap) * 100
        soc_trace.append(soc)
    
    seasonal_deficit = (max(soc_trace) - min(soc_trace)) / 100 * bess_a_cap
    bess_a = seasonal_deficit * 1.1
    capex_a = (pv_ideal * PRICE_PV) + (bess_a * PRICE_BESS) + (hh * 1500)
    
    # Scenario B: Hybrid
    bess_b = total_d * 1.5
    el_kw, fc_kw = total_d / 6, total_d / 10
    pv_hybrid = pv_ideal * 1.3
    
    for _ in range(15):
        soc, h2_bal = 50.0, 0.0
        for i, row in df_h.iterrows():
            g, l = row['Gen_1kW'] * pv_hybrid, (total_d / 24) * norm_profile[row['Timestamp'].hour]
            bal = g - l
            if bal > 0:
                ch = min(bal, (95 - soc) * bess_b / 100)
                soc += (ch * np.sqrt(BESS_EFF) / bess_b) * 100
                bal -= ch
                if bal > 0 and soc >= 90:
                    hp_in = min(bal, el_kw); h2_bal += (hp_in * H2_EL_EFF) / 33.33
            else:
                defic = abs(bal)
                if soc > 20:
                    dis = min(defic, (soc - 20) * bess_b / 100 / np.sqrt(BESS_EFF))
                    soc -= (dis * np.sqrt(BESS_EFF) / bess_b) * 100
                    defic -= dis
                if defic > 0:
                    fc_out = min(defic, fc_kw); h2_bal -= (fc_out / H2_FC_EFF) / 33.33
        if abs(h2_bal) < 5: break
        pv_hybrid += ((-h2_bal * 33.33) / annual_yield_1kW) * 1.1
        pv_hybrid = max(pv_hybrid, pv_ideal)

    h2_max = 0 # Dummy for max h2 stock calculation in real loop
    # (Simplified for batch result reporting)
    capex_b = (pv_hybrid * PRICE_PV) + (bess_b * PRICE_BESS) + (el_kw * PRICE_EL) + (fc_kw * PRICE_FC) + (hh * 1500)
    
    return {
        'PV_A_kWp': pv_ideal, 'BESS_A_kWh': bess_a, 'CAPEX_A': capex_a,
        'PV_B_kWp': pv_hybrid, 'BESS_B_kWh': bess_b, 'CAPEX_B': capex_b,
        'Saving_Rate': (1 - capex_b/capex_a) * 100
    }
