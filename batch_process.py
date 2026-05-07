import pandas as pd
import time
from core_engine import simulate

# 1. 시뮬레이션 대상 리스트 설정
# Latitude, Longitude, Households (hh), Daily Demand per HH (kwh/d)
locations = [
    {"name": "Location_A", "lat": -5.0, "lon": 120.0, "hh": 500, "demand": 3.0},
    {"name": "Location_B", "lat": 10.0, "lon": 35.0, "hh": 500, "demand": 3.0},
    {"name": "Location_C", "lat": -20.0, "lon": 45.0, "hh": 500, "demand": 3.0},
    # 여기에 더 많은 좌표를 추가하세요.
]

# 24시간 부하 패턴 (기본값: 50:50 상업/주거 혼합)
# (app.py의 PATTERN_A, B를 기반으로 생성하거나 고정된 패턴 사용)
default_load_profile = [0.4, 0.3, 0.3, 0.3, 0.3, 0.4, 0.7, 1.2, 1.5, 1.6, 1.7, 1.8, 1.7, 1.6, 1.5, 1.4, 1.5, 1.8, 2.2, 2.1, 1.5, 1.0, 0.7, 0.5]

results = []

print("🚀 배치 시뮬레이션 시작...")

for loc in locations:
    print(f"📡 분석 중: {loc['name']} ({loc['lat']}, {loc['lon']})...")
    
    # 총 일일 수요량 산출
    total_d = loc['hh'] * loc['demand']
    
    # 시뮬레이션 실행
    res = simulate(loc['lat'], loc['lon'], total_d, default_load_profile, loc['hh'])
    
    if res:
        res['Name'] = loc['name']
        res['Lat'] = loc['lat']
        res['Lon'] = loc['lon']
        results.append(res)
        print(f"✅ 완료: 절감률 {res['Saving_Rate']:.1f}%")
    else:
        print(f"❌ 실패: {loc['name']}")
    
    # NASA API 속도 제한 방지를 위한 대기 (필요시)
    time.sleep(1)

# 3. 결과 저장
df_results = pd.DataFrame(results)
df_results.to_csv("batch_simulation_results.csv", index=False, encoding='utf-8-sig')

print("\n✨ 모든 시뮬레이션이 완료되었습니다!")
print("결과 파일: batch_simulation_results.csv")
