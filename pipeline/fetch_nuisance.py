"""기피·주의 시설 수집 (OSM Overpass, 키 불필요) -> data/raw/nuisance_osm.json

  python pipeline/fetch_nuisance.py [--bbox S,W,N,E]

분류(kind)와 OSM 태그:
  substation   변전소            power=substation (node/way/rel, 이름 없어도 포함)
  powerline    고압 송전선       power=line (선: 좌표열 그대로 저장, 거리 계산용)
  landfill     매립장/소각장     landuse=landfill, amenity=waste_transfer_station, man_made=incinerator? (industrial=waste)
  wastewater   하수·분뇨 처리장  man_made=wastewater_plant
  crematorium  화장장·장례식장   amenity=crematorium, amenity=funeral_hall, shop=funeral_directors
  prison       교도소·구치소     amenity=prison
  military     군부대            landuse=military, military=*
  fuel         주유소·충전소     amenity=fuel
  nightlife    유흥(나이트·클럽·성인)  amenity=nightclub, amenity=stripclub, shop=erotic, amenity=love_hotel, tourism=love_hotel
  motel        모텔               tourism=motel, tourism=hotel + name~모텔
  rail         철도(지상)         railway=rail and not tunnel=yes (선)
  motorway     고속도로·자동차전용 highway=motorway|trunk (선)
유흥주점·단란주점 등 인허가 업소는 LOCALDATA(지방행정인허가) 로 별도 수집 (fetch_localdata.py, 사이트 복구 후).
"""
import argparse
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_trades import RAW  # noqa: E402

OUT = os.path.join(RAW, "nuisance_osm.json")
DEFAULT_BBOX = "37.425,126.760,37.705,127.190"
URLS = ["https://overpass-api.de/api/interpreter", "https://lz4.overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
HEADERS = {"User-Agent": "apt-map-mvp/0.1 (personal project)"}

QUERIES = {
    "substation": 'nwr["power"="substation"]({bbox});',
    "powerline": 'way["power"="line"]({bbox});',
    "landfill": 'nwr["landuse"="landfill"]({bbox}); nwr["amenity"="waste_transfer_station"]({bbox}); nwr["man_made"="incinerator"]({bbox}); nwr["industrial"="waste"]({bbox});',
    "wastewater": 'nwr["man_made"="wastewater_plant"]({bbox});',
    "crematorium": 'nwr["amenity"="crematorium"]({bbox}); nwr["amenity"="funeral_hall"]({bbox}); nwr["shop"="funeral_directors"]({bbox});',
    "prison": 'nwr["amenity"="prison"]({bbox});',
    "military": 'nwr["landuse"="military"]({bbox}); nwr["military"]({bbox});',
    "fuel": 'nwr["amenity"="fuel"]({bbox});',
    "nightlife": 'nwr["amenity"="nightclub"]({bbox}); nwr["amenity"="stripclub"]({bbox}); nwr["shop"="erotic"]({bbox}); nwr["amenity"="love_hotel"]({bbox}); nwr["tourism"="love_hotel"]({bbox});',
    "motel": 'nwr["tourism"="motel"]({bbox}); nwr["tourism"="hotel"]["name"~"모텔"]({bbox});',
    "rail": 'way["railway"="rail"]["tunnel"!="yes"]({bbox});',
    "motorway": 'way["highway"~"^(motorway|trunk)$"]({bbox});',
}
LINE_KINDS = {"powerline", "rail", "motorway"}


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
            if kind in LINE_KINDS:
                geom = el.get("geometry")
                if geom:
                    items.append({"name": name, "coords": [[round(p["lon"], 5), round(p["lat"], 5)] for p in geom], "tags": {k: tags[k] for k in ("voltage", "highway", "railway") if k in tags}})
            else:
                c = el.get("center") or ({"lat": el.get("lat"), "lon": el.get("lon")} if el.get("lat") else None)
                if c and c.get("lat"):
                    items.append({"name": name, "lat": round(c["lat"], 6), "lng": round(c["lon"], 6)})
        out[kind] = items
        print("{:12s} {}".format(kind, len(items)))
        time.sleep(6)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("->", OUT)


if __name__ == "__main__":
    sys.exit(main())
