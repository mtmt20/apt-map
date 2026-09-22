# -*- coding: utf-8 -*-
"""동(법정동)별 아파트 시세·학군 페이지 (generate_content.py 에서 사용)

왜 만드나: 사람들은 "강서구 아파트"보다 "화곡동 아파트 시세"로 검색한다. 구 페이지는
25개뿐이라 그 검색어를 받을 페이지가 없었다. 동 단위는 230개가 나오고, 각 동마다
평당가·학군·학원비·배정 초등·역이 실제로 다르므로 내용이 겹치지 않는다.

단지가 3개 미만인 동은 만들지 않는다(내용이 얇아 오히려 감점이다).
"""
import datetime as dt
import html
import statistics
import urllib.parse

MIN_COMPLEXES = 3


def esc(x):
    return html.escape(str(x if x is not None else ""))


def price(v):
    if not v:
        return "-"
    return "{:.1f}억".format(v / 10000).replace(".0억", "억") if v >= 10000 else "{:,}만".format(v)


def slug(gu, umd):
    return "{}-{}".format(gu, umd)


def page_path(gu, umd):
    return "dong/{}.html".format(slug(gu, umd))


def link(c):
    return '<a href="../apt/{}.html">{}</a>'.format(urllib.parse.quote(c["id"]), esc(c["name"]))


def rep84(c):
    """84㎡급(70~100) 최근 실거래. 없으면 표본이 가장 많은 평형."""
    ba = c.get("by_area") or []
    big = [b for b in ba if 70 <= b["area"] < 100 and b.get("latest")]
    if big:
        return big[0]
    got = [b for b in ba if b.get("latest")]
    return sorted(got, key=lambda b: -b["count"])[0] if got else None


def groups(cs):
    out = {}
    for c in cs:
        if c.get("umd") and c.get("sgg"):
            out.setdefault((c["sgg"], c["umd"]), []).append(c)
    return {k: v for k, v in out.items() if len(v) >= MIN_COMPLEXES}


