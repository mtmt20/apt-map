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
    out = []
    for key, g in groups.items():
        loc = geo.get(key)
        if not loc:
            continue                      # geocode.py 로 좌표를 먼저 채워야 함
        cid = key.lower().replace("|", "-").replace(" ", "")
        areas = sorted({t["area"] for t in g["trades"]})
        out.append({
            "id": cid, "name": g["apt"], "sgg": loc.get("sgg", ""), "umd": g["umd"], "jibun": g["jibun"],
            "addr": loc.get("addr", ""), "lat": loc["lat"], "lng": loc["lng"],
            "households": loc.get("households", 0), "built": g["built"], "max_floor": loc.get("max_floor", 0),
            "far": loc.get("far", 0), "areas": areas, "trades": sorted(g["trades"], key=lambda t: t["date"]),
            "ask": None,
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


def enrich(c, roads, today):
    tr = c["trades"]
    recent = [t for t in tr if dt.date.fromisoformat(t["date"]) >= months_ago(today, 3)]
    if len(recent) < 3:
        recent = tr[-5:]
    y_ago = [t for t in tr if months_ago(today, 14) <= dt.date.fromisoformat(t["date"]) < months_ago(today, 10)]
    if len(y_ago) < 2:
        y_ago = tr[:5]
    now_ppy, old_ppy = median_ppy(recent), median_ppy(y_ago)
    c["ppy"] = int(now_ppy) if now_ppy else None
    c["chg_1y"] = round((now_ppy / old_ppy - 1) * 100, 1) if now_ppy and old_ppy else None
    c["trade_count_1y"] = sum(1 for t in tr if dt.date.fromisoformat(t["date"]) >= months_ago(today, 12))

    # 평형별 최근가
    by_area = {}
    for t in tr:
        by_area.setdefault(int(t["area"]), []).append(t)   # 84.9 -> 84 (관행 표기)
    c["by_area"] = []
    for a, ts in sorted(by_area.items()):
        ts.sort(key=lambda t: t["date"])
        last3 = ts[-3:]
        c["by_area"].append({
            "area": a, "pyeong": round(a * 1.32 / PY),   # 공급면적 기준 평형(관행), 전용 84 -> 34평형
            "latest": last3[-1]["price"], "latest_date": last3[-1]["date"],
            "avg_recent": int(statistics.mean(t["price"] for t in last3)), "count": len(ts),
        })

    # 역
    st = sorted(((dist_m(c["lat"], c["lng"], s[2], s[3]), s) for s in demo_data.STATIONS), key=lambda x: x[0])
    near = [(round(d), s[0], s[1]) for d, s in st if d <= 600]
    d0, s0 = st[0]
    c["station"] = {"name": s0[0], "line": s0[1], "dist": round(d0), "walk_min": max(1, round(d0 / 70)),
                    "within_600": [{"name": n, "line": l, "dist": d} for d, n, l in near]}

    # 초등 배정 (폴리곤 포함 여부 -> 없으면 최근접)
    elem = None
    for name, lat, lng, poly in demo_data.ELEM_SCHOOLS:
        if point_in_ring(c["lng"], c["lat"], poly):
            elem = (name, lat, lng)
            break
    if not elem:
        name, lat, lng, _ = min(demo_data.ELEM_SCHOOLS, key=lambda s: dist_m(c["lat"], c["lng"], s[1], s[2]))
        elem = (name, lat, lng)
    de = dist_m(c["lat"], c["lng"], elem[1], elem[2])
    c["school"] = {
        "elem": elem[0], "elem_dist": round(de), "elem_walk_min": max(1, round(de / 60)),
        "chopuma": de <= 300,
        "middle": demo_data.MIDDLE_ZONES.get(c["umd"], []),
        "middle_note": "중학교는 학교군 단위 배정 + 추첨 (특정 학교 확정 아님)",
    }

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
    c["pros"], c["cons"] = pros[:4], cons[:4]

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
    mode = "real" if real else "demo"
    cs = real or demo_data.complexes()
    cs = [enrich(c, roads, today) for c in cs]

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
    dump("schools.geojson", demo_data.elem_schools_geojson())
    dump("auctions.json", [a for a in aucs if "lat" in a])
    dump("meta.json", {
        "mode": mode, "built_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "area": "서울 마포구 (공덕·아현·염리)", "complexes": len(cs), "roads": len(roads),
        "center": [126.9515, 37.5505],
    })
    print("mode={} 단지 {}개, 도로 {}개, 경매 {}건 -> {}".format(mode, len(cs), len(roads), len(aucs), OUT))
    for c in cs[:5]:
        print("  {:14s} 평당 {:>6,}만 1y {:+.1f}%  초등 {} {}m  역 {} {}m  대로 {}m | {} / {}".format(
            c["name"][:14], c["ppy"] or 0, c["chg_1y"] or 0, c["school"]["elem"], c["school"]["elem_dist"],
            c["station"]["name"], c["station"]["dist"], c["road"]["major_dist"], ", ".join(c["pros"]), ", ".join(c["cons"])))


if __name__ == "__main__":
    main()
