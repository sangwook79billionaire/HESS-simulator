import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
import folium
import datetime
import numpy as np
import io

# --- Page Config ---
st.set_page_config(page_title="Net-Zero Optimizer Pro", page_icon="⚡", layout="wide")

# --- Constants & Benchmarks ---
COUNTRY_BENCHMARKS = {
    "Indonesia": 4.2,
    "Philippines": 8.5,
    "Vietnam": 6.5,
    "South Korea": 11.2,
    "United States": 29.5,
    "Germany": 8.5,
    "Unknown": 5.0
}

# Load Patterns (A: Night/Residential, B: Day/Commercial)
PATTERN_A = [0.4, 0.3, 0.3, 0.3, 0.4, 0.5, 0.7, 0.8, 0.9, 0.8, 0.7, 0.6, 0.6, 0.7, 0.8, 1.2, 1.8, 2.5, 3.2, 2.8, 1.8, 1.2, 0.8, 0.5]
PATTERN_B = [0.2, 0.2, 0.2, 0.2, 0.3, 0.6, 1.2, 2.0, 2.8, 3.2, 3.0, 2.8, 2.5, 2.5, 2.5, 2.0, 1.5, 1.0, 0.8, 0.6, 0.4, 0.3, 0.2, 0.2]

# Financial Defaults (Benchmark Prices)
PRICE_PV = 800  # $/kWp
PRICE_BESS = 350 # $/kWh
PRICE_EL = 1200 # $/kW
PRICE_FC = 2000 # $/kW
PRICE_TANK = 50 # $/kg (Storage)
OPEX_RATE = 0.02 # 2% of CAPEX/year

# --- Session State ---
if 'step' not in st.session_state: st.session_state.step = 'input'
if 'lat' not in st.session_state: st.session_state.lat = -8.4095
if 'lon' not in st.session_state: st.session_state.lon = 115.1889
if 'country' not in st.session_state: st.session_state.country = 'Bali, Indonesia'

# --- Styles ---
st.markdown("""<style>
    .main { background-color: #0b0e14; color: #ffffff; }
    .stMetric { background: #1a1f2b; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    .status-card { padding: 20px; border-radius: 15px; border: 1px solid #1f2937; margin-bottom: 20px; }
    .scenario-a { border-left: 5px solid #ff4b4b; background: rgba(255, 75, 75, 0.05); }
    .scenario-b { border-left: 5px solid #00d4ff; background: rgba(0, 212, 255, 0.05); }
</style>""", unsafe_allow_html=True)

# --- Helper Functions ---
@st.cache_data
def get_nasa_data(lat, lon):
    url_m = f"https://power.larc.nasa.gov/api/temporal/climatology/point?parameters=ALLSKY_SFC_SW_DWN,T2M&community=RE&longitude={lon}&latitude={lat}&format=JSON"
    url_h = f"https://power.larc.nasa.gov/api/temporal/hourly/point?parameters=ALLSKY_SFC_SW_DWN,T2M&community=RE&longitude={lon}&latitude={lat}&format=JSON&start=20230101&end=20231231"
    try:
        res_m = requests.get(url_m, timeout=10).json()
        res_h = requests.get(url_h, timeout=20).json()
        ins_h, tmp_h = res_h['properties']['parameter']['ALLSKY_SFC_SW_DWN'], res_h['properties']['parameter']['T2M']
        df_h = pd.DataFrame({'Timestamp': pd.to_datetime(list(ins_h.keys()), format='%Y%m%d%H'), 'Insolation': list(ins_h.values()), 'Temp': list(tmp_h.values())})
        return df_h
    except: return None

def calc_edcf_payment(amount, years=40, grace=15, rate=0.0001):
    n = years - grace
    if amount == 0: return 0
    # Simple EDCF model: Interest only during grace, then annuity
    grace_pay = amount * rate
    annuity_pay = amount * (rate * (1+rate)**n) / ((1+rate)**n - 1)
    return (grace_pay * grace + annuity_pay * n) / years

