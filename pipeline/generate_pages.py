"""단지별 정적 페이지(SEO) + 목록 + sitemap/robots 생성 -> app/apt/<slug>.html, app/apt/index.html, app/sitemap.xml

  python pipeline/generate_pages.py [--base https://example.com]

app/data/complexes.json (build.py 산출물)만 읽는다. 지도는 없고 텍스트/표 위주라 검색엔진이 읽기 좋다.
각 페이지에서 "지도에서 보기" 는 ../index.html?id=<id> 로 앱 상세를 연다.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_trades import load_env  # noqa: E402
load_env()
APP = os.path.join(HERE, "..", "app")
PY = 3.3058


def esc(x):
    return html.escape(str(x if x is not None else ""))


def slugify(c):
    """페이지 파일명 = 단지 id (법정동-단지명-지번, build.py 와 동일) -> 항상 유일"""
    return c["id"]


def price(v):
    if v is None:
        return "-"
    return "{:.1f}억".format(v / 10000).replace(".0억", "억") if v >= 10000 else "{:,}만".format(v)


def chg(v):
    if v is None:
        return ""
    return '<span class="{}">{:+.1f}%</span>'.format("up" if v >= 0 else "down", v)


CSS = """
:root{--fg:#0f172a;--muted:#64748b;--line:#e2e8f0;--bg:#fff;--bg2:#f4f6fa;--brand:#2563eb;--good:#16a34a;--bad:#dc2626}
@media(prefers-color-scheme:dark){:root{--fg:#f1f5f9;--muted:#94a3b8;--line:#334155;--bg:#0f172a;--bg2:#1e293b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",system-ui,sans-serif;line-height:1.5}
.wrap{max-width:760px;margin:0 auto;padding:16px 16px 60px}a{color:var(--brand);text-decoration:none}
header.top{display:flex;justify-content:space-between;align-items:center;padding:8px 0 16px;border-bottom:1px solid var(--line);margin-bottom:16px}
header.top .logo{font-weight:900;font-size:18px;color:var(--fg)}.btn{display:inline-block;padding:9px 14px;border-radius:12px;background:var(--brand);color:#fff;font-weight:800}
h1{font-size:24px;margin:8px 0 4px;letter-spacing:-.5px}.sub{color:var(--muted);font-size:14px}.sub b{color:var(--fg)}
h2{font-size:16px;margin:26px 0 10px;color:var(--muted);text-transform:uppercase;letter-spacing:.3px}
.card{background:var(--bg2);border-radius:16px;padding:14px 16px;margin:10px 0}
.big{font-size:32px;font-weight:900;letter-spacing:-1px}.big small{font-size:13px;font-weight:600;color:var(--muted);margin-left:6px}
table{width:100%;border-collapse:collapse;font-size:14px}th{text-align:left;color:var(--muted);font-size:12px;font-weight:700;padding:6px 4px;border-bottom:1px solid var(--line)}td{padding:7px 4px;border-bottom:1px solid var(--line)}td.r,th.r{text-align:right}
.up{color:#ef4444}.down{color:var(--brand)}.tags{display:flex;flex-wrap:wrap;gap:6px}.tag{font-size:12.5px;font-weight:600;padding:4px 9px;border-radius:999px;background:var(--bg);color:var(--muted)}
.tag.good{color:var(--good);background:rgba(22,163,74,.1)}.tag.bad{color:var(--bad);background:rgba(220,38,38,.1)}.tag.school{color:#7c3aed;background:rgba(124,58,237,.1)}
ul.plist{list-style:none;padding:0;margin:0}ul.plist li{padding:6px 0;display:flex;gap:8px}ul.plist li i{flex:0 0 22px;height:22px;border-radius:6px;display:grid;place-items:center;font-style:normal;font-weight:800;font-size:12px}
li.good i{background:rgba(22,163,74,.12);color:var(--good)}li.bad i{background:rgba(220,38,38,.12);color:var(--bad)}li.info i{background:rgba(37,99,235,.12);color:var(--brand)}
.kv{display:grid;grid-template-columns:1fr 1fr;gap:10px}.kv div{background:var(--bg);border-radius:12px;padding:10px 12px}.kv .k{font-size:12px;color:var(--muted);font-weight:600}.kv .v{font-size:16px;font-weight:800}.kv .v small{font-size:12px;color:var(--muted);font-weight:600;margin-left:3px}
.note{font-size:12px;color:var(--muted);margin-top:8px}.list a{display:block;padding:12px 0;border-bottom:1px solid var(--line);color:var(--fg)}.list a b{font-size:16px}.list a span{color:var(--muted);font-size:13px;margin-left:8px}
.disclaim{font-size:12px;color:var(--muted);margin-top:30px;line-height:1.6}
"""


def page_html(c, base, all_by_umd):
    slug = slugify(c)
    areas = c.get("by_area") or []
    rep = next((a for a in areas if 70 <= a["area"] < 100), areas[0] if areas else None)
    title = "{} 실거래가·전세가율·학군 | 집콕맵".format(c["name"])
    desc = "{} ({}) 최근 실거래 {}, 평당 {}만원, 1년 {}. 배정 초등 {}, 1km 내 교과학원 {}개, 전세가율 {}. 장단점 요약과 육아·생활 편의시설까지.".format(
        c["name"], c["addr"], price(rep["latest"]) if rep else "-", "{:,}".format(c["ppy"] or 0), "{:+.1f}%".format(c["chg_1y"]) if c["chg_1y"] is not None else "변동 미확인",
        c["school"]["elem"], (c.get("edu") or {}).get("exam_1km", 0), "{}%".format(c["jeonse_ratio"]) if c.get("jeonse_ratio") else "미확인")
    age = dt.date.today().year - c["built"]
    trades = list(reversed(c["trades"]))[:20]
    st = c["school"].get("elem_stats") or {}
    life = c.get("life") or {}
    edu = c.get("edu") or {}
    sib = [x for x in all_by_umd.get(c["umd"], []) if x["id"] != c["id"]][:8]
    ld = {
        "@context": "https://schema.org", "@type": "ApartmentComplex", "name": c["name"],
        "address": {"@type": "PostalAddress", "streetAddress": c["addr"], "addressLocality": "서울", "addressRegion": c["sgg"], "addressCountry": "KR"},
        "geo": {"@type": "GeoCoordinates", "latitude": c["lat"], "longitude": c["lng"]},
        "numberOfAccommodationUnits": c.get("households") or None, "yearBuilt": c["built"],
    }
    parts = []
    parts.append("""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{t}</title><meta name="description" content="{d}"><link rel="canonical" href="{base}/apt/{slugq}.html">
<meta property="og:title" content="{t}"><meta property="og:description" content="{d}"><meta property="og:type" content="article"><meta property="og:url" content="{base}/apt/{slugq}.html">
<script type="application/ld+json">{ld}</script><link rel="stylesheet" href="page.css"></head><body><div class="wrap">
<header class="top"><a class="logo" href="../index.html">🏠 집콕맵</a><a class="btn" href="../index.html?id={id}">지도에서 보기</a></header>
<h1>{name}</h1><div class="sub">{addr} · {hh}{built}년 준공 ({age}년차){fl}{dong}</div>""".format(
        t=esc(title), d=esc(desc), base=base, slug=slug, slugq=__import__("urllib.parse").parse.quote(slug), ld=json.dumps(ld, ensure_ascii=False), css=CSS, id=esc(c["id"]), name=esc(c["name"]), addr=esc(c["addr"]),
        hh=("<b>{:,}세대</b> · ".format(c["households"]) if c.get("households") else ""), built=c["built"], age=age,
        fl=(" · 최고 {}층".format(c["max_floor"]) if c.get("max_floor") else ""), dong=(" · {}개동".format(c["dongs"]) if c.get("dongs") else "")))

    # 가격
    parts.append('<h2>실거래가</h2><div class="card">')
    if rep:
        parts.append('<div class="big">{}<small>전용 {}㎡ 최근 실거래 · {}</small></div><div class="sub">평당 <b>{:,}만원</b> · 1년 {} · 최근 1년 거래 {}건</div>'.format(
            price(rep["latest"]), rep["area"], rep["latest_date"], int(rep["latest"] / (rep["area"] / PY)), chg(c["chg_1y"]) or "변동 미확인", c["trade_count_1y"]))
    parts.append('<table style="margin-top:12px"><tr><th>전용면적</th><th class="r">최근 실거래</th><th class="r">거래일</th><th class="r">전세 (전세가율)</th><th class="r">거래 수</th></tr>')
    for a in areas:
        parts.append('<tr><td>{}㎡ <span class="sub">{}평형</span></td><td class="r"><b>{}</b></td><td class="r">{}</td><td class="r">{}</td><td class="r">{}</td></tr>'.format(
            a["area"], a["pyeong"], price(a["latest"]), a["latest_date"], ("{} ({}%)".format(price(a["jeonse"]), a["jeonse_ratio"]) if a.get("jeonse") and a.get("jeonse_ratio") else "-"), a["count"]))
    parts.append('</table></div>')

    # 아이 키우기 점수
    kid = c.get("kid")
    if kid:
        parts.append('<h2>아이 키우기 점수</h2><div class="card"><div class="big">{}<small>/100 · 서울 상위 {}%</small></div><div class="kv" style="margin-top:10px">{}</div><div class="note">초등 접근·학군·보육/의료·지형/보행·환경/안전·생활 편의 6축 가중 평균 (참고용)</div></div>'.format(
            kid["score"], kid.get("top_pct"), "".join('<div><div class="k">{}</div><div class="v">{}</div></div>'.format(esc(k), v) for k, v in kid["axes"].items())))
    if c.get("phase"):
        parts.append('<p class="sub">📈 지금 국면: <b>{}</b></p>'.format(esc(c["phase"])))

    # 장단점
    parts.append('<h2>장단점 요약</h2><div class="card"><ul class="plist">')
    for p in c["pros"]:
        parts.append('<li class="good"><i>+</i><span>{}</span></li>'.format(esc(p)))
    for p in c["cons"]:
        parts.append('<li class="bad"><i>−</i><span>{}</span></li>'.format(esc(p)))
    for p in c.get("notes", []):
        parts.append('<li class="info"><i>i</i><span>{}</span></li>'.format(esc(p)))
    parts.append('</ul></div>')

    # 학군
    parts.append('<h2>학군</h2><div class="card">')
    if c.get("edu_score") is not None:
        parts.append('<div class="sub">학군 지수 <b>{}</b>/100 · 권역 {}위 (상위 {}%)</div>'.format(c["edu_score"], c.get("edu_rank"), c.get("edu_top_pct")))
    parts.append('<p><b>배정 초등학교{}</b>: {} · 도보 {}분 ({}m){}{}</p>'.format(
        "(교육청 공식 학구)" if c["school"].get("elem_official") else "(추정)", esc(c["school"]["elem"]), c["school"]["elem_walk_min"], c["school"]["elem_dist"],
        " · <b style='color:#7c3aed'>초품아</b>" if c["school"]["chopuma"] else "",
        " · 공동통학구역: " + " / ".join(esc(x) for x in c["school"]["elem_shared"]) if c["school"].get("elem_shared") else ""))
    if c["school"].get("middle_zone"):
        mg = c["school"].get("middle_gender") or {}
        parts.append('<p><b>중학교 학군</b>: {}{}</p>'.format(esc(c["school"]["middle_zone"]), " · 공학 {} / 남중 {} / 여중 {} (아들 {}곳 · 딸 {}곳 배정 가능)".format(mg.get("공학", 0), mg.get("남", 0), mg.get("여", 0), mg.get("공학", 0) + mg.get("남", 0), mg.get("공학", 0) + mg.get("여", 0)) if mg else ""))
        mids_ = c["school"].get("middle_detail") or []
        if mids_:
            parts.append('<p>' + ", ".join("{} ({}m · {})".format(esc(m["name"]), m["dist"], {"남": "남중", "여": "여중"}.get(m.get("coedu"), "공학")) for m in mids_) + '</p>')
    hi = c["school"].get("high")
    if hi and hi.get("general"):
        parts.append('<p><b>고등학교 {}</b>: {}</p>'.format(esc(hi.get("zone") or "인근 일반고"), ", ".join("{} ({}m)".format(esc(x["name"]), x["dist"]) for x in hi["general"])))
        if hi.get("special"):
            parts.append('<p><b>인근 자율·특목고</b>: {}</p>'.format(", ".join("{} {} ({:.1f}km)".format(esc(x["type"]), esc(x["name"]), x["dist"] / 1000) for x in hi["special"])))
    if st:
        parts.append('<p class="sub">학생 {:,}명{} · 학급당 {}명{}</p>'.format(st["students"], (" (전년 {:+.1f}%)".format(st["chg_pct"]) if st.get("chg_pct") is not None else ""), st.get("class_size"),
                                                                           (" · 순전입 {:+d}명".format(st["net_move"]) if st.get("net_move") is not None else "")))
    if edu:
        parts.append('<div class="kv"><div><div class="k">1km 내 교과학원</div><div class="v">{}개<small>권역 상위 {}%</small></div></div><div><div class="k">1km 내 학원 전체</div><div class="v">{}개<small>예체능 {}</small></div></div></div>'.format(
            edu["exam_1km"], edu.get("exam_top_pct"), edu["aca_1km"], edu["art_1km"]))
    mids = c["school"].get("middle_detail") or []
    if mids:
        parts.append('<p><b>가까운 중학교</b>: ' + ", ".join("{} ({}m{})".format(esc(m["name"]), m["dist"], " · 사립" if m.get("public") == "사립" else "") for m in mids) + '</p>')
    parts.append('<div class="note">초등 통학구역은 학구도안내서비스(교육청 공식) 기준이며 매년 조정될 수 있습니다. 중학교는 학교군 내 추첨 배정입니다. 학생 수·전출입은 학교알리미 공시.</div></div>')

    # 교통/도로 + 편의
    parts.append('<h2>교통 · 도로 · 생활 편의</h2><div class="card"><div class="kv">')
    parts.append('<div><div class="k">가까운 역</div><div class="v">{}<small>도보 {}분</small></div></div>'.format(esc(c["station"]["name"]), c["station"]["walk_min"]))
    parts.append('<div><div class="k">큰길과 거리</div><div class="v">{}<small>{}</small></div></div>'.format("{}m".format(c["road"]["major_dist"]) if c["road"]["major_dist"] is not None else "-", "대로변" if c["road"]["roadside"] else "이면"))
    if c.get("terrain"):
        tr_ = c["terrain"]
        parts.append('<div><div class="k">지형</div><div class="v">해발 {}m<small>{}{}</small></div></div>'.format(tr_["elev"], ("역보다 {:+d}m".format(tr_["station_dh"]) if tr_.get("station_dh") is not None else ""), (" · 경사 {}%".format(tr_["slope_pct"]) if tr_.get("slope_pct") is not None else "")))
    if c.get("parking"):
        parts.append('<div><div class="k">주차</div><div class="v">{:,}대<small>세대당 {}</small></div></div>'.format(c["parking"], c.get("parking_per_hh", "-")))
    if life:
        for k, lab in (("daycare", "어린이집·유치원 (700m)"), ("pediatric", "소아과 (1km)"), ("hospital", "병원 (700m)"), ("mart", "대형마트 (1km)"), ("park", "공원 (700m)"), ("library", "도서관 (1km)")):
            parts.append('<div><div class="k">{}</div><div class="v">{}곳</div></div>'.format(lab, life.get(k, "-")))
    parts.append('</div></div>')

    # 위험·상승 신호
    sg = c.get("signals") or {}
    if sg.get("risk") or sg.get("up"):
        parts.append('<h2>위험 · 상승 신호</h2><div class="card"><ul class="plist">')
        for x in sg.get("up", []):
            parts.append('<li class="good"><i>↑</i><span>{}</span></li>'.format(esc(x)))
        for x in sg.get("risk", []):
            parts.append('<li class="bad"><i>!</i><span>{}</span></li>'.format(esc(x)))
        parts.append('</ul><div class="note">최근 24개월 실거래·전월세로 자동 계산한 참고 지표입니다. 투자 판단의 근거가 아닙니다.</div></div>')

    # 주요시설
    am = c.get("amen") or {}
    if am:
        parts.append('<h2>가까운 주요시설</h2><div class="card"><div class="kv">')
        for k in ("kindergarten", "playground", "clinic_ped", "hospital", "mart", "park", "library"):
            v = am.get(k)
            if v:
                parts.append('<div><div class="k">{}</div><div class="v">{}<small>{}</small></div></div>'.format(esc(v["label"]), "{:.1f}km".format(v["dist"] / 1000) if v["dist"] >= 1000 else "{}m".format(v["dist"]), esc(v.get("name") or "")))
        parts.append('</div>{}</div>'.format('<div class="note">초등 통학로: {}</div>'.format("큰길을 건너야 할 가능성 (직선 기준)" if c["school"].get("cross_major") else "큰길 횡단 없음 (직선 기준)")))

    # 기피시설
    nz = sorted((c.get("nuisance") or {}).values(), key=lambda v: v["dist"])
    if nz:
        parts.append('<h2>기피·주의 시설</h2><div class="card"><ul class="plist">')
        for v in nz[:8]:
            parts.append('<li class="{}"><i>{}</i><span>{}{} · {}{}</span></li>'.format("bad" if v["within"] else "info", "!" if v["within"] else "i", esc(v["label"]), (" (" + esc(v["name"]) + ")") if v.get("name") else "", "{:.1f}km".format(v["dist"] / 1000) if v["dist"] >= 1000 else "{}m".format(v["dist"]), " · {}곳".format(v["count"]) if v["count"] > 1 else ""))
        parts.append('</ul><div class="note">오픈스트리트맵·지방행정 인허가 자료 기준. 누락·오류가 있을 수 있습니다.</div></div>')

    # 실거래 내역
    parts.append('<h2>최근 실거래 내역</h2><div class="card"><table><tr><th>계약일</th><th>전용</th><th>층</th><th class="r">가격</th></tr>')
    for t in trades:
        parts.append('<tr><td>{}</td><td>{}㎡</td><td>{}층</td><td class="r"><b>{}</b></td></tr>'.format(t["date"], int(t["area"]), t["floor"], price(t["price"])))
    parts.append('</table><div class="note">출처: 국토교통부 실거래가 공개시스템 (신고 지연 최대 30일, 해제 거래 제외)</div></div>')

    # 같은 동 단지
    if sib:
        parts.append('<h2>{} 다른 단지</h2><div class="card list">'.format(esc(c["umd"])))
        for x in sib:
            xr = next((a for a in (x.get("by_area") or []) if 70 <= a["area"] < 100), (x.get("by_area") or [None])[0])
            parts.append('<a href="{}.html"><b>{}</b><span>{} · {}년{}</span></a>'.format(slugify(x), esc(x["name"]), price(xr["latest"]) if xr else "-", x["built"], " · 초품아" if x["school"]["chopuma"] else ""))
        parts.append('</div>')
    parts.append('<p style="margin-top:20px"><a class="btn" href="../index.html?id={}">지도에서 이 단지 보기</a> &nbsp; <a href="index.html">전체 단지 목록</a></p>'.format(esc(c["id"])))
    parts.append('<div class="disclaim">집콕맵은 공공데이터(국토교통부 실거래가, K-apt, 나이스, 학교알리미)와 오픈스트리트맵, 카카오 지도 정보를 조합해 자동 생성한 참고 자료입니다. 매매 판단 전 반드시 현장과 등기부등본, 교육청 배정 공지를 확인하세요. 생성 {}</div></div></body></html>'.format(dt.date.today().isoformat()))
    return slug, "".join(parts)


def index_html(cs, base):
    by_gu = {}
    for c in cs:
        by_gu.setdefault(c["sgg"], {}).setdefault(c["umd"], []).append(c)
    parts = ["""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>서울 아파트 단지별 실거래가·전세가율·학군 목록 | 집콕맵</title><meta name="description" content="서울 {n}개 아파트 단지의 최근 실거래가, 전세가율, 배정 초등학교, 학원 밀집도, 장단점 요약을 단지별 페이지로 정리했습니다.">
<link rel="canonical" href="{base}/apt/index.html"><link rel="stylesheet" href="page.css"></head><body><div class="wrap">
<header class="top"><a class="logo" href="../index.html">🏠 집콕맵</a><a class="btn" href="../index.html">지도로 보기</a></header>
<h1>단지별 실거래가·전세가율·학군</h1><div class="sub">서울 {n}개 단지 · {gus}</div>""".format(n=len(cs), base=base, css=CSS, gus=" · ".join(sorted(by_gu)))]
    for gu in sorted(by_gu):
        parts.append("<h2>{}</h2>".format(esc(gu)))
        for umd in sorted(by_gu[gu]):
            parts.append('<div class="card list"><b>{}</b>'.format(esc(umd)))
            for c in sorted(by_gu[gu][umd], key=lambda x: -x["trade_count_1y"]):
                r = next((a for a in (c.get("by_area") or []) if 70 <= a["area"] < 100), (c.get("by_area") or [None])[0])
                parts.append('<a href="{}.html"><b>{}</b><span>{} · {}년{}{}{}</span></a>'.format(slugify(c), esc(c["name"]), price(r["latest"]) if r else "-", c["built"],
                                                                                           " · 초품아" if c["school"]["chopuma"] else "", " · 전세가율 {}%".format(c["jeonse_ratio"]) if c.get("jeonse_ratio") else "",
                                                                                           " · 아이키우기 {}".format(c["kid"]["score"]) if c.get("kid") else ""))
            parts.append("</div>")
    parts.append('<div class="disclaim">공공데이터 기반 자동 생성 자료입니다. 생성 {}</div></div></body></html>'.format(dt.date.today().isoformat()))
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("SITE_BASE") or "https://jipkokmap.kr")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    cdir = os.path.join(APP, "data", "c")
    cs = [json.load(open(os.path.join(cdir, f), encoding="utf-8")) for f in sorted(os.listdir(cdir)) if f.endswith(".json")]
    out = os.path.join(APP, "apt")
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.endswith(".html"):
            os.remove(os.path.join(out, f))
    open(os.path.join(out, "page.css"), "w", encoding="utf-8").write(CSS)
    by_umd = {}
    for c in cs:
        by_umd.setdefault(c["umd"], []).append(c)
    urls = []
    for c in cs:
        slug, h = page_html(c, base, by_umd)
        open(os.path.join(out, slug + ".html"), "w", encoding="utf-8").write(h)
        urls.append("{}/apt/{}.html".format(base, __import__("urllib.parse").parse.quote(slug)))
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(index_html(cs, base))
    today = dt.date.today().isoformat()
    sm = ['<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
          "<url><loc>{}/index.html</loc><lastmod>{}</lastmod><changefreq>daily</changefreq></url>".format(base, today),
          "<url><loc>{}/apt/index.html</loc><lastmod>{}</lastmod><changefreq>daily</changefreq></url>".format(base, today)]
    sm += ["<url><loc>{}</loc><lastmod>{}</lastmod><changefreq>weekly</changefreq></url>".format(html.escape(u), today) for u in urls]
    sm.append("</urlset>")
    open(os.path.join(APP, "sitemap.xml"), "w", encoding="utf-8").write("".join(sm))
    open(os.path.join(APP, "robots.txt"), "w", encoding="utf-8").write("User-agent: *\nAllow: /\nSitemap: {}/sitemap.xml\n".format(base))
    print("단지 페이지 {}개 + index + sitemap -> {}".format(len(urls), out))


if __name__ == "__main__":
    sys.exit(main())
