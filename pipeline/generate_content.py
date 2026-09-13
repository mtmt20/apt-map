# -*- coding: utf-8 -*-
"""설명·랭킹 콘텐츠 페이지 생성 (애드센스 심사용 원문 콘텐츠 + 검색 유입)

  python pipeline/generate_content.py

출력: app/about.html, app/guide.html, app/privacy.html, app/moving.html, app/rank/index.html, app/rank/<구>.html
쿠팡 파트너스 링크는 data/coupang_links.json ({"제목": "https://link.coupang.com/..."}) 이 있으면 이사 준비 페이지에 넣는다.
"""
import datetime as dt
import html
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
sys.path.insert(0, HERE)
from fetch_trades import load_env  # noqa: E402
from content_calc import CALC_BODY, CALC_CSS  # noqa: E402
from calc_js import CALC_JS  # noqa: E402
from content_fund import FUND_BODY, FUND_JS  # noqa: E402
load_env()
BASE = (os.environ.get("SITE_BASE") or "https://jipkokmap.kr").rstrip("/")
CONTACT = os.environ.get("CONTACT_EMAIL", "")


def esc(x):
    return html.escape(str(x if x is not None else ""))


def price(v):
    if v is None:
        return "-"
    return "{:.1f}억".format(v / 10000).replace(".0억", "억") if v >= 10000 else "{:,}만".format(v)


def shell(title, desc, body, path, extra_head=""):
    return """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{t}</title><meta name="description" content="{d}"><link rel="canonical" href="{base}/{path}">
<meta property="og:title" content="{t}"><meta property="og:description" content="{d}"><meta property="og:url" content="{base}/{path}">
<link rel="icon" type="image/svg+xml" href="{root}icon.svg"><link rel="stylesheet" href="{root}apt/page.css">{extra}</head><body><div class="wrap">
<header class="top"><a class="logo" href="{root}index.html">🏠 집콕맵</a><nav style="display:flex;gap:10px;font-size:13px"><a href="{root}calc.html">계산기</a><a href="{root}rank/index.html">랭킹</a><a href="{root}guide.html">지표 설명</a><a href="{root}about.html">소개</a><a class="btn" href="{root}index.html">지도</a></nav></header>
{body}
<footer class="disclaim" style="margin-top:40px;border-top:1px solid var(--line);padding-top:14px">집콕맵 · <a href="{root}about.html">소개</a> · <a href="{root}guide.html">지표 설명</a> · <a href="{root}calc.html">계산기</a> · <a href="{root}fund.html">자금 마련</a> · <a href="{root}privacy.html">개인정보처리방침</a> · <a href="{root}moving.html">이사 준비</a> · <a href="{root}feed.html">제보 피드</a><br>공공데이터(국토교통부·교육부·한국교육시설안전원·나이스·학교알리미·서울시)와 오픈스트리트맵, 카카오 지도 정보를 조합해 자동 생성한 참고 자료입니다. 매매 판단 전 반드시 현장·등기부·교육청 공지를 확인하세요.</footer>
</div></body></html>""".format(t=esc(title), d=esc(desc), base=BASE, path=path, root="../" if "/" in path else "", body=body, extra=extra_head)


