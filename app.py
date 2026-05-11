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
if 'lat' not in st.session_state: st.session_state.lat = 0.0
if 'lon' not in st.session_state: st.session_state.lon = 0.0
if 'country' not in st.session_state: st.session_state.country = ''
if 'country_benchmark' not in st.session_state: st.session_state.country_benchmark = 'Global Average'
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
    with st.expander("📖 시뮬레이터 상세 사용 매뉴얼 (User Guide)", expanded=False):
        st.markdown("""
        ### 📗 글로벌 마이크로그리드 시뮬레이터 가이드
        격오지 재생에너지 전환을 위한 시스템 설계 및 사업성 검토 과정을 안내합니다.
        
        ---
        
        #### 1️⃣ Phase 1: 위치 선정 및 데이터 동기화
        *   **위치 검색**: 상단 검색창에 지명을 입력하거나 지도를 직접 클릭하세요.
        *   **위치 확정**: 지점을 선택하는 즉시 NASA 기상 데이터 및 해당 국가의 IEA 통계 데이터가 자동으로 연동됩니다.
        
        #### 2️⃣ Phase 2: 에너지 수요 및 소비 패턴 설계
        *   **가구 수 및 국가 데이터**: 마을 규모와 에너지 사용량을 설정합니다.
        *   **부하 믹스(Load Mix)**: 슬라이더를 조절하여 주거 중심(저녁 피크) 혹은 상업 중심(낮 피크) 패턴을 선택하세요.
        *   **최적 설계 시작**: 모든 설정이 완료되면 **[🚀 시뮬레이션 시작]** 버튼을 클릭합니다.
        
        #### 3️⃣ Phase 3: 시나리오 분석 및 산출 로직 확인
        *   **비교 분석**: 거대 배터리(Scenario A)와 수소 하이브리드(Scenario B)의 장단점을 비교합니다.
        *   **산출 로직**: 각 항목 옆의 **ℹ️ 아이콘**에 마우스를 올리면 상세한 공학적 산출 근거를 확인할 수 있습니다.
        
        #### 4️⃣ Phase 4: 전략적 사업성 검토 (Strategic FS)
        *   **사업성 지표**: 리포트 하단의 버튼을 통해 NPV, IRR, LCOE 등 재무적 타당성을 검토합니다.
        *   **금융 지원 연동**: EDCF 차관 등 실제 금융 지원 패키지를 적용하여 최적의 비즈니스 모델을 도출합니다.
        
        ---
        <small style='color: #888;'>※ 본 매뉴얼을 숙지하신 후 아래 Phase 1부터 분석을 시작해 주세요.</small>
        """, unsafe_allow_html=True)

    main_tabs = st.tabs(["📍 단일 지점 분석", "🚀 대량 배치 시뮬레이션"])
    
    with main_tabs[0]:
        col1, col2 = st.columns([1, 1.2])
        # Robust country detection helper (shared)
        def find_country_match(addr):
            if not addr: return "Global Average"
            # Clean and tokenize (support both English space and potential Asian characters)
            addr_clean = addr.lower().replace(',', ' ').replace('.', ' ')
            words = addr_clean.split()
            benchmark_keys = list(COUNTRY_BENCHMARKS.keys())
            
            # 1. Comprehensive Alias & ISO Code Check (Multilingual & City-Level)
            aliases = {
                # ISO 3-Letter Codes & English
                "kor": "South Korea", "idn": "Indonesia", "vnm": "Vietnam", "phl": "Philippines",
                "tha": "Thailand", "mys": "Malaysia", "usa": "United States", "can": "Canada",
                "deu": "Germany", "ind": "India", "bgd": "Bangladesh", "jpn": "Japan",
                "arg": "Argentina", "bra": "Brazil", "khm": "Cambodia", "eth": "Ethiopia",
                "ken": "Kenya", "zaf": "South Africa", "gbr": "United Kingdom",
                
                # Extended Aliases
                "uae": "United Arab Emirates", "emirates": "United Arab Emirates", "dubai": "United Arab Emirates",
                "korea": "South Korea", "kr": "South Korea", "seoul": "South Korea",
                "id": "Indonesia", "jakarta": "Indonesia", "bali": "Indonesia",
                "america": "United States", "ny": "United States",
                "berlin": "Germany", "de": "Germany",
                "hanoi": "Vietnam", "vn": "Vietnam",
                "manila": "Philippines", "ph": "Philippines",
                
                # Korean Support (Countries & Cities)
                "대한민국": "South Korea", "한국": "South Korea", "남한": "South Korea", "서울": "South Korea", "부산": "South Korea", "인천": "South Korea",
                "인도네시아": "Indonesia", "인니": "Indonesia", "자카르타": "Indonesia", "발리": "Indonesia",
                "베트남": "Vietnam", "월남": "Vietnam", "하노이": "Vietnam", "호치민": "Vietnam",
                "필리핀": "Philippines", "마닐라": "Philippines",
                "태국": "Thailand", "타이": "Thailand", "방콕": "Thailand",
                "말레이시아": "Malaysia", "쿠알라룸푸르": "Malaysia",
                "캄보디아": "Cambodia", "프놈펜": "Cambodia",
                "미국": "United States", "뉴욕": "United States",
                "독일": "Germany", "베를린": "Germany", "인도": "India"
            }
            
            # Check for direct alias/code match in any word
            for word in words:
                if word in aliases: return aliases[word]
            
            # Check if any alias exists as a substring (for non-spaced languages)
            for alias, full_name in aliases.items():
                if alias in addr_clean: return full_name
            
            # 2. Direct Keyword Match
            for word in words:
                for k in benchmark_keys:
                    if k.lower() == word: return k
            
            # 3. Substring Match (Fallback)
            for k in benchmark_keys:
                if k.lower() in addr_clean: return k
            
            return "Global Average"

        # Sequential UX State Initialization
        if 'loc_confirmed' not in st.session_state: st.session_state.loc_confirmed = False

        with col1:
            st.subheader("📍 Phase 1: 위치 선정 및 데이터 연동")
            st.markdown("<small style='color: #888;'>지명을 검색하거나 지도에서 핀을 이동하여 분석 지점을 확정하세요.</small>", unsafe_allow_html=True)
            
            with st.form("search_form"):
                address = st.text_input("지역 검색 (Geocoding)", value=st.session_state.country, placeholder="e.g. Seoul, Bali, Nairobi...", help="분석하고자 하는 지역의 지명이나 주소를 입력하세요. IEA/NASA 데이터와 자동 연동됩니다.")
                submitted = st.form_submit_button("위치 확정", use_container_width=True, help="입력한 주소의 위/경도 좌표를 찾아 지도를 이동하고 국가 데이터를 즉시 연동합니다.")
                
            if submitted:
                try:
                    from geopy.geocoders import ArcGIS
                    geolocator = ArcGIS(user_agent="net_zero_simulator_sangwook_v2")
                    loc = geolocator.geocode(address, timeout=10)
                    if loc:
                        st.session_state.lat, st.session_state.lon = loc.latitude, loc.longitude
                        # Perform reverse geocode to get consistent address with CountryCode
                        try:
                            rev = geolocator.reverse(f"{loc.latitude}, {loc.longitude}", timeout=5)
                            if rev:
                                c_code = rev.raw.get('address', {}).get('CountryCode', '')
                                st.session_state.country = f"{rev.address} ({c_code})" if c_code else rev.address
                            else:
                                st.session_state.country = loc.address
                        except:
                            st.session_state.country = loc.address
                            
                        st.session_state.loc_confirmed = True # Auto-confirm and match country
                        st.rerun()
                    else: st.error("검색 결과가 없습니다.")
                except: st.error("위치 서비스 응답 지연. 지도에서 직접 클릭해 주세요.")
            
            m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=10)
            folium.Marker([st.session_state.lat, st.session_state.lon], draggable=True, tooltip="이 핀을 움직여 위치를 조정할 수 있습니다.").add_to(m)
            
            map_out = st_folium(m, height=400, use_container_width=True, key="location_map_v2")
            
            if map_out and map_out.get("last_clicked"):
                new_lat, new_lng = map_out["last_clicked"]["lat"], map_out["last_clicked"]["lng"]
                if abs(new_lat - st.session_state.lat) > 0.0001:
                    st.session_state.lat, st.session_state.lon = new_lat, new_lng
                    try:
                        from geopy.geocoders import ArcGIS
                        geolocator = ArcGIS(user_agent="net_zero_simulator_sangwook_v2")
                        rev = geolocator.reverse(f"{new_lat}, {new_lng}", timeout=5)
                        if rev: 
                            # Extract raw country code for absolute reliability
                            c_code = rev.raw.get('address', {}).get('CountryCode', '')
                            st.session_state.country = f"{rev.address} ({c_code})" if c_code else rev.address
                    except: pass
                    st.session_state.loc_confirmed = True # Auto-confirm on map click
                    st.rerun()
            
        with col2:
            if not st.session_state.loc_confirmed:
                st.subheader("🏁 위치 및 국가 정보 확정")
                st.info("선정된 위치를 기반으로 전력 수요 벤치마크 데이터를 연동합니다.")
                
                st.markdown(f"""
                <div style='background: #111; padding: 20px; border-radius: 10px; border-left: 5px solid #ffd700; margin-bottom: 20px;'>
                    <div style='color: #888; font-size: 13px;'>검색된 주소 / 지명</div>
                    <div style='color: #fff; font-size: 16px; font-weight: bold; margin-bottom: 15px;'>{st.session_state.country if st.session_state.country else "미지정 (지도를 클릭하세요)"}</div>
                    <div style='display: flex; gap: 20px;'>
                        <div><div style='color: #888; font-size: 11px;'>위도</div><div style='color: #00d4ff;'>{st.session_state.lat:.4f}</div></div>
                        <div><div style='color: #888; font-size: 11px;'>경도</div><div style='color: #00d4ff;'>{st.session_state.lon:.4f}</div></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("📍 이 위치로 확정 및 국가 데이터 연동", type="primary", use_container_width=True, help="선택한 위치의 일사량, 온도 데이터 및 해당 국가의 전력 통계를 불러옵니다."):
                    st.session_state.loc_confirmed = True
                    st.rerun()
            else:
                st.subheader("⚡ Phase 2: 에너지 수요 및 패턴 설계")
                st.success("✅ 위치 확정 완료: 국가별 통계 데이터가 활성화되었습니다.")
                
                # Demand Configuration
                d_c1, d_c2 = st.columns(2)
                hh = d_c1.number_input("가구 수 (Households)", value=500, min_value=1, help="마이크로그리드를 구축할 마을의 전체 가구 수를 입력하세요.")
                st.session_state.hh = hh
                
                benchmark_list = list(COUNTRY_BENCHMARKS.keys())
                detected_c = find_country_match(st.session_state.country)
                try: default_idx = benchmark_list.index(detected_c)
                except ValueError: default_idx = benchmark_list.index("Global Average")
                
                c_name = d_c2.selectbox("국가 레퍼런스 데이터 (IEA/WB)", benchmark_list, index=default_idx, help="에너지 사용 패턴과 단가를 참고할 국가를 선택하세요. 위치 검색 시 자동으로 매칭됩니다.")
                avg_kwh = COUNTRY_BENCHMARKS[c_name]['demand']
                total_daily_kwh = hh * avg_kwh
                st.markdown(f"""
                <div style='background: #1a1f2b; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #00d4ff; margin-bottom: 20px;'>
                    <span style='color: #888; font-size: 13px;'>예상 일일 총 전력 수요</span><br/>
                    <span style='color: #00d4ff; font-size: 24px; font-weight: bold;'>{total_daily_kwh:,.1f} kWh</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.write("📈 **에너지 부하 특성 조합 (Load Mix)**")
                mix_val = st.slider("주거용 🏠 vs 상업용 🏢 비중 조절", 0, 100, 50, help="마을의 성격에 따라 에너지 사용 시간대를 조절합니다. 주거용은 저녁, 상업용은 낮 시간에 수요가 집중됩니다.")
                
                ratio_a = mix_val / 100.0
                ratio_b = 1.0 - ratio_a
                combined_pattern = [(PATTERN_A[i]*ratio_a + PATTERN_B[i]*ratio_b) for i in range(24)]
                norm_factor = sum(combined_pattern) / 24
                final_pattern = [p / norm_factor for p in combined_pattern]
                
                fig_load = px.line(y=final_pattern, x=list(range(24)), title="24시간 Hourly Load Profile (Normalized)")
                fig_load.update_layout(height=200, margin=dict(l=0,r=0,t=30,b=0), template="plotly_dark")
                st.plotly_chart(fig_load, use_container_width=True)
                
                st.divider()
                if st.button("🚀 시뮬레이션 및 최적 설계 시작", type="primary", use_container_width=True, help="기상 데이터와 기술 사양을 결합하여 최적의 태양광/BESS/수소 설비 용량을 산출합니다."):
                    with st.status("🚀 시뮬레이션 엔진 가동 중...", expanded=True) as status:
                        st.session_state.total_d = total_daily_kwh
                        st.session_state.load_profile = final_pattern
                        import time
                        time.sleep(0.5)
                        st.write("📍 기상 데이터 및 물리 엔진 연동 완료...")
                        st.session_state.step = 'result'
                        status.update(label="✅ 설계 완료!", state="complete", expanded=False)
                        time.sleep(0.5)
                        st.rerun()
                
                if st.button("⬅ 위치 재설정", use_container_width=True):
                    st.session_state.loc_confirmed = False
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
                            # Robust Country Matching for Batch
                            def get_batch_benchmark(addr):
                                addr_c = addr.lower()
                                aliases = {"uae": "United Arab Emirates", "dubai": "United Arab Emirates", "korea": "South Korea", "indonesia": "Indonesia (Islands)", "usa": "USA (Average)"}
                                for a, full in aliases.items():
                                    if a in addr_c: return full
                                return next((k for k in COUNTRY_BENCHMARKS.keys() if k.lower() in addr_c), "Global Average")

                            matched_country = get_batch_benchmark(loc['country'])
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
    # Force scroll to top on step change (more robust script)
    st.components.v1.html("""
        <script>
            var scroll_to_top = function() {
                window.parent.window.scrollTo(0,0);
                window.scrollTo(0,0);
                parent.window.scrollTo(0,0);
            };
            setTimeout(scroll_to_top, 50);
            setTimeout(scroll_to_top, 200);
        </script>
    """, height=0)

    # Global CSS for Tooltips
    st.markdown("""
        <style>
        .custom-tooltip {
            position: relative;
            display: inline-block;
            cursor: pointer;
            margin-left: 5px;
            color: #ff4b4b;
            font-weight: bold;
        }
        .custom-tooltip .tooltiptext {
            visibility: hidden;
            width: 320px;
            background-color: #262626;
            color: #fff;
            text-align: left;
            border-radius: 8px;
            padding: 15px;
            position: absolute;
            z-index: 100;
            bottom: 125%;
            left: 50%;
            margin-left: -160px;
            opacity: 0;
            transition: opacity 0.3s;
            border: 1px solid #ff4b4b;
            font-size: 13px;
            font-weight: normal;
            line-height: 1.5;
            box-shadow: 0px 4px 15px rgba(0,0,0,0.5);
        }
        .custom-tooltip:hover .tooltiptext {
            visibility: visible;
            opacity: 1;
        }
        </style>
    """, unsafe_allow_html=True)

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
    # SCENARIO A: Giant BESS Only (CAPEX Optimization Engine)
    # ---------------------------------------------------------
    # We find the optimal PV/BESS ratio that minimizes total CAPEX
    # Increasing PV reduces the seasonal BESS requirement.
    pv_base = pv_ideal # Store raw net-zero baseline for comparison
    best_capex_a = float('inf')
    best_pv_a = pv_ideal
    best_bess_a = 0
    
    # Iterate through PV over-provisioning factors (from 1.0 to 3.0)
    for factor in np.linspace(1.0, 3.0, 21):
        test_pv = pv_ideal * factor
        df_test = df_h.copy()
        df_test['Gen'] = df_test['Gen_1kW'] * test_pv
        df_test['Net'] = df_test['Gen'] - (total_d / 24) * df_test['Timestamp'].dt.hour.map(lambda h: norm_profile[h])
        
        # Calculate required seasonal storage for this PV size
        df_test['Cum_Net'] = df_test['Net'].cumsum()
        test_swing = (df_test['Cum_Net'].max() - df_test['Cum_Net'].min())
        test_bess = (test_swing / np.sqrt(BESS_EFF)) * 1.05 # Tighter margin for optimized case
        
        test_capex = (test_pv * PRICE_PV) + (test_bess * PRICE_BESS)
        if test_capex < best_capex_a:
            best_capex_a = test_capex
            best_pv_a = test_pv
            best_bess_a = test_bess

    pv_ideal = best_pv_a # Update to optimized PV
    bess_a = best_bess_a # Update to optimized BESS
    capex_a = best_capex_a + (hh * 1500)

    # Re-run final simulation for SOC trace display
    df_a = df_h.copy()
    df_a['Gen'] = df_h['Gen_1kW'] * pv_ideal
    df_a['Net'] = df_a['Gen'] - (total_d / 24) * df_a['Timestamp'].dt.hour.map(lambda h: norm_profile[h])
    soc = 50.0
    net_trace = []
    for i, row in df_a.iterrows():
        bal = row['Net']
        if bal > 0:
            ch = min(bal, (95 - soc) * bess_a / 100)
            soc += (ch * np.sqrt(BESS_EFF) / bess_a) * 100
        else:
            dis = min(abs(bal), (soc - 20) * bess_a / 100 / np.sqrt(BESS_EFF))
            soc -= (dis * np.sqrt(BESS_EFF) / bess_a) * 100
        net_trace.append(soc)
    
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
            # --- Section 2: Strategic Base Conditions ---
        st.markdown("### 📋 2. 공통 전략 베이스 (Strategic Base Conditions)")
        
        # Calculate Base Metrics
        # 1. PV for min insolation period (approximation using worst month)
        monthly_avg_ghi = df_h.groupby(df_h['Timestamp'].dt.month)['Insolation'].mean()
        worst_ghi = monthly_avg_ghi.min()
        best_ghi = monthly_avg_ghi.max()
        
        # Theoretical PV to cover daily load during worst month without storage (12h day approx)
        pv_for_worst = (total_d / worst_ghi) * 1.1 
        
        # Potential Curtailment if sized for worst month
        potential_gen_best = pv_for_worst * best_ghi
        max_curtailment = max(0, potential_gen_best - total_d)
        
        st.markdown(f"""
        <div style='background: #0f172a; padding: 25px; border-radius: 15px; border: 1px solid #1e293b; margin-bottom: 30px;'>
            <div style='color: #38bdf8; font-size: 16px; font-weight: bold; margin-bottom: 20px;'>💡 시나리오 설계의 공학적 배경</div>
            <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;'>
                <div style='background: rgba(255,255,255,0.03); padding: 15px; border-radius: 10px;'>
                    <div style='color: #888; font-size: 12px; margin-bottom: 5px;'>최저 일사량 대응 PV</div>
                    <div style='color: #fff; font-size: 20px; font-weight: bold;'>{pv_for_worst:,.1f} <small>kWp</small></div>
                    <div style='color: #ccc; font-size: 11px; margin-top: 5px;'>일사량이 가장 적은 기간에 배터리 없이 실시간 수요를 충족하기 위한 용량입니다.</div>
                </div>
                <div style='background: rgba(255,255,255,0.03); padding: 15px; border-radius: 10px;'>
                    <div style='color: #888; font-size: 12px; margin-bottom: 5px;'>최고 일사량 시 잉여 전력</div>
                    <div style='color: #ff4b4b; font-size: 20px; font-weight: bold;'>{max_curtailment:,.1f} <small>kWh/d</small></div>
                    <div style='color: #ccc; font-size: 11px; margin-top: 5px;'>최저 기간에 맞추어 PV를 설계할 경우, 최고 일사량 기간에 매일 버려지는 에너지량입니다.</div>
                </div>
                <div style='background: rgba(255,255,255,0.03); padding: 15px; border-radius: 10px;'>
                    <div style='color: #888; font-size: 12px; margin-bottom: 5px;'>연간 에너지 밸런스 PV</div>
                    <div style='color: #00ff88; font-size: 20px; font-weight: bold;'>{pv_base:,.1f} <small>kWp</small></div>
                    <div style='color: #ccc; font-size: 11px; margin-top: 5px;'>1년 총 발전량과 총 수요량이 일치되는 기준점으로, 모든 시나리오 설계의 출발점입니다.</div>
                </div>
            </div>
            <div style='margin-top: 20px; padding-top: 15px; border-top: 1px dashed #333; color: #aaa; font-size: 13px; line-height: 1.6;'>
                위 데이터를 통해 확인되듯, <b>잉여 에너지를 부족한 시기로 이동(Energy Shifting)</b>시키는 것이 시스템 경제성의 핵심입니다. <br>
                이 에너지를 <b>배터리</b>로만 옮길 것인지(시나리오 A), <b>수소</b>를 병용할 것인지(시나리오 B) 아래에서 비교합니다.
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_title, col_cta = st.columns([3, 1])
        with col_title:
            st.markdown("### 🏗️ 3. 시스템 아키텍처 비교 (System Architecture Comparison)")
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
                        <b style='color: #38bdf8;'>2. 시나리오 A 도출 (CAPEX 최적화)</b><br>
                        태양광을 1.2~1.8배 과설계하여 값비싼 계절 비축용 배터리 용량을 최소화하는 최저 CAPEX 지점을 찾습니다.
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
        area_b = (pv_hybrid * 10) + (bess_b * 0.1) + (max(h2_stock) * 1.5) + 50

        with c1:
            st.markdown(f"""
            <div style='background-color: #1a1a1a; padding: 25px; border-radius: 12px; border: 1px solid #ff4b4b; min-height: 520px; color: #eee;'>
                <h4 style='color: #ff4b4b; text-align: center; font-size: 20px; margin-bottom: 15px;'>Scenario A: Giant BESS Only</h4>
                <div style='text-align: center; font-size: 40px; margin: 10px 0;'>☀️ ➡ 🔋 ➡ 🏠</div>
                <p style='font-size: 15px; color: #ccc; line-height: 1.5;'>거대 배터리 뱅크를 통해 계절적 불균형을 해소하는 단순 구조입니다.</p>
                <hr style='border-color: #444;'>
                <ul style='list-style: none; padding: 0; font-size: 18px;'>
                    <li style='margin-bottom: 15px;'>
                        <span style='font-size: 17px; color: #aaa;'>PV 규모:</span>
                        <div class="custom-tooltip"> ℹ️
                            <div class="tooltiptext">
                                <b style='color: #ff4b4b; font-size: 14px;'>📝 시나리오 A CAPEX 최적화 설계</b><br><br>
                                단순히 연간 균형을 맞추는 데 그치지 않고, <b>투자비가 최소화</b>되는 지점을 찾습니다:<br><br>
                                - <b>태양광 과설계:</b> 배터리보다 저렴한 태양광을 추가 설치하여 고가의 계절 비축 배터리 용량을 절감<br>
                                - <b>최적 비율 도출:</b> 시뮬레이션을 통해 총 투자비(CAPEX)가 가장 낮은 PV/BESS 조합 선정
                            </div>
                        </div>
                        <br>
                        <b style='color: #fff; font-size: 22px;'>{pv_ideal:,.1f} kWp</b>
                        <span style='background: rgba(255,75,75,0.2); color: #ff4b4b; padding: 2px 8px; border-radius: 4px; font-size: 14px; margin-left: 5px; vertical-align: middle;'>
                            📈 {((pv_ideal/pv_base)-1)*100:+.1f}% vs Base
                        </span>
                    </li>
                    <li style='margin-bottom: 15px;'>
                        <span style='font-size: 17px; color: #aaa;'>BESS 용량:</span>
                        <div class="custom-tooltip"> ℹ️
                            <div class="tooltiptext">
                                <b style='color: #ff4b4b; font-size: 14px;'>🔋 BESS 비축 용량 (Autonomy)</b><br><br>
                                일일 평균 전력 수요 대비 배터리에 저장 가능한 전력량의 비율입니다.<br><br>
                                시나리오 A에서는 태양광이 부족한 기간(우기/겨울)을 버티기 위해 필요한 <b>계절적 비축 일수</b>가 산출됩니다.
                            </div>
                        </div>
                        <br><b style='color: #fff; font-size: 22px;'>{bess_a:,.1f} kWh</b> <span style='font-size: 16px; color: #ff4b4b; font-weight: bold;'>({bess_a/total_d:.1f}일분)</span>
                    </li>
                    <li style='margin-top: 15px; border-top: 1px dashed #444; padding-top: 15px;'>
                        <span style='font-size: 16px; color: #aaa;'>📐 점유 면적 추정 (Footprint):</span>
                        <div class="custom-tooltip"> ℹ️
                            <div class="tooltiptext">
                                <b style='color: #ffffff; font-size: 14px;'>📐 면적 산출 근거</b><br><br>
                                설비 설치에 필요한 최소 부지 면적입니다:<br><br>
                                - <b>Solar PV:</b> 10 m²/kWp (이격거리 포함)<br>
                                - <b>BESS/H2:</b> 컨테이너 및 시스템 풋프린트 기반<br>
                                - <b>기타:</b> 인프라 및 시공 여유 부지 포함
                            </div>
                        </div>
                        <br>
                        <b style='color: #fff; font-size: 20px;'>{area_a:,.0f} m²</b> <small style='color: #888;'>(약 {area_a/3.3058:,.1f}평)</small>
                    </li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            h2_days = (max(h2_stock) * 33.33 * H2_FC_EFF) / total_d
            pv_diff = (pv_hybrid / pv_ideal - 1) * 100
            st.markdown(f"""
            <div style='background-color: #1a1a1a; padding: 25px; border-radius: 12px; border: 1px solid #00d4ff; min-height: 520px; color: #eee;'>
                <h4 style='color: #00d4ff; text-align: center; font-size: 20px; margin-bottom: 15px;'>Scenario B: BESS-HESS Hybrid</h4>
                <div style='text-align: center; font-size: 40px; margin: 10px 0;'>☀️ ➡ 🔋 + 💧(H2) ➡ 🏠</div>
                <p style='font-size: 15px; color: #ccc; line-height: 1.5;'>배터리와 수소가 단기/장기 변동을 나누어 담당하여 효율을 극대화합니다.</p>
                <hr style='border-color: #444;'>
                <ul style='list-style: none; padding: 0; font-size: 18px;'>
                    <li style='margin-bottom: 15px;'>
                        <span style='font-size: 17px; color: #aaa;'>PV 규모:</span>
                        <div class="custom-tooltip"> ℹ️
                            <div class="tooltiptext">
                                <b style='color: #00d4ff; font-size: 14px;'>📝 시나리오 B 하이브리드 최적화 로직</b><br><br>
                                BESS와 수소(H2)의 역할을 분담하여 경제성을 극대화합니다:<br><br>
                                1. <b>BESS 역할:</b> 일일 변동성 대응을 위해 1.5일분 고정 용량 산정<br>
                                2. <b>수소 시스템 역할:</b> 장기(계절) 에너지 저장을 담당<br>
                                3. <b>반복 연산(Iterative Solver):</b> 연간 수소 생산량과 소비량이 일치(Net-Zero)되는 최적의 태양광 및 수소 저장 용량을 정밀 도출
                            </div>
                        </div>
                        <br>
                        <b style='color: #fff; font-size: 28px;'>{pv_hybrid:,.1f} kWp</b>
                        <span style='background: rgba(0,212,255,0.2); color: #00d4ff; padding: 2px 8px; border-radius: 4px; font-size: 14px; margin-left: 5px; vertical-align: middle;'>
                            📈 {pv_diff:+.1f}% vs A
                        </span>
                    </li>
                    <li style='margin-bottom: 20px;'>
                        <span style='font-size: 17px; color: #aaa;'>에너지 저장 (Hybrid):</span>
                        <div class="custom-tooltip"> ℹ️
                            <div class="tooltiptext">
                                <b style='color: #00d4ff; font-size: 14px;'>🔋 하이브리드 저장 시스템</b><br><br>
                                배터리와 수소가 역할을 분담하는 구조입니다:<br><br>
                                - <b>BESS:</b> 일일 변동 대응 (1.5일분 고정)<br>
                                - <b>수소(H2):</b> 장기 계절 저장 (필요량에 따라 가변)
                            </div>
                        </div>
                        <br>
                        <div style='margin-top: 10px; padding-left: 10px; border-left: 2px solid #00d4ff;'>
                            <div style='font-size: 15px; color: #ccc; margin-bottom: 5px;'>▪️ BESS (배터리): <b style='color: #fff;'>{bess_b:,.1f} kWh</b> (1.5일분)</div>
                            <div style='font-size: 15px; color: #ccc; margin-bottom: 5px;'>▪️ 수전해기 (Electrolyzer): <b style='color: #00d4ff;'>{el_kw:,.1f} kW</b></div>
                            <div style='font-size: 15px; color: #ccc; margin-bottom: 5px;'>▪️ 연료전지 (Fuel Cell): <b style='color: #00d4ff;'>{fc_kw:,.1f} kW</b></div>
                            <div style='font-size: 15px; color: #ccc;'>
                                ▪️ 수소저장 (H2 Storage): <b style='color: #00ff88;'>{max(h2_stock):,.1f} kg</b> 
                                <span style='color: #00ff88; font-weight: bold; font-size: 18px; margin-left: 5px;'>({h2_days:.1f}일분)</span>
                            </div>
                        </div>
                    </li>
                    <li style='margin-top: 15px; border-top: 1px dashed #444; padding-top: 15px;'>
                        <span style='font-size: 16px; color: #aaa;'>📐 점유 면적 추정 (Footprint):</span>
                        <div class="custom-tooltip"> ℹ️
                            <div class="tooltiptext">
                                <b style='color: #ffffff; font-size: 14px;'>📐 면적 산출 근거</b><br><br>
                                설비 설치에 필요한 최소 부지 면적입니다:<br><br>
                                - <b>Solar PV:</b> 10 m²/kWp (이격거리 포함)<br>
                                - <b>BESS/H2:</b> 컨테이너 및 시스템 풋프린트 기반<br>
                                - <b>기타:</b> 인프라 및 시공 여유 부지 포함
                            </div>
                        </div>
                        <br>
                        <b style='color: #fff; font-size: 20px;'>{area_b:,.0f} m²</b> <small style='color: #888;'>(약 {area_b/3.3058:,.1f}평)</small>
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
        
        # Breakdown Data Calculation (Reinstated)
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
        
        # Scenario Totals for Annotations
        total_a = cost_pv_a + cost_bess_a + cost_dist
        total_b = cost_pv_b + cost_bess_b + cost_el + cost_fc + cost_h2_tank + cost_dist

        # Comparison Sign Annotation (Middle)
        sign = ">" if total_a > total_b else "<"
        fig_break.add_annotation(
            x=0.5, y=max(total_a, total_b) * 0.8,
            xref="paper", yref="y",
            text=sign,
            showarrow=False,
            font=dict(size=50, color="#444", family="Arial Black")
        )

        # Scenario A Total Annotation
        fig_break.add_annotation(
            x='Scenario A', y=total_a,
            text=f"Total: ${total_a:,.0f}",
            showarrow=False, yshift=30,
            font=dict(size=22, color='#ff4b4b', family="Arial Black")
        )
        
        # Scenario B Total Annotation
        fig_break.add_annotation(
            x='Scenario B', y=total_b,
            text=f"Total: ${total_b:,.0f}",
            showarrow=False, yshift=30,
            font=dict(size=22, color="#00d4ff", family="Arial Black")
        )
        
        # Highlight Annotation for Feasibility (Scenario B winner)
        if total_b < total_a:
            fig_break.add_annotation(
                x='Scenario B', y=total_b,
                text="🚀 사업성 있음 (Feasible)",
                showarrow=False, yshift=70,
                font=dict(size=14, color="#00ff88", family="Arial Black"),
                bgcolor="rgba(0,0,0,0.8)",
                bordercolor="#00ff88",
                borderwidth=1,
                borderpad=4
            )
        
        fig_break.update_layout(
            title="투자 비용 구성 항목 비교 (Cost Breakdown)", 
            barmode='stack', 
            template="plotly_dark", 
            height=620, 
            margin=dict(t=120, b=100), 
            yaxis=dict(range=[0, max(total_a, total_b)*1.5]),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
        )
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
            
            # 0. Global Financial Settings
            f_set1, f_set2, f_set3 = st.columns([1, 1, 2])
            p_life = f_set1.number_input("운영 기간 (Year)", 10, 50, 30, key="fs_life", help="프로젝트가 수익을 창출하는 총 운영 기간(수명)을 설정합니다.")
            p_disc = f_set2.number_input("할인율 (%)", 0.0, 20.0, 8.0, key="fs_disc", help="자본 비용 및 물가 상승률을 고려하여 미래의 현금 흐름을 현재 가치로 환산할 때 사용하는 비율입니다.")
            use_edcf = f_set3.toggle("🇰🇷 EDCF 차관 및 금융 패키지 활용 (40% 차관 + 보조금)", value=False, key="fs_edcf", help="한국의 경제협력증진자금(EDCF) 금융 지원 조건을 적용합니다. 저금리 차관 및 일부 설비 보조가 포함됩니다.")
            
            st.divider()

            # 1-2. CAPEX/OPEX 세부 편집
            st.markdown("##### 🏗️ 1~2. 투자비 및 운영 수익 상세 (CAPEX / OPEX / Revenue)")
            inc_desal = st.toggle("💧 해수 담수화 시스템 포함 (Desalination Unit)", value=False, help="식수 공급을 위해 태양광 에너지를 사용하는 해수 담수화 설비를 투자비에 추가합니다.")
            
            # CAPEX Breakdown Editor
            st.markdown("<small style='color: #888;'>투자비 항목별 단가와 수량을 수정할 수 있습니다.</small>", unsafe_allow_html=True)
            capex_items = {
                "구분": ["발전설비", "저장설비", "수소설비", "수소설비", "수소설비", "수소설비", "기타설비", "시공/인프라", "시공/인프라"],
                "세부 항목": [
                    "Solar PV System ($/kWp)", "BESS (Battery) ($/kWh)", "Electrolyzer (EL) ($/kW)", "Fuel Cell (FC) ($/kW)", 
                    "H2 Storage Tank ($/kg)", "H2 기자재/물류 ($/job)", "EMS & Control ($/set)", "물류 및 시공 (Logistics) ($/job)", "인프라 (Distribution) ($/hh)"
                ],
                "단가 ($)": [1000, 300, 550, 700, 650, 15000, 30000, 100000, 1500],
                "수량": [int(pv_hybrid), int(bess_b), int(el_kw), int(fc_kw), int(max(h2_stock)), 1, 1, 1, int(hh)],
                "총 금액 ($)": [0] * 9
            }
            
            if use_edcf:
                capex_items["구분"].append("금융지원")
                capex_items["세부 항목"].append("EDCF 설비 보조금 (Grant Component)")
                capex_items["단가 ($)"].append(-150000) # Example Grant amount
                capex_items["수량"].append(1)
                capex_items["총 금액 ($)"].append(0)

            df_capex = pd.DataFrame(capex_items)
            df_capex["총 금액 ($)"] = df_capex["단가 ($)"] * df_capex["수량"]
            
            edited_capex = st.data_editor(
                df_capex, use_container_width=True, num_rows="fixed", key="capex_editor_v6",
                column_config={
                    "단가 ($)": st.column_config.NumberColumn(format="$%,d"),
                    "수량": st.column_config.NumberColumn(format="%,d"),
                    "총 금액 ($)": st.column_config.NumberColumn(format="$%,d", disabled=True)
                }
            )
            total_capex_fs = int(edited_capex["총 금액 ($)"].sum())
            st.markdown(f"<div style='text-align: right; font-size: 18px; color: #00d4ff; font-weight: bold;'>💰 Total CAPEX: ${total_capex_fs:,.0f}</div>", unsafe_allow_html=True)
            
            st.divider()

            # Revenue & OPEX Editor
            st.markdown("<small style='color: #888;'>연간 운영 수익 및 고정 비용 항목입니다.</small>", unsafe_allow_html=True)
            matched = next((c for c in COUNTRY_BENCHMARKS.keys() if c.lower() in st.session_state.country.lower()), "Global Average")
            ref_rate = COUNTRY_BENCHMARKS[matched]['rate']
            bess_replace_annual = (bess_b * 300 * 0.7) / 10
            stack_replace_annual = ((el_kw * 550 + fc_kw * 700) * 0.5) / 8
            
            subsidy_val = 30000.0 if use_edcf else 0.0
            rev_opex_items = {
                "구분": ["수익", "수익", "수익", "운영비", "운영비", "운영비", "운영비"],
                "상세 항목": ["전기 판매 요금 (PPA)", "정부 운영 보조금 ($/yr)", "기타 판매 수익 ($/yr)", "일반 유지보수비 ($/yr)", "현지 운영비 ($/yr)", "BESS 교체 적립금", "H2 스택 교체 적립금"],
                "금액 ($)": [ref_rate, subsidy_val, 0.0, float(total_capex_fs * 0.012), 30000.0, float(bess_replace_annual), float(stack_replace_annual)]
            }
            df_rev_init = pd.DataFrame(rev_opex_items)
            edited_rev = st.data_editor(
                df_rev_init, use_container_width=True, num_rows="fixed", key="rev_editor_v6",
                column_config={
                    "금액 ($)": st.column_config.NumberColumn(format="$%,.2f")
                }
            )
            rev_vals = edited_rev["금액 ($)"].values
            
            # Sub-sums for Rev/OPEX
            total_rev_sub = int((annual_demand * rev_vals[0]) + rev_vals[1] + rev_vals[2])
            total_opex_sub = int(sum(rev_vals[3:]))
            
            r_c1, r_c2 = st.columns(2)
            r_c1.markdown(f"""
                <div style='background: #111; padding: 20px; border-radius: 12px; border-left: 5px solid #00d4ff; box-shadow: 2px 2px 10px rgba(0,0,0,0.3);'>
                    <div style='color: #888; font-size: 13px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;'>Total Annual Revenue</div>
                    <div style='color: #00d4ff; font-size: 26px; font-weight: 800; margin-top: 5px;'>${total_rev_sub:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            r_c2.markdown(f"""
                <div style='background: #111; padding: 20px; border-radius: 12px; border-left: 5px solid #94a3b8; box-shadow: 2px 2px 10px rgba(0,0,0,0.3);'>
                    <div style='color: #888; font-size: 13px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;'>Total Annual OPEX</div>
                    <div style='color: #ffffff; font-size: 26px; font-weight: 800; margin-top: 5px;'>${total_opex_sub:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.divider()

            # 3. 연간 Cash Flow (EDCF 차관 분석 포함)
            st.markdown("##### 📈 3. 연간 현금 흐름 및 차관 분석 (Annual Cash Flow)")
            st.caption(f"※ 설정된 금융 조건: {p_life}년 운영, 할인율 {p_disc*100:.1f}%, EDCF {'활용' if use_edcf else '미활용'}")
            
            # Financial Calculations
            loan_amt = total_capex_fs * 0.4 if use_edcf else 0
            rev_annual = (annual_demand * rev_vals[0]) + rev_vals[1] + rev_vals[2]
            fixed_opex_annual = rev_vals[3] + rev_vals[4]
            bess_replace_cost = bess_b * 300 * 0.7 
            stack_replace_cost = (el_kw * 550 + fc_kw * 700) * 0.5 
            
            years = list(range(int(p_life) + 1))
            rev_in = [0] + [rev_annual] * int(p_life)
            opex_base = [0] + [fixed_opex_annual] * int(p_life)
            replace_out = [0] * (int(p_life) + 1)
            edcf_flow = [loan_amt] + [0] * int(p_life)
            rem_principal = loan_amt
            
            for y in range(1, int(p_life) + 1):
                if y % 10 == 0: replace_out[y] += bess_replace_cost
                if y % 8 == 0: replace_out[y] += stack_replace_cost
                if use_edcf:
                    interest = rem_principal * 0.0001
                    principal = loan_amt / 25 if y > 15 else 0
                    rem_principal = max(0, rem_principal - principal)
                    edcf_flow[y] = -(principal + interest)
            
            net_flow = [(rev_in[y] - opex_base[y] - replace_out[y] - (total_capex_fs if y==0 else 0) + edcf_flow[y]) for y in range(int(p_life) + 1)]
            cum_flow = np.cumsum(net_flow)
            
            fig_cf = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Scaled CAPEX for visualization (so it doesn't squash the chart)
            viz_capex_0 = min(total_capex_fs, rev_annual * 2) 
            
            # Inflow
            fig_cf.add_trace(go.Bar(x=years, y=rev_in, name='Annual Revenue', marker_color='#00d4ff'), secondary_y=False)
            fig_cf.add_trace(go.Bar(x=[0], y=[loan_amt], name='EDCF Loan Inflow', marker_color='#7e57c2'), secondary_y=False)
            
            # Outflow
            fig_cf.add_trace(go.Bar(x=years, y=[-v for v in opex_base], name='Base OPEX', marker_color='#555'), secondary_y=False)
            fig_cf.add_trace(go.Bar(x=years, y=[-v for v in replace_out], name='Replacement Cost', marker_color='#ff8800'), secondary_y=False)
            fig_cf.add_trace(go.Bar(x=[0], y=[-viz_capex_0], name='Initial CAPEX (Scaled)', marker_color='#ff4b4b', 
                                   hovertemplate="Initial CAPEX<br>Real Value: $"+f"{total_capex_fs:,.0f}"), secondary_y=False)
            
            # EDCF Repayment
            edcf_repay = [min(0, v) for v in edcf_flow]
            fig_cf.add_trace(go.Bar(x=years, y=edcf_repay, name='EDCF Repayment', marker_color='#4a148c'), secondary_y=False)
            
            # Cumulative Balance
            fig_cf.add_trace(go.Scatter(x=years, y=cum_flow, name='Cumulative Balance', line=dict(color='#ffffff', width=3, dash='dot')), secondary_y=True)
            
            fig_cf.update_layout(
                template="plotly_dark", height=450, barmode='relative', 
                margin=dict(t=20, b=20, l=0, r=0),
                xaxis=dict(title="Year", tickmode='linear', dtick=5, range=[-1, int(p_life)+1]),
                yaxis=dict(title="Annual Flow ($)", range=[-rev_annual*1.5, rev_annual*2]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_cf, use_container_width=True)
            st.caption(f"※ Year 0의 CAPEX(${total_capex_fs:,.0f})는 차트 가독성을 위해 시각적으로 축소 조정되었습니다.")
            
            st.divider()

            # 4. NPV, IRR 핵심 지표
            st.markdown("##### 📊 4. 핵심 수익성 및 사업성 지표 (NPV & IRR)")
            npv, irr, payback, lcoe_fs = calculate_fs_metrics(total_capex_fs - loan_amt, annual_demand, rev_vals[0], rev_vals[1], rev_vals[2], sum(rev_vals[3:]), p_life, p_disc)
            
            m1, m2, m3 = st.columns(3)
            with m1: st.markdown(f"<div style='background: #111; padding: 20px; border-radius: 10px; border-left: 5px solid {'#00ff88' if npv > 0 else '#ff4b4b'};'><div style='color: #888; font-size: 13px;'>순현재가치 (NPV)</div><div style='color: #fff; font-size: 24px; font-weight: bold;'>${npv/1e6:.2f}M</div><div style='color: {'#00ff88' if npv > 0 else '#ff4b4b'}; font-size: 12px;'>{'✅ 사업성 확보' if npv > 0 else '⚠️ 수익성 개선 필요'}</div></div>", unsafe_allow_html=True)
            with m2: st.markdown(f"<div style='background: #111; padding: 20px; border-radius: 10px; border-left: 5px solid #ffd700;'><div style='color: #888; font-size: 13px;'>내부수익률 (IRR)</div><div style='color: #fff; font-size: 24px; font-weight: bold;'>{irr:.2f}%</div><div style='color: #ffd700; font-size: 12px;'>Target 대비 {irr - p_disc*100:+.1f}%</div></div>", unsafe_allow_html=True)
            with m3: st.markdown(f"""
                <div style='background: #111; padding: 20px; border-radius: 10px; border-left: 5px solid #00d4ff;'>
                    <div style='color: #888; font-size: 13px;'>
                        발전단가 (LCOE)
                        <div class="custom-tooltip"> ℹ️
                            <div class="tooltiptext">
                                <b style='color: #00d4ff; font-size: 14px;'>📝 LCOE (Levelized Cost of Energy)</b><br><br>
                                에너지 생산에 들어가는 총 비용을 총 에너지 생산량으로 나눈 값입니다:<br><br>
                                - <b>분자:</b> 초기 투자비(CAPEX) + 운영 유지비(OPEX) + 교체비<br>
                                - <b>분모:</b> 프로젝트 기간 내 총 전력 판매량 (할인율 적용)
                            </div>
                        </div>
                    </div>
                    <div style='color: #fff; font-size: 24px; font-weight: bold;'>${lcoe_fs:.3f}</div>
                    <div style='color: #00d4ff; font-size: 12px;'>/kWh (HESS Hybrid)</div>
                </div>
                """, unsafe_allow_html=True)

            st.divider()

            # 5. 디젤 대비 LCOE 비교
            st.markdown("##### ⛽ 5. 디젤 대비 경제성 분석 (LCOE Comparison)")
            
            with st.popover("📊 디젤 발전 원가 산출 상세 설정"):
                d_c1, d_c2 = st.columns(2)
                fuel_p = d_c1.number_input("현지 디젤 가격 ($/L)", 0.5, 3.0, 1.85, help="해당 지역의 실제 디젤 구매 가격을 입력하세요. 물류비가 포함된 가격이 권장됩니다.")
                d_eff_val = d_c2.number_input("발전 효율 (kWh/L)", 1.0, 5.0, 3.3, help="디젤 발전기 1리터당 생산 가능한 전력량입니다. 통상 3.0~3.5 사이입니다.")
                d_maint = st.slider("운영 및 시공 할증 ($/kWh)", 0.05, 0.30, 0.06, help="디젤 발전기 유지보수비 및 인프라 구축 비용을 전력량 단위로 환산한 가산금입니다.")
                diesel_ref = (fuel_p / d_eff_val) + d_maint
                
                st.markdown(f"""
                <div style='background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; font-size: 13px;'>
                    <b style='color: #ffd700;'>📝 산출 방식:</b><br>
                    LCOE = (디젤 가격 ÷ 발전 효율) + 할증 비용<br>
                    = (${fuel_p} ÷ {d_eff_val}) + ${d_maint}<br>
                    = <span style='color: #00ff88; font-weight: bold;'>${diesel_ref:.3f} / kWh</span>
                </div>
                """, unsafe_allow_html=True)

            # Large LCOE Comparison Cards
            l_c1, l_c2 = st.columns(2)
            with l_c1:
                st.markdown(f"""
                <div style='background: #1e1e1e; padding: 25px; border-radius: 12px; border-top: 5px solid #888;'>
                    <div style='color: #888; font-size: 14px; text-transform: uppercase;'>Benchmark (Diesel)</div>
                    <div style='color: #fff; font-size: 32px; font-weight: 800; margin: 10px 0;'>${diesel_ref:.3f}<span style='font-size: 16px; font-weight: 400;'> /kWh</span></div>
                    <div style='color: #666; font-size: 12px;'>격오지 디젤 발전 기준가</div>
                </div>
                """, unsafe_allow_html=True)
            with l_c2:
                savings = (diesel_ref - lcoe_fs) / diesel_ref * 100
                st.markdown(f"""
                <div style='background: #0f172a; padding: 25px; border-radius: 12px; border-top: 5px solid #00d4ff;'>
                    <div style='color: #00d4ff; font-size: 14px; text-transform: uppercase;'>HESS Hybrid (LCOE)</div>
                    <div style='color: #fff; font-size: 32px; font-weight: 800; margin: 10px 0;'>${lcoe_fs:.3f}<span style='font-size: 16px; font-weight: 400;'> /kWh</span></div>
                    <div style='color: #00ff88; font-size: 12px; font-weight: bold;'>📉 디젤 대비 {savings:.1f}% 절감</div>
                </div>
                """, unsafe_allow_html=True)

            fig_lcoe = go.Figure()
            fig_lcoe.add_trace(go.Bar(x=['Benchmark (Diesel)', 'HESS Hybrid (LCOE)'], y=[diesel_ref, lcoe_fs], marker_color=['#888', '#00d4ff'], width=0.4))
            fig_lcoe.update_layout(template="plotly_dark", height=300, margin=dict(t=20, b=20), yaxis_title="LCOE ($/kWh)")
            st.plotly_chart(fig_lcoe, use_container_width=True)
            
            st.success(f"💡 **종합 평가:** 본 하이브리드 시스템은 디젤 대비 약 **{abs(savings):.1f}%**의 높은 원가 경쟁력을 확보하고 있습니다.")

            st.divider()

            # 6. 사업성 확보를 위한 목표 요금 가이드
            st.markdown("##### 💡 6. 사업성 확보 가이드 (Strategic Optimization Guide)")
            pv_factor = [(1 / (1 + p_disc) ** y) for y in years]
            pv_costs = sum(( (total_capex_fs if y==0 else 0) + opex_base[y] + replace_out[y] - edcf_flow[y]) * pv_factor[y] for y in years)
            pv_ifa = sum(pv_factor[y] for y in years[1:])
            req_tariff = (pv_costs - rev_vals[2]*pv_ifa - (rev_vals[1] * pv_ifa)) / (annual_demand * pv_ifa)
            req_subsidy = (pv_costs - rev_vals[2]*pv_ifa - (rev_vals[0] * annual_demand * pv_ifa)) / pv_ifa
            
            g1, g2 = st.columns(2)
            with g1: st.markdown(f"<div style='background: #0f172a; padding: 20px; border-radius: 12px; border: 1px solid #38bdf8;'><div style='color: #38bdf8; font-weight: bold; font-size: 14px;'>1. 필요한 최소 전기 요금</div><div style='color: #fff; font-size: 26px; font-weight: 800; margin: 8px 0;'>${req_tariff:.3f}/kWh</div><div style='color: #888; font-size: 12px;'>NPV를 0으로 맞추기 위한 목표 단가입니다.</div></div>", unsafe_allow_html=True)
            with g2: st.markdown(f"<div style='background: #064e3b; padding: 20px; border-radius: 12px; border: 1px solid #34d399;'><div style='color: #34d399; font-weight: bold; font-size: 14px;'>2. 필요한 연간 보조금</div><div style='color: #fff; font-size: 26px; font-weight: 800; margin: 8px 0;'>${req_subsidy/1000:,.1f}k/yr</div><div style='color: #888; font-size: 12px;'>현재 요금 유지 시 정부의 연간 지원 필요액입니다.</div></div>", unsafe_allow_html=True)

            if st.button("✅ 시나리오 확정 및 닫기", use_container_width=True): st.rerun()

        # Consolidated CTA (Summary Card moved to CAPEX section)
        f_col1, f_col2 = st.columns([1, 1])
        with f_col1:
            st.info("💡 **사업성 상세 검토:** 현지 전력 요금, 보조금 및 물류 할증이 반영된 상세 FS를 시작합니다.")
        with f_col2:
            if st.button("🚀 사업성 상세 검토", type="primary", use_container_width=True, help="투자비(CAPEX), 운영비(OPEX), 보조금 및 차관 조건을 상세히 설정하여 재무적 타당성을 시뮬레이션합니다."):
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
