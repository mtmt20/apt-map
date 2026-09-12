"""실거래 raw 에 나오는 단지(법정동|단지명|지번)를 카카오 주소검색으로 좌표화 -> data/raw/geocode.json

  python pipeline/geocode.py [--sgg "서울 마포구"]

KAKAO_REST_API_KEY 필요. 이미 좌표가 있는 키는 건너뛴다(캐시).
세대수/최고층/용적률은 여기서 못 구함 (K-apt 공동주택 API 붙이기 전까지 0).
"""
import argparse
import glob
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
OUT = os.path.join(RAW, "geocode.json")
URL = "https://dapi.kakao.com/v2/local/search/address.json"
KW_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


def load_env():
    p = os.path.join(HERE, "..", ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def kakao(url, key, query):
    r = requests.get(url, params={"query": query, "size": 1}, headers={"Authorization": "KakaoAK " + key}, timeout=15)
    if r.status_code != 200:
        print("  kakao {} {}: {}".format(r.status_code, query, r.text[:120]))
        return None
    docs = r.json().get("documents", [])
    return docs[0] if docs else None


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--sgg", default="서울 마포구")
    ap.add_argument("--redo-osm", action="store_true", help="OSM 이름매칭 좌표를 카카오 주소검색 결과로 덮어쓰기")
    a = ap.parse_args()
    key = os.environ.get("KAKAO_REST_API_KEY", "")
    if not key:
        raise SystemExit("KAKAO_REST_API_KEY 없음 (.env)")
    geo = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    keys = {}
    for fp in glob.glob(os.path.join(RAW, "trades_*.json")):
        for r in json.load(open(fp, encoding="utf-8")):
            keys["{}|{}|{}".format(r["umd"], r["apt"], r["jibun"])] = r
    todo = [k for k in keys if k not in geo or (a.redo_osm and geo[k].get("src", "").startswith("osm"))]
    print("단지 {}개 중 좌표 필요 {}개".format(len(keys), len(todo)))
    ok = fail = 0
    for i, k in enumerate(todo):
        umd, apt, jibun = k.split("|")
        q = "{} {} {}".format(a.sgg, umd, jibun)
        d = kakao(URL, key, q)
        src = "address"
        if not d:                                          # 지번 주소로 안 잡히면 단지명 키워드 검색
            d = kakao(KW_URL, key, "{} {} {}".format(a.sgg, umd, apt))
            src = "keyword"
        if d:
            geo[k] = {"lat": float(d["y"]), "lng": float(d["x"]), "sgg": a.sgg.split()[-1],
                      "addr": d.get("address_name") or d.get("road_address_name") or q,
                      "households": 0, "max_floor": 0, "far": 0, "src": src}
            ok += 1
        else:
            fail += 1
            print("  좌표 실패:", k)
        if (i + 1) % 20 == 0:
            json.dump(geo, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print("  {}/{} ...".format(i + 1, len(todo)))
        time.sleep(0.08)
    json.dump(geo, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("완료: 성공 {} 실패 {} -> {}".format(ok, fail, OUT))


if __name__ == "__main__":
    sys.exit(main())
