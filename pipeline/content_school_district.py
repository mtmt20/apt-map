# -*- coding: utf-8 -*-
"""학군지 페이지 (generate_content.py 에서 사용)

왜 만드나: "서울 학군지", "강남구 학군지", "중계동 학군지" 로 검색하는 사람이 많은데
지금 검색결과는 전부 블로그 글이다. 대치·목동·중계 다섯 곳을 의견으로 나열한 것들이고,
**계산된 전체 순위표를 가진 곳이 없다**. 우리는 동 422곳의 점수를 갖고 있다.

주의: 여기 쓰는 점수는 집콕맵 자체 지수다. 국가 학업성취도 학교별 공시는 2016년이
마지막이라 "학업성취도"나 "학교 등급"이라고 쓰면 거짓말이 된다. 페이지 안에 그 사실을
분명히 적는다 - 남들이 9년 전 자료를 최신인 양 쓰는 것과 구분되는 지점이기도 하다.
"""
import datetime as dt
import html
import io
import statistics
import urllib.parse

MIN_COMPLEXES = 3

# 시장 온도(신고가 비율). build.py 가 만든 heat_dong.geojson 을 읽어 쓴다.
# 학군 페이지가 1,000자대로 얇아 색인이 안 잡혔다(2026-09-30 확인) - 같은 동 얘기를 한 겹 더 쌓는다.
HEAT = {}


def load_heat(out_dir):
    import json
    import os
    p = os.path.join(out_dir, "heat_dong.geojson")
    if not os.path.exists(p):
        return
    try:
        gj = json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return
    for f in gj.get("features", []):
        pr = f.get("properties") or {}
        if pr.get("sgg") and pr.get("umd"):
            HEAT[(pr["sgg"], pr["umd"])] = pr


def esc(x):
    return html.escape(str(x if x is not None else ""))


def price(v):
    if not v:
        return "-"
    return "{:.1f}억".format(v / 10000).replace(".0억", "억")


def man(v):
    return "{}만원".format(round(v / 10000)) if v else "-"


def grade_of(pct):
    return "S" if pct <= 3 else "A" if pct <= 10 else "B" if pct <= 25 else "C" if pct <= 50 else "D" if pct <= 75 else "E"


def badge(g):
    return '<b class="grade g{}">{}</b>'.format(g, g)


def dong_link(d):
    return '<a href="../dong/{}.html">{}</a> <span class="sub">{}</span>'.format(
        urllib.parse.quote("{}-{}".format(d["sgg"], d["umd"])), esc(d["umd"]), esc(d["sgg"]))


