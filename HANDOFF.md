# HANDOFF - 집콕맵 (부동산 앱)

> 세션 협업 규칙은 `CLAUDE.md` 참고. 시작 전에 아래 "지금 작업 중" 표부터 확인.

## 지금 작업 중 (끝나면 본인 줄 삭제)
| 세션 | 시작 | 작업 | 만지는 파일 |
|---|---|---|---|
| (비어 있음) | | | |


## 최근 업데이트
- 2026-09-12 (컴퓨터 세션): 프로젝트 생성. 파이프라인 4개 + 앱 MVP 완성, 마포구 데모로 브라우저 검증 완료.
  - 지도(MapLibre + OpenFreeMap positron, 실패 시 OSM 래스터 폴백), 단지 가격 핀, 평형/정렬 필터, 검색
  - 하단 시트: 단지 리스트 -> 상세(실거래 vs 호가 갭 바, 평당가 추세 차트, 장단점, 배정 초등/중학교군, 교통·도로, 경매, 실거래 표, 호가 제보)
  - 레이어: 학군(통학구역 폴리곤), 도로(큰길 주황/동네길 회색/골목 점선/인도 초록 테두리), 경매 핀
  - 도로는 OSM 실데이터(마포 공덕·아현·염리 bbox), 나머지는 데모

- 2026-09-12 (컴퓨터 세션, 이어서): **실데이터 모드 전환 완료 (마포구)**
  - 사용자가 data.go.kr 키 발급 -> `.env` DATA_GO_KR_KEY. 실거래 24개월 5,750건 / 285개 단지 수집
  - 좌표: 카카오 주소검색은 앱(WhiskyHot)의 "카카오맵" 서비스가 비활성이라 403 -> OSM 단지명 매칭(geocode_osm.py)으로 184개 좌표 확보, 101개 미매칭
  - 마포구 경계(fetch_boundary.py)로 이웃 구 오매칭 37개 제거. 역 48개/초등학교 97개(OSM), 초등 통학구역은 보로노이 추정
  - 앱: 데모 배지 자동 해제, 줌 낮을 땐 거래 많은 단지만 + 압축 핀, 변동률은 표본 부족 시 숨김

- 2026-09-12 (컴퓨터 세션, 3차): 카카오맵 활성화됨 -> 285개 단지 전부 카카오 주소검색 좌표로 교체(`geocode.py --redo-osm`), 구 밖 0개.
  전월세(fetch_rent.py)·K-apt 세대수(fetch_kapt.py) 수집기와 build/app 연동(전세가율·갭·전세가율순 정렬)은 코드만 준비, **사용자 활용신청 대기**.

- 2026-09-12 (컴퓨터 세션, 4차): 활용신청 3건 완료 -> 전월세 12개월 수집(전세가율 141개 단지), K-apt 142개 단지(세대수/동수/최고층) 수집.
  K-apt 실제 경로는 `AptListService4/getSigunguAptList4`, `AptBasisInfoServiceV5/getAphusBassInfoV5` (data.go.kr 페이지에서 확인). 실거래 단지 285개 중 세대수 매칭 100개.

- 2026-09-12 (컴퓨터 세션, 5차): 나이스 키 2개(학교/학원) 발급 -> 학원·교습소 1,163곳 좌표화, 초등 134/중학교 84곳(마포+이웃 6개 구).
  단지별 1km 내 교과학원 수 + 구내 상위 % (대흥동 학원가가 1위권으로 잡힘), 가까운 중학교 3곳(공/사립·남녀 표시), 초등 통학구역은 나이스 공식 목록 기준 보로노이.
  카카오 로컬로 단지 반경 어린이집·소아과·병원·약국·마트·편의점·공원·도서관 개수 집계 -> "육아·생활 편의" 카드.
  사용자 질문 "임대비율·학군 순위 크로스" -> 혼합단지/세입자비중/학원밀집도까지 반영, 특목고 진학률(학교알리미 키)과 정확한 임대세대수(서울시 데이터)는 미착수.

- 2026-09-12 (컴퓨터 세션, 6차): 학교알리미 OpenAPI 키 발급(2026년부터 sggCode 필수). apiType 탐색 결과:
  0=학교기본정보(좌표 포함), 10=전·출입, 62=학년별·학급별 학생수(학급당 인원), 63=성별, 51=졸업생 진로(중학교는 진학/취업 합계만, **특목고·자사고 분류 없음**), 64=직위별 교원, 22=자격종별 교원.
  최근 3개년(2024~2026)만 제공. 마포+이웃 6개 구 초·중 수집 -> 배정 초등 학생 수·전년 증감·학급당·순전입·권역 전입 선호 순위, 중학교 학생 수·학급당 표시.
  특목고 진학률은 API에 없어 학교알리미 웹 페이지(학교별 '졸업생의 진로 현황' 표) 스크래핑이 필요 -> 미착수.

- 2026-09-12 (컴퓨터 세션, 7차): 학교알리미 웹 크롤링 조사 결과 -> **중학교 '졸업생의 진로 현황' 항목 자체가 공시 목록에 없음**(06번 결번, 특목고 진학률 확보 불가),
  '교과별 학업성취 사항'(44)은 캡차 뒤에 있어 자동 수집 불가(우회 안 함). 학교 페이지는 POST /ei/ss/Pneiss_b01_s0.do (SHL_IDF_CD=uuid), 항목은 /ei/pp/Pneipp_bNN_s0p.do 를 jQuery load 로 부름(파이썬 직접 호출은 WAF가 '서비스 일시 중단' 페이지로 차단).
  대신 **학군 지수(0~100)** 도입: 교과학원 밀집 40 + 초등 전입 선호 25 + 초등 학생 증감 15 + 중학교 규모/과밀 20 -> 구내 순위·상위 %, "학군순" 정렬 칩. 염리동·공덕동 단지가 상위.

- 2026-09-12 (컴퓨터 세션, 8차): CLAUDE.md(세션 협업 규칙) 추가. 지도 핀 겹침 완화(우선순위 greedy 충돌 회피, moveend 재계산).
  **서대문구 확장**: 실거래 24개월·전월세·K-apt·카카오 좌표 234개·학원(NEIS)·편의시설 수집 -> 마포+서대문 519개 단지 한 지도. geocode.py 는 sgg_cd 로 구를 자동 판별.
  서울시 공동주택 정보(OpenAptInfo: 분양/임대/혼합·세대수·주차·면적별 세대수, 좌표 포함) 수집기+build 연동 준비, **SEOUL_KEY 사용자 발급 대기**.

- 2026-09-12 (컴퓨터 세션, 9차): **1단계(배포+SEO) 준비 완료**. `generate_pages.py` 로 단지별 정적 페이지 519개 + /apt/index.html + sitemap.xml + robots.txt,
  앱 딥링크 `index.html?id=`, 상세에 "단지 상세 페이지" 링크. `deploy_github_pages.py` (GITHUB_TOKEN 으로 저장소 생성/푸시/Pages ON) 작성.
  **실제 배포는 GITHUB_TOKEN 사용자 발급 대기**. 위스키(whiskyhot.com)는 이 PC 의 nginx+Cloudflare 라 건드리지 않고 GitHub Pages 로 분리.
  알려진 이슈: 1년 변동률이 평형 섞인 중앙값이라 일부 단지 과장(-18.8% 등) -> 평형별 매칭으로 개선 필요.

- 2026-09-12 (컴퓨터 세션, 10차): **배포 완료** https://mtmt88087044-pixel.github.io/apt-map/ (GitHub 저장소 mtmt88087044-pixel/apt-map, gh-pages).
  재배포는 `python pipeline/build.py && python pipeline/generate_pages.py && python pipeline/deploy_github_pages.py`. 1년 변동률 평형별 계산으로 수정 완료.
  도메인은 위스키(whiskyhot.com)에 붙이지 않기로 (주제 분리). 유입 생기면 집콕맵 전용 도메인 구매 후 Cloudflare 연결.

