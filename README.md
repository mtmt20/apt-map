# 집콕맵 (apt-map) - 실거래·호가·학군·도로·경매를 지도 한 장에

"좋은 아파트를 싸게 사도록 돕는" 모바일 우선 웹앱 MVP. 정적 파일(HTML/JS) + Python 파이프라인.

## 구조
```
pipeline/
  fetch_trades.py   국토교통부 실거래가 API -> data/raw/  (DATA_GO_KR_KEY 필요)
  fetch_roads.py    OSM Overpass -> app/data/roads.geojson (큰길/골목/인도 분류, 키 불필요)
  demo_data.py      키 없을 때 쓰는 데모 단지·학군·경매 (마포구 공덕·아현·염리)
  build.py          위 소스를 합쳐 app/data/*.json 생성 (평당가, 1년 변동, 배정초등, 역거리, 대로변 여부, 장단점 자동 요약)
app/
  index.html, app.js, style.css   MapLibre GL 기반 지도 + 하단 시트 UI
  data/                           build.py 산출물
  vendor/                         maplibre-gl 4.7.1 (로컬 번들)
```

## 실행
```bash
pip install -r requirements.txt
python pipeline/fetch_roads.py          # 최초 1회 (Overpass, 1~2분)
python pipeline/build.py                # app/data 생성 (키 없으면 데모 모드)
python -m http.server 8765 --directory app
# -> http://localhost:8765
```

## 실데이터로 전환
1. 공공데이터포털에서 "국토교통부_아파트 매매 실거래가 자료" 활용신청 -> 인증키를 `.env`의 `DATA_GO_KR_KEY`에 저장
2. `python pipeline/fetch_trades.py --lawd 11440 --months 24` (11440 = 마포구)
3. 단지 좌표: `data/raw/geocode.json` 에 `"법정동|단지명|지번": {lat, lng, addr, households, max_floor, far}` 형태로 채우기 (카카오 주소검색 API로 자동화 예정)
4. `python pipeline/build.py` -> meta.mode 가 `real` 로 바뀌고 앱의 "데모 데이터" 배지가 사라짐

## 데이터 출처 / 한계
| 기능 | 현재 | 실서비스 계획 |
|---|---|---|
| 실거래가 | 데모 생성값 | 국토교통부 API (무료, 신고 지연 최대 30일) |
| 호가 | 데모 구간 + 사용자 제보(localStorage) | KB시세 상하한 / 지역 중개사 제휴 / 제보 검수. 네이버부동산 크롤링은 하지 않음 |
| 초등 배정 | 데모 폴리곤 | 학구도안내서비스(schoolzone.emac.kr) 통학구역 |
| 중학교 | 법정동별 학교군 목록 (데모) | 교육지원청 중학교 학교군 |
| 도로/인도 | **실데이터** (OSM, 마포구 일대) | 전국 확장 + 표준노드링크 교통량 |
| 경매 | 데모 3건 | 대법원 법원경매정보 수집 |
