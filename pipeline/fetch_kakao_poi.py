"""카카오 로컬 API로 단지 주변(반경) 육아·생활 편의시설 개수 집계 -> data/raw/kakao_poi.json

  python pipeline/fetch_kakao_poi.py

단지 키(법정동|단지명|지번)별로 {daycare, pediatric, hospital, mart, park, cafe} 개수를 저장.
이미 집계된 단지는 건너뛴다. KAKAO_REST_API_KEY 필요.
"""
import glob
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_trades import load_env, RAW  # noqa: E402

OUT = os.path.join(RAW, "kakao_poi.json")
CAT = "https://dapi.kakao.com/v2/local/search/category.json"
KW = "https://dapi.kakao.com/v2/local/search/keyword.json"

# (필드, 방식, 코드/키워드, 반경m)
QUERIES = [
    ("daycare", "cat", "PS3", 700),        # 어린이집·유치원
    ("pediatric", "kw", "소아과", 1000),
    ("hospital", "cat", "HP8", 700),
    ("pharmacy", "cat", "PM9", 500),
    ("mart", "cat", "MT1", 1000),          # 대형마트
    ("convenience", "cat", "CS2", 300),
    ("park", "kw", "공원", 700),
    ("library", "kw", "도서관", 1000),
]


def count(key, how, q, lat, lng, radius):
    url = CAT if how == "cat" else KW
    params = {"x": lng, "y": lat, "radius": radius, "size": 1}
    params["category_group_code" if how == "cat" else "query"] = q
    for _ in range(3):
        r = requests.get(url, params=params, headers={"Authorization": "KakaoAK " + key}, timeout=15)
        if r.status_code == 200:
            return r.json()["meta"]["total_count"]
        time.sleep(1)
    return None


def main():
    load_env()
    key = os.environ.get("KAKAO_REST_API_KEY", "")
    if not key:
        raise SystemExit("KAKAO_REST_API_KEY 없음")
    geo = json.load(open(os.path.join(RAW, "geocode.json"), encoding="utf-8"))
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    todo = [k for k in geo if k not in out]
    print("단지 {}개 중 집계 필요 {}개 (쿼리 {}종)".format(len(geo), len(todo), len(QUERIES)))
    for i, k in enumerate(todo):
        g = geo[k]
        rec = {}
        for field, how, q, radius in QUERIES:
            rec[field] = count(key, how, q, g["lat"], g["lng"], radius)
            time.sleep(0.04)
        out[k] = rec
        if (i + 1) % 20 == 0:
            json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
            print("  {}/{}".format(i + 1, len(todo)))
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("완료 -> {}".format(OUT))


if __name__ == "__main__":
    sys.exit(main())
