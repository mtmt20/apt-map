"""키 없이 OSM(Overpass) 아파트 단지명 매칭으로 좌표를 채운다 -> data/raw/geocode.json (기존 항목은 유지)

  python pipeline/geocode_osm.py [--bbox S,W,N,E] [--sgg "서울 마포구"]

카카오 주소검색(geocode.py)이 막혀 있을 때의 대안. 이름이 짧거나 흔한 단지(예: '우성')는 매칭이 안 될 수 있다.
"""
import argparse
import difflib
import glob
import json
import os
import re
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
OUT = os.path.join(RAW, "geocode.json")
DEFAULT_BBOX = "37.520,126.860,37.605,126.975"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
HEADERS = {"User-Agent": "apt-map-mvp/0.1 (personal project)"}

STRIP = re.compile(r"(아파트|APT|apt|\(.*?\)|\s|·|-|_|,)")


def norm(name):
    n = STRIP.sub("", name)
    n = n.replace("아이파크", "IPARK").replace("IPARK", "아이파크")  # 그대로 두되 대소문자 통일
    return n.lower()


def overpass(query):
    last = None
    for url in OVERPASS_URLS:
        try:
            r = requests.post(url, data={"data": query}, timeout=150, headers=HEADERS)
            if r.status_code == 200:
                return r.json()
            last = "{} -> {}".format(url, r.status_code)
            print("  실패", last)
        except Exception as e:  # noqa
            last = "{} -> {}".format(url, e)
        time.sleep(8)
    raise SystemExit("Overpass 실패: {}".format(last))


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


def load_boundary(sgg_name):
    p = os.path.join(RAW, "boundary_{}.geojson".format(sgg_name))
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))["geometry"]["coordinates"][0]


def fetch_osm_apts(bbox):
    cache = os.path.join(RAW, "osm_apts_{}.json".format(bbox.replace(",", "_")))
    if os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    out = _fetch_osm_apts(bbox)
    json.dump(out, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    return out


def _fetch_osm_apts(bbox):
    q = """
[out:json][timeout:120];
(
  nwr["building"~"^(apartments|residential)$"]["name"]({bbox});
  nwr["landuse"="residential"]["name"]({bbox});
  nwr["residential"="apartment"]["name"]({bbox});
  nwr["place"~"^(neighbourhood|quarter)$"]["name"~"아파트|자이|래미안|푸르지오|아이파크|힐스테이트|e편한|더샵|롯데캐슬|센트럴|타워"]({bbox});
);
out center tags;
""".format(bbox=bbox)
    data = overpass(q)
    out = {}
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name:
            continue
        if el["type"] == "node":
            lat, lng = el["lat"], el["lon"]
        elif "center" in el:
            lat, lng = el["center"]["lat"], el["center"]["lon"]
        else:
            continue
        out.setdefault(norm(name), []).append({"name": name, "lat": lat, "lng": lng, "dong": tags.get("addr:neighbourhood") or tags.get("addr:district") or ""})
    return out


def match(apt, umd, osm):
    key = norm(apt)
    cands = []
    if key in osm:
        cands = osm[key]
    else:
        # 포함 관계 (동 이름 접두 허용: '마포래미안푸르지오' vs '래미안푸르지오')
        for k, v in osm.items():
            if len(key) >= 4 and (key in k or k in key):
                cands.extend(v)
        if not cands and len(key) >= 5:
            best = difflib.get_close_matches(key, list(osm.keys()), n=1, cutoff=0.82)
            if best:
                cands = osm[best[0]]
    if not cands and umd:
        stem = umd[:-1] if umd.endswith("동") else umd
        for alt in (norm(stem + apt), norm(umd + apt)):
            if alt in osm:
                cands = osm[alt]
                break
        if not cands:
            for k, v in osm.items():
                if k.startswith(norm(stem)) and k[len(norm(stem)):] == key:
                    cands.extend(v)
    if not cands:
        return None
    # 여러 개면 동 이름이 맞는 것 우선, 아니면 첫 번째
    for c in cands:
        if umd and umd in (c["dong"] or ""):
            return c
    return cands[0] if len(cands) == 1 or len(key) >= 5 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", default=DEFAULT_BBOX)
    ap.add_argument("--sgg", default="서울 마포구")
    a = ap.parse_args()
    geo = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    keys = {}
    for fp in glob.glob(os.path.join(RAW, "trades_*.json")):
        for r in json.load(open(fp, encoding="utf-8")):
            keys["{}|{}|{}".format(r["umd"], r["apt"], r["jibun"])] = r
    todo = [k for k in keys if k not in geo]
    print("단지 {}개 중 좌표 필요 {}개, OSM 조회 중...".format(len(keys), len(todo)))
    osm = fetch_osm_apts(a.bbox)
    print("OSM 이름 있는 주거 건물/단지 {}개".format(sum(len(v) for v in osm.values())))
    ring = load_boundary(a.sgg.split()[-1])
    if ring:
        before = sum(len(v) for v in osm.values())
        osm = {k: [c for c in v if point_in_ring(c["lng"], c["lat"], ring)] for k, v in osm.items()}
        osm = {k: v for k, v in osm.items() if v}
        print("경계 필터: {} -> {}개 (구 밖 제외)".format(before, sum(len(v) for v in osm.values())))
        # 이미 저장된 좌표 중 구 밖인 것도 제거
        bad = [k for k, g in geo.items() if not point_in_ring(g["lng"], g["lat"], ring)]
        for k in bad:
            del geo[k]
        if bad:
            print("기존 좌표 {}개가 구 밖이라 제거".format(len(bad)))
        todo = [k for k in keys if k not in geo]
    else:
        print("경고: 경계 파일 없음 (fetch_boundary.py) - 이웃 구 오매칭 가능")
    ok, miss = 0, []
    for k in todo:
        umd, apt, jibun = k.split("|")
        m = match(apt, umd, osm)
        if m:
            geo[k] = {"lat": m["lat"], "lng": m["lng"], "sgg": a.sgg.split()[-1],
                      "addr": "{} {} {}".format(a.sgg, umd, jibun), "households": 0, "max_floor": 0, "far": 0,
                      "src": "osm:" + m["name"]}
            ok += 1
        else:
            miss.append(k)
    json.dump(geo, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("매칭 {} / 미매칭 {} -> {}".format(ok, len(miss), OUT))
    for k in miss[:40]:
        print("  미매칭:", k)


if __name__ == "__main__":
    sys.exit(main())