- 2026-09-12 (컴퓨터 세션, 11차, 진행 중): **서울 25개 구 확장 작업**. 실거래 24개월 136,533건 / 6,809개 단지 / K-apt 3,402개 수집 완료.
  앱 구조 변경: complexes.json 은 요약만, 상세는 app/data/c/<id>.json 온디맨드; 도로는 app/data/roads/<r>_<c>.geojson 0.02도 타일(화면 걸친 것만) + roads_major.geojson(줌<13.5).
  학교 좌표는 학교알리미 apiType 0(LTTUD/LGTUD)로 서울 전체 보강. 경계 25개 구, 역 317/초등 842(OSM).
  생성물(app/data, app/apt)은 소스 저장소에서 제외(.gitignore) - gh-pages 로만 배포. 재빌드 시 반드시 build -> generate_pages -> deploy 순서.
  카카오 호출은 타임아웃 재시도 추가 (fetch_kakao_poi, fetch_neis). 좌표 6,809 전부, 학원 24,037곳 완료. 편의시설(kakao_poi)은 2차 진행 중(약 2천/6.8천) - 끝나면 build+deploy 재실행 필요.
  서울 전체 빌드 1분, 페이지 6,809개(63MB, page.css 공용), 요약 JSON 4.5MB(gzip 전송). 페이지 파일명 = 단지 id.
  **서울 전체 버전 배포 완료** (2026-09-12 17시대). 편의시설 2차 끝나면 `build.py -> generate_pages.py -> deploy_github_pages.py` 한 번 더.

- 2026-09-12 (컴퓨터 세션, 12차): **3번 완료 - 제보·찜 백엔드**. Cloudflare Worker `aptmap-api` + KV `aptmap` (계정 0faa426e…, workers.dev 서브도메인 `jipkokmap` API 로 생성).
  API https://aptmap-api.jipkokmap.workers.dev (/reports GET·POST, /recent, /favs GET·POST, /health). 앱은 app/config.js 의 API_BASE 로 연결, 없으면 기기 저장으로 폴백.
  앱: 제보 모달(호가/실거래·면적·가격·메모, 허니팟), 상세에 커뮤니티 제보 목록, ♥ 찜 + "내 찜" 칩, 칩 더블클릭 = 기기 간 동기화 링크(?fav=CODE).
  워커 재배포: `python pipeline/deploy_worker.py` (CLOUDFLARE_API_TOKEN). KV 에 테스트 제보 1건(id test-단지-1) 남아 있음 - 삭제 API 없음, 무해.

- 2026-09-12 (컴퓨터 세션, 13차): 4단계 순차 진행 완료.
  (1) **갱신 자동화**: `pipeline/refresh.py` (25개 구 실거래·전월세 이번달/지난달 재수집 -> 좌표 -> 편의시설 -> build -> pages -> 알림 -> deploy, `--full` 은 K-apt/NEIS/학교알리미까지).
      Windows 작업 스케줄러 `JipkokMapRefresh` 매주 월 05:00 (로그인 상태에서만 실행, logs/scheduler.log). 드라이런 성공.
  (2) **공식 학구도**: 학구도안내서비스 zip(초등 통학구역·중학교 학군·연계·학교위치, 2026-03-20) -> `build_schoolzones.py` (EPSG:5186 TM 역변환 직접 구현, DP 단순화) -> schoolzones_seoul.json.
      서울 초등 학구 629(공동 67), 중학교 학군 46. 단지 6,808/6,809 이 공식 학구 안, 공동학구 162. 중학교는 소속 학군의 학교 목록(가까운 순)으로 표시.
  (3) **제보 검수/피드**: 워커 /flag(신고 3회 자동 숨김), /admin/reports·/admin/delete (ADMIN_KEY 시크릿), app/feed.html(최근 제보), app/admin.html(관리자, noindex).
  (4) **실거래 알림**: 워커 /alerts(이메일+찜 id), /alerts/unsub; `notify_alerts.py` 가 refresh 마다 새 거래 있으면 메일 (SMTP 설정은 위스키 .env 값 복사). 첫 실행은 기준일만 저장.
  테스트 등록 test@example.com 1건 KV 에 남아 있음(발송 실패로 무해). KV 알림 삭제 API 없음.

- 2026-09-12 (컴퓨터 세션, 14차): **지형 + 속도**. AWS Terrarium DEM(무료, ~30m) -> `pipeline/terrain.py` (타일 캐시 data/raw/terrain/14, 서울 전체 z14 약 320장, PIL 로 디코드).
  단지별 해발·반경100m 경사·역/초등 고도차 -> 상세 "지형" 칸, 장단점 "언덕 위 단지(역보다 +30m↑)"/"경사 가파름(8%↑)"/"평지". 서울 6,809 중 언덕 태그 391.
  앱 "지형" 토글: hillshade 레이어 + setTerrain 3D(exaggeration 1.3). 속도: app/sw.js 서비스워커(앱셸 네트워크우선, 데이터 SWR, 타일/글꼴 캐시 400장), preconnect, 학군 폴리곤 지연 로드, 마커 정렬 전 화면 밖 제외.
  deploy 스크립트가 sw.js 의 __BUILD__ 를 배포시각으로 치환해 캐시 버전을 올림.
  사용자 요청 "언덕/산 구분", "속도" 반영. 다음: 검색엔진 등록(사용자: 서치콘솔/서치어드바이저 meta 값 전달 필요) -> 구·동별 랭킹 페이지 -> 필터/비교 -> 경기도 확장 -> 갱신 실패 알림.

- 2026-09-12 (컴퓨터 세션, 15차): 사용자 요청 5종 진행.
  (1) 고등학교: 학구도 '고등학교 학교군' 11개 + 나이스 고교 유형(일반/자율/특목/특성화) + 학교알리미 좌표 -> 소속 학교군 일반고 5곳(가까운 순) + 3km 내 자율·특목고. apiType 51(고교)은 진로가 아니라 졸업·수료 현황이라 진학률 표시 제거.
  (2) 기피시설: OSM Overpass (변전소 ?, 송전선 145, 매립/소각 2, 하수 2, 화장/장례 11, 군부대 23, 주유소 483, 유흥 50, 모텔 549, 철도 1982, 고속도로 2074) -> 종류별 기준거리 내 여부·거리·개수, 상세 카드, 지도 '기피' 토글(nuisance.geojson), 장단점 최대 2개.
      LOCALDATA(유흥주점·단란주점·숙박업 인허가) 는 사이트 접속 불가(ECONNREFUSED)로 미수집 -> fetch_localdata.py 추후.
  (3) 위험·상승 신호(signals): 신고가/하락률(주력 평형 24개월 최고가 대비)/거래 급감·활발/환금성/노후+주차/깡통/갭·전세가율/초등 순전입/재건축 연한 -> 상세 카드, 카드 태그, '상승신호' 정렬.
  (4) 동 단위 인구(아동 비율·다세대원·외국인): 서울 API 종료됨, 행안부 jumin.mois.go.kr downloadCsvAge.do 는 지역명만 내려옴(열 조립 JS 필요) -> **보류**. 대안: KOSIS 공유서비스 API 키(사용자) 또는 SGIS.
  (5) 다문화 학생 수: 학교알리미 API 항목(63 성별학생수 등)에 없음 -> 미제공. 학폭 심의 결과·학업성취는 캡차 -> 학교알리미 링크만 제공.
  검색엔진: 네이버 소유확인·사이트맵 제출 완료(루트 사이트 mtmt88087044-pixel.github.io 저장소, deploy_root_site.py), 구글 소유확인 완료(meta refresh 제거 후), 사이트맵 2건 제출 → 첫 상태 '가져올 수 없음'(재배포 타이밍) - 재시도 필요.

- 2026-09-13: **도메인 jipkokmap.kr 연결 완료** (사용자 구매, 등록업체 DNS 에 A 4개 + CNAME www). GitHub Pages cname 설정, HTTPS 강제 ON, 인증서 approved.
  라이브 https://jipkokmap.kr/ (github.io 주소는 새 도메인으로 리다이렉트). generate_pages base/알림 링크/워커 CORS 는 SITE_BASE·SITE_DOMAIN(.env) 기준. 검색엔진에는 새 도메인 재등록 필요.

