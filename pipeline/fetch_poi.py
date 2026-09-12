"""OSM Overpass에서 지하철역 + 초등학교 위치를 받아 data/raw/poi.json 으로 저장.

  python pipeline/fetch_poi.py [--bbox S,W,N,E]

초등학교 '통학구역'은 공식 데이터(학구도안내서비스)가 붙기 전까지
최근접 학교 기준 보로노이(Voronoi) 영역으로 추정한다 (build.py 에서 계산).
"""
import argparse
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "raw", "poi.json")
DEFAULT_BBOX = "37.520,126.860,37.605,126.975"   # 서울 마포구 전역 + 여유

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
HEADERS = {"User-Agent": "apt-map-mvp/0.1 (personal project)"}


def overpass(query):
    last = None
    for url in OVERPASS_URLS:
        try:
            r = requests.post(url, data={"data": query}, timeout=120, headers=HEADERS)
            if r.status_code == 200:
                return r.json()
            last = "{} -> {}".format(url, r.status_code)
            print("  실패", last)
        except Exception as e:  # noqa
            last = "{} -> {}".format(url, e)
        time.sleep(8)
    raise SystemExit("Overpass 실패: {}".format(last))


def center(el, nodes):
    if el["type"] == "node":
        return el["lat"], el["lon"]
    if "center" in el:
        return el["center"]["lat"], el["center"]["lon"]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", default=DEFAULT_BBOX)
    a = ap.parse_args()
    q = """
[out:json][timeout:90];
(
  node["railway"="station"]["station"="subway"]({bbox});
  node["railway"="station"]["subway"="yes"]({bbox});
  node["public_transport"="station"]["subway"="yes"]({bbox});
  nwr["amenity"="school"]["name"~"초등학교"]({bbox});
);
out center tags;
""".format(bbox=a.bbox)
    print("Overpass POI 요청 bbox={}".format(a.bbox))
    data = overpass(q)
    stations, schools, seen = [], [], set()
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        c = center(el, None)
        if not name or not c:
            continue
        if tags.get("railway") == "station" or tags.get("public_transport") == "station":
            key = ("st", name)
            if key in seen:
                continue
            seen.add(key)
            line = tags.get("line") or tags.get("subway:lines") or tags.get("network") or ""
            stations.append({"name": name if name.endswith("역") else name + "역", "line": line, "lat": c[0], "lng": c[1]})
        elif "초등학교" in name:
            key = ("sc", name)
            if key in seen or "병설" in name or "부설" in name:
                continue
            seen.add(key)
            schools.append({"name": name, "lat": c[0], "lng": c[1]})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"bbox": a.bbox, "stations": stations, "elem_schools": schools},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("역 {}개, 초등학교 {}개 -> {}".format(len(stations), len(schools), OUT))
    for s in schools[:8]:
        print("  ", s["name"])


if __name__ == "__main__":
    sys.exit(main())
