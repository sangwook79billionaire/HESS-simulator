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
    "Afghanistan": {"demand": 1.2, "rate": 0.05},
    "Argentina": {"demand": 12.0, "rate": 0.04},
    "Bangladesh": {"demand": 2.0, "rate": 0.06},
    "Bhutan": {"demand": 4.0, "rate": 0.04},
    "Brazil": {"demand": 6.5, "rate": 0.19},
    "Cambodia": {"demand": 1.5, "rate": 0.14},
    "Canada": {"demand": 32.0, "rate": 0.12},
    "Chile": {"demand": 7.0, "rate": 0.16},
    "Colombia": {"demand": 5.5, "rate": 0.15},
    "Egypt": {"demand": 9.0, "rate": 0.03},
    "Ecuador": {"demand": 5.0, "rate": 0.09},
    "Ethiopia": {"demand": 0.5, "rate": 0.01},
    "Fiji": {"demand": 4.0, "rate": 0.13},
    "France": {"demand": 12.5, "rate": 0.25},
    "Germany": {"demand": 8.5, "rate": 0.42},
    "Ghana": {"demand": 1.5, "rate": 0.12},
    "Global Average": {"demand": 5.0, "rate": 0.15},
    "Guatemala": {"demand": 3.0, "rate": 0.21},
    "India": {"demand": 2.5, "rate": 0.08},
    "Indonesia": {"demand": 4.2, "rate": 0.10},
    "Iraq": {"demand": 12.0, "rate": 0.03},
    "Japan": {"demand": 15.5, "rate": 0.26},
    "Jordan": {"demand": 8.0, "rate": 0.10},
    "Kenya": {"demand": 0.8, "rate": 0.20},
    "Laos": {"demand": 2.0, "rate": 0.05},
    "Lebanon": {"demand": 7.0, "rate": 0.01},
    "Malaysia": {"demand": 15.0, "rate": 0.06},
    "Mexico": {"demand": 10.0, "rate": 0.11},
    "Morocco": {"demand": 4.5, "rate": 0.11},
    "Myanmar": {"demand": 1.2, "rate": 0.04},
    "Nepal": {"demand": 1.5, "rate": 0.09},
    "Nigeria": {"demand": 1.2, "rate": 0.06},
    "Norway": {"demand": 45.0, "rate": 0.15},
    "Pakistan": {"demand": 1.8, "rate": 0.10},
    "Papua New Guinea": {"demand": 1.0, "rate": 0.12},
    "Peru": {"demand": 4.5, "rate": 0.17},
    "Philippines": {"demand": 3.5, "rate": 0.18},
    "Rwanda": {"demand": 0.4, "rate": 0.22},
    "South Africa": {"demand": 8.5, "rate": 0.16},
    "South Korea": {"demand": 11.2, "rate": 0.12},
    "Sri Lanka": {"demand": 3.0, "rate": 0.10},
    "Tanzania": {"demand": 0.7, "rate": 0.15},
    "Thailand": {"demand": 7.5, "rate": 0.13},
    "Uganda": {"demand": 0.5, "rate": 0.18},
    "United Kingdom": {"demand": 10.0, "rate": 0.35},
    "United States": {"demand": 29.5, "rate": 0.18},
    "Vietnam": {"demand": 5.0, "rate": 0.08},
    "Yemen": {"demand": 1.0, "rate": 0.15},
    "Zambia": {"demand": 1.2, "rate": 0.05},
    "Zimbabwe": {"demand": 1.8, "rate": 0.13}
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

# Technical Efficiency Constants
BESS_EFF = 0.90  # Round-trip 90%
H2_EL_EFF = 0.70 # Electrolyzer
H2_FC_EFF = 0.50 # Fuel Cell
INV_EFF = 0.95   # Inverter/System

# --- Session State ---
if 'step' not in st.session_state: st.session_state.step = 'input'
if 'lat' not in st.session_state: st.session_state.lat = -8.4095
if 'lon' not in st.session_state: st.session_state.lon = 115.1889
if 'country' not in st.session_state: st.session_state.country = 'Bali, Indonesia'
if 'mix_slider' not in st.session_state: st.session_state.mix_slider = 50

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

