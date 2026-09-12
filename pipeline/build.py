"""단지/실거래/학군/도로/경매를 합쳐 앱용 JSON을 만든다.

  python pipeline/build.py

입력
  data/raw/trades_*.json   (fetch_trades.py, 있으면 실데이터 모드)
  app/data/roads.geojson   (fetch_roads.py, 없으면 도로 관련 판단 생략)
  pipeline/demo_data.py    (학군/경매/역 정보, 실거래 없을 땐 단지+거래도 데모)
출력
  app/data/complexes.json, schools.geojson, auctions.json, meta.json
"""
import datetime as dt
import glob
import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import demo_data  # noqa: E402

ROOT = os.path.join(HERE, "..")
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "app", "data")
PY = 3.3058


# ---------- geo utils ----------
def dist_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def point_in_ring(lng, lat, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            x = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if x > lng:
                inside = not inside
    return inside


def seg_dist_m(lat, lng, a, b):
    """점(lat,lng)과 선분 a-b([lng,lat]) 거리(m), 로컬 평면 근사."""
    kx = 111320.0 * math.cos(math.radians(lat))
    ky = 110540.0
    px, py = lng * kx, lat * ky
    ax, ay = a[0] * kx, a[1] * ky
    bx, by = b[0] * kx, b[1] * ky
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def nearest_major_road(lat, lng, roads):
    best, name = 1e9, ""
    for f in roads:
        if f["properties"]["class"] != "major":
            continue
        cs = f["geometry"]["coordinates"]
        # 대략 필터: bbox 300m 밖이면 스킵
        if all(abs(c[1] - lat) > 0.003 or abs(c[0] - lng) > 0.004 for c in cs):
            continue
        for i in range(len(cs) - 1):
            d = seg_dist_m(lat, lng, cs[i], cs[i + 1])
            if d < best:
                best, name = d, f["properties"].get("name", "")
    return (round(best) if best < 1e9 else None), name


def voronoi_zones(schools, bbox):
    """초등학교 점 -> 최근접 기준 통학구역 추정 폴리곤 (bbox 로 클리핑). schools: [{name,lat,lng}]"""
    import numpy as np
    from scipy.spatial import Voronoi
    s, w, n, e = bbox
    lat0 = (s + n) / 2
    kx, ky = 111320.0 * math.cos(math.radians(lat0)), 110540.0
    pts = np.array([[(sc["lng"] - w) * kx, (sc["lat"] - s) * ky] for sc in schools])
    W, H = (e - w) * kx, (n - s) * ky
    # 무한 영역을 막기 위해 멀리 떨어진 가짜 점 4개 추가
    far = 50 * max(W, H)
    aug = np.vstack([pts, [[-far, -far], [far, -far], [-far, far], [far, far]]])
    vor = Voronoi(aug)
    clip = [(0, 0), (W, 0), (W, H), (0, H)]

    def clip_poly(poly):
        def inside(p, a, b):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0

        def inter(p1, p2, a, b):
            x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
            x3, y3, x4, y4 = a[0], a[1], b[0], b[1]
            den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4) or 1e-12
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
            return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
        out = poly
        for i in range(4):
            a, b = clip[i], clip[(i + 1) % 4]
            inp, out = out, []
            if not inp:
                break
            sp = inp[-1]
            for pt in inp:
                if inside(pt, a, b):
                    if not inside(sp, a, b):
                        out.append(inter(sp, pt, a, b))
                    out.append(pt)
                elif inside(sp, a, b):
                    out.append(inter(sp, pt, a, b))
                sp = pt
        return out

    zones = []
    for i, sc in enumerate(schools):
        region = vor.regions[vor.point_region[i]]
        if not region or -1 in region:
            continue
        poly = clip_poly([tuple(vor.vertices[v]) for v in region])
        if len(poly) < 3:
            continue
        ring = [[round(w + x / kx, 5), round(s + y / ky, 5)] for x, y in poly]
        ring.append(ring[0])
        zones.append({"name": sc["name"], "ring": ring})
    return zones


