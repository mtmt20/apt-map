"""주요 생활시설 좌표 수집 (OSM Overpass) -> data/raw/amenities_osm.json

  python pipeline/fetch_amenities.py [--bbox S,W,N,E]

kind: hospital(병원, amenity=hospital), clinic_ped(소아과, healthcare:speciality~paediatrics 또는 이름 소아),
      mart(대형마트, shop=supermarket 중 이마트/홈플러스/롯데마트/코스트코/트레이더스 + shop=department_store/mall),
      kindergarten(어린이집·유치원, amenity=kindergarten|childcare), library(도서관), park(공원 leisure=park, 면적 2천㎡ 이상, 중심점+면적),
      university(대학), school(초중고는 이미 별도 파일 -> 생략)
"""
import argparse
import json
import math
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_trades import RAW  # noqa: E402

OUT = os.path.join(RAW, "amenities_osm.json")
DEFAULT_BBOX = "37.425,126.760,37.705,127.190"
URLS = ["https://overpass-api.de/api/interpreter", "https://lz4.overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
HEADERS = {"User-Agent": "apt-map-mvp/0.1 (personal project)"}
BIG_MARTS = ("이마트", "홈플러스", "롯데마트", "코스트코", "트레이더스", "하나로마트", "메가마트", "킴스클럽")

QUERIES = {
    "hospital": 'nwr["amenity"="hospital"]({bbox});',
    "clinic_ped": 'nwr["amenity"~"^(clinic|doctors)$"]["name"~"소아"]({bbox}); nwr["healthcare:speciality"~"paediatrics"]({bbox});',
    "mart": 'nwr["shop"="supermarket"]({bbox}); nwr["shop"~"^(department_store|mall)$"]({bbox});',
    "kindergarten": 'nwr["amenity"~"^(kindergarten|childcare)$"]({bbox});',
    "library": 'nwr["amenity"="library"]({bbox});',
    "park": 'way["leisure"="park"]({bbox}); relation["leisure"="park"]({bbox});',
    "university": 'nwr["amenity"="university"]({bbox});',
    "playground": 'nwr["leisure"="playground"]({bbox});',
    "police": 'nwr["amenity"="police"]({bbox});',
    "emergency": 'nwr["amenity"="hospital"]["emergency"="yes"]({bbox});',
}


def overpass(q):
    last = None
    for u in URLS:
        try:
            r = requests.post(u, data={"data": q}, timeout=180, headers=HEADERS)
            if r.status_code == 200:
                return r.json()
            last = "{} {}".format(u, r.status_code)
        except Exception as e:  # noqa
            last = "{} {}".format(u, e)
        time.sleep(10)
    raise SystemExit("Overpass 실패: " + str(last))


def ring_area_m2(coords, lat0):
    kx, ky = 111320.0 * math.cos(math.radians(lat0)), 110540.0
    s = 0.0
    for i in range(len(coords) - 1):
        x1, y1 = coords[i][0] * kx, coords[i][1] * ky
        x2, y2 = coords[i + 1][0] * kx, coords[i + 1][1] * ky
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", default=DEFAULT_BBOX)
    a = ap.parse_args()
    out = {}
    for kind, body in QUERIES.items():
        q = "[out:json][timeout:170];({});out center geom tags;".format(body.format(bbox=a.bbox))
        data = overpass(q)
        items = []
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            name = tags.get("name", "")
            if kind == "mart":
                big = tags.get("shop") in ("department_store", "mall") or any(b in name for b in BIG_MARTS)
                if not big or "익스프레스" in name or "에브리데이" in name:
                    continue
            c = el.get("center") or ({"lat": el.get("lat"), "lon": el.get("lon")} if el.get("lat") else None)
            if not c and el.get("bounds"):
                b = el["bounds"]; c = {"lat": (b["minlat"] + b["maxlat"]) / 2, "lon": (b["minlon"] + b["maxlon"]) / 2}
            if not c and el.get("geometry"):
                g = el["geometry"]; c = {"lat": sum(p["lat"] for p in g) / len(g), "lon": sum(p["lon"] for p in g) / len(g)}
            if not c or not c.get("lat"):
                continue
            rec = {"name": name, "lat": round(c["lat"], 6), "lng": round(c["lon"], 6)}
            if kind == "park":
                geom = el.get("geometry")
                if geom and len(geom) >= 4:
                    ring = [[p["lon"], p["lat"]] for p in geom]
                    area = ring_area_m2(ring, c["lat"])
                    if area < 2000:
                        continue
                    rec["area_m2"] = int(area)
                    rec["ring"] = [[round(x, 5), round(y, 5)] for x, y in ring[:: max(1, len(ring) // 60)]] + [[round(ring[0][0], 5), round(ring[0][1], 5)]]
                else:
                    continue
            if kind == "hospital":
                rec["beds"] = tags.get("beds", "")
            items.append(rec)
        out[kind] = items
        print("{:12s} {}".format(kind, len(items)))
        time.sleep(6)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("->", OUT)


if __name__ == "__main__":
    sys.exit(main())
