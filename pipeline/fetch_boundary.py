"""OSM 행정경계(시군구) 폴리곤을 받아 data/raw/boundary_<이름>.geojson 으로 저장.

  python pipeline/fetch_boundary.py --name 마포구

geocode 결과가 해당 구 안에 있는지 검증하는 데 쓴다 (bbox 에 이웃 구가 섞여 오매칭되는 것 방지).
"""
import argparse
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
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
        except Exception as e:  # noqa
            last = "{} -> {}".format(url, e)
        time.sleep(8)
    raise SystemExit("Overpass 실패: {}".format(last))


def stitch(ways):
    """outer way 조각들을 끝점 기준으로 이어 붙여 링 목록을 만든다."""
    segs = [[(p["lon"], p["lat"]) for p in w["geometry"]] for w in ways if w.get("geometry")]
    rings = []
    while segs:
        ring = segs.pop(0)
        changed = True
        while changed and ring[0] != ring[-1]:
            changed = False
            for i, s in enumerate(segs):
                if s[0] == ring[-1]:
                    ring += s[1:]
                elif s[-1] == ring[-1]:
                    ring += list(reversed(s))[1:]
                elif s[-1] == ring[0]:
                    ring = s[:-1] + ring
                elif s[0] == ring[0]:
                    ring = list(reversed(s))[:-1] + ring
                else:
                    continue
                segs.pop(i)
                changed = True
                break
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        rings.append(ring)
    return rings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="마포구")
    ap.add_argument("--level", default="6")
    a = ap.parse_args()
    q = '[out:json][timeout:90];rel["boundary"="administrative"]["admin_level"="{}"]["name"="{}"];out geom;'.format(a.level, a.name)
    data = overpass(q)
    rels = [el for el in data.get("elements", []) if el["type"] == "relation"]
    if not rels:
        raise SystemExit("경계를 찾지 못함: {}".format(a.name))
    rel = rels[0]
    outers = [m for m in rel.get("members", []) if m["type"] == "way" and m.get("role", "outer") in ("outer", "")]
    rings = stitch(outers)
    rings.sort(key=len, reverse=True)
    gj = {"type": "Feature", "properties": {"name": a.name},
          "geometry": {"type": "Polygon", "coordinates": [[[round(x, 6), round(y, 6)] for x, y in rings[0]]]}}
    out = os.path.join(RAW, "boundary_{}.geojson".format(a.name))
    os.makedirs(RAW, exist_ok=True)
    json.dump(gj, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print("{} 경계 점 {}개 (링 {}개 중 최대) -> {}".format(a.name, len(rings[0]), len(rings), out))


if __name__ == "__main__":
    sys.exit(main())