# ---------------------------------------------------------------- about
ABOUT = """
<h1>집콕맵 소개</h1>
<p class="sub">아파트를 "가격"이 아니라 "살아보면 어떤가"로 보는 지도</p>
<div class="card">
<p>집콕맵은 세 아이를 키우는 부모가 이사할 집을 고르다 만든 서비스입니다. 실거래가 앱은 많지만, 정작 궁금했던 것들은 흩어져 있었습니다. 배정 초등학교가 정확히 어디인지, 통학로에 큰길을 건너야 하는지, 단지가 언덕 위인지, 근처에 변전소나 유흥가가 있는지, 어린이집과 소아과는 몇 곳인지, 전세가율이 위험한 수준인지. 이걸 한 화면에 모으는 게 목표입니다.</p>
<p>모든 숫자는 공공기관이 공개한 자료를 그대로 계산한 것입니다. 사람이 임의로 점수를 매기지 않고, 같은 기준을 서울의 모든 단지에 똑같이 적용합니다. 그래서 어느 단지든 같은 잣대로 비교할 수 있습니다.</p>
</div>
<h2>어떤 데이터를 쓰나</h2>
<div class="card"><table><tr><th>항목</th><th>출처</th><th>갱신</th></tr>
<tr><td>매매·전월세 실거래</td><td>국토교통부 실거래가 공개시스템</td><td>매주</td></tr>
<tr><td>초등 통학구역·중학교 학군·고등학교 학교군</td><td>한국교육시설안전원 학구도안내서비스</td><td>연 2회</td></tr>
<tr><td>학교 학생 수·학급당 인원·전출입</td><td>학교알리미 (교육부)</td><td>연 1회</td></tr>
<tr><td>학원·교습소, 학교 기본정보</td><td>나이스 교육정보 개방포털</td><td>분기</td></tr>
<tr><td>세대수·동수·주차대수·분양/임대 구분</td><td>K-apt 공동주택관리정보, 서울시 공동주택 정보</td><td>분기</td></tr>
<tr><td>도로·인도·기피시설·주요시설·공원</td><td>오픈스트리트맵</td><td>분기</td></tr>
<tr><td>어린이집·소아과·병원·마트 개수</td><td>카카오 지도</td><td>새 단지 추가 시</td></tr>
<tr><td>고도·경사</td><td>AWS 공개 지형 자료 (약 30m 해상도)</td><td>고정</td></tr>
</table></div>
<h2>한계와 약속</h2>
<div class="card"><ul class="plist">
<li class="info"><i>i</i><span>실거래는 신고 지연이 최대 30일이라 오늘 계약된 거래는 아직 안 보일 수 있습니다.</span></li>
<li class="info"><i>i</i><span>초등 배정은 공식 학구도 기준이지만 매년 조정될 수 있고, 중·고등학교는 학교군 내 추첨이라 특정 학교를 확정할 수 없습니다.</span></li>
<li class="info"><i>i</i><span>기피시설·주요시설은 오픈스트리트맵 등록 기준이라 빠진 곳이 있을 수 있습니다. 잘못된 정보는 제보로 알려주세요.</span></li>
<li class="info"><i>i</i><span>모든 점수와 신호는 참고용이며 투자 권유가 아닙니다. 계약 전에는 반드시 현장을 보고 등기부등본과 교육청 공지를 확인하세요.</span></li>
<li class="info"><i>i</i><span>이용자 제보는 검수 없이 표시되며, 신고가 3회 쌓이면 자동으로 숨겨집니다.</span></li>
</ul></div>
<h2>문의</h2>
<div class="card"><p>오류 신고, 데이터 제안, 제휴 문의: {contact}</p></div>
"""

