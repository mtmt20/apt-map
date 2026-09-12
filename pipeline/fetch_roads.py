"""OSM Overpass에서 도로망을 받아 큰길/골목/인도 여부를 분류한 GeoJSON을 만든다.

사용: python pipeline/fetch_roads.py [--bbox S,W,N,E]
출력: app/data/roads.geojson

분류 규칙 (app에서 색상으로 씀)
  class = "major"  : 차 많이 다니는 길 (motorway/trunk/primary/secondary/tertiary)
  class = "minor"  : 동네 길 (unclassified/residential)
  class = "alley"  : 골목 (living_street/service/pedestrian)
  sidewalk = "yes" | "no" | "unknown"
    - OSM sidewalk 태그가 있으면 그대로
    - 없으면 major(2차로 이상)는 "likely" 로 추정 (한국 OSM은 sidewalk 태그가 거의 없음)
"""
import argparse
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "app", "data", "roads.geojson")

# 기본 데모 지역: 서울 마포구 공덕/아현/염리동 일대
DEFAULT_BBOX = "37.538,126.940,37.566,126.968"

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

MAJOR = {"motorway", "trunk", "primary", "secondary", "tertiary",
         "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
MINOR = {"unclassified", "residential"}
ALLEY = {"living_street", "service", "pedestrian"}


def classify(tags):
    hw = tags.get("highway", "")
    if hw in MAJOR:
        cls = "major"
    elif hw in MINOR:
        cls = "minor"
    elif hw in ALLEY:
        cls = "alley"
    else:
        return None
    sw = tags.get("sidewalk", "")
    if sw in ("both", "left", "right", "yes", "separate"):
        sidewalk = "yes"
    elif sw in ("no", "none"):
        sidewalk = "no"
    elif tags.get("sidewalk:left") or tags.get("sidewalk:right") or tags.get("sidewalk:both"):
        sidewalk = "yes"
    elif cls == "major":
        sidewalk = "likely"      # 한국 큰길은 대부분 보도 있음 (추정)
    else:
        sidewalk = "unknown"
    try:
        lanes = int(tags.get("lanes", "0"))
    except ValueError:
        lanes = 0
    return {
        "class": cls,
        "highway": hw,
        "sidewalk": sidewalk,
        "lanes": lanes,
        "name": tags.get("name", ""),
        "oneway": tags.get("oneway", "no") == "yes",
    }


def fetch(bbox):
    query = """
[out:json][timeout:60];
(
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|pedestrian|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"]({bbox});
);
out body;
>;
out skel qt;
""".format(bbox=bbox)
    last = None
    for url in OVERPASS_URLS:
        try:
            r = requests.post(url, data={"data": query}, timeout=90, headers={"User-Agent": "apt-map-mvp/0.1 (personal project)"})
            if r.status_code == 200:
                return r.json()
            last = "{} -> {}".format(url, r.status_code)
            print("  실패", last)
        except Exception as e:  # noqa
            last = "{} -> {}".format(url, e)
        time.sleep(8)
    raise SystemExit("Overpass 실패: {}".format(last))


def to_geojson(osm):
    nodes = {}
    for el in osm.get("elements", []):
        if el["type"] == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])
    feats = []
    for el in osm.get("elements", []):
        if el["type"] != "way":
            continue
        props = classify(el.get("tags", {}))
        if not props:
            continue
        coords = [nodes[n] for n in el.get("nodes", []) if n in nodes]
        if len(coords) < 2:
            continue
        feats.append({
            "type": "Feature",
            "properties": props,
            "geometry": {"type": "LineString", "coordinates": coords},
        })
    return {"type": "FeatureCollection", "features": feats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", default=DEFAULT_BBOX, help="S,W,N,E")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    print("Overpass 요청 bbox={}".format(a.bbox))
    osm = fetch(a.bbox)
    gj = to_geojson(osm)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(gj, f, ensure_ascii=False, separators=(",", ":"))
    from collections import Counter
    c = Counter((f["properties"]["class"], f["properties"]["sidewalk"]) for f in gj["features"])
    print("도로 {}개 저장 -> {}".format(len(gj["features"]), a.out))
    for k, v in sorted(c.items()):
        print("  {:6s} sidewalk={:8s} {}".format(k[0], k[1], v))


if __name__ == "__main__":
    sys.exit(main())
