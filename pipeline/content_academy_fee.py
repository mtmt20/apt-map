# -*- coding: utf-8 -*-
"""동네 학원비 페이지 본문 (generate_content.py 에서 사용)

컨셉: 학군지의 진짜 비용은 집값이 아니라 매달 나가는 학원비.
"""
import html
import statistics
import urllib.parse


def esc(x):
    return html.escape(str(x if x is not None else ""))


def man(v):
    return "{}만원".format(round(v / 10000)) if v else "-"


def link(c):
    return '<a href="../apt/{}.html">{}</a> <span class="sub">{}</span>'.format(urllib.parse.quote(c["id"]), esc(c["name"]), esc(c["umd"]))


INTRO = """
<h1>서울 동네별 학원비 · 학군 대비 학원비 싼 아파트</h1>
<p class="sub">학군지의 진짜 비용은 집값이 아니라 매달 나가는 학원비입니다.</p>
<div class="card">
<p>집값은 한 번 정하면 대출로 고정되지만, 학원비는 아이가 크는 내내 매달 나갑니다. 과목당 월 16만원 차이는 세 과목이면 월 50만원, 두 아이면 월 100만원 차이가 됩니다. 그런데 대부분의 부동산 앱은 학원을 <b>개수</b>로만 셉니다.</p>
<p>집콕맵은 교육청이 공시하는 <b>학원별 교습비</b>를 씁니다. 단지 반경 1km 안에 있는 입시·보습 학원들의 과목당 월 교습비 중앙값입니다. 교습비를 공개한 학원만 집계되고(서울 학원 4곳 중 1곳), 표본이 5곳 미만인 단지는 계산하지 않습니다.</p>
<p class="note">과목 수와 수업 시간이 학원마다 달라 단순 비교에는 한계가 있습니다. 동네 사이 수준 차이를 가늠하는 용도로 보세요. 실제 수강료는 학원에 직접 확인하셔야 합니다.</p>
</div>
"""

OUTRO = """
<div class="card">
<h2 style="margin-top:0">학원비를 볼 때 같이 보면 좋은 것</h2>
<ul class="plist">
<li class="info"><i>1</i><span><b>학군 지수와 함께</b> 보세요. 학원비만 싼 동네는 학원이 적어서 싼 것일 수 있습니다. 위 표는 학군 지수 55점 이상인 단지만 골랐습니다.</span></li>
<li class="info"><i>2</i><span><b>대출 상환액과 합쳐서</b> 감당 가능한지 계산하세요. <a href="../calc.html#dsr">대출한도 계산기</a>에서 월 상환액을 확인하고 학원비를 더해 보세요.</span></li>
<li class="info"><i>3</i><span>학원비가 비싼 동네는 <b>또래 분위기도 그만큼 세다</b>는 뜻입니다. 아이 성향에 따라 장점일 수도, 부담일 수도 있습니다.</span></li>
</ul>
</div>
"""


def page_body(cs, rank_table):
    have = [c for c in cs if (c.get("edu") or {}).get("fee_med")]
    if not have:
        return INTRO + '<div class="card"><p>학원비 데이터가 아직 없습니다.</p></div>' + OUTRO
    parts = [INTRO]
    # 구별 표
    by_gu = {}
    for c in have:
        by_gu.setdefault(c["sgg"], []).append(c["edu"]["fee_med"])
    rows = sorted(((g, statistics.median(v), len(v)) for g, v in by_gu.items()), key=lambda x: -x[1])
    parts.append('<h2>구별 학원비 (1km 내 교과학원 월 교습비 중앙값)</h2><div class="card"><table class="rank"><thead><tr><th>순위</th><th>구</th><th>월 교습비 중앙값</th><th>단지 수</th></tr></thead><tbody>')
    for i, (g, med, n) in enumerate(rows, 1):
        parts.append("<tr><td>{}</td><td><b>{}</b></td><td>{}</td><td>{}</td></tr>".format(i, esc(g), man(med), n))
    parts.append("</tbody></table></div>")

    cols = [
        ("단지", link),
        ("구", lambda c: esc(c["sgg"])),
        ("월 학원비", lambda c: "<b>{}</b>".format(man(c["edu"]["fee_med"]))),
        ("학군 지수", lambda c: c.get("edu_score")),
        ("1km 교과학원", lambda c: "{}개".format(c["edu"]["exam_1km"])),
        ("배정 초등", lambda c: "{}{}".format(esc(c["school"]["elem"].replace("등학교", "")), " 초품아" if c["school"]["chopuma"] else "")),
    ]
    good = [c for c in have if (c.get("edu_score") or 0) >= 55 and c.get("trade_count_1y", 0) >= 2]
    good.sort(key=lambda c: (c["edu"]["fee_med"], -(c.get("edu_score") or 0)))
    parts.append('<h2>학군 좋고 학원비 싼 단지 30 <span class="sub">(학군 지수 55점 이상)</span></h2>')
    parts.append('<div class="card">{}</div>'.format(rank_table(good[:30], cols)))

    pricey = sorted(have, key=lambda c: -c["edu"]["fee_med"])[:20]
    parts.append('<h2>학원비가 가장 비싼 단지 20</h2><div class="card"><p class="note">학원비가 비싸다는 건 그만큼 입시 학원이 몰려 있다는 뜻이기도 합니다.</p>{}</div>'.format(rank_table(pricey, cols)))
    parts.append(OUTRO)
    return "".join(parts)