def page_body(gu, umd, members, rank_table):
    today = dt.date.today()
    ppys = sorted(c["ppy"] for c in members if c.get("ppy"))
    med_ppy = ppys[len(ppys) // 2] if ppys else 0
    chgs = [c["chg_1y"] for c in members if c.get("chg_1y") is not None]
    med_chg = statistics.median(chgs) if chgs else None
    r84 = [rep84(c) for c in members]
    p84 = sorted(b["latest"] for b in r84 if b and 70 <= b["area"] < 100)
    med84 = p84[len(p84) // 2] if p84 else None
    chop = sum(1 for c in members if c["school"]["chopuma"])
    elems = sorted({c["school"]["elem"] for c in members if c["school"].get("elem")})
    stations = sorted({c["station"]["name"] for c in members if c.get("station", {}).get("name")})
    fees = [c["fee"] for c in members if c.get("fee")]
    med_fee = statistics.median(fees) if len(fees) >= 3 else None
    edus = [c["edu_score"] for c in members if c.get("edu_score") is not None]
    med_edu = int(statistics.median(edus)) if edus else None
    hh = sum(c.get("households") or 0 for c in members)
    builts = [c["built"] for c in members if c.get("built")]

    b = ['<h1>{} 아파트 시세·학군</h1>'.format(esc(umd))]
    b.append('<p class="sub">{} {} · 단지 {}개 · {} 기준 실거래</p>'.format(esc(gu), esc(umd), len(members), today.isoformat()))

    p = ["{} {}에서 실거래가 확인되는 아파트 단지는 <b>{}개</b>, 합쳐서 <b>{:,}세대</b>입니다.".format(esc(gu), esc(umd), len(members), hh)]
    if med_ppy:
        p.append("평당가 중앙값은 <b>{:,}만원</b>입니다.".format(med_ppy))
    if med84:
        p.append("84㎡급(34평형) 최근 실거래 중앙값은 <b>{}</b>입니다.".format(price(med84)))
    if med_chg is not None:
        p.append("같은 평형 기준 1년 변동은 중앙값 <b>{:+.1f}%</b>입니다.".format(med_chg))
    b.append('<div class="card"><p>{}</p>'.format(" ".join(p)))

    p2 = []
    if elems:
        p2.append("배정 초등학교는 {}이고, 초등학교가 300m 안에 있는 초품아 단지는 {}개입니다.".format(
            ", ".join(esc(e) for e in elems[:6]) + (" 등 {}곳".format(len(elems)) if len(elems) > 6 else ""), chop))
    if med_edu is not None:
        p2.append("학군 지수 중앙값은 {}점입니다.".format(med_edu))
    if med_fee:
        p2.append("반경 1km 교과학원의 과목당 월 교습비 중앙값은 <b>{}만원</b>입니다.".format(round(med_fee / 10000)))
    if stations:
        p2.append("가장 가까운 지하철역은 {}입니다.".format(", ".join(esc(s) for s in stations[:5])))
    if builts:
        p2.append("준공 연도는 {}년~{}년입니다.".format(min(builts), max(builts)))
    if p2:
        b.append("<p>{}</p>".format(" ".join(p2)))
    b.append("</div>")

    cols = [
        ("단지", link),
        ("세대", lambda c: "{:,}".format(c["households"]) if c.get("households") else "-"),
        ("준공", lambda c: c.get("built") or "-"),
        ("최근 실거래", lambda c: (lambda r: "<b>{}</b> <span class=\"sub\">{}㎡</span>".format(price(r["latest"]), r["area"]) if r else "-")(rep84(c))),
        ("평당가", lambda c: "{:,}만".format(c["ppy"]) if c.get("ppy") else "-"),
        ("1년", lambda c: "{:+.1f}%".format(c["chg_1y"]) if c.get("chg_1y") is not None else "-"),
        ("배정 초등", lambda c: "{}{}".format(esc((c["school"].get("elem") or "").replace("서울", "").replace("등학교", "")), " 초품아" if c["school"]["chopuma"] else "")),
        ("역", lambda c: "{} {}분".format(esc(c["station"]["name"]), c["station"]["walk_min"]) if c.get("station", {}).get("name") else "-"),
    ]
    order = sorted(members, key=lambda c: (-(c.get("trade_count_1y") or 0), -(c.get("households") or 0)))
    b.append("<h2>{} 아파트 단지 전체 {}개</h2>".format(esc(umd), len(members)))
    b.append('<div class="card">{}</div>'.format(rank_table(order, cols)))
    b.append('<div class="note">국토교통부 실거래가 공개시스템 자료입니다. 매물 호가가 아니라 실제 신고된 거래가이고, 계약 후 30일 안에 신고되므로 최근 며칠 거래는 아직 안 들어와 있을 수 있습니다.</div>')

    b.append('<div class="card"><p style="margin:0"><b>🗺️ <a href="../?q={}">지도에서 {} 보기</a></b> — 단지를 누르면 실거래 추이, 학군, 출퇴근 시간이 나옵니다.</p></div>'.format(
        urllib.parse.quote(umd), esc(umd)))
    b.append('<div class="card"><p style="margin:0"><b>🏆 <a href="../rank/{}.html">{} 아파트 랭킹</a></b> · <b>📚 <a href="../rank/academy-fee.html">동네별 학원비</a></b> · <b>💰 <a href="../rank/budget-school.html">예산별 학군지</a></b></p></div>'.format(
        urllib.parse.quote(gu), esc(gu)))
    return "".join(b)


def index_body(gs):
    by_gu = {}
    for (gu, umd), members in gs.items():
        by_gu.setdefault(gu, []).append((umd, len(members)))
    b = ['<h1>서울 동네별 아파트 시세</h1>',
         '<p class="sub">법정동 {}곳 · 단지 3개 이상인 동만</p>'.format(len(gs)),
         '<div class="card"><p>동네마다 평당가, 배정 초등학교, 학원비, 지하철 접근성이 다릅니다. 구 단위로는 안 보이는 차이를 동 단위로 정리했습니다.</p></div>']
    for gu in sorted(by_gu):
        items = sorted(by_gu[gu])
        b.append('<h2>{}</h2><div class="card"><div class="tags">{}</div></div>'.format(
            esc(gu),
            "".join('<a class="tag" href="{}.html" style="font-size:14px;padding:8px 12px">{} <span class="sub">{}</span></a>'.format(
                urllib.parse.quote(slug(gu, umd)), esc(umd), n) for umd, n in items)))
    return "".join(b)


def pages(cs, shell, rank_table):
    gs = groups(cs)
    out = {}
    for (gu, umd), members in gs.items():
        path = page_path(gu, umd)
        ppys = sorted(c["ppy"] for c in members if c.get("ppy"))
        med = ppys[len(ppys) // 2] if ppys else 0
        out[path] = shell(
            "{} 아파트 시세·학군·실거래가 | 집콕맵".format(umd),
            "{} {} 아파트 {}개 단지의 최근 실거래가, 평당가 중앙값 {:,}만원, 배정 초등학교, 학군 지수, 학원비, 지하철 도보 시간을 한 번에 정리했습니다.".format(
                gu, umd, len(members), med),
            page_body(gu, umd, members, rank_table), path)
    out["dong/index.html"] = shell(
        "서울 동네별 아파트 시세 | 집콕맵",
        "서울 법정동 {}곳의 아파트 시세·학군·학원비 정리. 구 단위로는 안 보이는 동네별 차이를 봅니다.".format(len(gs)),
        index_body(gs), "dong/index.html")
    return out