# --- UI: Input Step ---
if st.session_state.step == 'input':
    st.title("🌍 Universal Net-Zero Microgrid Optimizer")
    st.markdown("전 세계 격오지 재생에너지 전환을 위한 하이브리드 시스템 설계 솔루션")
    
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.subheader("📍 1. 위치 및 수요 설정")
        address = st.text_input("지역 검색 (Geocoding)", value=st.session_state.country)
        if st.button("위치 확인"):
            geolocator = Nominatim(user_agent="net_zero_optimizer")
            loc = geolocator.geocode(address)
            if loc:
                st.session_state.lat, st.session_state.lon, st.session_state.country = loc.latitude, loc.longitude, loc.address
                st.rerun()
        
        m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=10)
        folium.Marker([st.session_state.lat, st.session_state.lon]).add_to(m)
        st_folium(m, height=250, use_container_width=True)
        
        st.info(f"좌표: {st.session_state.lat:.4f}, {st.session_state.lon:.4f}")
        
    with col2:
        st.subheader("⚡ 2. 에너지 부하 패턴 (Mixed Load)")
        hh = st.number_input("가구 수 (Households)", value=200, min_value=1)
        st.session_state.hh = hh
        
        mode = st.radio("수요 산정", ["국가별 레퍼런스", "직접 입력"], horizontal=True)
        if mode == "국가별 레퍼런스":
            c_name = st.selectbox("대상 국가 선택", list(COUNTRY_BENCHMARKS.keys()))
            avg_kwh = COUNTRY_BENCHMARKS[c_name]
        else:
            avg_kwh = st.number_input("가구당 일일 사용량 (kWh)", value=5.0)
        
        total_daily_kwh = hh * avg_kwh
        st.success(f"총 일일 수요: {total_daily_kwh:,.1f} kWh")
        
        mix_ratio = st.slider("부하 패턴 혼합 (Pattern A:주거 vs Pattern B:상업)", 0, 100, 70) / 100
        combined_pattern = [(PATTERN_A[i]*mix_ratio + PATTERN_B[i]*(1-mix_ratio)) for i in range(24)]
        norm_factor = sum(combined_pattern) / 24
        final_pattern = [p / norm_factor for p in combined_pattern]
        
        fig_load = px.line(y=final_pattern, x=list(range(24)), title="24시간 Hourly Load Profile (Normalized)")
        fig_load.update_layout(height=200, margin=dict(l=0,r=0,t=30,b=0), template="plotly_dark")
        st.plotly_chart(fig_load, use_container_width=True)

    if st.button("🚀 최적화 시뮬레이션 시작", use_container_width=True, type="primary"):
        st.session_state.total_d = total_daily_kwh
        st.session_state.load_profile = final_pattern
        st.session_state.step = 'result'
        st.rerun()

