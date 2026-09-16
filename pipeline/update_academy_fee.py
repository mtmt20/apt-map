"""이미 받아둔 data/raw/academies_<구>.json 에 교육청 공시 '교습비'를 채워 넣는다.

  python pipeline/update_academy_fee.py [--gu 강남구,노원구]

학원 좌표는 그대로 두고(지오코딩 재실행 없음) NEIS acaInsTiInfo 의 PSNBY_THCC_CNTNT 만 다시 받아
학원명+주소로 매칭해 fee(과목별 월 교습비 중앙값, 원)를 넣는다.
"""
import argparse
import glob
import json
import os
import re
import statistics
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_trades import load_env, RAW  # noqa: E402

URL = "https://open.neis.go.kr/hub/acaInsTiInfo"


def fee_median(txt):
    """'문법 영어:268000, 리딩:268000' -> 268000 (과목별 월 교습비 중앙값)."""
    vals = [int(m) for m in re.findall(r":\s*(\d{4,7})", txt or "")]
    vals = [v for v in vals if 30000 <= v <= 3000000]
    return int(statistics.median(vals)) if vals else None


def norm(s):
    return re.sub(r"\s+", "", (s or "")).lower()


def fetch_gu(key, gu):
    """구 단위 전체 학원 -> {(학원명, 주소): fee}"""
    out, page = {}, 1
    while page <= 12:
        r = requests.get(URL, timeout=60, params={"KEY": key, "Type": "json", "pIndex": page, "pSize": 1000,
                                                  "ATPT_OFCDC_SC_CODE": "B10", "ADMST_ZONE_NM": gu})
        try:
            body = r.json()["acaInsTiInfo"]
        except Exception:
            break
        rows = next((b["row"] for b in body if "row" in b), [])
        if not rows:
            break
        for x in rows:
            f = fee_median(x.get("PSNBY_THCC_CNTNT"))
            if f:
                out[(norm(x.get("ACA_NM")), norm(x.get("FA_RDNMA")))] = f
        if len(rows) < 1000:
            break
        page += 1
        time.sleep(0.3)
    return out


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--gu", default="", help="쉼표 구분, 비우면 data/raw 의 모든 구")
    a = ap.parse_args()
    key = os.environ.get("NEIS_KEY") or os.environ.get("NEIS_API_KEY")
    if not key:
        raise SystemExit("NEIS_KEY 없음 (.env)")
    files = ([os.path.join(RAW, "academies_{}.json".format(g)) for g in a.gu.split(",") if g]
             or sorted(glob.glob(os.path.join(RAW, "academies_*.json"))))
    tot_hit = tot = 0
    for path in files:
        gu = os.path.basename(path).replace("academies_", "").replace(".json", "")
        acas = json.load(open(path, encoding="utf-8"))
        fees = fetch_gu(key, gu)
        hit = 0
        for c in acas:
            f = fees.get((norm(c.get("name")), norm(c.get("addr"))))
            c["fee"] = f
            hit += 1 if f else 0
        json.dump(acas, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        edu = [c["fee"] for c in acas if c.get("fee") and "입시" in (c.get("realm") or "")]
        med = int(statistics.median(edu)) if edu else 0
        print("{:6} 학원 {:5}개 중 교습비 {:5}개  교과학원 중앙값 {:>9,}원".format(gu, len(acas), hit, med))
        tot_hit += hit
        tot += len(acas)
    print("전체 {}개 중 {}개에 교습비 ({}%)".format(tot, tot_hit, round(tot_hit / max(1, tot) * 100)))


if __name__ == "__main__":
    main()
