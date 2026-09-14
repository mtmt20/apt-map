"""OSM Overpass 에서 수도권 전철 노선 경로(공식 색) + 역별 노선을 받아 data/raw/subway.json 으로 저장.

  python pipeline/fetch_subway.py [--raw lines.json]

- 노선: route relation 의 선로 way 를 ref(호선) 단위로 합치고(지선·급행 계통 중복 제거) 서울 주변만 남긴 뒤 단순화.
- 역: relation 의 정차 노드 이름으로 역별 노선 목록(환승역 판단용)을 만든다.
- KTX/SRT/ITX/무궁화 같은 간선철도는 넣지 않는다 (집 고르는 데 의미 있는 건 수도권 전철).
"""
import argparse
import json
import math
import os
import re
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "raw", "subway.json")
URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter"]
HEADERS = {"User-Agent": "apt-map-mvp/0.1 (personal project)"}
BBOX = (37.40, 126.75, 37.72, 127.20)          # 서울 + 경계 바깥 여유
KEEP = (37.42, 126.76, 37.71, 127.19)          # 이 박스에 걸친 선로만 남김

# 앱 표시용 짧은 이름 (ref -> 라벨)
LABEL = {"1": "1호선", "2": "2호선", "3": "3호선", "4": "4호선", "5": "5호선", "6": "6호선", "7": "7호선", "8": "8호선",
         "9": "9호선", "신분당": "신분당선", "경의·중앙": "경의중앙선", "경춘": "경춘선", "공항철도": "공항철도",
         "서해": "서해선", "수인·분당": "수인분당선", "GTX-A": "GTX-A", "Silim": "신림선", "W": "우이신설선"}
QUERY = """[out:json][timeout:300];
relation["route"~"^(subway|light_rail|train)$"]["colour"]["ref"~"^({refs})$"]({s},{w},{n},{e})->.r;
.r out body;
way(r.r)->.w;
.w out geom;
node(r.r)->.n;
.n out tags center;
"""


def overpass(q):
    last = None
    for u in URLS:
        try:
            r = requests.post(u, data={"data": q}, headers=HEADERS, timeout=330)
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                return r.json()
            last = "{} {}".format(u, r.status_code)
        except Exception as e:  # noqa: BLE001
            last = "{} {}".format(u, e)
        time.sleep(3)
    raise SystemExit("overpass 실패: {}".format(last))


def norm(name):
    """'한성대입구역', '한성대입구(성북구청)' -> '한성대입구'"""
    n = re.sub(r"\(.*?\)", "", name or "").strip()
    return n[:-1] if n.endswith("역") and len(n) > 2 else n


def simplify(pts, tol=0.00004):
    """Douglas-Peucker (경위도 그대로, tol ~ 4m)."""
    if len(pts) < 3:
        return pts
    ax, ay = pts[0]
    bx, by = pts[-1]
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy) or 1e-12
    far, idx = -1.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        d = abs(dy * px - dx * py + bx * ay - by * ax) / L
        if d > far:
            far, idx = d, i
    if far <= tol:
        return [pts[0], pts[-1]]
    return simplify(pts[:idx + 1], tol)[:-1] + simplify(pts[idx:], tol)


def build(data):
    rels = [e for e in data["elements"] if e["type"] == "relation"]
    ways = {e["id"]: e for e in data["elements"] if e["type"] == "way"}
    nodes = {e["id"]: e for e in data["elements"] if e["type"] == "node"}
    s, w, n, e = KEEP
    lines, st_lines = {}, {}
    for r in rels:
        ref = r["tags"].get("ref")
        if ref not in LABEL:
            continue
        L = lines.setdefault(ref, {"ref": ref, "name": LABEL[ref], "color": r["tags"]["colour"].upper(), "ways": set()})
        for m in r.get("members", []):
            if m["type"] == "way" and m.get("role", "") in ("", "forward", "backward") and m["ref"] in ways:
                L["ways"].add(m["ref"])
            elif m["type"] == "node" and m["ref"] in nodes and (m.get("role") or "").startswith("stop"):
                nm = norm(nodes[m["ref"]].get("tags", {}).get("name"))
                if nm:
                    st_lines.setdefault(nm, set()).add(LABEL[ref])
    features = []
    for ref, L in lines.items():
        segs = []
        for wid in sorted(L["ways"]):
            g = ways[wid].get("geometry") or []
            if not any(s <= p["lat"] <= n and w <= p["lon"] <= e for p in g):
                continue
            pts = simplify([(round(p["lon"], 6), round(p["lat"], 6)) for p in g])
            if len(pts) >= 2:
                segs.append([[x, y] for x, y in pts])
        if segs:
            features.append({"type": "Feature", "properties": {"ref": ref, "name": L["name"], "color": L["color"]},
                             "geometry": {"type": "MultiLineString", "coordinates": segs}})
    return {"lines": {"type": "FeatureCollection", "features": features},
            "station_lines": {k: sorted(v) for k, v in st_lines.items()},
            "colors": {L["name"]: L["color"] for L in lines.values()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", help="이미 받아둔 Overpass 응답 JSON (재수집 없이 가공만)")
    a = ap.parse_args()
    if a.raw:
        data = json.load(open(a.raw, encoding="utf-8"))
    else:
        s, w, n, e = BBOX
        refs = "|".join(re.escape(k).replace("\\·", "·") for k in LABEL)
        data = overpass(QUERY.format(refs=refs, s=s, w=w, n=n, e=e))
    out = build(data)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    pts = sum(len(c) for f in out["lines"]["features"] for seg in f["geometry"]["coordinates"] for c in [seg])
    print("노선 {}개, 선로 좌표 {}개, 노선 정보 있는 역 {}개 -> {} ({:,} bytes)".format(
        len(out["lines"]["features"]), pts, len(out["station_lines"]), OUT, os.path.getsize(OUT)))


if __name__ == "__main__":
    main()
