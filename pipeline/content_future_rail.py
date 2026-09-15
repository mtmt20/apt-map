# -*- coding: utf-8 -*-
"""공사 중 노선 예정역 도보권 아파트 페이지 본문 (generate_content.py 에서 사용)"""
import html
import urllib.parse


def esc(x):
    return html.escape(str(x if x is not None else ""))


def price(v):
    if not v:
        return "-"
    return "{:.1f}억".format(v / 10000).replace(".0억", "억") if v >= 10000 else "{:,}만".format(v)


def link(c):
    return '<a href="../apt/{}.html">{}</a> <span class="sub">{}</span>'.format(urllib.parse.quote(c["id"]), esc(c["name"]), esc(c["umd"]))


INTRO = """
<h1>공사 중 지하철 예정역 도보권 아파트</h1>
<p class="sub">동북선, 월곶판교선 등 지금 공사 중인 노선의 예정역에서 걸어서 갈 수 있는 서울 아파트를 역별로 정리했습니다.</p>
<div class="card">
<p>새 역이 생기는 동네는 개통 전후로 생활 반경이 바뀝니다. 다만 공사 중인 노선은 <b>개통 시기가 미뤄지거나 역 위치·이름이 바뀌는 일이 흔합니다</b>. 이 페이지는 OpenStreetMap에 공사 중(railway=construction)으로 등록된 선로와, 이름까지 확인된 예정역만 사용합니다. 계획 단계 노선이나 위치가 확인되지 않은 역은 넣지 않았습니다.</p>
<p class="note">매수 판단 전에 반드시 국토교통부·서울시·시행사의 공식 발표로 개통 시기와 역 위치를 확인하세요. 예정역까지 거리는 직선 기준입니다.</p>
</div>
"""

OUTRO = """
<div class="card">
<h2 style="margin-top:0">지도에서 보기</h2>
<p>집콕맵 지도에서 🚇 지하철 레이어를 켜면 공사 중 노선이 점선으로, 예정역이 주황 테두리 원으로 표시됩니다. 단지를 누르면 "공사 중 노선 예정역" 항목에서 거리를 확인할 수 있습니다. <a href="../index.html">지도 열기</a></p>
</div>
"""


def page_body(cs, rank_table):
    parts = [INTRO]
    grp = {}
    for c in cs:
        f = c.get("future")
        if f and f["dist"] <= 800 and c.get("trade_count_1y", 0) >= 1:
            grp.setdefault((f["line"], f["name"]), []).append(c)
    if not grp:
        parts.append('<div class="card"><p>현재 서울 단지 중 예정역 도보권(800m)에 해당하는 곳이 없습니다.</p></div>')
        return "".join(parts) + OUTRO
    lines = {}
    for (ln, st), v in grp.items():
        lines.setdefault(ln, []).append((st, v))
    parts.append('<div class="card"><div class="tags">' + "".join(
        '<a class="tag" href="#l{}" style="font-size:14px;padding:8px 12px">{} ({}개 역)</a>'.format(i, esc(ln), len(v))
        for i, (ln, v) in enumerate(sorted(lines.items()))) + '</div></div>')
    cols = [
        ("단지", link),
        ("도보", lambda c: "{}분 ({}m)".format(c["future"]["walk_min"], c["future"]["dist"])),
        ("지금 가까운 역", lambda c: "{} {}분".format(esc(c["station"]["name"]), c["station"]["walk_min"])),
        ("최근 실거래", lambda c: price(max(c["by_area"], key=lambda a: a["count"])["latest"]) if c.get("by_area") else "-"),
        ("학군 지수", lambda c: c.get("edu_score") if c.get("edu_score") is not None else "-"),
    ]
    for i, (ln, sts) in enumerate(sorted(lines.items())):
        parts.append('<h2 id="l{}">🚧 {} (공사 중)</h2>'.format(i, esc(ln)))
        for st, v in sorted(sts, key=lambda x: -len(x[1])):
            v.sort(key=lambda c: c["future"]["dist"])
            parts.append('<div class="card"><h3 style="margin-top:0">{}역 예정지 · 도보권 {}개 단지</h3>{}</div>'.format(
                esc(st), len(v), rank_table(v[:15], cols)))
    parts.append(OUTRO)
    return "".join(parts)