def load_poi():
    p = os.path.join(RAW, "poi.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding="utf-8"))
    s, w, n, e = [float(x) for x in d["bbox"].split(",")]
    d["bbox"] = (s, w, n, e)
    d["middle"], d["academies"] = [], []
    np_ = os.path.join(RAW, "schools_neis.json")
    if os.path.exists(np_):                       # 나이스 공식 목록이 있으면 초등은 그걸로 (병설/분교 제외 처리됨)
        ns = json.load(open(np_, encoding="utf-8"))
        if ns.get("elem"):
            d["elem_schools"] = [{"name": x["name"], "lat": x["lat"], "lng": x["lng"], "public": x.get("public", "")} for x in ns["elem"]]
        d["middle"] = ns.get("middle", [])
    ap_ = os.path.join(RAW, "academies.json")
    if os.path.exists(ap_):
        d["academies"] = json.load(open(ap_, encoding="utf-8"))
    d["zones"] = voronoi_zones(d["elem_schools"], d["bbox"])
    return d


import re as _re
_STRIP = _re.compile(r"(아파트|APT|apt|\(.*?\)|\s|·|-|_|,)")


def _norm(n):
    return _STRIP.sub("", n).lower()


def load_kapt():
    """K-apt 기본정보 (fetch_kapt.py). norm(name) -> [rec]"""
    p = os.path.join(RAW, "kapt.json")
    if not os.path.exists(p):
        return {}
    out = {}
    for rec in json.load(open(p, encoding="utf-8")).values():
        out.setdefault(rec["norm"], []).append(rec)
    return out


def kapt_lookup(kapt, apt, umd):
    key = _norm(apt)
    cands = kapt.get(key) or kapt.get(_norm(umd[:-1] + apt)) or []
    if not cands:
        for k, v in kapt.items():
            if len(key) >= 4 and (key in k or k in key):
                cands += v
    for c in cands:
        if umd and (umd in (c.get("addr") or "") or umd in (c.get("as3") or "")):
            return c
    return cands[0] if len(cands) == 1 else None


def load_rent():
    """전월세 raw (fetch_rent.py). key -> [rows]"""
    out = {}
    for fp in glob.glob(os.path.join(RAW, "rent_*.json")):
        for r in json.load(open(fp, encoding="utf-8")):
            out.setdefault("{}|{}|{}".format(r["umd"], r["apt"], r["jibun"]), []).append(r)
    return out


# ---------- 데이터 소스 ----------
def load_real_complexes():
    files = sorted(glob.glob(os.path.join(RAW, "trades_*.json")))
    if not files:
        return None
    geo_path = os.path.join(RAW, "geocode.json")
    geo = json.load(open(geo_path, encoding="utf-8")) if os.path.exists(geo_path) else {}
    groups = {}
    for fp in files:
        for r in json.load(open(fp, encoding="utf-8")):
            key = "{}|{}|{}".format(r["umd"], r["apt"], r["jibun"])
            g = groups.setdefault(key, {"apt": r["apt"], "umd": r["umd"], "jibun": r["jibun"], "built": r["built"], "trades": []})
            g["trades"].append({"date": r["date"], "area": r["area"], "floor": r["floor"], "price": r["price"], "kind": r["kind"]})
    kapt, rent = load_kapt(), load_rent()
    kp = os.path.join(RAW, "kakao_poi.json")
    kpoi = json.load(open(kp, encoding="utf-8")) if os.path.exists(kp) else {}
    out = []
    for key, g in groups.items():
        loc = geo.get(key)
        if not loc:
            continue                      # geocode.py 로 좌표를 먼저 채워야 함
        cid = key.lower().replace("|", "-").replace(" ", "")
        areas = sorted({t["area"] for t in g["trades"]})
        k = kapt_lookup(kapt, g["apt"], g["umd"]) if kapt else None
        out.append({
            "id": cid, "name": g["apt"], "sgg": loc.get("sgg", ""), "umd": g["umd"], "jibun": g["jibun"],
            "addr": loc.get("addr", ""), "lat": loc["lat"], "lng": loc["lng"],
            "households": (k or {}).get("households") or loc.get("households", 0), "built": g["built"],
            "max_floor": (k or {}).get("top_floor") or loc.get("max_floor", 0), "dongs": (k or {}).get("dongs", 0),
            "far": loc.get("far", 0), "areas": areas, "trades": sorted(g["trades"], key=lambda t: t["date"]),
            "rents": sorted(rent.get(key, []), key=lambda r: r["date"]),
            "sale_type": (k or {}).get("sale_type", ""), "hall": (k or {}).get("hall", ""), "heat": (k or {}).get("heat", ""),
            "life": kpoi.get(key), "ask": None,
        })
    return out


# ---------- 파생 지표 ----------
def ppy(t):
    return t["price"] / (t["area"] / PY)


def median_ppy(trades):
    return statistics.median([ppy(t) for t in trades]) if trades else None


def months_ago(d, n):
    y, m = d.year, d.month - n
    while m <= 0:
        y -= 1
        m += 12
    return dt.date(y, m, 1)


def enrich(c, roads, today, stations, schools, zones, middle=None, academies=None):
    tr = c["trades"]
    recent = [t for t in tr if dt.date.fromisoformat(t["date"]) >= months_ago(today, 3)]
    if len(recent) < 3:
        recent = tr[-5:]
    y_ago = [t for t in tr if months_ago(today, 14) <= dt.date.fromisoformat(t["date"]) < months_ago(today, 10)]
    if len(y_ago) < 2:
        y_ago = tr[:5]
    now_ppy, old_ppy = median_ppy(recent), median_ppy(y_ago)
    c["ppy"] = int(now_ppy) if now_ppy else None
    # 두 구간이 겹치거나 표본이 적으면 변동률을 내지 않는다 (0% 로 오해 방지)
    overlap = set(map(id, recent)) & set(map(id, y_ago))
    reliable = now_ppy and old_ppy and not overlap and len(tr) >= 6
    c["chg_1y"] = round((now_ppy / old_ppy - 1) * 100, 1) if reliable else None
    c["trade_count_1y"] = sum(1 for t in tr if dt.date.fromisoformat(t["date"]) >= months_ago(today, 12))

    # 평형별 최근가
    by_area = {}
    for t in tr:
        by_area.setdefault(int(t["area"]), []).append(t)   # 84.9 -> 84 (관행 표기)
    c["by_area"] = []
    for a, ts in sorted(by_area.items()):
        ts.sort(key=lambda t: t["date"])
        last3 = ts[-3:]
        js = [r["deposit"] for r in c.get("rents", []) if int(r["area"]) == a and r["monthly"] == 0
              and dt.date.fromisoformat(r["date"]) >= months_ago(today, 6)]
        jeonse = int(statistics.median(js)) if len(js) >= 2 else None
        c["by_area"].append({
            "area": a, "pyeong": round(a * 1.32 / PY),   # 공급면적 기준 평형(관행), 전용 84 -> 34평형
            "latest": last3[-1]["price"], "latest_date": last3[-1]["date"],
            "avg_recent": int(statistics.mean(t["price"] for t in last3)), "count": len(ts),
            "jeonse": jeonse, "jeonse_n": len(js),
            "jeonse_ratio": round(jeonse / statistics.median(t["price"] for t in last3) * 100) if jeonse and len(ts) >= 2 else None,
        })
    c["jeonse_ratio"] = next((b["jeonse_ratio"] for b in sorted(c["by_area"], key=lambda b: -b["count"]) if b["jeonse_ratio"]), None)
    rents = c.get("rents", [])
    c["rent_count_12m"] = sum(1 for r in rents if dt.date.fromisoformat(r["date"]) >= months_ago(today, 12))
    c["rent_turnover"] = round(c["rent_count_12m"] / c["households"] * 100) if c.get("households") else None
    c.pop("rents", None)

    # 역
    st = sorted(((dist_m(c["lat"], c["lng"], s["lat"], s["lng"]), s) for s in stations), key=lambda x: x[0])
    near = [(round(d), s["name"], s["line"]) for d, s in st if d <= 600]
    d0, s0 = st[0]
    c["station"] = {"name": s0["name"], "line": s0["line"], "dist": round(d0), "walk_min": max(1, round(d0 / 70)),
                    "within_600": [{"name": n, "line": l, "dist": d} for d, n, l in near]}

    # 초등 배정 (통학구역 폴리곤 포함 여부 -> 없으면 최근접)
    by_name = {sc["name"]: sc for sc in schools}
    elem = None
    for z in zones:
        if point_in_ring(c["lng"], c["lat"], z["ring"][:-1]):
            elem = by_name.get(z["name"])
            break
    if not elem:
        elem = min(schools, key=lambda sc: dist_m(c["lat"], c["lng"], sc["lat"], sc["lng"]))
    de = dist_m(c["lat"], c["lng"], elem["lat"], elem["lng"])
    if middle:
        near_mid = sorted(((dist_m(c["lat"], c["lng"], m["lat"], m["lng"]), m) for m in middle), key=lambda x: x[0])[:3]
        mids = ["{} {}".format(m["name"], "" if d > 1500 else "") .strip() for d, m in near_mid]
        mid_detail = [{"name": m["name"], "dist": round(d), "public": m.get("public", ""), "coedu": m.get("coedu", "")} for d, m in near_mid]
        mid_note = "가까운 중학교 3곳 (실제 배정은 학교군 내 추첨)"
    else:
        mids, mid_detail, mid_note = demo_data.MIDDLE_ZONES.get(c["umd"], []), [], "중학교는 학교군 단위 배정 + 추첨 (특정 학교 확정 아님)"
    c["school"] = {
        "elem": elem["name"], "elem_dist": round(de), "elem_walk_min": max(1, round(de / 60)),
        "chopuma": de <= 300,
        "middle": mids, "middle_detail": mid_detail, "middle_note": mid_note,
    }
    # 학원 밀집도 (반경 1km): 전체 / 입시·보습 교과
    if academies:
        near = [x for x in academies if abs(x["lat"] - c["lat"]) < 0.0095 and abs(x["lng"] - c["lng"]) < 0.0115
                and dist_m(c["lat"], c["lng"], x["lat"], x["lng"]) <= 1000]
        c["edu"] = {"aca_1km": len(near), "exam_1km": sum(1 for x in near if "입시" in x.get("realm", "")),
                    "art_1km": sum(1 for x in near if "예능" in x.get("realm", ""))}
    else:
        c["edu"] = None

    # 도로
    if roads:
        d, name = nearest_major_road(c["lat"], c["lng"], roads)
        c["road"] = {"major_dist": d, "major_name": name, "roadside": d is not None and d < 60}
    else:
        c["road"] = {"major_dist": None, "major_name": "", "roadside": False}

    # 장단점
    age = today.year - c["built"]
    pros, cons = [], []
    if c["households"] >= 1500:
        pros.append("대단지 {:,}세대".format(c["households"]))
    elif c["households"] and c["households"] < 500:
        cons.append("소단지 {}세대".format(c["households"]))
    if age <= 5:
        pros.append("신축 {}년차".format(age))
    elif age <= 12:
        pros.append("준신축 {}년차".format(age))
    elif age >= 20:
        cons.append("구축 {}년차".format(age))
    if len(c["station"]["within_600"]) >= 2:
        pros.append("더블 역세권")
    elif c["station"]["dist"] <= 500:
        pros.append("{} 도보 {}분".format(c["station"]["name"], c["station"]["walk_min"]))
    elif c["station"]["dist"] > 800:
        cons.append("역까지 도보 {}분".format(c["station"]["walk_min"]))
    if c["school"]["chopuma"]:
        pros.append("초품아 ({})".format(c["school"]["elem"]))
    elif c["school"]["elem_dist"] > 600:
        cons.append("초등학교 도보 {}분".format(c["school"]["elem_walk_min"]))
    if c["road"]["roadside"]:
        cons.append("대로변 소음 가능성")
    elif c["road"]["major_dist"] and c["road"]["major_dist"] > 150:
        pros.append("이면 조용한 입지")
    if c["far"] and c["far"] >= 280:
        cons.append("용적률 {}% (동간 간격 촘촘)".format(c["far"]))
    elif c["far"] and c["far"] <= 240:
        pros.append("용적률 {}% (쾌적)".format(c["far"]))
    if c["chg_1y"] is not None and c["chg_1y"] >= 8:
        pros.append("1년 평당가 +{}%".format(c["chg_1y"]))
    if c["trade_count_1y"] <= 3:
        cons.append("최근 1년 거래 {}건 (가격 확인 어려움)".format(c["trade_count_1y"]))
    life = c.get("life") or {}
    if life.get("daycare") is not None and life["daycare"] >= 20:      # 마포구 중앙값 14
        pros.append("어린이집·유치원 700m 내 {}곳 (많음)".format(life["daycare"]))
    elif life.get("daycare") is not None and life["daycare"] <= 5:
        cons.append("어린이집·유치원 700m 내 {}곳 (적음)".format(life["daycare"]))
    if life.get("pediatric") is not None and life["pediatric"] == 0:
        cons.append("1km 내 소아과 없음")
    if c["jeonse_ratio"] and c["jeonse_ratio"] >= 90:
        cons.append("전세가율 {}% (깡통전세 주의)".format(c["jeonse_ratio"]))
    # 중립 정보 (사람들이 잘 모르는 것)
    notes = []
    if c.get("sale_type") == "혼합":
        notes.append("분양·임대 혼합단지 (소셜믹스)")
    elif c.get("sale_type") == "임대":
        notes.append("임대 단지")
    if c["rent_turnover"] is not None and c["rent_turnover"] >= 20:
        notes.append("세입자 비중 높은 편 (1년 전월세 거래 {}건 = 세대수의 {}%)".format(c["rent_count_12m"], c["rent_turnover"]))
    if c.get("hall") and c["hall"] != "계단식":
        notes.append("{} 구조".format(c["hall"]))
    if age >= 30:
        notes.append("준공 30년 경과 (재건축 연한 충족)")
    c["pros"], c["cons"], c["notes"] = pros[:4], cons[:4], notes[:4]

    # 호가 갭
    if c.get("ask") and c["ppy"]:
        mid = (c["ask"]["low_ppy"] + c["ask"]["high_ppy"]) / 2
        c["ask"]["gap_pct"] = round((mid / c["ppy"] - 1) * 100, 1)
    return c


def main():
    today = dt.date.today()
    roads_path = os.path.join(OUT, "roads.geojson")
    roads = json.load(open(roads_path, encoding="utf-8"))["features"] if os.path.exists(roads_path) else []

    real = load_real_complexes()
    poi = load_poi() if real else None
    mode = "real" if real else "demo"
    cs = real or demo_data.complexes()
    if poi:
        stations, schools, zones = poi["stations"], poi["elem_schools"], poi["zones"]
        zone_note = "최근접 학교 기준 추정 (공식 학구도 반영 전)"
    else:
        stations = [{"name": n, "line": l, "lat": la, "lng": lo} for n, l, la, lo in demo_data.STATIONS]
        schools = [{"name": n, "lat": la, "lng": lo} for n, la, lo, _ in demo_data.ELEM_SCHOOLS]
        zones = [{"name": n, "ring": poly + [poly[0]]} for n, _, _, poly in demo_data.ELEM_SCHOOLS]
        zone_note = "데모 경계"
    middle, academies = (poi or {}).get("middle") or [], (poi or {}).get("academies") or []
    cs = [enrich(c, roads, today, stations, schools, zones, middle, academies) for c in cs]
    cs = [c for c in cs if c["by_area"]]
    # 학원 밀집도 구내 백분위 (교과학원 기준)
    vals = sorted(c["edu"]["exam_1km"] for c in cs if c.get("edu"))
    for c in cs:
        if not c.get("edu"):
            continue
        v = c["edu"]["exam_1km"]
        pct = 100 - int(round(sum(1 for x in vals if x <= v) / len(vals) * 100))     # 0 = 최상위
        c["edu"]["exam_top_pct"] = max(1, pct if pct > 0 else 1)
        if pct <= 20 and v >= 15:
            c["pros"].insert(0, "학원가 인접 (1km 내 교과학원 {}개, 구 상위 {}%)".format(v, c["edu"]["exam_top_pct"]))
            c["pros"] = c["pros"][:4]
        elif v <= 2:
            c["cons"].append("주변 교과학원 적음 (1km 내 {}개)".format(v))
            c["cons"] = c["cons"][:4]

    aucs = demo_data.auctions()
    by_id = {c["id"]: c for c in cs}
    for a in aucs:
        c = by_id.get(a["complex_id"])
        if c:
            a.update({"name": c["name"], "lat": c["lat"], "lng": c["lng"]})
            a["discount_pct"] = round((1 - a["min_price"] / a["appraisal"]) * 100, 1)
            recent = [t for t in c["trades"] if abs(t["area"] - a["area"]) < 3]
            a["recent_trade"] = recent[-1]["price"] if recent else None
            c.setdefault("auctions", []).append(a["case"])

    os.makedirs(OUT, exist_ok=True)
    dump = lambda name, obj: json.dump(obj, open(os.path.join(OUT, name), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    dump("complexes.json", cs)
    feats = []
    for z in zones:
        feats.append({"type": "Feature", "properties": {"name": z["name"], "kind": "zone", "note": zone_note},
                      "geometry": {"type": "Polygon", "coordinates": [z["ring"]]}})
    for sc in schools:
        feats.append({"type": "Feature", "properties": {"name": sc["name"], "kind": "school"},
                      "geometry": {"type": "Point", "coordinates": [sc["lng"], sc["lat"]]}})
    dump("schools.geojson", {"type": "FeatureCollection", "features": feats})
    dump("auctions.json", [a for a in aucs if "lat" in a])
    dump("meta.json", {
        "mode": mode, "built_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "area": "서울 마포구" if mode == "real" else "서울 마포구 (공덕·아현·염리 데모)", "complexes": len(cs), "roads": len(roads),
        "center": [round(sum(c["lng"] for c in cs) / len(cs), 5), round(sum(c["lat"] for c in cs) / len(cs), 5)],
        "zone_note": zone_note, "stations": len(stations), "schools": len(schools), "academies": len(academies),
    })
    print("mode={} 단지 {}개, 도로 {}개, 경매 {}건 -> {}".format(mode, len(cs), len(roads), len(aucs), OUT))
    for c in cs[:5]:
        print("  {:14s} 평당 {:>6,}만 1y {:+.1f}%  초등 {} {}m  역 {} {}m  대로 {}m | {} / {}".format(
            c["name"][:14], c["ppy"] or 0, c["chg_1y"] or 0, c["school"]["elem"], c["school"]["elem_dist"],
            c["station"]["name"], c["station"]["dist"], c["road"]["major_dist"], ", ".join(c["pros"]), ", ".join(c["cons"])))


if __name__ == "__main__":
    main()
