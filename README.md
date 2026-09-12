# 집콕맵 (apt-map) - 실거래·호가·학군·도로·경매를 지도 한 장에

"좋은 아파트를 싸게 사도록 돕는" 모바일 우선 웹앱 MVP. 정적 파일(HTML/JS) + Python 파이프라인.

## 구조
```
pipeline/
  fetch_trades.py    국토교통부 실거래가 API -> data/raw/trades_*.json  (DATA_GO_KR_KEY 필요)
  fetch_roads.py     OSM Overpass -> app/data/roads.geojson (큰길/골목/인도 분류, 키 불필요)
  fetch_poi.py       OSM Overpass -> data/raw/poi.json (지하철역, 초등학교 위치)
  fetch_boundary.py  OSM 행정경계 -> data/raw/boundary_<구>.geojson (좌표 검증용)
  geocode_osm.py     단지명 <-> OSM 아파트 매칭으로 좌표 채움 (키 불필요, 경계 밖 제외)
  geocode.py         카카오 주소검색으로 나머지 좌표 채움 (KAKAO_REST_API_KEY + 카카오맵 서비스 활성화 필요)
  fetch_rent.py      아파트 전월세 실거래 -> data/raw/rent_*.json (전세가율·갭)
  fetch_kapt.py      K-apt 단지목록(V4)+기본정보(V5) -> data/raw/kapt.json (세대수·동수·최고층·분양/임대/혼합·복도식)
  fetch_neis.py      나이스 학원·교습소 + 초·중학교 (카카오 좌표화) -> academies.json, schools_neis.json
  fetch_kakao_poi.py 카카오 로컬로 단지 반경 어린이집·소아과·병원·마트·공원·도서관 개수 -> kakao_poi.json
  demo_data.py       키 없을 때 쓰는 데모 단지·학군·경매 (마포구 공덕·아현·염리)
  build.py           위 소스를 합쳐 app/data/*.json 생성 (평당가, 1년 변동, 배정초등(보로노이 추정), 역거리, 대로변 여부, 장단점 자동 요약)
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

## 실데이터 갱신 순서 (마포구 기준)
```bash
python pipeline/fetch_trades.py --lawd 11440 --months 24   # 실거래 (지난달 캐시, 이번달만 재조회)
python pipeline/fetch_boundary.py --name 마포구             # 최초 1회
python pipeline/fetch_poi.py                                # 역/초등학교, 가끔
python pipeline/geocode_osm.py                              # 새 단지 좌표 (OSM)
python pipeline/geocode.py                                  # 나머지 좌표 (카카오)
python pipeline/fetch_rent.py --lawd 11440 --months 12      # 전월세
python pipeline/fetch_kapt.py --sgg 11440                   # 세대수 등 (가끔)
python pipeline/fetch_neis.py --gu 마포구                   # 학원/학교 (가끔)
python pipeline/fetch_kakao_poi.py                          # 생활 편의 (새 단지만)
python pipeline/build.py
```
`data/raw/geocode.json` 에 좌표가 없는 단지는 앱에 안 나온다. 세대수/최고층/용적률은 K-apt 공동주택 API 연동 전까지 0 (화면에서 숨김).

## 데이터 출처 / 한계
| 기능 | 현재 | 실서비스 계획 |
|---|---|---|
| 실거래가 | 데모 생성값 | 국토교통부 API (무료, 신고 지연 최대 30일) |
| 호가 | 데모 구간 + 사용자 제보(localStorage) | KB시세 상하한 / 지역 중개사 제휴 / 제보 검수. 네이버부동산 크롤링은 하지 않음 |
| 초등 배정 | 데모 폴리곤 | 학구도안내서비스(schoolzone.emac.kr) 통학구역 |
| 중학교 | 법정동별 학교군 목록 (데모) | 교육지원청 중학교 학교군 |
| 도로/인도 | **실데이터** (OSM, 마포구 일대) | 전국 확장 + 표준노드링크 교통량 |
| 경매 | 데모 3건 | 대법원 법원경매정보 수집 |