GUIDE = """
<h1>집콕맵 지표 설명</h1>
<p class="sub">화면에 나오는 점수와 태그가 어떻게 계산되는지</p>

<h2>👶 아이 키우기 점수 (0~100)</h2>
<div class="card"><p>여섯 가지 축을 가중 평균합니다. 각 축은 0~100이고, 서울 전체 단지 안에서의 순위(상위 %)를 함께 보여줍니다.</p>
<table><tr><th>축</th><th>비중</th><th>무엇을 보나</th></tr>
<tr><td>초등 접근</td><td>20%</td><td>배정 초등학교까지 거리. 300m 이내(초품아) 100점, 500m 75점, 800m 45점, 그 이상 15점</td></tr>
<tr><td>학군</td><td>15%</td><td>아래 '학군 지수'를 그대로 사용</td></tr>
<tr><td>보육·의료</td><td>20%</td><td>700m 내 어린이집·유치원 수, 1km 내 소아과 수, 병원·약국 수</td></tr>
<tr><td>지형·보행</td><td>15%</td><td>반경 100m 경사, 역과의 고도차, 대로변 여부</td></tr>
<tr><td>환경·안전</td><td>15%</td><td>기준 거리 안 기피시설 개수 (0개 100점, 1개 60점, 2개 30점)</td></tr>
<tr><td>생활 편의</td><td>15%</td><td>세대당 주차, 공원·도서관·대형마트 유무</td></tr></table>
<p class="note">점수가 높다고 좋은 집이라는 뜻은 아닙니다. 부모가 자주 보는 조건을 같은 기준으로 줄 세운 것이고, 가족마다 우선순위가 다르니 축별 점수를 함께 보세요.</p></div>

<h2>🎓 학군 지수 (0~100)</h2>
<div class="card"><p>교과학원 밀집(반경 1km 입시·보습 학원 수) 40%, 배정 초등의 전입 순유입 25%, 초등 학생 수 증감 15%, 중학교 규모·학급당 인원 20%를 서울 전체 백분위로 환산해 합칩니다. 특목고 진학률이나 학업성취도는 학교알리미가 더 이상 공시하지 않거나 자동 수집이 막혀 있어 넣지 않았습니다. 그래서 이 지수는 "학구열이 높은 동네인가"를 보는 대리 지표입니다.</p></div>

<h2>📈 위험·상승 신호와 국면</h2>
<div class="card"><p>최근 24개월 실거래로 자동 계산합니다.</p>
<ul class="plist">
<li class="good"><i>↑</i><span>신고가 경신: 주력 평형의 최근 6개월 거래가 24개월 최고가를 넘김</span></li>
<li class="good"><i>↑</i><span>거래 활발: 최근 6개월 월평균 거래가 이전 12개월의 1.8배 이상</span></li>
<li class="good"><i>↑</i><span>갭·전세가율: 전세가율 70~90% 구간, 초등 순전입 증가, 준공 30년 경과(재건축 연한)</span></li>
<li class="bad"><i>!</i><span>하락: 최근 3건 중앙값이 최고가 대비 10% 이상 낮음 (신고가 경신 중이면 제외)</span></li>
<li class="bad"><i>!</i><span>거래 급감: 최근 6개월 월평균이 이전의 40% 이하</span></li>
<li class="bad"><i>!</i><span>환금성: 300세대 미만이면서 1년 거래 3건 이하</span></li>
<li class="bad"><i>!</i><span>깡통전세: 전세가율 90% 이상</span></li>
<li class="bad"><i>!</i><span>노후+주차: 25년 이상이면서 세대당 주차 0.7대 미만</span></li></ul>
<p>국면 한 줄은 최근 6개월 평당가 중앙값을 이전 12개월과 비교하고 거래량 변화를 합쳐 "상승 지속·가격은 올랐지만 거래 감소·조정·거래 위축·횡보" 다섯 가지로 요약합니다.</p></div>

<h2>🚧 기피·주의 시설</h2>
<div class="card"><p>종류별로 기준 거리를 다르게 둡니다. 변전소 300m, 고압 송전선 100m, 매립·소각·폐기물 1km, 하수처리 800m, 화장장·장례식장 300m, 교도소 500m, 군부대 300m, 주유소 150m, 유흥·모텔 200m, 지상 철도 100m, 고속도로 150m. 기준 거리 안이면 ⚠️로 표시하고 장단점에 최대 2개까지 넣습니다. 지하로 지나는 철도는 제외합니다.</p></div>

<h2>⛰️ 지형과 통학로</h2>
<div class="card"><p>해발고도, 반경 100m 안의 최대 고도차를 거리로 나눈 경사(%), 가까운 역과의 고도차를 계산합니다. 역보다 30m 이상 높으면 "언덕 위 단지", 경사 8% 이상이면 "경사 가파름", 평지에 고도차 10m 미만이면 "평지"로 표시합니다. 통학로는 단지와 배정 초등학교를 잇는 직선이 큰길(간선도로)과 교차하면 "큰길 횡단 가능성"으로 표시하며 지하보도·육교는 반영하지 못합니다.</p></div>

<h2>🏫 배정 학교</h2>
<div class="card"><p>초등학교는 교육청이 고시한 통학구역 폴리곤 안에 단지가 들어가면 그 학교로 표시합니다(공동통학구역이면 후보 학교를 모두 표시). 중학교는 학교군 안의 학교를 가까운 순으로, 고등학교는 학교군 안 일반고와 3km 안 자율·특목고를 보여줍니다. 중·고등학교는 추첨 배정이라 특정 학교를 확정할 수 없습니다.</p></div>

<h2>제보와 알림</h2>
<div class="card"><p>호가·실거래 제보는 로그인 없이 익명으로 받고, 같은 IP는 시간당 20건까지입니다. 잘못된 제보는 "신고"로 알려주시면 3회 이상 신고 시 숨겨집니다. 찜한 단지의 실거래 알림은 이메일만 저장하며 메일 하단 링크로 언제든 해제할 수 있습니다.</p></div>
"""