- 2026-09-13 (컴퓨터 세션, 16차): 사용자 요청 묶음 배포.
  구 경계/이름/평당가 중앙값(districts.geojson, symbol 라벨), 구별 대장 👑 핀(줌<13.3), 3D 기울이기 버튼(pitch 58, 과장 1.5).
  속도2: roads_major·nuisance·amenity 소스 지연 로드(켤 때만), SW 앱셸 SWR, 웹폰트 제거(시스템 글꼴).
  👶 아이 키우기 점수(6축: 초등접근·학군·보육의료·지형보행·환경안전·생활편의, 레이더, 서울 순위) + '아이키우기' 정렬 + 상위 10% 장점 태그.
  국면(phase) 한 줄, 동네 진실 카드(단점·중립·위험 모음 + 복사 공유), 단지 비교 3개(모달 표, localStorage), 예산으로 찾기(최소/최대 억·평형·구·역·아이우선).
  주요시설 레이어(OSM: 병원 528, 소아과 91, 대형마트 302, 어린이집 753, 도서관 675, 공원 1478, 놀이터 2851, 경찰 608, 응급 28, 대학 143) + 단지 선택 시 500m/1km 원, 큰 라벨, 상세 '가까운 주요시설', 통학로 큰길 횡단 여부(직선 교차).
  사용자에게 활용신청 링크 3건(응급의료 15000563, 에어코리아 15073861, 어린이보호구역 15012891) 안내함 - 완료되면 fetch 스크립트 작성.

- 2026-09-13 (17차): 애드센스 승인용 콘텐츠 `pipeline/generate_content.py` -> about/guide/privacy/moving + rank/index + rank/<구> 25개 (구 소개 문단 + 아이키우기·학군·평당가·초품아·상승/주의 표). refresh 에 content 단계 추가, 앱 하단 링크, 사이트맵 포함.
  쿠팡 파트너스 링크는 data/coupang_links.json ({"제목":"url"}) 넣으면 moving.html 에 자동 삽입. CONTACT_EMAIL(.env) 있으면 소개/개인정보 페이지에 표시.

- 2026-09-13 (18차): 학군 **남/여/공학 구분** 배포. `build.py` 가 중학교 학교군의 성별 구성(`school.middle_gender`)과
  고등학교 학교군 구성(`school.high.gender`)을 세고, 요약(`mg = [아들 기준, 딸 기준]`)에 넣음. 앱에 학교별 남/여/공학 배지,
  "아들 N곳 · 딸 N곳 배정 가능" 한 줄, 예산찾기에 자녀 성별 조건(배정 가능 중학교 2곳 이상), 1곳 이하면 카드에 경고 태그.
  단지 페이지(generate_pages.py)에도 같은 정보. 검증: 아현동 더클래시 중학교 공학4/남2/여1, 고교 공학7/남8/여5.

- 2026-09-14 (19차): **부동산 계산기 + 자금 마련 가이드** 신규 2페이지.
  - `pipeline/content_calc.py` (폼 HTML + CSS), `pipeline/calc_js.py` (계산 로직), `pipeline/content_fund.py` (가이드 + 증여/차용 계산기)
  - `app/calc.html` 7종 탭: 취득세 / 중개수수료 / 대출 월상환금 / 내 소득 대출한도(DSR·LTV) / 보유세(재산세+종부세) / 전세↔월세 환산 / 갈아타기 비용
  - `app/fund.html`: 정책대출(신생아특례·디딤돌·보금자리론·버팀목, 다자녀 우대), 1금융권 vs 보험사 vs 상호금융 vs 저축은행 비교표,
    부모님 증여(5천만+혼인출산 1억 공제) vs 차용(적정이자율 4.6%, **무이자 한도 2억 1,739만원** = 이자차액 1천만원 미만 기준),
    차용증 체크리스트, 자금조달계획서 주의, 자주 하는 실수 5가지. 증여세·차용 판정 계산기 포함.
  - 세율 기준 `content_calc.RATE_ASOF = "2026-09"`. 자주 바뀌는 값(기준금리·LTV·스트레스금리·전환율)은 입력 필드로 빼서 사용자가 직접 수정 가능.
  - 입력값은 localStorage(`jipkok_calc_v1`)에만 저장. 탭은 `#acq` 같은 해시로 직접 링크 가능(hashchange 대응).
  - 지도 화면 칩 + 모든 콘텐츠 페이지 nav/footer 에 링크 추가. 사이트맵 포함(32개 페이지).
  - 로컬 서버(127.0.0.1:8899)로 7종 전부 수치 검증: 9억 1주택 85㎡ 이하 취득세 2,970만(3.3%), 중개 495만,
    4억/4.2%/30년 원리금균등 월 196만·총이자 3억 418만, 연소득 6천 DSR40% 한도 3억 4,459만, 공시 7억 1주택 보유세 101만,
    전세5억→보증금1억 전환율 4.5% 월세 150만, 7억→11억 갈아타기 거래비용 5,061만(4.6%).
  - 단지 페이지 -> 계산기 연결: generate_pages.py 가 대표 실거래가를 `calc.html?price=<억>&name=<단지명>#<탭>` 으로 넘기고,
    calc_js.py 가 취득세/중개수수료/대출한도/갈아타기 입력에 채운 뒤 어느 단지 기준인지 안내 카드를 띄움.
  - 주의: 세무 자문이 아니라는 고지를 두 페이지 모두에 넣었음. 세율 바뀌면 `calc_js.py` 의 SALE/RENT/CFT2/CFT3/propTax/acqRate 와 `content_fund.py` 의 GIFT/LEGAL 만 고치면 됨.


- 2026-09-14 (20차): **경매/공매 물건 가격** 조사 + 수집기 골격.
  - 현재 `app/data/auctions.json` 은 0건(데모 전용). 지도 ⚖️ 경매 레이어·상세 UI 는 이미 완성돼 있어 데이터만 붙이면 됨.
  - **법원경매(courtauction.go.kr)는 하지 않기로.** 공식 오픈API 없음(대법원 제공 없음, CODEF 등은 유료 스크래핑 중계).
    자동 요청에는 "시스템안내" 페이지를 돌려주는 구조라 사실상 자동수집 차단. 네이버부동산과 같은 범주로 취급.
  - **온비드(캠코) 공매는 공식 무료 API 존재** -> `pipeline/fetch_auction.py` 신규. 엔드포인트 `https://apis.data.go.kr/B010003/Onbid*Srvc2`.
    확인된 서비스: OnbidPbancListSrvc2/getPbancList(공고목록), OnbidRlstDtlSrvc2/getRlstDtlInf(부동산 물건상세),
    OnbidPbancCltrDtlSrvc2(공고상세 물건정보), OnbidCltrBidDtlSrvc2(입찰정보). 부동산 물건목록은 오퍼레이션명 미확정.
  - `--probe` 로 승인 후 서비스/오퍼레이션/응답 필드를 확정해 `data/raw/auction_probe.json` 에 저장하고, 본 수집은 그 결과를 읽어 동작.
    지금 돌리면 전부 NO_OPENAPI_SERVICE_ERROR (활용신청 미승인). **사용자 활용신청 3건 대기 중.**
  - 주의: 온비드 공매는 법원경매보다 물량이 훨씬 적어 서울 아파트는 시기에 따라 0건일 수 있음. 데이터 확인 후 앱 라벨을 "경매"->"공매"로 바꿀 것.


