"""OSM 에서 '공사 중' 철도 노선(경로)과 예정 역을 받아 data/raw/future_rail.json 으로 저장.

  python pipeline/fetch_future_rail.py [--raw 응답.json]

- railway=construction 인 선로만 쓴다. 계획(proposed) 단계 노선은 확정이 아니라 넣지 않는다.
- 예정 역은 construction:railway=station 등 공사 태그가 있고 이름이 숫자가 아닌 것만 쓴다 (번호만 있는 역은 위치 신뢰가 낮음).
- 개통 시기·역 위치는 바뀔 수 있으므로 앱/페이지에서 반드시 "공사 중, OSM 기준" 으로 표시한다.
"""
import argparse
import json
import math
import os
import re
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "raw", "future_rail.json")
URLS = ["https://overpass-api.de/api/interpreter", "https://lz4.overpass-api.de/api/interpreter",
        "https://overpass.private.coffee/api/interpreter"]
HEADERS = {"User-Agent": "apt-map-mvp/0.1 (personal project)"}
QUERY = """[out:json][timeout:250];
way["railway"="construction"]["construction"~"^(rail|subway|light_rail|tram)$"](37.13,126.55,37.85,127.35)->.w;
.w out geom tags;
(
  node(around.w:120)["railway"~"^(station|halt|stop|construction)$"];
  node(around.w:120)["public_transport"~"^(station|stop_position)$"];
  node(around.w:120)["construction:railway"];
  node(around.w:120)["construction:public_transport"];
)->.n;
.n out body;
"""
# OSM 선로 이름 -> 표시 이름, 색
NAMES = [
    (r"비선", "GTX-B", "#1C4DA1"), (r"씨선", "GTX-C", "#8B6B2E"), (r"에이선", "GTX-A", "#AB087D"),
    (r"신안산", "신안산선", "#0B7A75"), (r"동북선", "동북선", "#C4A000"), (r"도봉산옥정", "7호선 도봉산옥정선", "#6E7E31"),
    (r"^9호선", "9호선 4단계", "#A49D87"), (r"경강", "월곶판교선", "#0B318F"), (r"동탄인덕원", "동탄인덕원선", "#E4572E"),
    (r"위례", "위례선(트램)", "#2E86C1"),
]


def label(name):
    for pat, lab, col in NAMES:
        if re.search(pat, name or ""):
            return lab, col
    return None, None


def overpass(q):
    last = None
    for u in URLS:
        try:
            r = requests.post(u, data={"data": q}, headers=HEADERS, timeout=280)
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                return r.json()
            last = "{} {}".format(u, r.status_code)
        except Exception as e:  # noqa: BLE001
            last = "{} {}".format(u, e)
        time.sleep(5)
    raise SystemExit("overpass 실패: {}".format(last))


def dist_m(a, b):
    dy = (a[0] - b[0]) * 111320
    dx = (a[1] - b[1]) * 111320 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def build(data):
    ways = [e for e in data["elements"] if e["type"] == "way"]
    nodes = [e for e in data["elements"] if e["type"] == "node"]
    lines = {}
    for w in ways:
        t = w.get("tags", {})
        lab, col = label(t.get("name") or t.get("construction:name"))
        if not lab or not w.get("geometry"):
            continue
        L = lines.setdefault(lab, {"name": lab, "color": col, "segs": []})
        L["segs"].append([[round(p["lon"], 5), round(p["lat"], 5)] for p in w["geometry"]])
    stations = []
    for n in nodes:
        t = n.get("tags", {})
        is_con = t.get("railway") == "construction" or any(k.startswith("construction:") for k in t)
        nm = re.sub(r"\(.*?\)", "", t.get("name") or "").strip()
        if not is_con or not nm or re.fullmatch(r"[0-9A-Za-z-]+", nm) or "기지" in nm:
            continue
        # 가장 가까운 공사 중 선로에 붙인다
        best, bd = None, 1e9
        for L in lines.values():
            for seg in L["segs"]:
                for x, y in seg[::2]:
                    d = dist_m((n["lat"], n["lon"]), (y, x))
                    if d < bd:
                        best, bd = L["name"], d
        if best and bd <= 300:
            stations.append({"name": nm, "line": best, "lat": round(n["lat"], 6), "lng": round(n["lon"], 6)})
    # 같은 노선·이름 중복 제거
    seen, uniq = set(), []
    for s in stations:
        k = (s["line"], s["name"])
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    feats = [{"type": "Feature", "properties": {"name": L["name"], "color": L["color"]},
              "geometry": {"type": "MultiLineString", "coordinates": L["segs"]}} for L in lines.values()]
    return {"lines": {"type": "FeatureCollection", "features": feats}, "stations": uniq,
            "note": "OpenStreetMap railway=construction 기준. 개통 시기·역 위치는 바뀔 수 있음"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw")
    a = ap.parse_args()
    data = json.load(open(a.raw, encoding="utf-8")) if a.raw else overpass(QUERY)
    out = build(data)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("공사 중 노선 {}개: {}".format(len(out["lines"]["features"]), ", ".join(f["properties"]["name"] for f in out["lines"]["features"])))
    by = {}
    for s in out["stations"]:
        by.setdefault(s["line"], []).append(s["name"])
    for k, v in by.items():
        print("  예정역 {} ({}): {}".format(k, len(v), " ".join(v)))


if __name__ == "__main__":
    main()
