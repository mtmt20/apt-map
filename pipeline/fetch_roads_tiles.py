"""서울 전체 도로를 구별 bbox 로 Overpass 에서 받아 격자 타일(app/data/roads/<r>_<c>.geojson)로 저장.

  python pipeline/fetch_roads_tiles.py [--only 마포구,서대문구]

- 구 bbox 는 data/raw/boundary_<구>.geojson (fetch_boundary.py) 에서 계산.
- 원본은 data/raw/roads_<구>.json 에 캐시 (Overpass 재요청 방지).
- 타일 크기 0.02도(약 2.2km x 1.8km). 앱은 줌 13.5 이상에서 화면에 걸친 타일만 불러온다.
- 큰길(major)은 별도 서울 전체 파일 roads_major.geojson 으로도 저장 (줌 낮을 때 표시용, 좌표 4자리로 축약).
"""
import argparse
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_roads import fetch, to_geojson  # noqa: E402
from fetch_trades import RAW  # noqa: E402

OUT = os.path.join(HERE, "..", "app", "data", "roads")
TILE = 0.02


def bbox_of(boundary_path):
    ring = json.load(open(boundary_path, encoding="utf-8"))["geometry"]["coordinates"][0]
    lngs, lats = [p[0] for p in ring], [p[1] for p in ring]
    return min(lats), min(lngs), max(lats), max(lngs)


def tile_key(lng, lat):
    return "{}_{}".format(int(lat / TILE), int(lng / TILE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    bounds = sorted(glob.glob(os.path.join(RAW, "boundary_*.geojson")))
    only = set(x for x in a.only.split(",") if x)
    feats_all = []
    for bp in bounds:
        gu = os.path.basename(bp)[len("boundary_"):-len(".geojson")]
        if only and gu not in only:
            continue
        cache = os.path.join(RAW, "roads_{}.json".format(gu))
        if os.path.exists(cache):
            gj = json.load(open(cache, encoding="utf-8"))
        else:
            s, w, n, e = bbox_of(bp)
            bbox = "{:.4f},{:.4f},{:.4f},{:.4f}".format(s - 0.002, w - 0.002, n + 0.002, e + 0.002)
            print("{} Overpass bbox={}".format(gu, bbox))
            osm = fetch(bbox)
            gj = to_geojson(osm)
            for f in gj["features"]:
                f["geometry"]["coordinates"] = [[round(x, 5), round(y, 5)] for x, y in f["geometry"]["coordinates"]]
            json.dump(gj, open(cache, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
            time.sleep(6)
        print("  {} 도로 {}개".format(gu, len(gj["features"])))
        feats_all += gj["features"]

    # 구 bbox 가 겹쳐 중복된 way 제거 (좌표열 기준)
    seen, uniq = set(), []
    for f in feats_all:
        k = (f["properties"]["highway"], f["geometry"]["coordinates"][0][0], f["geometry"]["coordinates"][0][1], f["geometry"]["coordinates"][-1][0], f["geometry"]["coordinates"][-1][1], len(f["geometry"]["coordinates"]))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(f)
    print("전체 {}개 (중복 제거 후)".format(len(uniq)))

    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    tiles = {}
    for f in uniq:
        cs = f["geometry"]["coordinates"]
        # way 가 걸치는 모든 타일에 넣는다 (경계에서 끊기지 않게)
        keys = {tile_key(x, y) for x, y in cs[:: max(1, len(cs) // 6)]} | {tile_key(cs[0][0], cs[0][1]), tile_key(cs[-1][0], cs[-1][1])}
        for k in keys:
            tiles.setdefault(k, []).append(f)
    for k, fs in tiles.items():
        json.dump({"type": "FeatureCollection", "features": fs}, open(os.path.join(OUT, k + ".geojson"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    major = [{"type": "Feature", "properties": {"class": "major", "sidewalk": f["properties"]["sidewalk"], "name": f["properties"]["name"]},
              "geometry": {"type": "LineString", "coordinates": [[round(x, 4), round(y, 4)] for x, y in f["geometry"]["coordinates"]]}}
             for f in uniq if f["properties"]["class"] == "major"]
    json.dump({"type": "FeatureCollection", "features": major}, open(os.path.join(OUT, "..", "roads_major.geojson"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump({"tile": TILE, "tiles": sorted(tiles.keys())}, open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"))
    print("타일 {}개 -> {} / 큰길 {}개 -> roads_major.geojson".format(len(tiles), OUT, len(major)))


if __name__ == "__main__":
    sys.exit(main())