def collect(cs):
    """동별 학군 요약. edu_dong.geojson 과 같은 기준으로 계산한다."""
    by = {}
    for c in cs:
        if c.get("edu_score") is None or not c.get("umd"):
            continue
        by.setdefault((c["sgg"], c["umd"]), []).append(c)
    out = []
    for (sgg, umd), members in by.items():
        if len(members) < MIN_COMPLEXES:
            continue
        sc = sorted(x["edu_score"] for x in members)
        fees = sorted(x["edu"]["fee_med"] for x in members if (x.get("edu") or {}).get("fee_med"))
        p84 = sorted(b["latest"] for x in members for b in x["by_area"]
                     if 70 <= b["area"] < 100 and b.get("latest"))
        chop = sum(1 for x in members if x["school"]["chopuma"])
        stations = sorted({x["station"]["name"] for x in members if x.get("station", {}).get("name")})
        out.append({
            "sgg": sgg, "umd": umd, "n": len(members),
            "edu": sc[len(sc) // 2],
            "fee": fees[len(fees) // 2] if len(fees) >= 3 else None,
            "p84": p84[len(p84) // 2] if p84 else None,
            "chop": chop, "stations": stations,
            "hh": sum(x.get("households") or 0 for x in members),
            "built_med": (sorted(x["built"] for x in members if x.get("built")) or [None])[len(
                [x for x in members if x.get("built")]) // 2] if any(x.get("built") for x in members) else None,
            "big": sum(1 for x in members if (x.get("households") or 0) >= 1000),
            "walk": min([x["station"]["walk_min"] for x in members
                         if (x.get("station") or {}).get("walk_min") is not None] or [None]),
            "heat": HEAT.get((sgg, umd)),
        })
    out.sort(key=lambda d: -d["edu"])
    for i, d in enumerate(out):
        d["rank"] = i + 1
        d["pct"] = max(1, round((i + 1) / len(out) * 100))
        d["grade"] = grade_of(d["pct"])
    return out


def josa(word, pair="은는"):
    """받침에 따라 조사를 고른다. '대치동 는' 같은 문장이 나오면 자동 생성 티가 난다."""
    if not word:
        return pair[1]
    ch = word[-1]
    if not ("가" <= ch <= "힣"):
        return pair[1]
    return pair[0] if (ord(ch) - 0xAC00) % 28 else pair[1]


COLS_BASE = [
    ("순위", lambda d: d["rank"]),
    ("동네", dong_link),
    ("등급", lambda d: badge(d["grade"])),
    ("학군 지수", lambda d: "<b>{}</b>".format(d["edu"])),
    ("84㎡ 실거래", lambda d: price(d["p84"])),
    ("월 학원비", lambda d: man(d["fee"])),
    ("단지", lambda d: "{}개".format(d["n"])),
]


def page_body(cs, rank_table):
    ds = collect(cs)
    today = dt.date.today()
    a_list = [d for d in ds if d["grade"] in ("S", "A")]
    med_all = statistics.median([d["edu"] for d in ds])
    b = ['<h1>서울·수도권 학군지 순위</h1>',
         '<p class="sub">동네 {}곳을 점수로 줄 세웠습니다 · {} 기준 실거래</p>'.format(len(ds), today.isoformat())]

    b.append('''<div class="card">
<p>"학군지가 어디냐"고 물으면 대개 대치·목동·중계·반포 몇 곳을 꼽습니다. 그런데 그건 <b>누군가의 의견</b>이지
기준이 아닙니다. 예산이 8억인 사람에게 대치동 이야기는 쓸모가 없고, 직장이 일산인 사람에게 반포는 남의 동네입니다.</p>
<p>그래서 서울 25개 구와 경기 출퇴근권 22곳의 <b>동네 {n}곳을 같은 잣대로 계산</b>했습니다.
1km 안 교과학원 밀집도(45%), 대형 입시학원 수(10%), 초등학생 전입(30%), 중학교 여건(15%)입니다.
100점 만점이고 전체 중앙값은 {med}점입니다.</p>
<p class="note"><b>이건 학교 성적이 아닙니다.</b> 국가 학업성취도 평가의 학교별 공시는 <b>2016년이 마지막</b>입니다.
2017년부터 전체 학생이 아니라 일부만 시험을 보게 바뀌어서 학교별 결과가 나오지 않습니다.
지금 인터넷에 도는 "학교 등급"은 대부분 그 2016년 자료입니다. 집콕맵은 그 자료를 쓰지 않고,
<b>동네의 교육 환경</b>을 측정한 자체 지수를 그렇게 밝히고 씁니다.</p>
</div>'''.format(n=len(ds), med=int(med_all)))

    b.append('<div class="card"><p style="margin:0">등급은 전체 안에서의 순위입니다. '
             '{S} 상위 3% · {A} 10% · {B} 25% · {C} 50% · {D} 75% · {E} 그 아래.</p></div>'.format(
                 S=badge("S"), A=badge("A"), B=badge("B"), C=badge("C"), D=badge("D"), E=badge("E")))

    b.append('<h2>🥇 학군지 S·A등급 {}곳</h2>'.format(len(a_list)))
    b.append('<div class="card">{}</div>'.format(rank_table(a_list, COLS_BASE)))

    # 가성비: A·B 등급 중 84㎡ 가 싼 순. 이게 이 페이지의 핵심이다.
    value = [d for d in ds if d["grade"] in ("S", "A", "B") and d["p84"]]
    value.sort(key=lambda d: d["p84"])
    b.append('<h2>💰 학군 좋은데 집값 싼 동네 20</h2>')
    b.append('<div class="card"><p class="note">S·A·B 등급(상위 25%) 중에서 84㎡ 실거래 중앙값이 낮은 순입니다. '
             '같은 학군 등급이어도 동네에 따라 집값이 서너 배 차이 납니다.</p>{}</div>'.format(
                 rank_table(value[:20], COLS_BASE)))

    cheap = [d for d in ds if d["grade"] in ("S", "A", "B") and d["fee"]]
    cheap.sort(key=lambda d: d["fee"])
    b.append('<h2>📚 학군 좋은데 학원비 싼 동네 20</h2>')
    b.append('<div class="card"><p class="note">학원비는 교육청이 공시하는 학원별 교습비에서 계산한 '
             '<b>과목당 월 중앙값</b>입니다. 집값은 대출로 고정되지만 학원비는 아이가 크는 내내 매달 나갑니다.</p>{}</div>'.format(
                 rank_table(cheap[:20], COLS_BASE)))

    # 구/시별 요약 (지역명 + 학군지 검색을 받는 자리)
    by_gu = {}
    for d in ds:
        by_gu.setdefault(d["sgg"], []).append(d)
    gu_rows = []
    for gu, items in by_gu.items():
        items.sort(key=lambda d: -d["edu"])
        gu_rows.append({"gu": gu, "med": statistics.median([d["edu"] for d in items]),
                        "top": items[0], "n": len(items),
                        "a": sum(1 for d in items if d["grade"] in ("S", "A", "B"))})
    gu_rows.sort(key=lambda r: -r["med"])
    gu_cols = [
        ("순위", lambda r: gu_rows.index(r) + 1),
        ("지역", lambda r: '<a href="{}.html">{}</a>'.format(urllib.parse.quote(r["gu"]), esc(r["gu"]))),
        ("학군 지수 중앙값", lambda r: "<b>{}</b>".format(int(r["med"]))),
        ("S·A·B 등급 동네", lambda r: "{}곳".format(r["a"])),
        ("대표 동네", lambda r: "{} {}".format(esc(r["top"]["umd"]), badge(r["top"]["grade"]))),
    ]
    b.append('<h2>🏙️ 구·시별 학군지 순위</h2>')
    b.append('<div class="card">{}</div>'.format(rank_table(gu_rows, gu_cols)))

    # 전체 목록 (동 페이지로 가는 내부 링크 허브 역할도 한다)
    b.append('<h2>전체 {}곳</h2>'.format(len(ds)))
    b.append('<div class="card"><div class="tags">{}</div></div>'.format(
        "".join('<a class="tag" href="../dong/{}.html" style="font-size:13px;padding:6px 10px">{} {}</a>'.format(
            urllib.parse.quote("{}-{}".format(d["sgg"], d["umd"])), esc(d["umd"]), d["grade"]) for d in ds)))

    b.append('''<div class="card">
<h2 style="margin-top:0">학군지를 고를 때 같이 보면 좋은 것</h2>
<ul class="plist">
<li class="info"><i>1</i><span><b>예산 안에서</b> 고르세요. 절대 순위가 아니라 내 가격대 안의 순위가 중요합니다.
<a href="budget-school.html">예산별 학군지</a>에 가격 구간별로 정리했습니다.</span></li>
<li class="info"><i>2</i><span><b>학원비를 더해서</b> 계산하세요. 과목당 월 20만원 차이는 세 과목이면 60만원,
두 아이면 120만원입니다. <a href="academy-fee.html">동네별 학원비</a></span></li>
<li class="info"><i>3</i><span><b>배정 초등학교 학급당 인원</b>을 확인하세요. 학군 좋다는 동네 중에도 한 반 24명이 넘는 곳이 있습니다.</span></li>
<li class="info"><i>4</i><span><b>출퇴근을 먼저</b> 거르세요. 학군이 좋아도 매일 왕복 세 시간이면 오래 못 버팁니다.
<a href="../">지도</a>에서 회사 역을 넣고 걸러볼 수 있습니다.</span></li>
</ul>
</div>''')
    return "".join(b)


def gu_page_body(gu, ds_all, rank_table):
    """구·시 하나짜리 학군지 페이지 ("강남구 학군지" 검색을 받는 자리)."""
    items = [d for d in ds_all if d["sgg"] == gu]
    if not items:
        return None
    items.sort(key=lambda d: -d["edu"])
    med = statistics.median([d["edu"] for d in items])
    ab = [d for d in items if d["grade"] in ("S", "A", "B")]
    fees = [d["fee"] for d in items if d["fee"]]
    p84 = [d["p84"] for d in items if d["p84"]]
    b = ['<h1>{} 학군지 순위</h1>'.format(esc(gu)),
         '<p class="sub">{} 동네 {}곳 · {} 기준</p>'.format(esc(gu), len(items), dt.date.today().isoformat())]
    p = ["{}에서 아파트 실거래가 있는 동네는 <b>{}곳</b>이고, 학군 지수 중앙값은 <b>{}점</b>입니다.".format(
        esc(gu), len(items), int(med))]
    if ab:
        p.append("수도권 상위 25%(S·A·B 등급)에 드는 동네는 <b>{}곳</b>이고, 가장 높은 곳은 <b>{} {}점</b>입니다.".format(
            len(ab), esc(items[0]["umd"]), items[0]["edu"]))
    if fees:
        p.append("과목당 월 학원비 중앙값은 <b>{}</b>입니다.".format(man(statistics.median(fees))))
    if p84:
        p.append("84㎡ 실거래 중앙값은 <b>{}</b>입니다.".format(price(statistics.median(p84))))
    b.append('<div class="card"><p>{}</p>'.format(" ".join(p)))
    b.append('<p class="note">학원 밀집·대형 입시학원·초등 전입·중학교 여건으로 계산한 <b>집콕맵 학군 지수</b>입니다. '
             '학교 성적이 아닙니다(학교별 학업성취도 공시는 2016년이 마지막).</p></div>')
    b.append('<div class="card">{}</div>'.format(rank_table(items, COLS_BASE)))

    # --- 동네별 한 줄 설명. 표만 있으면 본문이 1,000자대라 검색엔진이 얇은 페이지로 본다.
    b.append('<h2>{} 동네별로 보면</h2>'.format(esc(gu)))
    b.append('<div class="card">')
    for d in items[:12]:
        bits = ["<b>{}</b>{} {} 학군 {}등급({}점)으로 {}개 동 중 <b>{}위</b>입니다.".format(
            esc(d["umd"]), josa(d["umd"]), esc(gu), d["grade"], d["edu"], len(items),
            items.index(d) + 1)]
        if d["p84"]:
            bits.append("84㎡ 실거래 중앙값은 {}입니다.".format(price(d["p84"])))
        if d["fee"]:
            bits.append("주변 교과학원 과목당 월 교습비 중앙값은 {}입니다.".format(man(d["fee"])))
        if d["chop"]:
            bits.append("단지 안에서 초등학교로 붙는 이른바 초품아가 {}개 단지입니다.".format(d["chop"]))
        if d.get("big"):
            bits.append("1,000세대 이상 대단지가 {}개 있습니다.".format(d["big"]))
        if d.get("walk") is not None and d.get("stations"):
            bits.append("가장 가까운 역은 {}이고 도보 {}분 거리 단지가 있습니다.".format(
                esc(d["stations"][0]), d["walk"]))
        h = d.get("heat")
        if h:
            word = "뜨거운" if h["hi"] >= 50 else "따뜻한" if h["hi"] >= 30 else "보통인" if h["hi"] >= 15 else "차가운"
            bits.append("최근 4개월 실거래 {}건 가운데 신고가가 {}%로 시장 온기는 {} 편이고, "
                        "오른 거래가 {}% 내린 거래가 {}%입니다.".format(h["n"], h["hi"], word, h["up"], h["dn"]))
        b.append('<p style="margin:0 0 10px">{}</p>'.format(" ".join(bits)))
    b.append('</div>')

    # --- 이 구에서 가성비 좋은 동네
    val = [d for d in items if d["p84"] and d["grade"] in ("S", "A", "B")]
    if val:
        val.sort(key=lambda d: d["p84"])
        b.append('<h2>{} 안에서 학군 대비 집값이 낮은 동네</h2>'.format(esc(gu)))
        b.append('<div class="card"><p class="note">같은 구 안에서도 학군 등급이 상위 25%(S·A·B)인 동네끼리 '
                 '84㎡ 실거래 중앙값이 얼마나 차이 나는지 본 것입니다.</p>{}</div>'.format(
                     rank_table(val[:8], COLS_BASE)))

    # --- 자주 묻는 것 (검색 질의와 그대로 맞물리는 자리)
    top = items[0]
    b.append('<h2>{} 학군지 자주 묻는 것</h2><div class="card">'.format(esc(gu)))
    b.append('<p><b>{} 학군지는 어디인가요?</b><br>집콕맵 학군 지수 기준으로는 <b>{}</b>{} {}점으로 가장 높고, '
             '그다음이 {}입니다. 다만 이건 학교 성적이 아니라 학원 밀집도와 초등학생 전입을 중심으로 계산한 '
             '동네 교육환경 점수입니다.</p>'.format(
                 esc(gu), esc(top["umd"]), josa(top["umd"], "이가"), top["edu"],
                 ", ".join(esc(d["umd"]) for d in items[1:4]) or "-"))
    if fees:
        lo = min(items, key=lambda d: d["fee"] or 10 ** 9)
        b.append('<p><b>{} 학원비는 얼마인가요?</b><br>과목당 월 교습비 중앙값이 {}입니다. '
                 '동네별로는 {}{} {}으로 가장 낮습니다. 교습비를 공시한 학원만 집계한 값입니다.</p>'.format(
                     esc(gu), man(statistics.median(fees)), esc(lo["umd"]), josa(lo["umd"], "이가"), man(lo["fee"])))
    if p84:
        b.append('<p><b>{} 84㎡ 아파트값은 얼마인가요?</b><br>실거래 중앙값이 {}입니다. '
                 '계약 후 30일 안에 신고하는 자료라 최근 며칠 거래는 아직 안 들어와 있을 수 있습니다.</p>'.format(
                     esc(gu), price(statistics.median(p84))))
    b.append('</div>')

    b.append('<div class="card"><p style="margin:0">'
             '<b>🏆 <a href="{gq}.html">{gu} 아파트 랭킹</a></b> · '
             '<b>🎓 <a href="school-district.html">수도권 전체 학군지 순위</a></b> · '
             '<b>💰 <a href="budget-school.html">예산별 학군지</a></b> · '
             '<b>📚 <a href="academy-fee.html">동네별 학원비</a></b></p></div>'.format(
                 gq=urllib.parse.quote(gu), gu=esc(gu)))
    return "".join(b)


def pages(cs, shell, rank_table):
    ds = collect(cs)
    out = {}
    a_n = sum(1 for d in ds if d["grade"] in ("S", "A"))
    out["rank/school-district.html"] = shell(
        "서울·수도권 학군지 순위 {}곳 · 동네별 학군 등급 | 집콕맵".format(len(ds)),
        "서울 25개 구와 경기 출퇴근권의 동네 {}곳을 학군 지수로 줄 세웠습니다. S·A등급 {}곳, "
        "학군 좋은데 집값 싼 동네, 학원비 싼 동네까지 실거래가와 함께 정리했습니다.".format(len(ds), a_n),
        page_body(cs, rank_table), "rank/school-district.html")
    for gu in sorted({d["sgg"] for d in ds}):
        body = gu_page_body(gu, ds, rank_table)
        if not body:
            continue
        path = "rank/{}-학군지.html".format(gu)
        n = sum(1 for d in ds if d["sgg"] == gu)
        out[path] = shell(
            "{} 학군지 순위 · 동네별 학군 등급과 아파트 시세 | 집콕맵".format(gu),
            "{} 동네 {}곳의 학군 지수, 등급, 84㎡ 실거래가, 월 학원비를 한 표로 정리했습니다.".format(gu, n),
            body, path)
    return out
