"""학교알리미(schoolinfo.go.kr) OpenAPI -> data/raw/schoolinfo/<apiType>_<schulKnd>_<year>.json

  python pipeline/fetch_schoolinfo.py --probe                 # apiType 0~120 을 훑어 어떤 항목이 있는지 목록 저장
  python pipeline/fetch_schoolinfo.py --types 0,XX,YY --knd 02,03 --year 2025 --sido 11 --sgg 11440

SCHOOLINFO_KEY 필요 (schoolinfo.go.kr > 알리미 소식 > OpenAPI > SNS 로그인 > API키 발급).
요청 형식: http://www.schoolinfo.go.kr/openApi.do?apiKey=..&apiType=0&sidoCode=11&sggCode=11440&schulKndCode=03&pbanYr=2025
schulKndCode: 02 초등, 03 중, 04 고. 응답: {resultCode, resultMsg, list:[...]}
"""
import argparse
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_trades import load_env, RAW  # noqa: E402

URL = "https://www.schoolinfo.go.kr/openApi.do"
OUT = os.path.join(RAW, "schoolinfo")
HEADERS = {"User-Agent": "Mozilla/5.0 apt-map-mvp/0.1"}


def call(key, api_type, knd, year=None, sido=None, sgg=None):
    p = {"apiKey": key, "apiType": str(api_type), "schulKndCode": knd}
    if year:
        p["pbanYr"] = str(year)
    if sido:
        p["sidoCode"] = str(sido)
    if sgg:
        p["sggCode"] = str(sgg)
    r = requests.get(URL, params=p, headers=HEADERS, timeout=60)
    try:
        return r.json()
    except ValueError:
        return {"resultCode": "parse-error", "resultMsg": r.text[:200]}


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--types", default="0")
    ap.add_argument("--knd", default="02,03")
    ap.add_argument("--year", default="")
    ap.add_argument("--sido", default="11")
    ap.add_argument("--sgg", default="11440", help="시군구 코드 (2026년부터 필수)")
    a = ap.parse_args()
    key = os.environ.get("SCHOOLINFO_KEY", "")
    if not key:
        raise SystemExit("SCHOOLINFO_KEY 없음 (.env). schoolinfo.go.kr > 알리미 소식 > OpenAPI 에서 발급")
    os.makedirs(OUT, exist_ok=True)

    if a.probe:
        found = {}
        for t in range(0, 121):
            j = call(key, t, "03", a.year or None, a.sido, a.sgg)
            lst = j.get("list") or []
            code, msg = j.get("resultCode"), j.get("resultMsg")
            if lst:
                keys = sorted(lst[0].keys())
                found[t] = {"count": len(lst), "fields": keys[:40]}
                print("apiType {:3d}: {}건, 필드 {}".format(t, len(lst), ", ".join(keys[:12])))
            else:
                print("apiType {:3d}: {} {}".format(t, code, (msg or "")[:60]))
            time.sleep(0.3)
        json.dump(found, open(os.path.join(OUT, "_probe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("-> {}".format(os.path.join(OUT, "_probe.json")))
        return

    for t in a.types.split(","):
        for knd in a.knd.split(","):
            j = call(key, t, knd, a.year or None, a.sido, a.sgg)
            lst = j.get("list") or []
            fn = os.path.join(OUT, "{}_{}_{}_{}.json".format(t, knd, a.sgg, a.year or "latest"))
            json.dump(lst, open(fn, "w", encoding="utf-8"), ensure_ascii=False)
            print("apiType {} knd {}: {}건 ({}) -> {}".format(t, knd, len(lst), j.get("resultMsg"), fn))
            time.sleep(0.3)


if __name__ == "__main__":
    sys.exit(main())