if st.session_state.step == 'input':
    st.title("🌍 Universal Net-Zero Microgrid Optimizer")
    st.markdown("전 세계 격오지 재생에너지 전환을 위한 하이브리드 시스템 설계 솔루션")
    st.markdown("""
    <div style='background: rgba(0, 212, 255, 0.1); padding: 10px 15px; border-radius: 8px; border-left: 4px solid #00d4ff; margin-bottom: 20px;'>
        <span style='color: #00d4ff; font-weight: bold;'>📖 시뮬레이터 사용법:</span> 
        <span style='color: #ccc; margin-left: 10px;'>1. 위치 선정 ➜ 2. 수요 설정 ➜ 3. 에너지 부하 패턴 지정</span>
    </div>
    """, unsafe_allow_html=True)

    main_tabs = st.tabs(["📍 단일 지점 분석", "🚀 대량 배치 시뮬레이션"])
    
    with main_tabs[0]:
        col1, col2 = st.columns([1, 1.2])
        with col1:
            st.subheader("📍 1. 위치 및 수요 설정")
            st.markdown("<small style='color: #888;'>지명을 검색하거나 지도 위의 포인트를 클릭하여 위치를 선정하세요.</small>", unsafe_allow_html=True)
            
            address = st.text_input("지역 검색 (Geocoding)", value=st.session_state.country)
            if st.button("위치 확인"):
                try:
                    from geopy.geocoders import ArcGIS
                    geolocator = ArcGIS(user_agent="net_zero_simulator_sangwook_v1")
                    loc = geolocator.geocode(address, timeout=10)
                    if loc:
                        st.session_state.lat, st.session_state.lon, st.session_state.country = loc.latitude, loc.longitude, loc.address
                        st.rerun()
                    else:
                        st.error("검색 결과가 없습니다. 다른 지명을 입력해 주세요.")
                except:
                    st.error("위치 서비스(ArcGIS)가 일시적으로 응답하지 않습니다. 지도에서 직접 클릭해 주세요.")
            
            m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=10)
            folium.Marker([st.session_state.lat, st.session_state.lon], tooltip="선택된 위치").add_to(m)
            
            # Restore Map Click Functionality
            map_out = st_folium(m, height=300, use_container_width=True, key="location_map")
            
            if map_out and map_out.get("last_clicked"):
                new_lat = map_out["last_clicked"]["lat"]
                new_lng = map_out["last_clicked"]["lng"]
                if abs(new_lat - st.session_state.lat) > 0.0001 or abs(new_lng - st.session_state.lon) > 0.0001:
                    st.session_state.lat = new_lat
                    st.session_state.lon = new_lng
                    # Attempt reverse geocode using ArcGIS
                    try:
                        from geopy.geocoders import ArcGIS
                        geolocator = ArcGIS(user_agent="net_zero_simulator_sangwook_v1")
                        rev = geolocator.reverse(f"{new_lat}, {new_lng}", timeout=5)
                        if rev: st.session_state.country = rev.address
                    except:
                        pass
                    st.rerun()
            
            st.info(f"현재 선택 좌표: {st.session_state.lat:.4f}, {st.session_state.lon:.4f}")
            
        with col2:
            st.subheader("⚡ 2. 에너지 부하 패턴 (Mixed Load)")
            hh = st.number_input("가구 수 (Households)", value=500, min_value=1)
            st.session_state.hh = hh
            
            mode = st.radio("수요 산정", ["국가별 레퍼런스", "직접 입력"], horizontal=True)
            if mode == "국가별 레퍼런스":
                # Auto-detect country from session state address
                addr_parts = st.session_state.country.split(',')
                detected_country = addr_parts[-1].strip() if addr_parts else ""
                
                benchmark_list = list(COUNTRY_BENCHMARKS.keys())
                # Find best match index
                default_idx = 0
                for i, c in enumerate(benchmark_list):
                    if c.lower() in detected_country.lower():
                        default_idx = i
                        break
                
                c_name = st.selectbox("대상 국가 선택 (출처: IEA/World Bank 2023)", benchmark_list, index=default_idx)
                avg_kwh = COUNTRY_BENCHMARKS[c_name]['demand']
            else:
                avg_kwh = st.number_input("가구당 일일 사용량 (kWh)", value=5.0)
            
            total_daily_kwh = hh * avg_kwh
            st.success(f"총 일일 수요: {total_daily_kwh:,.1f} kWh")
            
            st.write("📈 **에너지 부하 특성 조합 (Dynamic Load Mix)**")
            
            res_pct = st.session_state.get('mix_slider', 50)
            com_pct = 100 - res_pct
            st.markdown(f"""
            <div style='display: flex; width: auto; height: 40px; border-radius: 6px; overflow: hidden; margin: 0 12px 10px 12px; border: 1px solid #444;'>
                <div style='flex: {res_pct if res_pct > 0 else 0.1}; background: linear-gradient(90deg, #801a1a 0%, #ff4b4b 100%); display: flex; align-items: center; padding-left: 15px; transition: flex 0.1s ease;'>
                    <span style='color: white; font-weight: bold; white-space: nowrap; font-size: 13px;'>🏠 주거 {res_pct}%</span>
                </div>
                <div style='flex: {com_pct if com_pct > 0 else 0.1}; background: linear-gradient(90deg, #00d4ff 0%, #0055ff 100%); display: flex; align-items: center; justify-content: flex-end; padding-right: 15px; transition: flex 0.1s ease;'>
                    <span style='color: white; font-weight: bold; white-space: nowrap; font-size: 13px;'>상업 {com_pct}% 🏢</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            mix_val = st.slider("부하 패턴 혼합 비율", 0, 100, 50, key='mix_slider', label_visibility="collapsed")
            
            ratio_a = mix_val / 100.0
            ratio_b = 1.0 - ratio_a
            
            combined_pattern = [(PATTERN_A[i]*ratio_a + PATTERN_B[i]*ratio_b) for i in range(24)]
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

    with main_tabs[1]:
        st.subheader("🚀 지도 기반 대량 배치 시뮬레이션 (Spatial Batch)")
        st.markdown("""
        지도 위를 클릭하여 지점들을 선택하세요. 각 지역의 국가별 전력 수요 통계가 자동으로 반영됩니다.
        """)
        
        if 'batch_list' not in st.session_state:
            st.session_state.batch_list = []
        if 'batch_results' not in st.session_state:
            st.session_state.batch_results = []
            
        b_col1, b_col2 = st.columns([2, 1])
        
        with b_col1:
            bm = folium.Map(location=[0, 0], zoom_start=2)
            for i, loc in enumerate(st.session_state.batch_list):
                folium.Marker([loc['lat'], loc['lon']], popup=f"{loc['name']} ({loc['country']})").add_to(bm)
            
            map_batch = st_folium(bm, height=450, use_container_width=True, key="batch_map_v2")
            
            if map_batch and map_batch.get("last_clicked"):
                b_lat, b_lng = map_batch["last_clicked"]["lat"], map_batch["last_clicked"]["lng"]
                if not st.session_state.batch_list or (abs(st.session_state.batch_list[-1]['lat'] - b_lat) > 0.001):
                    try:
                        from geopy.geocoders import ArcGIS
                        geolocator = ArcGIS(user_agent="net_zero_batch_v2")
                        rev = geolocator.reverse(f"{b_lat}, {b_lng}", timeout=3)
                        # Extract country for benchmark matching
                        addr_parts = rev.address.split(',')
                        b_country = addr_parts[-1].strip()
                        b_name = addr_parts[0].strip()
                    except:
                        b_country = "Unknown"
                        b_name = f"Point_{len(st.session_state.batch_list)+1}"
                    
                    st.session_state.batch_list.append({
                        'name': b_name, 'lat': b_lat, 'lon': b_lng, 'country': b_country
                    })
                    st.rerun()

        with b_col2:
            st.markdown("### ⚙️ 일괄 설정 (Batch Settings)")
            batch_hh = st.number_input("모든 지점 가구 수 적용", 1, 5000, 500)
            
            st.markdown(f"**선택된 지점: {len(st.session_state.batch_list)}개**")
            if st.session_state.batch_list:
                batch_df_show = pd.DataFrame(st.session_state.batch_list)
                st.dataframe(batch_df_show[['name', 'country']], use_container_width=True, height=200)
                
                c1, c2 = st.columns(2)
                if c1.button("🔄 리스트 초기화", use_container_width=True):
                    st.session_state.batch_list = []; st.session_state.batch_results = []; st.rerun()
                
                if c2.button("🔥 시뮬레이션 시작", type="primary", use_container_width=True):
                    st.session_state.batch_results = []
                    prog = st.progress(0)
                    status = st.empty()
                    
                    for idx, loc in enumerate(st.session_state.batch_list):
                        status.text(f"📡 {loc['name']} 분석 중... ({loc['country']})")
                        try:
                            # Match Country Benchmark
                            matched_country = next((c for c in COUNTRY_BENCHMARKS.keys() if c.lower() in loc['country'].lower()), "Global Average")
                            avg_kwh = COUNTRY_BENCHMARKS.get(matched_country, {"demand": 3.0})['demand']
                            b_total_d = batch_hh * avg_kwh
                            
                            b_df_h = get_nasa_data(loc['lat'], loc['lon'])
                            if b_df_h is not None:
                                # Logic from single-site simulation
                                b_df_h['Gen_1kW'] = (b_df_h['Insolation'] * (0.85 * (1 - 0.004 * (b_df_h['Temp'] - 25))) * INV_EFF) / 1000
                                b_yield = b_df_h['Gen_1kW'].sum()
                                b_pv_ideal = (b_total_d * 365) / (b_yield * 0.98)
                                
                                # Scenario A
                                b_bess_a = b_total_d * 15 # Simplified
                                b_capex_a = (b_pv_ideal * PRICE_PV) + (b_bess_a * PRICE_BESS) + (batch_hh * 1500)
                                
                                # Scenario B
                                b_pv_hybrid = b_pv_ideal * 1.3
                                b_bess_b = b_total_d * 1.5
                                b_el, b_fc = b_total_d/6, b_total_d/10
                                
                                # 2-Pass for trace data
                                b_soc, b_h2 = 50.0, 0.0
                                b_soc_trace, b_h2_trace = [], []
                                for _, r in b_df_h.iterrows():
                                    gl, ll = r['Gen_1kW'] * b_pv_hybrid, (b_total_d / 24)
                                    bal = gl - ll
                                    if bal > 0:
                                        ch = min(bal, (95-b_soc)*b_bess_b/100)
                                        b_soc += (ch * np.sqrt(BESS_EFF) / b_bess_b) * 100
                                        bal -= ch
                                        if bal > 0 and b_soc >= 90: b_h2 += (min(bal, b_el) * H2_EL_EFF) / 33.33
                                    else:
                                        defic = abs(bal)
                                        if b_soc > 20:
                                            dis = min(defic, (b_soc-20)*b_bess_b/100/np.sqrt(BESS_EFF))
                                            b_soc -= (dis * np.sqrt(BESS_EFF) / b_bess_b) * 100
                                            defic -= dis
                                        if defic > 0: b_h2 -= (min(defic, b_fc) / H2_FC_EFF) / 33.33
                                    b_soc_trace.append(b_soc); b_h2_trace.append(b_h2)
                                
                                b_h2_max = max(b_h2_trace)
                                b_capex_b = (b_pv_hybrid * PRICE_PV) + (b_bess_b * PRICE_BESS) + (b_el * PRICE_EL) + (b_fc * PRICE_FC) + (b_h2_max * PRICE_TANK) + (batch_hh * 1500)
                                
                                st.session_state.batch_results.append({
                                    'loc': loc, 'df_h': b_df_h, 'res': {
                                        'pv_a': b_pv_ideal, 'bess_a': b_bess_a, 'capex_a': b_capex_a,
                                        'pv_b': b_pv_hybrid, 'bess_b': b_bess_b, 'h2_max': b_h2_max, 'capex_b': b_capex_b,
                                        'soc_trace': b_soc_trace, 'h2_trace': b_h2_trace, 'country_match': matched_country, 'demand': avg_kwh
                                    }
                                })
                        except Exception as e:
                            st.warning(f"Error at {loc['name']}: {e}")
                        prog.progress((idx + 1) / len(st.session_state.batch_list))
                    status.text("✅ 시뮬레이션 완료!")
                    st.rerun()

        # Batch Results Dashboard
        if st.session_state.batch_results:
            st.divider()
            st.subheader("📊 배치 시뮬레이션 상세 리포트")
            
            for b_res in st.session_state.batch_results:
                loc, res, b_df = b_res['loc'], b_res['res'], b_res['df_h']
                with st.expander(f"📍 {loc['name']} ({loc['country']}) - 분석 결과 확인", expanded=False):
                    m1, m2 = st.columns([1, 2])
                    with m1:
                        st.markdown(f"**적용 데이터:** {res['country_match']} (가구당 {res['demand']}kWh/d)")
                        st.markdown(f"""
                        <div style='background:#111; padding:15px; border-radius:10px; border-left:4px solid #00d4ff;'>
                            <p style='margin:0; font-size:14px; color:#aaa;'>시스템 구성 (Scenario B)</p>
                            <ul style='font-size:13px; color:#eee; margin-top:10px;'>
                                <li>태양광: <b>{res['pv_b']:,.0f} kWp</b></li>
                                <li>배터리: <b>{res['bess_b']:,.0f} kWh</b></li>
                                <li>수소탱크: <b>{res['h2_max']:,.1f} kg</b></li>
                            </ul>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # CAPEX Comparison
                        saving = (1 - res['capex_b']/res['capex_a']) * 100
                        st.markdown(f"""
                        <div style='margin-top:20px; text-align:center;'>
                            <p style='color:#aaa; font-size:12px;'>투자비 총액 비교 (CAPEX)</p>
                            <h4 style='color:#ff4b4b; margin:0;'>A: ${res['capex_a']/1e6:.2f}M</h4>
                            <h4 style='color:#00d4ff; margin:5px 0;'>B: ${res['capex_b']/1e6:.2f}M</h4>
                            <div style='background:#00d4ff; color:black; font-weight:bold; padding:5px; border-radius:5px; margin-top:10px;'>
                                {saving:.1f}% 절감 효과
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    with m2:
                        # Monthly Net Balance + GHI
                        b_df['Month'] = b_df['Timestamp'].dt.month
                        monthly_net = (b_df['Gen_1kW']*res['pv_b'] - (batch_hh*res['demand']/24)).groupby(b_df['Month']).sum()
                        monthly_ghi = b_df['Insolation'].groupby(b_df['Month']).mean()
                        st.plotly_chart(create_net_chart(monthly_net, monthly_ghi, f"{loc['name']} 월간 수지 & 일사량"), use_container_width=True)
                        
                        # Hybrid Status
                        fig_b = make_subplots(specs=[[{"secondary_y": True}]])
                        fig_b.add_trace(go.Scatter(x=b_df['Timestamp'], y=res['soc_trace'], name="SOC(%)", line=dict(color="#00d4ff")), secondary_y=False)
                        fig_b.add_trace(go.Scatter(x=b_df['Timestamp'], y=res['h2_trace'], name="H2(kg)", fill='tozeroy', line=dict(color="#00ff88")), secondary_y=True)
                        fig_b.update_layout(height=250, margin=dict(l=0,r=0,t=30,b=0), template="plotly_dark", showlegend=False, title="BESS SOC & 수소 저장량")
                        st.plotly_chart(fig_b, use_container_width=True)

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
    
    # Efficiency Constants (Now Global)
    
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
    tabs = st.tabs(["📊 종합 분석 리포트", "🔍 상세 시계열 분석", "📥 데이터 익스포트", "🚀 배치 시뮬레이션"])
    
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
        
        col_title, col_cta = st.columns([3, 1])
        with col_title:
            st.markdown("### 🏗️ 2. 시스템 아키텍처 비교 (System Architecture Comparison)")
        with col_cta:
            with st.popover("📖 설계 산출 로직 확인 (Design Rationale)", use_container_width=True):
                st.markdown(f"""
                <div style='background-color: #0f172a; padding: 20px; border-radius: 10px; color: #e2e8f0; font-size: 14px; line-height: 1.8;'>
                    <h4 style='color: #38bdf8; margin-top: 0;'>💡 설계 산출 로직</h4>
                    <div style='margin-bottom: 20px;'>
                        <b style='color: #38bdf8;'>1. 데이터 분석</b><br>
                        NASA 기상 데이터와 마을의 24시간 전력 사용 패턴을 결합하여 1시간 단위의 에너지 수지를 시뮬레이션합니다.
                    </div>
                    <div style='margin-bottom: 20px;'>
                        <b style='color: #38bdf8;'>2. 시나리오 A 도출</b><br>
                        일조량이 가장 적은 기간에도 정전이 발생하지 않도록 오직 <b>배터리 용량만</b>을 늘려 설계합니다.
                    </div>
                    <div style='margin-bottom: 20px;'>
                        <b style='color: #38bdf8;'>3. 시나리오 B 도출</b><br>
                        배터리는 단기 변동만 담당하고, 잉여 에너지를 <b>수소로 저장</b>해 장기적으로 꺼내 쓰는 '계절 이동' 원리를 적용합니다.
                    </div>
                    <div style='margin-bottom: 10px;'>
                        <b style='color: #38bdf8;'>4. 경제성 최적화</b><br>
                        두 시나리오 중 전체 투자비(CAPEX)와 운영 비용을 고려하여 가장 낮은 발전단가(LCOE)를 만드는 설비 조합을 선정합니다.
                    </div>
                </div>
                """, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        
        # Footprint Estimation
        area_a = (pv_ideal * 10) + (bess_a * 0.1)
        area_b = (pv_hybrid * 10) + (bess_b * 0.1) + (max(h2_stock) * 1.5) + 50 # Including EL/FC base

        with c1:
            st.markdown(f"""
            <div style='background-color: #1a1a1a; padding: 25px; border-radius: 12px; border: 1px solid #ff4b4b; min-height: 520px; color: #eee;'>
                <h4 style='color: #ff4b4b; text-align: center; font-size: 20px; margin-bottom: 15px;'>Scenario A: Giant BESS Only</h4>
                <div style='text-align: center; font-size: 40px; margin: 10px 0;'>☀️ ➡ 🔋 ➡ 🏠</div>
                <p style='font-size: 15px; color: #ccc; line-height: 1.5;'>거대 배터리 뱅크를 통해 계절적 불균형을 해소하는 단순 구조입니다.</p>
                <hr style='border-color: #444;'>
                <ul style='list-style: none; padding: 0; font-size: 18px;'>
                    <li style='margin-bottom: 15px;'><span style='font-size: 17px; color: #aaa;'>PV 규모:</span> <br><b style='color: #fff; font-size: 22px;'>{pv_ideal:,.1f} kWp</b></li>
                    <li style='margin-bottom: 15px;'><span style='font-size: 17px; color: #aaa;'>BESS 용량:</span> <br><b style='color: #fff; font-size: 22px;'>{bess_a:,.1f} kWh</b> <span style='font-size: 16px; color: #ff4b4b; font-weight: bold;'>({bess_a/total_d:.1f}일분)</span></li>
                    <li style='margin-top: 15px; border-top: 1px dashed #444; padding-top: 15px;'>
                        <span style='font-size: 16px; color: #aaa;'>📐 점유 면적 추정 (Footprint):</span><br>
                        <b style='color: #fff; font-size: 20px;'>{area_a:,.0f} m²</b> <small style='color: #888;'>(약 {area_a/3.3058:,.1f}평)</small>
                        <div style='font-size: 11px; color: #888; margin-top: 8px; line-height: 1.4;'>
                            • PV: {pv_ideal * 10:,.0f}m²(10m²/kWp) | • BESS: {bess_a * 0.1:,.0f}m²(0.1m²/kWh) | • HESS: 0m²(1.5m²/kg)
                        </div>
                    </li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            h2_days = (max(h2_stock) * 33.33 * H2_FC_EFF) / total_d
            st.markdown(f"""
            <div style='background-color: #1a1a1a; padding: 25px; border-radius: 12px; border: 1px solid #00d4ff; min-height: 520px; color: #eee;'>
                <h4 style='color: #00d4ff; text-align: center; font-size: 20px; margin-bottom: 15px;'>Scenario B: BESS-HESS Hybrid</h4>
                <div style='text-align: center; font-size: 40px; margin: 10px 0;'>☀️ ➡ 🔋 + 💧(H2) ➡ 🏠</div>
                <p style='font-size: 15px; color: #ccc; line-height: 1.5;'>배터리와 수소가 단기/장기 변동을 나누어 담당하여 효율을 극대화합니다.</p>
                <hr style='border-color: #444;'>
                <ul style='list-style: none; padding: 0; font-size: 18px;'>
                    <li style='margin-bottom: 15px;'>
                        <span style='font-size: 17px; color: #aaa;'>PV 규모:</span> <br>
                        <b style='color: #fff; font-size: 22px;'>{pv_hybrid:,.1f} kWp</b> 
                        <span style='font-size: 12px; color: #00d4ff;'> (*수소 효율 고려로 인한 PV 증대 반영)</span>
                    </li>
                    <li style='margin-bottom: 20px;'><span style='font-size: 17px; color: #aaa;'>에너지 저장 시스템 (BESS + HESS):</span> <br>
                        <span style='font-size: 16px; color: #ccc;'>▪️ BESS: <b style='color: #fff;'>{bess_b:,.1f} kWh</b> (1.5일분) | ▪️ HESS: <b style='color: #00d4ff;'>{el_kw:,.1f}/{fc_kw:,.1f} kW</b>, <b style='color: #00ff88;'>{max(h2_stock):,.1f} kg</b></span>
                    </li>
                    <li style='margin-top: 15px; border-top: 1px dashed #444; padding-top: 15px;'>
                        <span style='font-size: 16px; color: #aaa;'>📐 점유 면적 추정 (Footprint):</span><br>
                        <b style='color: #fff; font-size: 20px;'>{area_b:,.0f} m²</b> <small style='color: #888;'>(약 {area_b/3.3058:,.1f}평)</small>
                        <div style='font-size: 11px; color: #888; margin-top: 8px; line-height: 1.4;'>
                            • PV: {pv_hybrid * 10:,.0f}m²(10m²/kWp) | • BESS: {bess_b * 0.1:,.0f}m²(0.1m²/kWh) | • HESS: {max(h2_stock) * 1.5 + 50:,.0f}m²(1.5m²/kg)
                        </div>
                    </li>
                </ul>
            </div>
            """, unsafe_allow_html=True)



        # 3. 주요 운영 지표 시각화
        st.markdown("### 📊 3. 시나리오별 주요 지표 비교 (Operational Indicators)")
        
        # Monthly Net Balance & Solar Data
        df_h['Month'] = df_h['Timestamp'].dt.month
        monthly_net_a = df_a.groupby(df_a['Timestamp'].dt.month)['Net'].sum()
        monthly_net_b = df_h.groupby('Month').apply(lambda x: (x['Gen_B'] - x['Load_B']).sum())
        monthly_ghi = df_h.groupby('Month')['Insolation'].mean()
        
        # Unified Y-axis range for comparison
        y_min = min(monthly_net_a.min(), monthly_net_b.min()) * 1.2
        y_max = max(monthly_net_a.max(), monthly_net_b.max()) * 1.2
        
        c_net1, c_net2 = st.columns(2)
        
        def create_net_chart(net_data, ghi_data, title):
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            colors = ['#00d4ff' if x > 0 else '#ff4b4b' for x in net_data.values]
            fig.add_trace(go.Bar(x=net_data.index, y=net_data.values, name="Net Balance", marker_color=colors), secondary_y=False)
            fig.add_trace(go.Scatter(x=ghi_data.index, y=ghi_data.values, name="평균 일사량", line=dict(color="#FFD700", width=3, dash='dot'), mode='lines+markers'), secondary_y=True)
            
            fig.update_layout(title=dict(text=title, font=dict(size=18)), template="plotly_dark", height=350, 
                              margin=dict(l=60, r=60, t=60, b=50), showlegend=True,
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig.update_yaxes(title_text="순 수지 (kWh)", range=[y_min, y_max], secondary_y=False)
            fig.update_yaxes(title_text="일사량 (kWh/m²/d)", secondary_y=True)
            fig.update_xaxes(title_text="월 (Month)", tickmode='linear', tick0=1, dtick=1)
            return fig

        with c_net1:
            st.plotly_chart(create_net_chart(monthly_net_a, monthly_ghi, "Scenario A: 월간 수지 & 일사량"), use_container_width=True)
            # Scenario A SOC
            fig_soc_a = go.Figure()
            fig_soc_a.add_trace(go.Scatter(x=df_h['Timestamp'], y=net_trace, name="BESS SOC", line=dict(color='#ff4b4b', width=1)))
            fig_soc_a.update_layout(title=dict(text="Scenario A: Battery SOC (%)", font=dict(size=18)), 
                                    template="plotly_dark", height=350, margin=dict(l=60, r=60, t=60, b=50))
            fig_soc_a.update_yaxes(title_text="BESS SOC (%)")
            st.plotly_chart(fig_soc_a, use_container_width=True)
            
        with c_net2:
            st.plotly_chart(create_net_chart(monthly_net_b, monthly_ghi, "Scenario B: 월간 수지 & 일사량"), use_container_width=True)
            # Scenario B Hybrid Status
            fig_hybrid = make_subplots(specs=[[{"secondary_y": True}]])
            fig_hybrid.add_trace(go.Scatter(x=df_h['Timestamp'], y=df_h['SOC_B'], name="BESS SOC (%)", line=dict(color="#00d4ff", width=1)), secondary_y=False)
            fig_hybrid.add_trace(go.Scatter(x=df_h['Timestamp'], y=df_h['H2_Stock'], name="수소 저장량 (kg)", fill='tozeroy', line=dict(color="#00ff88", width=1)), secondary_y=True)
            fig_hybrid.update_layout(title=dict(text="Scenario B: BESS & 수소 저장 현황", font=dict(size=18)), 
                                    template="plotly_dark", height=350, margin=dict(l=60, r=60, t=60, b=50), showlegend=False)
            fig_hybrid.update_yaxes(title_text="BESS SOC (%)", secondary_y=False)
            fig_hybrid.update_yaxes(title_text="수소 저장량 (kg)", secondary_y=True)
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

        # --- 4. Financial Feasibility Study (Indonesia Strategy Model) ---
        # --- 4. Financial Feasibility Study (Universal Strategy Model) ---
        st.markdown("### 💰 4. 글로벌 마이크로그리드 사업성 정밀 평가 (Financial Feasibility Study)")
        
        def calculate_fs_metrics(capex, annual_demand, rate, subsidy, other_rev, opex_total, life, discount):
            annual_rev = (annual_demand * rate) + subsidy + other_rev
            annual_net = annual_rev - opex_total
            cash_flows = [-capex] + [annual_net] * int(life)
            
            # Simple NPV
            npv = sum(cf / (1 + discount)**t for t, cf in enumerate(cash_flows))
            
            # IRR search
            def get_irr(flows):
                for r in np.linspace(-0.2, 1.0, 1500):
                    n = sum(cf / (1 + r)**t for t, cf in enumerate(flows))
                    if n < 0: return r * 100
                return 0
            
            # LCOE Calculation
            total_opex_life = opex_total * life
            lcoe = (capex + total_opex_life) / (annual_demand * life)
            
            irr = get_irr(cash_flows)
            payback = capex / annual_net if annual_net > 0 else 99
            return npv, irr, payback, lcoe

        @st.dialog("🚀 글로벌 마이크로그리드 사업성 시뮬레이션", width="large")
        def show_fs_modal():
            st.markdown(f"#### 🌍 {st.session_state.country} 전략적 사업성 검토")
            st.caption("격오지 마이크로그리드 구축을 위한 물류비, 보조금 모델 및 디젤 대체 원가 분석을 지원합니다.")
            
            # Toggle for Desalination
            inc_desal = st.toggle("💧 해수 담수화 시스템 포함 (Desalination Unit)", value=False)
            
            # Initial Data Calculation
            equip_capex = (pv_hybrid * 1000) + (bess_b * 300) + (el_kw * 550) + (fc_kw * 700) + (max(h2_stock) * 650)
            
            # 1. CAPEX Breakdown Editor
            st.markdown("##### 🏗️ A. 초기 투자비 상세 (CAPEX Breakdown)")
            capex_items = {
                "구성 항목": [
                    "Solar PV System", "BESS (Battery)", "Hydrogen System (EL/FC/Tank)", 
                    "해수 담수화/수처리 (Optional)", "에너지 관리 시스템(EMS)", "격오지 물류 및 시공비", "인프라 (배전망 등)"
                ],
                "설정 금액": [
                    int(pv_hybrid * 1000), int(bess_b * 300), 
                    int((el_kw * 550) + (fc_kw * 700) + (max(h2_stock) * 650)),
                    int(equip_capex * 0.07) if inc_desal else 0, 
                    int(equip_capex * 0.03), 
                    int(equip_capex * 0.25), 
                    int(hh * 1500)
                ],
                "설계 및 산출 근거 (Basis)": [
                    f"{pv_hybrid:,.1f} kWp * $1,000/kWp", f"{bess_b:,.1f} kWh * $300/kWh", "H2 System Costs",
                    "전체 CAPEX의 7% (선택 시)" if inc_desal else "미포함", 
                    "설비가액의 3% (EMS)", "장비가의 25% (물류/설치 할증)",
                    f"{hh} 가구 대상 인프라"
                ]
            }
            df_capex = pd.DataFrame(capex_items)
            edited_capex = st.data_editor(
                df_capex, use_container_width=True, num_rows="fixed", key="capex_editor_final",
                column_config={"설정 금액": st.column_config.NumberColumn("설정 금액 (USD)", format="%d")}
            )
            total_capex_fs = edited_capex["설정 금액"].sum()
            
            st.divider()
            
            # 2. Revenue & OPEX Editor
            st.markdown("##### 🪙 B. 수익 및 운영비 상세 (Revenue & OPEX)")
            matched = next((c for c in COUNTRY_BENCHMARKS.keys() if c.lower() in st.session_state.country.lower()), "Global Average")
            ref_rate = COUNTRY_BENCHMARKS[matched]['rate']
            
            rev_opex_items = {
                "구분": ["Revenue", "Revenue", "Revenue", "OPEX", "OPEX"],
                "상세 항목": [
                    "전기 판매 요금 (PPA 단가)", "보조금/디젤 절감 지원금", "담수 판매 및 부가 수익", 
                    "정기 유지보수비 (Fixed PM)", "현지 운영 인건비"
                ],
                "설정값": [ref_rate, 50000.0, 10000.0 if inc_desal else 0.0, float(total_capex_fs * 0.015), 30000.0],
                "운영 및 수익 근거": [
                    "전력 구매 계약 단가", "정부 보조금 등", "식수 판매/탄소권 수익" if inc_desal else "미발생",
                    "연간 CAPEX의 1.5%", "현지 상주 및 운영비"
                ]
            }
            df_rev = pd.DataFrame(rev_opex_items)
            edited_rev = st.data_editor(
                df_rev, use_container_width=True, num_rows="fixed", key="rev_editor_final",
                column_config={"설정값": st.column_config.NumberColumn("설정값", format="%.2f")}
            )
            
            # 3. Financial Terms
            st.markdown("##### 📉 C. 금융 및 타당성 조건 (Financial & Feasibility)")
            c_f1, c_f2, c_f3 = st.columns(3)
            p_life = c_f1.number_input("운영 기간 (Project Life)", 10, 50, 30)
            p_disc = c_f2.number_input("할인율 (%)", 0.0, 20.0, 8.0) / 100
            diesel_ref = c_f3.number_input("에너지 벤치마크 원가 ($/kWh)", 0.0, 1.0, 0.62)
            
            # Calculations
            rev_vals = edited_rev["설정값"].values
            p_rate, p_subsidy, p_other = rev_vals[0], rev_vals[1], rev_vals[2]
            p_opex_total = rev_vals[3] + rev_vals[4]
            
            npv, irr, payback, lcoe_fs = calculate_fs_metrics(total_capex_fs, annual_demand, p_rate, p_subsidy, p_other, p_opex_total, p_life, p_disc)
            
            st.divider()
            st.markdown("#### 📊 전략적 사업성 분석 결과 (Strategic Result)")
            f1, f2, f3 = st.columns(3)
            f1.metric("순현재가치 (NPV)", f"${npv/1e6:.2f}M", delta=f"{'Success' if npv > 0 else 'Deficit'}")
            f2.metric("내부수익률 (IRR)", f"{irr:.2f}%", delta=f"{irr - (p_disc*100):.1f}% vs Target")
            f3.metric("LCOE vs Benchmark", f"${lcoe_fs:.3f}", delta=f"{(lcoe_fs - diesel_ref)/diesel_ref*100:.1f}% vs Benchmark", delta_color="inverse")
            
            fig_lcoe = go.Figure()
            fig_lcoe.add_trace(go.Bar(x=['Benchmark (Diesel)', 'HESS Hybrid (Target)'], y=[diesel_ref, lcoe_fs], marker_color=['#888', '#00d4ff'], width=0.4))
            fig_lcoe.update_layout(title="LCOE 발전 원가 비교 ($/kWh)", template="plotly_dark", height=300, margin=dict(l=0,r=0,t=40,b=0))
            st.plotly_chart(fig_lcoe, use_container_width=True)
            
            st.info(f"💡 **종합 평가:** 본 프로젝트는 벤치마크 원가(${diesel_ref}) 대비 **{abs((lcoe_fs - diesel_ref)/diesel_ref*100):.1f}%**의 높은 원가 경쟁력을 확보하고 있습니다.")
            if st.button("✅ 시나리오 확정 및 닫기", use_container_width=True): st.rerun()

        # Summary Card and CTA
        f_col1, f_col2 = st.columns([2, 1])
        with f_col1:
            st.markdown(f"""
            <div style='background: rgba(0, 212, 255, 0.05); border: 1px solid #00d4ff; padding: 20px; border-radius: 12px;'>
                <p style='margin:0; color:#aaa; font-size:14px;'>Scenario B 전략적 투자 규모 (Estimated CAPEX)</p>
                <h3 style='margin:10px 0; color:#00d4ff;'>Total: ${capex_b * 1.35:,.0f}</h3>
                <p style='margin:0; font-size:13px; color:#888;'>• <b>물류/시공 할증 반영:</b> 격오지 패키지 인프라 포함가</p>
            </div>
            """, unsafe_allow_html=True)
        with f_col2:
            st.write("") # Spacer
            if st.button("🚀 전략 사업성 시뮬레이션", type="primary", use_container_width=True):
                show_fs_modal()
            st.caption("※ 보조금 및 벤치마크 에너지 원가 연동")


    with tabs[1]:
        from plotly.subplots import make_subplots
        st.subheader("🔍 상세 시계열 데이터 분석 (Time-Span Analysis)")
        span = st.radio("분석 주기 선택", ["1D", "1W", "1M"], horizontal=True)
        span_map = {"1D": "d", "1W": "W", "1M": "ME"}
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

    with tabs[3]:
        st.subheader("🚀 대량 위치 배치 시뮬레이션 (Batch Processing)")
        st.markdown("""
        여러 지역의 데이터를 한꺼번에 분석하고 싶을 때 사용하세요. 
        아래 형식의 CSV 파일을 업로드하면 모든 지역에 대해 시뮬레이션을 자동 수행합니다.
        
        **CSV 형식 (헤더 포함):** `Name, Lat, Lon, HH, Demand`
        """)
        
        uploaded_file = st.file_uploader("위치 리스트 CSV 파일 업로드", type="csv")
        
        if uploaded_file is not None:
            batch_df = pd.read_csv(uploaded_file)
            if st.button("배치 시뮬레이션 시작"):
                batch_results = []
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, row in batch_df.iterrows():
                    status_text.text(f"⏳ 처리 중 ({idx+1}/{len(batch_df)}): {row['Name']}...")
                    
                    # Core Logic Subset (Simplified for speed)
                    try:
                        b_lat, b_lon = row['Lat'], row['Lon']
                        b_total_d = row['HH'] * row['Demand']
                        
                        # Fetch NASA (Reuse get_nasa_data)
                        b_df_h = get_nasa_data(b_lat, b_lon)
                        if b_df_h is not None:
                            b_df_h['Gen_1kW'] = (b_df_h['Insolation'] * (0.85 * (1 - 0.004 * (b_df_h['Temp'] - 25))) * INV_EFF) / 1000
                            b_yield = b_df_h['Gen_1kW'].sum()
                            b_pv_ideal = (b_total_d * 365) / (b_yield * 0.98)
                            
                            # Simple BESS sizing for batch
                            b_bess_a = b_total_d * 15 # Heuristic for quick batch
                            b_capex_a = (b_pv_ideal * PRICE_PV) + (b_bess_a * PRICE_BESS) + (row['HH'] * 1500)
                            
                            # Hybrid sizing (simplified)
                            b_pv_hybrid = b_pv_ideal * 1.3
                            b_bess_b = b_total_d * 1.5
                            b_capex_b = (b_pv_hybrid * PRICE_PV) + (b_bess_b * PRICE_BESS) + (b_total_d/6 * PRICE_EL) + (b_total_d/10 * PRICE_FC) + (row['HH'] * 1500)
                            
                            batch_results.append({
                                'Name': row['Name'], 'Lat': b_lat, 'Lon': b_lon,
                                'PV_kWp': b_pv_hybrid, 'BESS_kWh': b_bess_b,
                                'CAPEX_A($)': b_capex_a, 'CAPEX_B($)': b_capex_b,
                                'Saving(%)': (1 - b_capex_b/b_capex_a) * 100
                            })
                    except:
                        pass
                    
                    progress_bar.progress((idx + 1) / len(batch_df))
                
                status_text.text("✅ 모든 배치가 완료되었습니다!")
                res_df = pd.DataFrame(batch_results)
                st.dataframe(res_df.style.format(precision=1), use_container_width=True)
                
                res_csv = res_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 배치 결과 CSV 다운로드", data=res_csv, file_name="batch_results.csv", mime='text/csv')