# --- UI: Result Step ---
elif st.session_state.step == 'result':
    st.title("📊 시나리오 비교 분석 및 최적화 설계")
    if st.button("⬅ 처음으로"): st.session_state.step = 'input'; st.rerun()
    
    with st.spinner("NASA 데이터 호출 및 시나리오 연산 중..."):
        df_h = get_nasa_data(st.session_state.lat, st.session_state.lon)
        if df_h is None: st.error("기상 데이터를 불러오지 못했습니다."); st.stop()

    # --- Calculation Engine ---
    total_d = st.session_state.total_d
    load_profile = st.session_state.load_profile
    hh = st.session_state.hh
    annual_demand = total_d * 365
    
    # Efficiency Constants
    BESS_EFF = 0.90  # Round-trip 90%
    H2_EL_EFF = 0.70 # Electrolyzer
    H2_FC_EFF = 0.50 # Fuel Cell
    INV_EFF = 0.95   # Inverter/System
    
    # Common: Ideal PV sizing (Annual Net-Zero)
    # NASA Hourly is W/m^2. Convert to kWh/kWp/hour
    df_h['Gen_1kW'] = (df_h['Insolation'] * (0.85 * (1 - 0.004 * (df_h['Temp'] - 25))) * INV_EFF) / 1000
    annual_yield_1kW = df_h['Gen_1kW'].sum()
    pv_ideal = annual_demand / (annual_yield_1kW * 0.98) # Base degradation/misc
    
    # Normalize Load Profile (Ensure sum = 24.0)
    profile_sum = sum(load_profile)
    norm_profile = [ (v / profile_sum) * 24 for v in load_profile ]
    
    # ---------------------------------------------------------
    # SCENARIO A: Giant BESS Only
    # ---------------------------------------------------------
    df_a = df_h.copy()
    df_a['Gen'] = df_a['Gen_1kW'] * pv_ideal
    df_a['Load'] = [ (total_d / 24) * norm_profile[h] for h in df_a['Timestamp'].dt.hour ]
    df_a['Net'] = df_a['Gen'] - df_a['Load']
    
    soc = 50.0
    bess_a_cap = total_d * 5 # Estimator
    net_trace = []
    for i, row in df_a.iterrows():
        bal = row['Gen'] - row['Load']
        if bal > 0:
            ch = min(bal, (95 - soc) * bess_a_cap / 100)
            soc += (ch * np.sqrt(BESS_EFF) / bess_a_cap) * 100
        else:
            dis = min(abs(bal), (soc - 20) * bess_a_cap / 100 / np.sqrt(BESS_EFF))
            soc -= (dis * np.sqrt(BESS_EFF) / bess_a_cap) * 100
        net_trace.append(soc)
    
    seasonal_deficit = (max(net_trace) - min(net_trace)) / 100 * bess_a_cap
    bess_a = seasonal_deficit * 1.1
    capex_a = (pv_ideal * PRICE_PV) + (bess_a * PRICE_BESS) + (hh * 1500)
    
    # ---------------------------------------------------------
    # SCENARIO B: BESS-HESS Hybrid (Advanced Steady-State Solver)
    # ---------------------------------------------------------
    bess_b = total_d * 1.5
    el_kw = total_d / 6
    fc_kw = total_d / 10
    
    # Precise Iterative Solver for Net-Zero H2 Balance
    pv_hybrid = pv_ideal * 1.3 # Start with higher guess
    for _ in range(20):
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
        
        # Binary adjustment
        if abs(h2_bal) < 5: break
        pv_hybrid += ((-h2_bal * 33.33) / annual_yield_1kW) * 1.1 
        pv_hybrid = max(pv_hybrid, pv_ideal)

    # 2-Pass Simulation for Visualization
    soc, h2s = 50.0, 0.0
    h2_trace = []
    for i, row in df_h.iterrows():
        g, l = row['Gen_1kW'] * pv_hybrid, (total_d / 24) * norm_profile[row['Timestamp'].hour]
        bal = g - l
        if bal > 0:
            ch = min(bal, (95 - soc) * bess_b / 100); soc += (ch * np.sqrt(BESS_EFF) / bess_b) * 100; bal -= ch
            if bal > 0 and soc >= 90: h2s += (min(bal, el_kw) * H2_EL_EFF) / 33.33
        else:
            defic = abs(bal)
            if soc > 20:
                dis = min(defic, (soc - 20) * bess_b / 100 / np.sqrt(BESS_EFF)); soc -= (dis * np.sqrt(BESS_EFF) / bess_b) * 100; defic -= dis
            if defic > 0: h2s -= (min(defic, fc_kw) / H2_FC_EFF) / 33.33
        h2_trace.append(h2s)
    
    init_h2 = abs(min(h2_trace))
    soc, h2s = 50.0, init_h2
    soc_b, h2_stock, h2_prod, gen_b, load_b = [], [], [], [], []
    for i, row in df_h.iterrows():
        g, l = row['Gen_1kW'] * pv_hybrid, (total_d / 24) * norm_profile[row['Timestamp'].hour]
        bal, hp = g - l, 0
        if bal > 0:
            ch = min(bal, (95 - soc) * bess_b / 100); soc += (ch * np.sqrt(BESS_EFF) / bess_b) * 100; bal -= ch
            if bal > 0 and soc >= 90:
                hp_in = min(bal, el_kw); hp = (hp_in * H2_EL_EFF) / 33.33; h2s += hp
        else:
            defic = abs(bal)
            if soc > 20:
                dis = min(defic, (soc - 20) * bess_b / 100 / np.sqrt(BESS_EFF)); soc -= (dis * np.sqrt(BESS_EFF) / bess_b) * 100; defic -= dis
            if defic > 0:
                fc_out = min(defic, fc_kw); hc_kg = (fc_out / H2_FC_EFF) / 33.33
                if h2s > 0: h2s -= min(hc_kg, h2s)
        soc_b.append(soc); h2_stock.append(h2s); h2_prod.append(hp); gen_b.append(g); load_b.append(l)
    
    df_h['SOC_B'], df_h['H2_Stock'], df_h['H2_Prod'], df_h['Gen_B'], df_h['Load_B'] = soc_b, h2_stock, h2_prod, gen_b, load_b
    capex_b = (pv_hybrid * PRICE_PV) + (bess_b * PRICE_BESS) + (el_kw * PRICE_EL) + (fc_kw * PRICE_FC) + (max(h2_stock)*500) + (hh * 1500)

    # --- Financial Comparison ---
    pay_a = calc_edcf_payment(capex_a)
    lcoe_a = (pay_a + capex_a*OPEX_RATE) / annual_demand
    pay_b = calc_edcf_payment(capex_b)
    lcoe_b = (pay_b + capex_b*OPEX_RATE) / annual_demand

    # --- UI Rendering ---
    tabs = st.tabs(["📊 종합 분석 리포트", "🔍 상세 시계열 분석", "📥 데이터 익스포트"])
    
    with tabs[0]:
        st.markdown("### 📋 1. 전체 에너지 수요 (Total Energy Demand)")
        st.markdown(f"""
        <div class='status-card' style='background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); border-left: 5px solid #00d4ff; padding: 25px;'>
            <div style='display: flex; justify-content: space-around; text-align: center; gap: 20px;'>
                <div style='flex: 1;'>
                    <span style='color: #d1d1d1; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;'>일간 총 수요</span><br>
                    <span style='color: #ffffff; font-size: 26px; font-weight: 800;'>{total_d:,.1f} <small style='font-size: 14px; font-weight: 400;'>kWh/d</small></span>
                </div>
                <div style='flex: 1; border-left: 1px solid rgba(255,255,255,0.1); border-right: 1px solid rgba(255,255,255,0.1);'>
                    <span style='color: #d1d1d1; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;'>연간 총 수요</span><br>
                    <span style='color: #ffffff; font-size: 26px; font-weight: 800;'>{annual_demand/1000:,.1f} <small style='font-size: 14px; font-weight: 400;'>MWh/y</small></span>
                </div>
                <div style='flex: 1;'>
                    <span style='color: #d1d1d1; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;'>가구당 평균 수요</span><br>
                    <span style='color: #ffffff; font-size: 26px; font-weight: 800;'>{total_d/hh:,.1f} <small style='font-size: 14px; font-weight: 400;'>kWh/hh</small></span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 🏗️ 2. 시스템 아키텍처 비교 (Simplified 2D Architecture)")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
            <div style='background-color: #1a1a1a; padding: 25px; border-radius: 12px; border: 1px solid #ff4b4b; min-height: 430px; color: #eee;'>
                <h4 style='color: #ff4b4b; text-align: center; font-size: 20px; margin-bottom: 15px;'>Scenario A: Giant BESS Only</h4>
                <div style='text-align: center; font-size: 45px; margin: 15px 0;'>☀️ ➡ 🔋 ➡ 🏠</div>
                <p style='font-size: 15px; color: #ccc; line-height: 1.5;'>거대 배터리 뱅크를 통해 계절적 불균형을 해소하는 단순 구조입니다.</p>
                <hr style='border-color: #444;'>
                <ul style='list-style: none; padding: 0; font-size: 16px;'>
                    <li style='margin-bottom: 12px;'>🔆 <span style='color: #aaa;'>PV 규모:</span> <b style='color: #fff;'>{pv_ideal:,.1f} kWp</b></li>
                    <li style='margin-bottom: 12px;'>🔋 <span style='color: #aaa;'>BESS 용량:</span> <b style='color: #fff;'>{bess_a:,.1f} kWh</b></li>
                    <li style='margin-bottom: 12px;'>📅 <span style='color: #aaa;'>저장 필요 일수:</span> <b style='color: #ff4b4b;'>{bess_a/total_d:.1f} 일분</b></li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            h2_days = (max(h2_stock) * 33.33 * H2_FC_EFF) / total_d
            st.markdown(f"""
            <div style='background-color: #1a1a1a; padding: 25px; border-radius: 12px; border: 1px solid #00d4ff; min-height: 430px; color: #eee;'>
                <h4 style='color: #00d4ff; text-align: center; font-size: 20px; margin-bottom: 15px;'>Scenario B: BESS-HESS Hybrid</h4>
                <div style='text-align: center; font-size: 45px; margin: 15px 0;'>☀️ ➡ 🔋 + 💧(H2) ➡ 🏠</div>
                <p style='font-size: 15px; color: #ccc; line-height: 1.5;'>배터리와 수소가 단기/장기 변동을 나누어 담당하여 효율을 극대화합니다.</p>
                <hr style='border-color: #444;'>
                <ul style='list-style: none; padding: 0; font-size: 15px;'>
                    <li style='margin-bottom: 10px;'>🔆 <span style='color: #aaa;'>PV 규모:</span> <b style='color: #fff;'>{pv_hybrid:,.1f} kWp</b> <span style='font-size: 13px; color: #00d4ff;'>({pv_hybrid/pv_ideal:.2f}배)</span></li>
                    <li style='margin-bottom: 10px;'>🔋 <span style='color: #aaa;'>BESS 용량:</span> <b style='color: #fff;'>{bess_b:,.1f} kWh</b> <span style='font-size: 13px; color: #00d4ff;'>(1.5일분)</span></li>
                    <li style='margin-bottom: 10px;'>💧 <span style='color: #aaa;'>수소 시스템 (HESS):</span>
                        <ul style='font-size: 14px; color: #ccc; margin-top: 5px;'>
                            <li>수전해기(EL): <b style='color: #fff;'>{el_kw:,.1f} kW</b></li>
                            <li>연료전지(FC): <b style='color: #fff;'>{fc_kw:,.1f} kW</b></li>
                            <li>최대 수소 저장: <b style='color: #00ff88;'>{max(h2_stock):,.1f} kg</b> <span style='color: #00ff88;'>({h2_days:.1f}일분)</span></li>
                            <p style='font-size: 11px; color: #aaa; margin-top: 5px; line-height: 1.4;'>
                                * 수소는 계절 간 에너지 불균형(Seasonal Shifting)을 해소하며, 일조량이 가장 적은 시기를 안전하게 통과하기 위한 최대 잔량 기준으로 설계되었습니다.
                            </p>
                        </ul>
                    </li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        # 3. 주요 운영 지표 시각화
        st.markdown("### 📊 3. 시나리오별 주요 지표 비교 (Operational Indicators)")
        
        # Monthly Net Balance Data
        df_h['Month'] = df_h['Timestamp'].dt.month
        monthly_net_a = df_a.groupby(df_a['Timestamp'].dt.month)['Net'].sum()
        monthly_net_b = df_h.groupby('Month').apply(lambda x: (x['Gen_B'] - x['Load_B']).sum())
        
        # Unified Y-axis range for comparison
        y_min = min(monthly_net_a.min(), monthly_net_b.min()) * 1.1
        y_max = max(monthly_net_a.max(), monthly_net_b.max()) * 1.1
        
        # Color Coding: Blue for +, Red for -
        colors_a = ['#00d4ff' if x > 0 else '#ff4b4b' for x in monthly_net_a.values]
        colors_b = ['#00d4ff' if x > 0 else '#ff4b4b' for x in monthly_net_b.values]
        
        c_net1, c_net2 = st.columns(2)
        with c_net1:
            fig_ma = go.Figure(go.Bar(x=monthly_net_a.index, y=monthly_net_a.values, name="Scenario A Net", marker_color=colors_a))
            fig_ma.update_layout(title="Scenario A: 월간 순 수지", template="plotly_dark", yaxis=dict(range=[y_min, y_max], title="kWh"), xaxis=dict(title="Month"))
            st.plotly_chart(fig_ma, use_container_width=True)
            
        with c_net2:
            fig_mb = go.Figure(go.Bar(x=monthly_net_b.index, y=monthly_net_b.values, name="Scenario B Net", marker_color=colors_b))
            fig_mb.update_layout(title="Scenario B: 월간 순 수지", template="plotly_dark", yaxis=dict(range=[y_min, y_max]), xaxis=dict(title="Month"))
            st.plotly_chart(fig_mb, use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Scenario A: BESS SOC Trend")
            fig_soc_a = px.line(x=df_h['Timestamp'], y=net_trace, title="Scenario A: Battery SOC (%)", color_discrete_sequence=['#ff4b4b'])
            fig_soc_a.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig_soc_a, use_container_width=True)
        with col_b:
            st.subheader("Scenario B: BESS & H2 Status")
            fig_hybrid = make_subplots(specs=[[{"secondary_y": True}]])
            fig_hybrid.add_trace(go.Scatter(x=df_h['Timestamp'], y=df_h['SOC_B'], name="BESS SOC (%)", line=dict(color="#00d4ff", width=1)), secondary_y=False)
            fig_hybrid.add_trace(go.Scatter(x=df_h['Timestamp'], y=df_h['H2_Stock'], name="H2 Stock (kg)", fill='tozeroy', line=dict(color="#00ff88", width=2)), secondary_y=True)
            fig_hybrid.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=30,b=0), showlegend=False)
            st.plotly_chart(fig_hybrid, use_container_width=True)

        # 4. CAPEX 상세 내역 및 비교
        st.markdown("### 💰 4. 투자비 상세 내역 (CAPEX Breakdown)")
        
        # Breakdown Data Calculation
        cost_pv_a = pv_ideal * PRICE_PV
        cost_bess_a = bess_a * PRICE_BESS
        cost_dist = hh * 1500
        
        cost_pv_b = pv_hybrid * PRICE_PV
        cost_bess_b = bess_b * PRICE_BESS
        cost_el = el_kw * PRICE_EL
        cost_fc = fc_kw * PRICE_FC
        cost_h2_tank = max(h2_stock) * 500
        
        # Stacked Bar Chart for Breakdown
        fig_break = go.Figure()
        # Scenario A
        fig_break.add_trace(go.Bar(name='Solar PV', x=['Scenario A'], y=[cost_pv_a], marker_color='#FFD700', text=[f"${cost_pv_a/1e6:.2f}M"], textposition='auto'))
        fig_break.add_trace(go.Bar(name='BESS (Battery)', x=['Scenario A'], y=[cost_bess_a], marker_color='#4CAF50', text=[f"${cost_bess_a/1e6:.2f}M"], textposition='auto'))
        fig_break.add_trace(go.Bar(name='Distribution', x=['Scenario A'], y=[cost_dist], marker_color='#9E9E9E', text=[f"${cost_dist/1e6:.2f}M"], textposition='auto'))
        # Scenario B
        fig_break.add_trace(go.Bar(name='Solar PV', x=['Scenario B'], y=[cost_pv_b], marker_color='#FFD700', showlegend=False, text=[f"${cost_pv_b/1e6:.2f}M"], textposition='auto'))
        fig_break.add_trace(go.Bar(name='BESS (Battery)', x=['Scenario B'], y=[cost_bess_b], marker_color='#4CAF50', showlegend=False, text=[f"${cost_bess_b/1e6:.2f}M"], textposition='auto'))
        fig_break.add_trace(go.Bar(name='Electrolyzer (EL)', x=['Scenario B'], y=[cost_el], marker_color='#2196F3', text=[f"${cost_el/1e6:.2f}M"], textposition='auto'))
        fig_break.add_trace(go.Bar(name='Fuel Cell (FC)', x=['Scenario B'], y=[cost_fc], marker_color='#03A9F4', text=[f"${cost_fc/1e6:.2f}M"], textposition='auto'))
        fig_break.add_trace(go.Bar(name='H2 Tank', x=['Scenario B'], y=[cost_h2_tank], marker_color='#00BCD4', text=[f"${cost_h2_tank/1e6:.2f}M"], textposition='auto'))
        fig_break.add_trace(go.Bar(name='Distribution', x=['Scenario B'], y=[cost_dist], marker_color='#9E9E9E', showlegend=False, text=[f"${cost_dist/1e6:.2f}M"], textposition='auto'))
        
        # Add Total Labels at the top
        fig_break.add_trace(go.Scatter(
            x=['Scenario A', 'Scenario B'], 
            y=[capex_a, capex_b], 
            mode='text', 
            text=[f"Total: ${capex_a/1e6:.2f}M", f"Total: ${capex_b/1e6:.2f}M"],
            textposition='top center',
            textfont=dict(size=16, color='white', family="Arial Black"),
            showlegend=False
        ))
        
        fig_break.update_layout(title="투자 비용 구성 항목 비교 (Cost Breakdown)", barmode='stack', template="plotly_dark", height=500, yaxis=dict(range=[0, max(capex_a, capex_b)*1.2]))
        st.plotly_chart(fig_break, use_container_width=True)

        # Comparison Table
        st.markdown("#### 📑 세부 항목별 산출 근거 (Unit Price Basis)")
        breakdown_html = f"""
        <table style='width: 100%; color: white; border-collapse: collapse; font-size: 13px; background-color: #1a1f2b; border-radius: 10px; overflow: hidden;'>
            <tr style='background-color: #333; border-bottom: 2px solid #555;'>
                <th style='padding: 10px; text-align: left; color: white;'>항목 (Component)</th>
                <th style='padding: 10px; text-align: center;'>단위</th>
                <th style='padding: 10px; text-align: right;'>단가 (Price)</th>
                <th style='padding: 10px; text-align: right;'>Scenario A</th>
                <th style='padding: 10px; text-align: right;'>Scenario B</th>
                <th style='padding: 10px; text-align: left; padding-left: 15px;'>산출 근거 (Rationale)</th>
            </tr>
            <tr style='border-bottom: 1px solid #444;'>
                <td style='padding: 8px; color: white;'>Solar PV System</td>
                <td style='padding: 8px; text-align: center; color: white;'>kWp</td>
                <td style='padding: 8px; text-align: right; color: white;'>${PRICE_PV:,.0f}</td>
                <td style='padding: 8px; text-align: right; color: white;'>${cost_pv_a:,.0f}</td>
                <td style='padding: 8px; text-align: right; color: white;'>${cost_pv_b:,.0f}</td>
                <td style='padding: 8px; color: #aaa; padding-left: 15px;'>모듈, 인버터, 구조물 및 설치비 포함 (글로벌 평균)</td>
            </tr>
            <tr style='border-bottom: 1px solid #444;'>
                <td style='padding: 8px; color: white;'>BESS (Battery)</td>
                <td style='padding: 8px; text-align: center; color: white;'>kWh</td>
                <td style='padding: 8px; text-align: right; color: white;'>${PRICE_BESS:,.0f}</td>
                <td style='padding: 8px; text-align: right; color: white;'>${cost_bess_a:,.0f}</td>
                <td style='padding: 8px; text-align: right; color: white;'>${cost_bess_b:,.0f}</td>
                <td style='padding: 8px; color: #aaa; padding-left: 15px;'>Li-ion 랙, PCS 및 컨테이너 패키징 공사비</td>
            </tr>
            <tr style='border-bottom: 1px solid #444; color: #00d4ff;'>
                <td style='padding: 8px;'>Electrolyzer (H2)</td>
                <td style='padding: 8px; text-align: center;'>kW</td>
                <td style='padding: 8px; text-align: right;'>${PRICE_EL:,.0f}</td>
                <td style='padding: 8px; text-align: right;'>-</td>
                <td style='padding: 8px; text-align: right;'>${cost_el:,.0f}</td>
                <td style='padding: 8px; color: #00d4ff; padding-left: 15px;'>PEM 수전해 스택 및 BOP(정수, 건조) 시스템 일체</td>
            </tr>
            <tr style='border-bottom: 1px solid #444; color: #00d4ff;'>
                <td style='padding: 8px;'>Fuel Cell (H2)</td>
                <td style='padding: 8px; text-align: center;'>kW</td>
                <td style='padding: 8px; text-align: right;'>${PRICE_FC:,.0f}</td>
                <td style='padding: 8px; text-align: right;'>-</td>
                <td style='padding: 8px; text-align: right;'>${cost_fc:,.0f}</td>
                <td style='padding: 8px; color: #00d4ff; padding-left: 15px;'>Stationary PEM 수소 연료전지 발전기 시스템</td>
            </tr>
            <tr style='border-bottom: 1px solid #444; color: #00d4ff;'>
                <td style='padding: 8px;'>H2 Storage Tank</td>
                <td style='padding: 8px; text-align: center;'>kg</td>
                <td style='padding: 8px; text-align: right;'>$500</td>
                <td style='padding: 8px; text-align: right;'>-</td>
                <td style='padding: 8px; text-align: right;'>${cost_h2_tank:,.0f}</td>
                <td style='padding: 8px; color: #00d4ff; padding-left: 15px;'>350bar 고압 기체 저장 탱크 (Type-III)</td>
            </tr>
            <tr style='border-bottom: 2px solid #555;'>
                <td style='padding: 8px; color: white;'>Distribution/Grid</td>
                <td style='padding: 8px; text-align: center; color: white;'>hh</td>
                <td style='padding: 8px; text-align: right; color: white;'>$1,500</td>
                <td style='padding: 8px; text-align: right; color: white;'>${cost_dist:,.0f}</td>
                <td style='padding: 8px; text-align: right; color: white;'>${cost_dist:,.0f}</td>
                <td style='padding: 8px; color: #aaa; padding-left: 15px;'>마을 내 가공 배전로, 전신주 및 가구별 계량기</td>
            </tr>
            <tr style='background-color: #222; font-size: 15px; font-weight: bold;'>
                <td colspan='3' style='padding: 10px; text-align: center;'>총 투자비 (Total CAPEX)</td>
                <td style='padding: 10px; text-align: right; color: #ff4b4b;'>${capex_a:,.0f}</td>
                <td style='padding: 10px; text-align: right; color: #00d4ff;'>${capex_b:,.0f}</td>
                <td style='padding: 10px;'></td>
            </tr>
        </table>
        """
        st.markdown(breakdown_html, unsafe_allow_html=True)
        st.info(f"💡 **분석 결과:** Scenario B(하이브리드)가 시나리오 A 대비 **${(capex_a - capex_b)/1e6:.2f}M ({ (1 - capex_b/capex_a)*100:.1f}%)**의 비용 절감 효과가 있는 것으로 나타났습니다.")

        # 5. EDCF 기반 LCOE 비교 (Moved to main tab)
        st.markdown("### 🪙 5. EDCF 금융 모델 기반 사업성 분석")
        st.markdown("""
        <div style='background-color: #1a1f2b; padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #333;'>
            <p style='margin: 0; color: #ddd; font-size: 14px;'>
                <b>💡 금융 조건 알림:</b> 본 분석의 LCOE(균등화발전비용)는 <b>시나리오 A와 B 모두 동일하게</b> EDCF 양자 차관 조건(이율 0.01%, 40년 상환)을 반영하여 산출되었습니다.
            </p>
        </div>
        """, unsafe_allow_html=True)

        lcoe_saving = (lcoe_a - lcoe_b) / lcoe_a * 100
        lcoe_html = f"""
        <div style='display: flex; gap: 20px; margin-bottom: 20px;'>
            <div style='flex: 1; background: #1a1f2b; padding: 20px; border-radius: 15px; border-top: 5px solid #ff4b4b; text-align: center;'>
                <p style='margin: 0; color: #aaa; font-size: 14px;'>LCOE (Scenario A)</p>
                <h2 style='margin: 10px 0; color: #ff4b4b; font-size: 32px;'>${lcoe_a:.3f}<span style='font-size: 16px; color: #aaa;'> /kWh</span></h2>
                <p style='margin: 0; color: #888; font-size: 12px;'>Giant BESS Only</p>
            </div>
            <div style='flex: 1; background: #1a1f2b; padding: 20px; border-radius: 15px; border-top: 5px solid #00d4ff; text-align: center;'>
                <p style='margin: 0; color: #aaa; font-size: 14px;'>LCOE (Scenario B)</p>
                <h2 style='margin: 10px 0; color: #00d4ff; font-size: 32px;'>${lcoe_b:.3f}<span style='font-size: 16px; color: #aaa;'> /kWh</span></h2>
                <p style='margin: 0; color: #888; font-size: 12px;'>BESS-HESS Hybrid</p>
            </div>
            <div style='flex: 1; background: linear-gradient(135deg, #00d4ff 0%, #0055ff 100%); padding: 20px; border-radius: 15px; text-align: center;'>
                <p style='margin: 0; color: rgba(255,255,255,0.8); font-size: 14px;'>LCOE 절감 효과</p>
                <h2 style='margin: 10px 0; color: white; font-size: 36px;'>{lcoe_saving:.1f}%</h2>
                <p style='margin: 0; color: rgba(255,255,255,0.6); font-size: 12px;'>Scenario B vs A</p>
            </div>
        </div>
        """
        st.markdown(lcoe_html, unsafe_allow_html=True)
        
        st.success(f"✅ **Sweet Spot Insight:** 수소 하이브리드(Scenario B) 시스템을 적용할 경우, 배터리 단독 모델 대비 연간 균등화발전원가(LCOE)를 **{lcoe_saving:.1f}%** 절감할 수 있으며, 이는 프로젝트의 장기적 재무 건전성을 획기적으로 개선합니다.")

    with tabs[1]:
        from plotly.subplots import make_subplots
        st.subheader("🔍 상세 시계열 데이터 분석 (Time-Span Analysis)")
        span = st.radio("분석 주기 선택", ["1H", "1D", "1W", "1M"], horizontal=True)
        span_map = {"1H": "H", "1D": "D", "1W": "W", "1M": "M"}
        df_resampled = df_h.set_index('Timestamp').resample(span_map[span]).agg({
            'SOC_B': 'mean', 'H2_Stock': 'last', 'Gen_B': 'sum', 'Load_B': 'sum'
        }).reset_index()
        df_resampled['Net Balance'] = df_resampled['Gen_B'] - df_resampled['Load_B']
        
        fig_span = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                                 subplot_titles=("에너지 순 수지 (kWh)", "배터리 SOC (%)", "수소 저장량 (kg)"))
        fig_span.add_trace(go.Bar(x=df_resampled['Timestamp'], y=df_resampled['Net Balance'], marker_color=['#00d4ff' if x>0 else '#ff4b4b' for x in df_resampled['Net Balance']]), row=1, col=1)
        fig_span.add_trace(go.Scatter(x=df_resampled['Timestamp'], y=df_resampled['SOC_B'], name="BESS SOC", line=dict(color="#00d4ff", width=2)), row=2, col=1)
        fig_span.add_trace(go.Scatter(x=df_resampled['Timestamp'], y=df_resampled['H2_Stock'], name="수소 잔량", fill='tozeroy', line=dict(color="#00ff88", width=2)), row=3, col=1)
        
        fig_span.update_layout(template="plotly_dark", height=800, margin=dict(l=50,r=20,t=60,b=20), hovermode="x unified", showlegend=False)
        fig_span.update_yaxes(gridcolor="#333")
        st.plotly_chart(fig_span, use_container_width=True)

    with tabs[2]:
        df_daily = df_h.groupby(df_h['Timestamp'].dt.date).agg({
            'Gen_B': 'sum', 'Load_B': 'sum', 'SOC_B': 'last', 'H2_Prod': 'sum', 'H2_Stock': 'last'
        }).reset_index()
        df_daily['Net Balance'] = df_daily['Gen_B'] - df_daily['Load_B']
        st.dataframe(df_daily.style.format(precision=1), use_container_width=True)
        
        csv = df_daily.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Daily Ledger CSV 다운로드", data=csv, file_name=f"ledger_{st.session_state.country}.csv", mime='text/csv')