PRIVACY = """
<h1>개인정보처리방침</h1>
<p class="sub">시행일 2026-09-13</p>
<div class="card">
<p>집콕맵(이하 "서비스")은 회원가입 없이 이용할 수 있으며, 이용자의 개인정보를 최소한으로만 처리합니다.</p>
<h3>1. 수집하는 정보</h3>
<ul class="plist">
<li class="info"><i>1</i><span>실거래 알림 신청 시 이메일 주소와 찜한 단지 목록. 알림 발송과 수신 해제에만 사용하며 1년 후 자동 삭제됩니다.</span></li>
<li class="info"><i>2</i><span>제보 등록 시 접속 IP를 해시(복원 불가)로 변환해 저장합니다. 도배·남용 방지 목적이며 30일 후 삭제됩니다.</span></li>
<li class="info"><i>3</i><span>찜·비교 목록·제보 초안은 이용자 브라우저(localStorage)에만 저장되며 서버로 전송되지 않습니다. 동기화 링크를 만든 경우에만 6자리 코드와 단지 목록이 서버에 저장됩니다.</span></li>
<li class="info"><i>4</i><span>서비스는 별도의 접속 로그를 남기지 않으며, 호스팅 제공자(GitHub Pages, Cloudflare)가 보안 목적으로 남기는 표준 접속 기록은 각 제공자의 정책을 따릅니다.</span></li></ul>
<h3>2. 쿠키와 광고</h3>
<p>서비스는 로그인 쿠키를 사용하지 않습니다. 향후 Google AdSense 등 제3자 광고가 게재될 경우 광고 제공자가 쿠키를 사용해 맞춤 광고를 표시할 수 있으며, 이용자는 <a href="https://adssettings.google.com" target="_blank" rel="noopener">Google 광고 설정</a>에서 맞춤 광고를 끌 수 있습니다. 쿠팡 파트너스 활동의 일환으로 일정액의 수수료를 제공받을 수 있습니다.</p>
<h3>3. 제3자 제공</h3>
<p>수집한 정보는 법령에 따른 요청을 제외하고 제3자에게 제공하지 않습니다.</p>
<h3>4. 이용자의 권리</h3>
<p>알림 이메일은 메일 하단 링크로 즉시 삭제할 수 있고, 그 밖의 삭제 요청은 아래 연락처로 보내주시면 처리합니다.</p>
<h3>5. 문의</h3>
<p>{contact}</p>
</div>
"""

MOVING_STEPS = [
    ("계약 전", ["등기부등본 열람(소유자·근저당·가압류)", "건축물대장·토지대장 확인", "관리비 체납·장기수선충당금 정산 방식 확인", "학교 배정은 교육청 공지로 재확인(집콕맵 학구도는 참고용)", "낮·밤·평일·주말 4번 이상 현장 방문 (소음·주차·냄새)"]),
    ("계약~잔금", ["계약금 입금 전 소유자 신분증·계좌 일치 확인", "전입신고·확정일자(전세) 잔금 당일", "이사업체 견적 3곳 이상, 사다리차 포함 여부", "입주청소 예약(잔금 전날 또는 당일 오전)", "가스·전기·수도 명의 변경 예약, 인터넷 이전 신청"]),
    ("이사 당일", ["잔금 이체 후 열쇠·비밀번호 인수", "기존 집 가스 잠금·계량기 사진", "새 집 하자 사진(벽·바닥·창틀·수전) 당일 촬영", "냉장고·세탁기 설치 위치 미리 표시"]),
    ("이사 후 2주", ["전입신고·학교 전학 서류(재학증명·건강기록부)", "아이 방 안전(모서리 보호대·콘센트 커버·창문 잠금)", "관리사무소 주차 등록·택배함", "동네 소아과·약국·응급실 위치 저장 (집콕맵 주요시설 참고)"]),
]