- 2026-09-14 (21차): **법원경매정보 링크 카드** 구현 (기본 OFF). 사용자 승인: "1번 진행하고 온비드승인 기다려".
  - 대법원 사이트 푸터의 **"법원경매정보 링크" 정책**을 확인함. 요약: (1) 링크 전에 사이트 이용문의로 8개 항목을 접수해야 함,
    (2) **첫 화면(courtauction.go.kr)으로만** 연결, 딥링크·주소 프리필 불가, (3) 연결됨을 표시하고 추천·제휴 관계가 아님을 밝혀야 함.
    문의: 사용자지원센터 02-3480-1715 (평일 9~18시).
  - **저작권보호정책**도 확인: 법원이 저작재산권 전부를 보유한 자료는 저작권법 제24조의2(공공저작물의 자유이용)로 **출처 표시 시 자유이용 가능**.
    즉 자료 자체의 라이선스는 열려 있고, 막히는 건 "수집 방법"(약관·기술적 차단)이다. 그래서 데이터 확보는 공공데이터 제공신청이 정답.
  - 구현: 지도 상세 패널(app.js) + 단지 페이지(generate_pages.py)에 주소 + 주소복사 버튼 + "법원경매정보 열기"(첫 화면) + 고지문.
    스위치 2개 — `app/config.js` 의 `COURT_LINK`, generate_pages 는 환경변수 `COURTAUCTION_LINK=1`. **둘 다 기본 false/미설정.**
  - **접수 완료 후 켜는 법**: config.js 의 COURT_LINK 를 true 로, `.env` 에 `COURTAUCTION_LINK=1` 추가 -> generate_pages + deploy.
  - app.js/style.css v47 -> **v48**. 로컬에서 지도 패널·단지 페이지 양쪽 렌더 확인함(링크는 첫 화면, rel=noopener noreferrer).


- 2026-09-14 (22차): **예산 대비 학군** 신규 지표 + 예산별 학군지 가이드. 포지셔닝을 사용자가 정리해 줌:
  "엄밀히 따지면 본인 수준에 맞는 학군지 아파트 가이드를 도와주는 것". 인스타(맘스타그램) 게시물에서 출발 —
  "학군지를 찾는 이유는 성적이 아니라 반 분위기(또래 환경)".
  - `build.py`: 대표 실거래가(84㎡급 우선) -> 6구간(5억미만/5~8/8~11/11~15/15~20/20억+) -> **구간 안에서만** 학군 지수 백분위.
    필드 `rep_price`, `budget_band`, `edu_band_pct`, `edu_band_n` (요약에도 포함). 6,809개 전부 값 있음.
  - 앱: 칩 `💰 예산 대비 학군`, 카드 태그(구간 상위 20% 이하), 상세에 "같은 가격대 N개 단지 중 학군 상위 X%" 줄,
    비교표에 2줄(같은 가격대 학군 / 분양·임대), 예산찾기에 "무엇을 우선할까요" select(eduvalue 기본).
  - 새 페이지 `app/rank/budget-school.html` 예산별 학군지 가이드 (구간별 학군 상위 20). 랭킹 인덱스·푸터에 링크.
  - `guide.html`: 학군 지수 설명을 또래 환경 관점으로 다시 씀 + "예산 대비 학군" + "공급 유형(분양/임대/혼합)" 항목 추가.
  - 검증: 5~8억 구간 학군 1위권이 중계동(노원 학원가) — 의도한 결과. 중계현대2 6억, 구간 1880개 중 상위 1%, 초품아, 학원 449개.
  - app.js/style.css **v49**.
  - **원칙 명시**: 사람을 분류하는 지표(외국인 비율, 장애·질환 비율 등)는 만들지 않는다. 가격대·학원밀도·배정학교·공급유형처럼
    공개된 사실만 다룬다. guide.html 과 budget-school.html 에 이 문장을 넣어 뒀음. 사용자 요청("비슷한 이웃")의 대리 지표는 **가격대**로 해결.


