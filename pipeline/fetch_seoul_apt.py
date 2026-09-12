"""서울 열린데이터광장 '서울시 공동주택 아파트 정보'(OpenAptInfo) 전체 -> data/raw/seoul_apt.json

  python pipeline/fetch_seoul_apt.py

SEOUL_KEY 필요 (data.seoul.go.kr 로그인 > 인증키 신청, 즉시 발급).
K-apt 보다 범위가 넓고(의무관리 아닌 단지 포함, 서울 약 2,900개) 좌표(XCRD/YCRD)·분양/임대/혼합(HH_TYPE)·세대수(TNOHSH)·
동수·주차대수(PRK_CNTOM)·복도식(ROAD_TYPE)·면적별 세대수(XUAR_HH_STTS60/85/135/136)가 있다.
build.py 에서 좌표 150m 이내 + 이름 유사로 실거래 단지와 매칭한다.
"""
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_trades import load_env, RAW  # noqa: E402

OUT = os.path.join(RAW, "seoul_apt.json")


def main():
    load_env()
    key = os.environ.get("SEOUL_KEY", "")
    if not key:
        raise SystemExit("SEOUL_KEY 없음 (.env). https://data.seoul.go.kr 에서 인증키 신청")
    rows, start, step = [], 1, 1000
    while True:
        url = "http://openapi.seoul.go.kr:8088/{}/json/OpenAptInfo/{}/{}/".format(key, start, start + step - 1)
        r = requests.get(url, timeout=60)
        j = r.json()
        body = j.get("OpenAptInfo")
        if not body:
            raise SystemExit("API 오류: {}".format(str(j)[:300]))
        got = body.get("row") or []
        rows += got
        total = int(body.get("list_total_count") or 0)
        print("  {}/{}".format(len(rows), total))
        if len(rows) >= total or not got:
            break
        start += step
        time.sleep(0.3)
    slim = []
    for r in rows:
        try:
            lat, lng = float(r.get("YCRD") or 0), float(r.get("XCRD") or 0)
        except ValueError:
            lat = lng = 0
        slim.append({
            "code": r.get("APT_CD"), "name": (r.get("APT_NM") or "").strip(), "gu": r.get("SGG_ADDR", ""), "umd": r.get("EMD_ADDR", ""),
            "addr": r.get("APT_STDG_ADDR") or r.get("APT_RDN_ADDR", ""), "lat": lat, "lng": lng,
            "hh_type": r.get("HH_TYPE", ""), "households": int(float(r.get("TNOHSH") or 0)), "dongs": int(float(r.get("WHOL_DONG_CNT") or 0)),
            "parking": int(float(r.get("PRK_CNTOM") or 0)), "hall": r.get("ROAD_TYPE", ""), "heat": r.get("MN_MTHD", ""),
            "usedate": (r.get("USE_APRV_YMD") or "")[:10], "mandatory": r.get("SE_CD", ""),
            "hh_60": int(float(r.get("XUAR_HH_STTS60") or 0)), "hh_85": int(float(r.get("XUAR_HH_STTS85") or 0)),
            "hh_135": int(float(r.get("XUAR_HH_STTS135") or 0)), "hh_136": int(float(r.get("XUAR_HH_STTS136") or 0)),
        })
    json.dump(slim, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("서울 아파트 {}개 -> {}".format(len(slim), OUT))


if __name__ == "__main__":
    sys.exit(main())