def moving_page(links):
    parts = ["<h1>이사 준비 체크리스트</h1><p class=\"sub\">계약 전부터 이사 후 2주까지, 아이 있는 집 기준으로 정리했습니다</p>"]
    for title, items in MOVING_STEPS:
        parts.append("<h2>{}</h2><div class=\"card\"><ul class=\"plist\">{}</ul></div>".format(esc(title), "".join('<li class="info"><i>☐</i><span>{}</span></li>'.format(esc(x)) for x in items)))
    parts.append("<h2>이사할 때 미리 사두면 편한 것</h2><div class=\"card\">")
    if links:
        parts.append('<ul class="plist">' + "".join('<li class="good"><i>🛒</i><span><a href="{}" target="_blank" rel="noopener sponsored">{}</a></span></li>'.format(esc(u), esc(t)) for t, u in links.items()) + '</ul><div class="note">이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</div>')
    else:
        parts.append('<ul class="plist">' + "".join('<li class="info"><i>·</i><span>{}</span></li>'.format(esc(x)) for x in ["이사 박스·완충재·박스테이프 (박스는 이사업체 대여가 더 쌀 때가 많음)", "모서리 보호대·콘센트 안전커버·서랍 잠금 (아이 방 먼저)", "창문 방충망·안전잠금장치 (고층·저층 모두)", "공기청정기 필터·환기 타이머 (새집 냄새)", "현관 도어락 교체 또는 비밀번호 즉시 변경", "층간소음 매트 (아래층 인사 전에 깔기)"]) + '</ul>')
    parts.append("</div>")
    return "".join(parts)


# ---------------------------------------------------------------- rank
GU_INTRO = {
    "강남구": "학원가와 재건축 단지가 공존해 평당가 편차가 큽니다. 대치·도곡은 학군, 개포·압구정은 재건축 흐름이 가격을 이끕니다.",
    "서초구": "반포·잠원 신축 대단지가 서울 최고가 축을 형성하고, 방배·서초동은 학군과 도심 접근성이 강점입니다.",
    "송파구": "잠실 대단지와 위례·문정 신도시권이 섞여 있어 같은 구 안에서도 생활권이 뚜렷이 나뉩니다.",
    "마포구": "공덕·아현 신축 대단지와 대흥동 학원가, 상암 DMC가 각각 다른 수요층을 가집니다. 언덕 지형이 많아 지형 지표를 꼭 보세요.",
    "용산구": "한남·이촌·용산 개발 기대와 함께 구축 비중이 높습니다. 대로변·철도 인접 여부가 단지별로 크게 갈립니다.",
    "성동구": "옥수·금호·행당의 한강·도심 접근성이 강점이며 경사지가 많아 지형 확인이 필수입니다.",
    "광진구": "광장동 학군과 자양·구의 생활권, 한강변 조망이 가격 요인입니다.",
    "양천구": "목동 학원가와 재건축 기대가 핵심이며 학군 지수가 서울 상위권입니다.",
    "노원구": "중계동 학원가가 있는 대표적 학군지이고 대단지가 많아 세대당 가격이 상대적으로 낮습니다.",
    "강동구": "고덕·둔촌 신축 대단지 입주로 신축 비중이 높고 초품아 단지가 많습니다.",
    "동작구": "흑석·사당·상도의 도심 접근성이 좋고 경사지가 많습니다.",
    "영등포구": "여의도 재건축 기대와 신길 뉴타운 신축이 공존합니다.",
    "강서구": "마곡 신도시와 발산·등촌 구축이 나뉘며 공항 소음 여부를 확인하세요.",
    "은평구": "뉴타운 신축과 구축이 섞여 있고 언덕 지형이 많습니다.",
    "서대문구": "가재울 뉴타운 대단지와 신촌·연희 생활권이 있습니다.",
    "종로구": "구축 위주이며 학교·학원 밀도가 낮은 편입니다.",
    "중구": "도심 직주근접이 강점이나 아파트 단지 수가 적습니다.",
    "동대문구": "청량리·전농 재개발 신축이 늘고 있습니다.",
    "중랑구": "가격 접근성이 좋고 신축 공급이 이어지는 지역입니다.",
    "성북구": "길음·장위 뉴타운 대단지와 구축이 섞여 있고 경사지가 많습니다.",
    "강북구": "미아 뉴타운 대단지 위주로 가격 접근성이 좋습니다.",
    "도봉구": "창동·쌍문 구축 대단지가 많고 개발 기대가 있습니다.",
    "구로구": "신도림·구로 역세권과 개봉·고척 생활권으로 나뉩니다.",
    "금천구": "가산·독산 직주근접 수요가 있고 신축 공급이 늘었습니다.",
    "관악구": "봉천·신림 재개발 신축이 늘고 있으며 언덕 지형이 많습니다.",
}