- 2026-09-14 (23차): **지하철역 레이어 추가 + 학교 강조** (사용자 요청 "지하철이랑 학교 강조해줘").
  - `build.py` -> `app/data/stations.geojson` 신규 (data/raw/poi.json 의 stations 317개, name/line).
  - `app.js`: 소스 `stations` + 레이어 `sub-dot`(원, 줌 11~, 반경 4~10px, #0ea5e9) / `sub-label`(볼드 12~19px, 흰 halo 2.2).
    레이어 토글 `🚇 지하철` 신설, **기본 ON** (state.layers.subway=true). lazySource 로 켤 때 로드.
  - 학교 마커: 표시 줌 14.3 -> **13.8** 로 낮추고 `.mk.school` CSS 신설 (14px/900, 테두리 2px currentColor, 꼬리 제거).
    13.2 까지 낮췄다가 DOM 마커 수(615개) 성능 고려해 13.8 로 되돌림.
  - **버그 발견·수정**: 폴백 스타일 `OSM_RASTER` 에 `glyphs` 가 없어서, 벡터 베이스맵 실패 시
    text-field 를 쓰는 심볼 레이어(`gu-label` 구 이름, `am-label` 편의시설, 신규 `sub-label`)가 **전부 조용히 사라졌음**.
    에러: `use of "text-field" requires a style "glyphs" property`. OSM_RASTER 에
    `glyphs: https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf` 추가 (응답 200 확인).
  - app.js/style.css **v50**.
  - **검증 한계**: 브라우저 pane 에서 MapLibre 가 렌더 패스를 못 끝내(map.loaded() 계속 false, rAF 미동작)
    queryRenderedFeatures 가 항상 빈 배열. 레이어 정의는 에러 0으로 추가됨을 확인했고 역 317개 데이터도 확인했으나,
    **실제 화면 모양은 사용자 확인 필요.**


- 2026-09-15 (24차): **지하철 노선 경로·공식 색** (사용자 요청).
  - 신규 `pipeline/fetch_subway.py`: Overpass route relation -> ref(호선)별 선로 way 합집합(지선·급행 중복 제거), 서울 박스 클립, DP 단순화(~4m).
    수도권 전철 18개 노선(1~9, 신분당, 경의중앙, 경춘, 공항철도, 서해, 수인분당, GTX-A, 신림, 우이신설). KTX/SRT/ITX 제외.
    정차 노드 이름으로 역별 노선 목록 -> `data/raw/subway.json`. 역 317개 전부 매칭. `--raw` 로 재수집 없이 가공 가능.
    overpass-api.de 는 406 을 줘서 private.coffee 미러로 받음. 주간 refresh 에는 넣지 않음(노선은 거의 안 바뀜, 개통 시 수동 재실행).
  - `build.py`: 역에 `lines/line/color`, 단지 `station.lines`, `app/data/subway_lines.geojson`(176KB), stations.geojson 에 color/transfer.
    장점 "환승역 X (2호선·5호선) 도보 N분" (800m 이내) -> 1,162개 단지.
  - `app.js`: 레이어 sub-line-case(흰 테두리) + sub-line(노선색) + sub-dot(일반역 노선색, 환승역 흰 원+검은 테두리 크게) + sub-label(역명 + 작은 노선명).
    카드·상세에 노선 배지 `.lnb` (LINE_COLORS). v51.
  - 검증: 실제 app.js 레이어 블록을 빈 스타일에 실행해 4개 레이어 에러 0, matplotlib 으로 노선도 그려 모양 확인. pane 에서 지도 캔버스 렌더는 여전히 불가.


- 2026-09-15 (25차): **출퇴근 시간으로 찾기** (차별화 기능, 사용자: "조회수가 안 나와서 슬프다").
  - `fetch_subway.py` 에 `build_graph()`: relation 정차 순서로 역 그래프 549역/662구간. 소요 = 직선x1.15/표정속도 + 정차 0.4분
    (일반 0.6km/분, FAST: 신분당 1.1, GTX-A 1.7, 공항철도 0.9, 경춘 0.8), 급행·특급 계통 제외(완행 기준), 순환선 닫기.
    원본 Overpass 응답을 `data/raw/subway_overpass.json` 에 보관 -> `python pipeline/fetch_subway.py --raw data/raw/subway_overpass.json`.
    검증(강남 출발): 역삼 2, 잠실 16, 여의도 28, 시청 34, 홍대입구 45, 노원 52분.
  - `build.py` -> `app/data/subway_graph.json` (27KB).
  - `app.js`: 칩 `🚉 출퇴근 시간`(.chip.hot) -> 모달(회사 역 1·2, 최대 30/40/50/60분, datalist 549역).
    브라우저에서 Dijkstra(역x노선 상태, 환승 4분) -> 단지 1.5km 내 역 최대 3곳 중 min(도보 d/70 + 대기 3 + 탑승).
    조건 켜지면 화면 밖 단지 포함, 소요시간 정렬, 카드 태그 `.tag.cm`, 상세 "출퇴근 (추정)" 줄. 예산찾기와 동시 적용.
    공유: URL `?cm=강남,여의도,40` 복원 + `🔗 공유` 버튼(navigator.share / 클립보드).
  - 예산찾기 개선: 기본 평형 "50㎡ 이상 가족형"(+100세대 이상), 카드 가격을 조건에 맞는 평형으로 표시(`c._bRep`). 옛 "출퇴근 역" 텍스트 필드 제거.
    이유: 원룸형 25㎡ 가 상위를 차지해 가족 수요에 쓸모없었음.
  - `index.html` OG 태그 + `app/og.png`(1200x630, 노선도+문구) -> 카톡/SNS 공유 미리보기.
  - guide.html 에 출퇴근 시간 계산 방식 설명. app v52.
  - 조회수 0 진단: 도메인 개설 2일차, 검색 색인 전으로 보임 (robots/sitemap/검증태그는 정상). 서치콘솔 색인 요청·커뮤니티 공유가 필요.


- 2026-09-15 (26차): **항상 밝은 테마** (사용자: "전반적으로 너무 다크여 화사하게").
  원인: style.css / generate_pages.py 가 `prefers-color-scheme: dark` 를 따라가서 폰이 다크모드면 앱이 남색으로 바뀌었고,
  index.html theme-color 가 #0f172a 라 브라우저 상단바도 어두웠음.
  - 다크 미디어쿼리 전부 제거, `color-scheme: light only` (CSS + 모든 html/생성기 meta) 로 삼성인터넷·크롬 강제 다크도 방지.
  - app.js `dark = false` (베이스맵 항상 positron). theme-color #ffffff.
  - 팔레트 약간 화사하게: bg2 #f7f9fc, brand #3b82f6, 선택 칩 검정 -> 파랑(그림자), 레이어 버튼 on 배경 #eff6ff. v54.
  - 확인: 다크 모드 에뮬레이션에서 body 배경 rgb(247,249,252) 유지.
  - **앞으로 다크모드 다시 넣지 말 것** (사용자 선호).


- 2026-09-15 (27차): **익명 방문 통계** (사용자: "사람 오나 안 오나").
  - Worker `POST /hit` (sendBeacon text/plain, preflight 없음): 타입 visit/commute/budget/share/compare/fav/report.
    KV `stats:YYYY-MM-DD`(KST) 에 {visit, mobile, pages{app,apt,rank,...}, ev{...}, ref{도메인}} 합계만. IP·쿠키 저장 안 함, 봇 UA 제외, 400일 TTL.
    `GET /admin/stats?key=&days=` (최대 90).
  - 클라이언트는 sessionStorage 로 **세션당 방문 1회, 기능별 1회**만 전송 -> KV 무료 쓰기 한도(하루 1,000) 대비.
    방문이 하루 700~800 을 넘기 시작하면 Workers Analytics Engine 으로 옮길 것. 동시 쓰기 시 약간 덜 셀 수 있음.
  - 앱: app.js `hit()` (visit, 출퇴근·예산 찾기, 공유). 정적 페이지: generate_pages/generate_content 의 </body> 앞 인라인 비콘.
    **주의**: 두 생성기의 해당 문자열은 .format() 안이라 중괄호를 {{ }} 로 이스케이프해야 함 (한 번 깨져서 app/apt 가 비었다가 재생성으로 복구).
  - `app/admin.html` 상단에 방문 통계(오늘/7일/30일, 30일 막대, 들어온 곳, 처음 연 페이지, 기능 사용). 관리자 키 필요.
  - privacy.html 에 익명 이용 통계 항목 추가.
  - **deploy_worker.py 주의**: 실행하면 app/config.js 를 API_BASE 한 줄로 덮어써 COURT_LINK 설정이 사라짐 -> 실행 전 백업/복원했음. 스크립트 자체 수정은 아직 안 함.


- 2026-09-16 (28차): **공사 중 지하철 노선 + 예정역** (차별화, 검색 유입용 "동북선 역세권" 수요).
  - 신규 `pipeline/fetch_future_rail.py`: OSM `railway=construction` 선로만(계획 단계 proposed 는 제외) + 공사 태그 있고 이름이 숫자 아닌 예정역만.
    원본 `data/raw/future_rail_overpass.json`, 결과 `data/raw/future_rail.json`. `--raw` 로 재가공.
    노선 9개(GTX-A·B·C, 신안산선, 동북선, 9호선 4단계, 7호선 도봉산옥정선, 월곶판교선, 동탄인덕원선), 이름 확인된 예정역 20곳
    (동북선 11, 월곶판교선 6, GTX-A 삼성, 도봉산옥정선 탑석, 동탄인덕원선 원천). 신안산선·GTX-B/C 서울 구간 역은 OSM 에 없어 미표시.
    overpass-api.de 는 User-Agent 없으면 406.
  - `build.py`: 전역 FUTURE_RAIL, 단지별 1km 내 최근접 예정역 `c.future` (요약 `fut`), 800m 이내면 장점 "동북선 상계역 예정(공사 중) 도보 N분".
    340개 단지(800m 이내 227). `app/data/future_rail.geojson`(선로+예정역 포인트).
  - `app.js`: 지하철 레이어에 fut-line(노선색 점선)·fut-line-label("(공사 중)")·fut-dot(흰 원 주황 테두리)·fut-label("OO 예정").
    카드 태그 `.tag.fut`, 상세 "공사 중 노선 예정역" + "OSM 기준, 개통 시기·역 위치 변동 가능". v56.
  - 단지 페이지 문구, 신규 `rank/future-rail.html`(content_future_rail.py, 노선·역별 도보권 단지 표, 공식 발표 확인 안내), 랭킹 인덱스 링크.
  - 통계: localhost/127./192.168. 에서 연 경우 집계 안 함(app.js, 두 생성기 비콘). 9/16 방문 1은 로컬 테스트 흔적.


- 2026-09-16 (29차): **검색 노출(SEO) 기술 정비** (사용자: "검색에도 안 뜨고 유입 어찌 늘리나").
  점검 결과: 단지 페이지는 이미 양호(canonical·og·JSON-LD·내부링크 21). 문제는 **홈**이었음 —
  canonical 없음, 내부 링크 7개, 본문 1,039자, 그리고 **홈에서 apt/index.html 로 가는 링크가 아예 없어** 6,809개 페이지가 사이트맵으로만 도달 가능.
  - `app/index.html`: canonical, WebSite JSON-LD, 하단에 허브 링크 추가(단지 목록 / 예산별 학군지 / 공사 중 예정역 / 계산기 / 자금 마련 / 구별 랭킹).
  - 사이트맵 분할: `sitemap.xml`(인덱스) -> `sitemap-core.xml`(홈·허브·콘텐츠 36개) + `sitemap-apt.xml`(단지 6,809).
    크롤링 예산이 적은 신규 도메인에서 허브부터 수집되게 하려는 것. generate_pages 가 core 를 만들고 generate_content 가 콘텐츠 URL 로 덮어씀(순서 주의: pages -> content).
  - 네이버 서치어드바이저용 `app/rss.xml` (콘텐츠 34개) 생성.
  - **사용자 작업 필요**: 구글/네이버에 sitemap.xml 재제출, 네이버에 rss.xml 제출, 주요 URL 수집 요청.


- 2026-09-16 (30차): **동네 학원비 + 과밀학급 + 맞벌이 중간지점** (경쟁 앱 분석 후 "기존 앱에 없는 것" 구현).
  경쟁 조사: 아실(학업성취도 2017년·진로 2021년 자료로 낡음), 호갱노노(배정학교·학교등급·통학거리, 출퇴근은 자차+업무지구 고정),
  리치고(학군·학원가 입지), 학원앱(학원맵·런즈: 리뷰 강점이나 집값과 단절), 공공(학구도안내서비스·스마트서울맵).
  -> 부동산 앱은 학원을 "개수"로만 세고, 학원 앱은 집값을 모름. 그 사이가 비어 있음.
  - **핵심 발견**: NEIS acaInsTiInfo 의 `PSNBY_THCC_CNTNT` 에 과목별 월 교습비가 원 단위로 들어있음(우리가 버리고 있던 필드).
    `fetch_neis.py` 에 fee_median() 추가, 신규 `pipeline/update_academy_fee.py` 로 기존 academies_*.json 에 fee 채움(지오코딩 재실행 없음).
    커버리지: 서울 학원 25,452개 중 6,461개(25%)가 교습비 공개. 구별 중앙값 강남 36만 > 서초 30만 > ... > 강북 19.8만.
  - `build.py`: `c.edu.fee_med`(1km 내 교과학원 교습비 중앙값, **표본 5곳 미만이면 None**), fee_n, 서울 백분위 `fee_top_pct`.
    6,371개 단지에 값. 상위10%면 단점, 하위(60%+)이고 학군 55+ 면 장점 "학군 대비 학원비 저렴".
    과밀 기준 28명 -> **24명**으로 현실화(서울 초등 학급당 중앙값 18, 최대 27.8이라 28 기준은 한 번도 안 걸렸음). 요약에 school.class_size 추가.
  - 앱: 칩 `📚 학원비 싼 학군`(학군 50+ 중 저렴순), 카드 태그 `.tag.fee`(상위20% 빨강/하위 초록), 상세 "동네 학원비" 줄, 비교표 2줄.
    출퇴근 모달에 정렬 기준 select(긴 쪽 기준 / **두 사람 합계=중간지점**). 중학교 성별 배정 2곳 미만 태그 `.tag.warn2`. v59.
  - 신규 `rank/academy-fee.html`(content_academy_fee.py): 구별 학원비 표, 학군 좋고 학원비 싼 단지 30, 비싼 단지 20.
  - guide.html 에 "동네 학원비", "학급당 인원·중학교 성별" 항목 추가. 단지 페이지에 학원비 문단.


- 2026-09-16 (31차): 리스트 카드 축소 + 검색 노출 후속.
  - 카드: 여백 14->10px, 제목 16->14.5, 가격 17->15.5, 태그 11.5->10.5px, **태그 6개 제한**(app.js `].slice(0, 6)`).
    모바일 카드 높이 180px 안팎 -> 107~147px. v60.
  - "집콕맵" 검색 시 GitHub 저장소가 먼저 뜨는 문제: GitHub Pages 무료 플랜은 공개 저장소가 필수라 비공개 불가.
    대신 GitHub API 로 repo homepage=https://jipkokmap.kr, description 설정(검색결과에서 사이트로 연결되게).
  - 신규 `pipeline/indexnow.py` + 소유권 키 파일 `app/<32hex>.txt`: 계정 없이 빙·네이버 등에 색인 요청.
    `python pipeline/indexnow.py`(허브 37개) / `--all`(단지 포함). 첫 제출 HTTP 202 접수 확인.
  - 리모트 컨트롤: 세션 시작 시 자동으로 켜달라는 요청 -> 앱 설정 파일에 옵션이 없어 메모리
    (feedback_remote_control_on_start)로 저장, 다음 세션부터 첫 턴에 켠다.


- 2026-09-16 (32차): 폰 사용성 3건 (사용자 요청).
  - **지도가 시트에 가리지 않게**: `syncMapSize()` 가 시트 상태별 목표 높이(peek 156px / half 52vh / full 62vh)만큼
    `#map` 의 bottom 을 띄우고 `map.resize()`. full 이어도 지도 38% 는 남는다. 데스크톱(>=900px)은 그대로 전체 화면.
    `#map` 에 bottom transition .28s 추가, resize 이벤트에도 연결.
  - **리스트 상단 탭으로 크기 조절**: 기존에는 얇은 손잡이(.grip)에만 있던 peek->half->full 순환을 `.list-head` 클릭에도 연결.
    제목 뒤에 ⌃⌄ 표시 추가.
  - **뒤로가기 3단계**: 로드 시 history 더미 2개를 쌓고 popstate 에서 1번=열린 모달/상세 닫기(또는 full->half),
    2번=`goHome()`(검색·출퇴근·예산·정렬 초기화 + 기본 위치로 flyTo + 토스트), 3번=그대로 앱 종료. v62.
  - **검증 한계**: 브라우저 pane 이 레이아웃 재계산을 멈춰서(인라인 bottom 250px 를 줘도 computed 0px, 시트 peek 인데 height 792px)
    크기 변화는 확인 불가. data-state 순환과 스크립트 동작(문법·핸들러)은 확인함. **실제 모양은 폰에서 확인 필요.**


- 2026-09-16 (33차): 폰 첫 화면 비율 + 주소창 안내 (사용자가 인스타 인앱 브라우저 스크린샷 보냄).
  - 리스트 기본값을 **25%** 로: `--sheet-peek: 156px -> 25vh`, 모바일 초기 상태 half -> **peek**, syncMapSize 도 0.25 로 맞춤.
    처음 열면 지도 75% / 리스트 25%.
  - **주소창은 사이트가 숨길 수 없음**(인앱 브라우저는 특히). 대신 `#browserHint` 배너(.hintbar) 추가:
    인앱 브라우저(Instagram/KAKAOTALK/NAVER/Line/FBAN/DaumApps UA)면 "⋮ -> 다른 브라우저로 열기",
    아니면 "홈 화면에 추가" 안내(iOS 는 공유 버튼 문구). standalone 으로 실행 중이면 안 뜨고, ✕ 로 닫으면 localStorage 에 기억.
  - PWA 보강: manifest background/theme_color 를 #0f172a -> #ffffff(밝은 테마와 일치),
    apple-mobile-web-app-capable / mobile-web-app-capable / apple-mobile-web-app-title 메타 추가.
  - v63. 모바일 375x812 에뮬레이션에서 확인: state=peek, 지도 bottom 203px(25%), 배너 노출.


- 2026-09-16 (34차): 검색 색인 점검 + 소유 확인 태그 재등록.
  진단: 기술 문제 없음 — Googlebot/Yeti 모두 200, noindex 없음, http/www 리디렉션 정상, 사이트맵·RSS 200.
  원인은 **서치콘솔/서치어드바이저에 사이트가 등록돼 있지 않아 발견 경로가 없었던 것**.
  - `app/index.html` 에 새 소유 확인 태그 2개 추가(기존 것은 유지):
    google `Jzk1x5wcuZz3o5Tzk5_3YNQgCJBWujVCXqPUpbUgGfg`, naver `509a823e2833877d63575ea1fb283a38b00f9e61`. 둘 다 라이브 확인.
  - GitHub README 라이브 주소를 github.io -> **jipkokmap.kr** 로 교체하고 주요 페이지 링크 추가(저장소 페이지는 이미 구글에 색인돼 있어 크롤 경로가 됨).
    repo About homepage/description 도 설정. 로컬 repo 에 origin 이 없어 push 는 토큰 URL 로 직접 (`git push https://x-access-token:$GITHUB_TOKEN@github.com/mtmt88087044-pixel/apt-map.git master:master`).
  - IndexNow 재제출(200). v65.
  - **사용자 작업 대기**: 구글(확인 -> sitemap.xml 제출 -> 색인 요청), 네이버(소유확인 -> 사이트맵/RSS 제출 -> 웹페이지 수집 -> 수집 설정 허용 확인).


- 2026-09-16 (35차): **공유 품질 개선** (사용자: "다른 곳 올릴 퀄리티인가, 뭔가 부족해 보인다").
  진단: 내용(학원비 등 고유 지표, 단지 페이지 2,855자 x 6,809개)은 충분. 부족한 건 겉보기였음 —
  랭킹 페이지에 이미지·차트 0개, 홈 외에는 og:image 가 없어 링크 공유 시 썸네일 없이 글자만 떴음.
  - 신규 `pipeline/make_og.py`: 실제 데이터로 1200x630 공유 카드 3종 생성
    (og-academy-fee: 구별 학원비 막대, og-budget-school: 가격대별 단지 수, og-future-rail: 노선별 예정역 수). 한글 폰트는 malgunbd.ttf.
  - `generate_content.py` 에 `og_head(img)` 추가, 랭킹 3개 페이지에 og:image/twitter:card 연결.
  - `content_academy_fee.py` 에 `fee_chart()` 인라인 SVG 가로 막대(외부 라이브러리 없음, 상위 3 빨강·하위 3 초록).
  - 첫 방문자용 **"이럴 때 써보세요"** 예시 버튼 3개(#demoRow): 맞벌이 강남·여의도 40분 / 8억 학군 최고 / 학군 좋고 학원비 싼 곳.
    한 번 누르면 조건이 걸린 결과로 이동하고, 조건이 걸리면 자동으로 숨김(updateDemoRow).
  - 시트 하단에 **만든 사람 한 줄**(.maker) + **데이터 기준일**(#dataStamp, meta.built_at/complexes/zone_note). v67.


- 2026-09-16 (36차): 조작 단순화 + 예시를 직접 입력으로 전환 (사용자: "강남·여의도가 아니라 종로·마곡이면?", "조작이 불편하다").
  - **고정 예시 폐기**: "이럴 때 써보세요"(강남·여의도 40분 등 하드코딩)를 없애고, 리스트 맨 위에 **직접 입력 폼**을 둠.
    `#quickCommute`(회사 역 + 배우자 회사 역 + 30/40/50/60분 + 찾기) / `#quickBudget`(예산 억 + 찾기) / 학원비 프리셋 버튼 1개.
    역 자동완성 목록(549역)은 입력에 **focus 할 때** loadGraph() 로 지연 로딩. 검증: 종로3가+마곡 40분 -> 영등포시장역 1분 단지가 1위(5호선 중간지점, 타당).
  - **컨트롤 접기**: 상단 칩 17개 중 평당가순·상승률순·상승신호·전세가율·초품아·학군순을 `data-more="1"` 로 접고 `⋯ 더보기` 칩으로 토글
    (body.more-chips). 우측 레이어 8개 중 도로·기피·지형·경매를 접고 `⋯ 더보기`(body.more-lyr). 900px 이상에서는 전부 표시.
    모바일 기준 보이는 칩 19->13, 레이어 8->4(+더보기).
  - 홈 하단 링크에 `📚 동네별 학원비` 추가 — academy-fee 페이지가 홈에서 도달 불가였음(랭킹 인덱스·지표설명에만 링크). v69.


- 2026-09-16 (37차): 학원비 페이지 진입 버튼 강조 (`.cta`). 보라 그라데이션 배너로 리스트 상단(빠른 입력 아래)에 배치,
  문구 "우리 동네 학원비, 얼마일까? / 강남 36만원 · 강북 19.8만원 — 서울 25개 구 비교". 지도 안 정렬(칩)과 읽는 페이지를 구분하기 위해
  프리셋 버튼 문구는 "지도에서 보기"로 바꿨음. v70.
  - 참고: 이번 로컬 확인에서 **처음으로 MapLibre 가 pane 에서 정상 렌더됨** — 지하철 노선(6호선 갈색 선)·역 라벨(녹사평역 6호선)·통학구역 폴리곤 확인.
    그동안의 "렌더 안 됨" 은 환경 문제였고 코드는 정상이었음이 확인됨.


- 2026-09-17 (38차): 폰에서 리스트가 지도를 덮어 못 돌아오던 문제 — full 높이 62vh 로 제한, `.list-head` sticky, `#mapBtn`("🗺 지도 보기", 시트가 peek 가 아닐 때만 표시). v71.
  - **배포가 느리거나 멈춘 것처럼 보일 때**: deploy_github_pages.py 가 app/ 전체(파일 13,940개)를 %TEMP%\ghpages_* 로 복사 후 git add 하는데,
    Windows Defender 실시간 검사 때문에 초당 약 40개로 매우 느림(15분+). 중간에 끊기면 index.lock 과 빈 ghpages_* 폴더가 남음(46개 쌓여 있었음, 정리함).
    확인법: `master` 는 올라갔는데 `gh-pages` 커밋 시각이 안 바뀌면 복사/추가 단계에서 걸린 것. 끝까지 기다리면 성공함.
    개선 후보: 임시 폴더를 Defender 제외 경로로 옮기거나 gh-pages 를 증분 커밋으로 바꾸기.


- 2026-09-18 (39차): **애드센스 코드 삽입** (ca-pub-2024521419046920). index.html, generate_content shell, generate_pages 2개 템플릿 head 에 삽입(admin/feed 제외).
  `app/ads.txt` = `google.com, pub-2024521419046920, DIRECT, f08c47fec0942fa0`. 이용약관 `terms.html` 도 추가(09-17). 라이브 확인 완료. v72.
  - **GitHub 계정명 변경**: `mtmt88087044-pixel` -> **`mtmt20`** (토큰 /user 조회로 확인, 같은 저장소, 예전 주소는 리디렉트됨).
    deploy_github_pages.py 기본 owner 를 mtmt20 으로 수정. Pages cname jipkokmap.kr 그대로 정상.
  - 사용자 작업 대기: 애드센스 화면에서 "코드 삽입함" 체크 -> 확인 -> 검토 요청.


- 2026-09-20 (40차): **실거래 차트 축 개선 + 지도 학교/지하철 우선 + 실거래 재수집**.
  - 사용자 제보: 우장산아이파크,이편한세상 84㎡ 가 앱에서 16.4억인데 실제 마지막 거래는 15.6억.
    원인은 계산 오류가 아니라 **실거래 신고 지연**(계약 후 30일 내 신고). 9/14 수집 시점엔 9/2 계약 건이 미신고 상태였음.
    -> 25개 구 최근 3개월 재수집(31초) 후 15.6억(2026-09-02, 19층)으로 정정. **재수집을 주기적으로 돌릴 것.**
  - `app/app.js` chartSVG 전면 수정: y축을 평당가 -> **실거래가(억)**, 가격 눈금+가로 격자선, x축 연·월 눈금 최대 4개,
    `preserveAspectRatio="none"` 제거(글자 늘어남 해결), 높이 150->196, 평당가는 하단 한 줄로. `.chart` height auto.
  - 지도: renderMarkers 에서 **역·학교 자리를 boxes 에 먼저 넣어** 아파트 핀이 비켜가게 함(keepOut).
    stations.geojson 로드 시 `state.stationPts` 캐시. `.mk` z-index 2 / `.mk.sel` 5 / `.mk.school` 6.
    학교 이름표 13.8->13.2 줌, 역 이름표 minzoom 12->11.6, 환승역 symbol-sort-key 우선.
  - v73 배포 완료, 라이브 확인.


- 2026-09-21 (41차): **자동 갱신이 주 1회였던 것 발견 + 온비드 공매 실데이터 연결 + 폰 레이어 버튼 수정**.
  - **원인 규명**: 사용자가 "우장산아이파크 84㎡ 가 15.6억인데 앱은 16.4억" 제보. 계산 오류가 아니라
    Windows 예약작업 `JipkokMapRefresh` 가 **매주 월요일** 트리거였음(마지막 9/14, 다음 9/21).
    실거래 신고기한이 계약 후 30일이라 주 1회로는 계속 낡는다. -> **매일 05:00 + StartWhenAvailable 로 변경.**
    아침 시간표 충돌 확인: 05:00 집콕맵(16분) / 08:00,18:00 위스키 / 09:00 투게더스테이 / 10:40,16:40 프리소프트 / 19:00 위스키보강. 겹침 없음.
  - **온비드 공매 3개 API 승인 완료(2026-09-21)**. 기존 fetch_auction.py 는 오퍼레이션명을 추측만 했었음. 실제:
    `OnbidPbancListSrvc2/getPbancList2`(필수 cltrTypeCd=0001, prptDivCd, opbdDtStart/End),
    `OnbidPbancCltrDtlSrvc2/getPbancCltrInf2`(pbancMngNo. **압류재산 주소는 ***** 마스킹**),
    `OnbidRlstDtlSrvc2/getRlstDtlInf2`(cltrMngNo. 마스킹 없는 지번주소·PNU·bldSqms·유찰횟수, **진행 중 물건만**).
    재산유형: 0007 압류재산 / 0003 금융권담보 / 0008 수탁 / 0002 공유 / 0005 기타일반 / 0010 국유.
    개발계정 하루 1,000회인데 공고 1건에 물건 200~1,200개 -> `auction_seen.json` 으로 새 공고만, `--budget` 으로 분할 수집.
    `auction_history.jsonl` 에 매 실행 스냅샷 누적(유찰 회차별 하락폭·낙찰가율용).
  - build.py `load_auctions()`: 법정동+지번으로 단지 매칭, **vs_trade_pct**(같은 평형 실거래 대비 최저가) 계산. 서울 119건 중 29건 매칭.
    앱 마커 "시세 -N%", 상세에 용도·상태·실거래 대비 낙폭·온비드 안내. refresh.py 에 수집 단계 추가.
  - 폰에서 경매 버튼이 안 눌리던 문제: 레이어 버튼 9개가 세로 540px 를 넘어 하단 리스트(sheet top 480) 밑으로 깔림.
    좁은 화면에서 2열 그리드로 접고 높이를 리스트 위에서 끊음. v74 -> v75.
  - **백업 미결**: realestate / whisky-pipeline / freesoft-pipeline 은 git remote 가 없어 이 PC에만 있음.
    together-stay-index, k-guide 는 github.com/mtmt20 에 있음. 비공개 저장소 3개 생성 여부를 사용자가 결정해야 함.


- 2026-09-23 (42차): **첫 로딩 절반으로 + 동 페이지 231개 + 피드백 창구 + 화면 그대로 공유**.
  - 버벅임 제보 -> 원인 3가지. `complexes.json` 6.6MB(단지 6,825개가 같은 키 이름 반복, 파일의 절반이 키)
    -> `pack_summary()` 로 키를 한 번만 적는 형식(k/sub/list/r), 앱의 `unpackComplexes()` 가 원래 객체로 복원. **3.1MB**.
    학교 이름표 615개를 시작 즉시 DOM 생성하던 것 -> `syncSchoolMarkers()` 로 화면 안 + 줌 13.2 이상만.
    지도 편의시설 9,048개 -> 랜드마크 511개(3만㎡+ 공원 266, 대학 143, 대형마트·백화점 74, 응급실 28). 점수 계산엔 전체 사용.
  - 사용자 요청: **주유소·모텔 기피시설에서 제외**(NUISANCE_SKIP). 레이어 '편의' -> '랜드마크'.
    마트 브랜드 매칭이 "케이마트"를 "이마트"로 잡던 버그 -> 앞 글자 경계 정규식.
  - **검색 유입**: 사람들은 "화곡동 아파트 시세"로 검색하는데 받을 페이지가 없었음(구 25개뿐).
    신규 `pipeline/content_dong.py` -> 법정동 **231곳** 페이지(단지 3개 미만 제외). 동별 평당가·84㎡ 중앙값·1년 변동·
    배정 초등·초품아 수·학군·학원비·역·단지 전체 표. 구↔동↔지도 상호 링크. sitemap-core 269개, IndexNow 제출 완료.
  - **피드백**: 워커 `POST /feedback`(익명·시간당 5회·허니팟) + `/admin/feedback`. 앱 하단 "의견 보내기" 모달,
    admin.html 맨 위에 목록·삭제. 엔드투엔드 확인.
  - **공유**: `viewUrl()`/`viewTitle()`/`shareView()`. id·q·sort·area·cm·at(지도 위치)를 주소에 담고 부팅 때 복원(칩 on 상태까지).
    버튼 2곳(리스트 헤더, 단지 상세 헤더). 폰은 navigator.share 시트, PC는 복사. v78.
  - **백업 완료**: github.com/mtmt20 에 비공개 3개 — jipkokmap / whiskyhot / freedowncenter. .env 는 제외(키 유출 방지).
  - docs/홍보글_초안_카페_2026-09-23.md: 맘카페·부동산스터디·신혼부부 3종. **게시는 사용자가 직접**
    (네이버 카페는 로그인 필요 + 홍보 자동필터로 계정 영구정지 위험, 디시는 캡차 때문에 불가).
  - 일 방문: 9/17 뽐뿌 유입으로 317명 찍은 뒤 하루 10~16명. 9/21 다음 검색 유입 3건이 처음 발생.


- 2026-09-23 (43차): **중·고등학교 + 대형 입시학원 지도 표시, 학교 옆 학급당 인원**.
  - schools.geojson 이 초등 615곳만 담고 있었음 -> 중 392, 고 321 추가(총 1,328).
    좌표는 이미 받아둔 자료에 있었음: 중학교는 `schools_neis.json["middle"]`, 고등학교는 `schoolinfo/0_04_*` 의 LTTUD/LGTUD.
    마커 🏫 초 / 🎒 중(#b45309) / 🎓 고(#7c3aed). 초등만 학구도 경계와 같은 PALETTE 색 유지.
  - **학교 옆 숫자 = 학급당 평균 인원**(학교알리미 62_* 의 AVG_FGR_SUM, 1,313곳). 서울 중앙값 18.4명.
    **점수를 못 쓴 이유(다시 시도하지 말 것)**: 학업성취도는 2017년부터 비공개(아실이 쓰는 그 자료가 2017년산).
    고교 진로현황 `51_04` 의 TOTAL_RATE 는 319곳 중 318곳이 정확히 100.0 - 진학률이 아니라 졸업생 구성 합계다.
  - 랜드마크에 **대형 입시학원 1,721곳**(#db2777) 추가. 조건: kind=학원, realm=입시.검정 및 보습, 정원 300~6,000명,
    이름에 "원격" 제외(원격학원은 정원이 수십만으로 잡혀 있어 반드시 걸러야 함). 대치동·중계동 학원가가 드러남.
  - `.mk b { display:block }` 때문에 "경복 / 20 / 명" 으로 줄이 쪼개지던 것 수정. v79 배포·확인 완료.


## 진행 중 / 남은 작업
0. 활용신청 3건 완료 시: 응급실(소아)·미세먼지(동/측정소)·스쿨존 레이어. 애드센스 승인용 콘텐츠(사이트 소개·지표 설명·구별 랭킹 글) + 쿠팡 파트너스 '이사 준비' 페이지.
0. 구글 서치콘솔 사이트맵 상태 재확인(며칠 뒤 자동 재시도됨). LOCALDATA 복구 시 유흥주점·단란주점·숙박업 수집 붙이기. 동 단위 인구는 KOSIS 키 받으면 진행.
0. (완료) 라이브 검증: 공식 학구·학교군·피드 확인. 학군 레이어 match 중복 라벨 오류·jrow float 겹침 수정 후 재배포.
0. 배포 자동화: 실거래 갱신(월 1회 이상) -> build -> pages -> deploy 를 한 스크립트로 (Windows 작업 스케줄러, 위스키 Airflow 와 무관)
0-1. (완료 2026-09-12) SEOUL_KEY 발급 -> 서울시 공동주택 2,888개 수집·매칭. 세대수 3,227/6,809, 주차 2,328 (나머지는 서울시 목록에도 없는 소규모 단지). hh_type 임대+분양 -> 혼합 정규화.
0-1. 다른 구 추가 절차: fetch_trades/fetch_rent --lawd, fetch_kapt --sgg, geocode.py, fetch_neis --gu, fetch_kakao_poi, (bbox 밖이면 fetch_roads/fetch_poi --bbox 확장), build
0-1. 정확한 임대 세대수: 서울 열린데이터광장 공동주택 정보 조사
1. K-apt 이름 매칭 개선 (100/285): '래미안공덕5차' vs K-apt 표기 차이, 소규모 단지는 K-apt 자체에 없음(의무관리 대상만) -> 건축물대장 API 검토
1. 학구도안내서비스 통학구역 폴리곤 실데이터 붙이기 (지금은 최근접 학교 보로노이 추정)
2. 지도 핀 겹침 완화 (밀집 지역에서 라벨 충돌) - 심볼 레이어 전환 검토
3. 용적률은 K-apt 에 없음 -> 건축물대장 API 또는 생략
4. 경매 수집기 (법원경매정보) - 크롤링 난이도 높음, 우선순위 낮음
5. 호가: KB시세 상하한으로 대체 -> 지역 중개사 제휴
6. 배포: 위스키 사이트처럼 정적 호스팅 (S3/Cloudflare Pages), PWA 아이콘 추가
