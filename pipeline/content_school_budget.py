# -*- coding: utf-8 -*-
"""예산별 학군지 가이드 페이지 본문 (generate_content.py 에서 사용)

컨셉: "대치동이 좋은 건 누구나 안다. 내 예산으로 갈 수 있는 최고 학군은 어디냐"
"""
import html

BANDS = ["5억 미만", "5~8억", "8~11억", "11~15억", "15~20억", "20억 이상"]


def esc(x):
    return html.escape(str(x if x is not None else ""))


def price(v):
    if not v:
        return "-"
    return "{:.1f}억".format(v / 10000).replace(".0억", "억") if v >= 10000 else "{:,}만".format(v)


def link(c):
    import urllib.parse
    return '<a href="../apt/{}.html">{}</a> <span class="sub">{}</span>'.format(
        urllib.parse.quote(c["id"]), esc(c["name"]), esc(c["umd"]))


INTRO = """
<h1>예산별 학군지 아파트 가이드</h1>
<p class="sub">대치동이 좋다는 건 누구나 압니다. 문제는 내 예산으로 갈 수 있는 최고 학군이 어디냐입니다.</p>

<div class="card">
<p>학군지를 찾는 이유를 "공부 잘하는 학교"로만 설명하면 절반만 맞습니다. 부모들이 실제로 사는 것은 <b>아이 주변의 분위기</b>입니다. 내 아이만 관리해도 반 친구들이 모두 다르게 움직이면 소용이 없고, 반대로 주변이 공부하는 분위기면 아이도 자연스럽게 끌려갑니다. 그래서 학군은 학교 성적표가 아니라 <b>또래 환경</b>의 문제입니다.</p>
<p>집콕맵의 학군 지수는 이 관점으로 만들었습니다. 학교 성적을 쓰지 않고, 주변 부모들이 교육에 실제로 얼마나 움직이는지를 봅니다. 반경 1km 교과학원 밀집도 40%, 배정 초등학교의 전입 순유입 25%, 학생 수 증감 15%, 중학교 규모와 학급당 인원 20%입니다. 학원이 몰려 있고 학부모가 굳이 이사 와서 들어오는 동네라면, 교실 분위기도 그쪽으로 형성됩니다.</p>
<p>여기에 <b>예산</b>을 겹칩니다. 아래 표는 대표 실거래가로 가격대를 나눈 뒤, <b>같은 가격대 안에서만</b> 학군 지수를 줄 세운 것입니다. 20억대와 비교하면 당연히 밀리는 단지도, 자기 가격대 안에서는 1등일 수 있습니다. 그 자리를 찾는 게 목적입니다.</p>
</div>
"""

OUTRO = """
<div class="card">
<h2 style="margin-top:0">이 표를 쓰는 법</h2>
<ul class="plist">
<li class="info"><i>1</i><span>먼저 <b>내 예산 구간</b>을 고르고 그 표만 봅니다. 위 구간은 참고만 하세요. 무리해서 올라가면 대출 이자로 학원비가 사라집니다. <a href="../calc.html#dsr">대출한도 계산기</a>로 감당 가능한 선을 먼저 확인하세요.</span></li>
<li class="info"><i>2</i><span>구간 안에서 학군 지수가 비슷하면 <b>배정 초등학교 거리</b>와 초품아 여부로 가릅니다. 저학년 몇 년은 등하교가 삶의 질을 좌우합니다.</span></li>
<li class="info"><i>3</i><span>같은 단지라도 평형에 따라 가격대가 달라집니다. 표의 대표 실거래가는 84㎡급 기준이라, 59㎡를 보신다면 한 구간 아래에서 다시 찾아보세요.</span></li>
<li class="info"><i>4</i><span>학군 지수가 높다고 좋은 동네라는 뜻은 아닙니다. 학원이 많다는 건 사교육비가 많이 든다는 뜻이기도 합니다. 아이 성향에 따라 오히려 힘든 환경일 수 있습니다.</span></li>
</ul>
</div>

<div class="card">
<h2 style="margin-top:0">숫자로 알 수 없는 것</h2>
<p>단지의 공급 유형(분양·임대·혼합)과 세대수, 주차 대수 같은 것은 공개 자료로 확인할 수 있어 단지 페이지에 적어 두었습니다. 하지만 이웃이 어떤 사람들인지, 놀이터 분위기가 어떤지는 어떤 통계로도 알 수 없습니다. 그건 <b>평일 저녁과 주말 낮에 직접 가서 30분씩 앉아 있어 보는 것</b>이 유일한 방법입니다. 놀이터, 단지 상가, 아파트 게시판, 등하교 시간대를 보세요. 통계보다 그 30분이 정확합니다.</p>
<p class="note">집콕맵은 사람을 분류하는 지표는 만들지 않습니다. 가격대, 학원 밀도, 배정 학교처럼 <b>확인 가능한 사실</b>만 다룹니다.</p>
</div>
"""


def page_body(cs, rank_table):
    """cs: 전체 단지 dict 리스트. rank_table: generate_content 의 표 생성 함수"""
    parts = [INTRO]
    parts.append('<div class="card"><div class="tags">' + "".join(
        '<a class="tag" href="#b{}" style="font-size:14px;padding:8px 12px">{}</a>'.format(i, esc(b)) for i, b in enumerate(BANDS)) + '</div></div>')
    cols = [
        ("단지", link),
        ("구", lambda c: esc(c["sgg"])),
        ("대표 실거래", lambda c: price(c.get("rep_price"))),
        ("학군 지수", lambda c: "<b>{}</b>".format(c["edu_score"])),
        ("구간 상위", lambda c: "{}%".format(c["edu_band_pct"])),
        ("배정 초등", lambda c: "{} {}m{}".format(esc(c["school"]["elem"]), c["school"].get("elem_dist") or "-", " · 초품아" if c["school"]["chopuma"] else "")),
    ]
    for i, band in enumerate(BANDS):
        grp = [c for c in cs if c.get("budget_band") == band and c.get("edu_band_pct") is not None and c.get("trade_count_1y", 0) >= 2]
        grp.sort(key=lambda c: (c["edu_band_pct"], -c.get("trade_count_1y", 0)))
        parts.append('<h2 id="b{}">{} · 학군 상위 20</h2>'.format(i, esc(band)))
        if not grp:
            parts.append('<div class="card"><p>이 구간에서 최근 1년 거래가 2건 이상인 단지가 없습니다.</p></div>')
            continue
        chop = sum(1 for c in grp if c["school"]["chopuma"])
        parts.append('<div class="card"><p class="note">거래가 있는 단지 {}개 중 초품아 {}개. 아래는 이 구간 안에서 학군 지수가 높은 순서입니다.</p>{}</div>'.format(
            len(grp), chop, rank_table(grp[:20], cols)))
    parts.append(OUTRO)
    return "".join(parts)