def rank_table(rows, cols):
    return "<table><tr>{}</tr>{}</table>".format("".join("<th{}>{}</th>".format(' class="r"' if i else "", esc(h)) for i, (h, _) in enumerate(cols)),
                                                 "".join("<tr>{}</tr>".format("".join("<td{}>{}</td>".format(' class="r"' if i else "", f(c)) for i, (_, f) in enumerate(cols))) for c in rows))


def link(c):
    return '<a href="../apt/{}.html">{}</a> <span class="sub">{}</span>'.format(__import__("urllib.parse").parse.quote(c["id"]), esc(c["name"]), esc(c["umd"]))


def rep_price(c):
    ba = sorted(c.get("by_area") or [], key=lambda b: -b["count"])
    return "{} <span class=\"sub\">{}㎡</span>".format(price(ba[0]["latest"]), ba[0]["area"]) if ba else "-"


def rank_pages(cs):
    by_gu = {}
    for c in cs:
        by_gu.setdefault(c["sgg"], []).append(c)
    pages = {}
    for gu, members in sorted(by_gu.items()):
        ppys = sorted(c["ppy"] for c in members if c.get("ppy"))
        med = ppys[len(ppys) // 2] if ppys else 0
        kids = [c["kid"]["score"] for c in members if c.get("kid")]
        kmed = statistics.median(kids) if kids else 0
        chop = sum(1 for c in members if c["school"]["chopuma"])
        hill = sum(1 for c in members if any("언덕" in x for x in c["cons"]))
        up = sum(1 for c in members if c.get("signals", {}).get("up"))
        body = ["<h1>{} 아파트 랭킹</h1><p class=\"sub\">실거래·학군·아이 키우기 점수로 본 {} 단지 {}개 · {} 기준</p>".format(esc(gu), esc(gu), len(members), dt.date.today().isoformat())]
        body.append("<div class=\"card\"><p>{}</p><p>{}에서 실거래가 있는 단지는 {}개이고, 평당가 중앙값은 {:,}만원입니다. 초등학교가 300m 안에 있는 초품아 단지는 {}개, 역보다 30m 이상 높은 언덕 단지는 {}개, 최근 상승 신호가 잡힌 단지는 {}개입니다. 아이 키우기 점수 중앙값은 {}점입니다.</p></div>".format(
            esc(GU_INTRO.get(gu, "")), esc(gu), len(members), med, chop, hill, up, int(kmed)))
        active = [c for c in members if c["trade_count_1y"] >= 3]
        body.append("<h2>👶 아이 키우기 점수 상위 10</h2><div class=\"card\">" + rank_table(sorted([c for c in active if c.get("kid")], key=lambda c: -c["kid"]["score"])[:10],
                    [("단지", link), ("점수", lambda c: "<b>{}</b>".format(c["kid"]["score"])), ("대표 실거래", rep_price), ("배정 초등", lambda c: "{} {}분".format(esc(c["school"]["elem"]), c["school"]["elem_walk_min"]))]) + "</div>")
        body.append("<h2>🎓 학군 지수 상위 10</h2><div class=\"card\">" + rank_table(sorted([c for c in active if c.get("edu_score") is not None], key=lambda c: -c["edu_score"])[:10],
                    [("단지", link), ("학군 지수", lambda c: "<b>{}</b>".format(c["edu_score"])), ("1km 교과학원", lambda c: (c.get("edu") or {}).get("exam_1km", "-")), ("대표 실거래", rep_price)]) + "</div>")
        body.append("<h2>💰 평당가 상위 10 (거래 활발 단지)</h2><div class=\"card\">" + rank_table(sorted([c for c in active if c.get("ppy")], key=lambda c: -c["ppy"])[:10],
                    [("단지", link), ("평당가", lambda c: "{:,}만".format(c["ppy"])), ("1년 변동", lambda c: "{:+.1f}%".format(c["chg_1y"]) if c.get("chg_1y") is not None else "-"), ("대표 실거래", rep_price)]) + "</div>")
        body.append("<h2>🏷️ 평당가 낮은 초품아 10</h2><div class=\"card\">" + rank_table(sorted([c for c in active if c["school"]["chopuma"] and c.get("ppy")], key=lambda c: c["ppy"])[:10],
                    [("단지", link), ("평당가", lambda c: "{:,}만".format(c["ppy"])), ("세대수", lambda c: "{:,}".format(c["households"]) if c.get("households") else "-"), ("대표 실거래", rep_price)]) + "</div>")
        body.append("<h2>📈 상승 신호 단지</h2><div class=\"card\">" + rank_table(sorted([c for c in active if c.get("signals", {}).get("up")], key=lambda c: (-len(c["signals"]["up"]), -c["trade_count_1y"]))[:10],
                    [("단지", link), ("신호", lambda c: "<br>".join(esc(x) for x in c["signals"]["up"][:2])), ("대표 실거래", rep_price)]) + "</div>")
        body.append("<h2>⚠️ 주의 신호 단지</h2><div class=\"card\">" + rank_table(sorted([c for c in active if c.get("signals", {}).get("risk")], key=lambda c: (-len(c["signals"]["risk"]), -c["trade_count_1y"]))[:10],
                    [("단지", link), ("신호", lambda c: "<br>".join(esc(x) for x in c["signals"]["risk"][:2])), ("대표 실거래", rep_price)]) + "</div><div class=\"note\">자동 계산 참고 지표이며 투자 판단의 근거가 아닙니다. 거래가 적은 단지는 제외했습니다.</div>")
        pages["rank/{}.html".format(gu)] = shell("{} 아파트 랭킹 · 아이 키우기·학군·평당가 | 집콕맵".format(gu), "{} 단지 {}개의 아이 키우기 점수, 학군 지수, 평당가, 초품아, 상승·주의 신호 랭킹".format(gu, len(members)), "".join(body), "rank/{}.html".format(gu))
    # 서울 전체 index
    active = [c for c in cs if c["trade_count_1y"] >= 5]
    body = ["<h1>서울 아파트 랭킹</h1><p class=\"sub\">구별 랭킹과 서울 전체 상위 단지 · {} 기준</p>".format(dt.date.today().isoformat())]
    body.append("<h2>구별 랭킹 보기</h2><div class=\"card\"><div class=\"tags\">" + "".join('<a class="tag" href="{}.html" style="font-size:14px;padding:8px 12px">{}</a>'.format(esc(g), esc(g)) for g in sorted(by_gu)) + "</div></div>")
    body.append("<h2>👶 서울 아이 키우기 점수 상위 30</h2><div class=\"card\">" + rank_table(sorted([c for c in active if c.get("kid")], key=lambda c: -c["kid"]["score"])[:30],
                [("단지", link), ("구", lambda c: esc(c["sgg"])), ("점수", lambda c: "<b>{}</b>".format(c["kid"]["score"])), ("대표 실거래", rep_price)]) + "</div>")
    body.append("<h2>🎓 서울 학군 지수 상위 30</h2><div class=\"card\">" + rank_table(sorted([c for c in active if c.get("edu_score") is not None], key=lambda c: -c["edu_score"])[:30],
                [("단지", link), ("구", lambda c: esc(c["sgg"])), ("학군 지수", lambda c: "<b>{}</b>".format(c["edu_score"])), ("대표 실거래", rep_price)]) + "</div>")
    body.append("<h2>🏷️ 10억 이하 초품아 · 아이 키우기 상위 30</h2><div class=\"card\">" + rank_table(sorted([c for c in active if c["school"]["chopuma"] and c.get("kid") and any(b["area"] >= 70 and b["latest"] <= 100000 for b in c["by_area"])], key=lambda c: -c["kid"]["score"])[:30],
                [("단지", link), ("구", lambda c: esc(c["sgg"])), ("점수", lambda c: "<b>{}</b>".format(c["kid"]["score"])), ("84㎡급 실거래", lambda c: price(min((b["latest"] for b in c["by_area"] if b["area"] >= 70), default=None)))]) + "</div>")
    pages["rank/index.html"] = shell("서울 아파트 랭킹 · 아이 키우기·학군·평당가 | 집콕맵", "서울 25개 구 아파트 랭킹. 아이 키우기 점수, 학군 지수, 10억 이하 초품아 상위 단지", "".join(body), "rank/index.html")
    return pages


def main():
    cdir = os.path.join(APP, "data", "c")
    cs = [json.load(open(os.path.join(cdir, f), encoding="utf-8")) for f in os.listdir(cdir) if f.endswith(".json")]
    os.makedirs(os.path.join(APP, "rank"), exist_ok=True)
    contact = esc(CONTACT) if CONTACT else "집콕맵 지도 화면의 제보 기능 또는 운영자 이메일(추후 공개)"
    pages = {
        "about.html": shell("집콕맵 소개 · 데이터 출처와 한계", "세 아이 부모가 만든 아파트 지도. 실거래·학구도·학교 통계·기피시설·지형을 공공데이터로 계산합니다.", ABOUT.format(contact=contact), "about.html"),
        "guide.html": shell("집콕맵 지표 설명 · 아이 키우기 점수, 학군 지수, 위험·상승 신호", "집콕맵의 점수와 태그가 어떻게 계산되는지 기준을 모두 공개합니다.", GUIDE, "guide.html"),
        "privacy.html": shell("개인정보처리방침 | 집콕맵", "집콕맵 개인정보처리방침", PRIVACY.format(contact=contact), "privacy.html"),
    }
    pages["calc.html"] = shell(
        "부동산 계산기 · 취득세·중개수수료·대출 상환금·보유세 | 집콕맵",
        "매매가만 넣으면 취득세, 중개수수료, 대출 월 상환금, 내 소득 기준 대출한도, 보유세, 전월세 환산, 갈아타기 비용을 한 번에 계산합니다.",
        CALC_BODY + CALC_JS, "calc.html", CALC_CSS)
    pages["fund.html"] = shell(
        "집 살 돈 마련하기 · 정책대출·부모님 증여와 차용·은행 vs 보험사 | 집콕맵",
        "정책대출 조건, 부모님께 빌릴 때 무이자 한도와 차용증 작성법, 증여세 공제, 1금융권과 보험사 대출의 장단점을 정리했습니다.",
        FUND_BODY + FUND_JS, "fund.html", CALC_CSS)
    lp = os.path.join(HERE, "..", "data", "coupang_links.json")
    links = json.load(open(lp, encoding="utf-8")) if os.path.exists(lp) else {}
    pages["moving.html"] = shell("이사 준비 체크리스트 · 아이 있는 집 기준 | 집콕맵", "계약 전부터 이사 후 2주까지, 아이 있는 가정이 놓치기 쉬운 이사 준비 항목", moving_page(links), "moving.html")
    pages.update(rank_pages(cs))
    for path, htm in pages.items():
        open(os.path.join(APP, path), "w", encoding="utf-8").write(htm)
    # sitemap 에 추가
    sm_path = os.path.join(APP, "sitemap.xml")
    if os.path.exists(sm_path):
        sm = open(sm_path, encoding="utf-8").read()
        today = dt.date.today().isoformat()
        add = "".join("<url><loc>{}/{}</loc><lastmod>{}</lastmod><changefreq>weekly</changefreq></url>".format(BASE, __import__("urllib.parse").parse.quote(p), today) for p in pages)
        sm = sm.replace("</urlset>", add + "</urlset>")
        open(sm_path, "w", encoding="utf-8").write(sm)
    print("콘텐츠 페이지 {}개 생성 (about/guide/privacy/moving/calc/fund + 랭킹 {})".format(len(pages), len(pages) - 6))


if __name__ == "__main__":
    sys.exit(main())
