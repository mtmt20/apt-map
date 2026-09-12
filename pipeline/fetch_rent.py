"""국토교통부 아파트 전월세 실거래가 API -> data/raw/rent_<LAWD>_<YM>.json

  python pipeline/fetch_rent.py --lawd 11440 --months 12

data.go.kr 에서 "국토교통부_아파트 전월세 실거래가 자료" 활용신청이 되어 있어야 한다 (매매와 별도 신청, 키는 동일).
전세가율(전세보증금 / 매매가)을 build.py 에서 계산하는 데 쓴다.
"""
import argparse
import json
import os
import sys
import time
import xml.etree.ElementTree as ET

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_trades import load_env, month_list, text, RAW  # noqa: E402

URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"


def parse(xml_text):
    root = ET.fromstring(xml_text)
    code = root.findtext("./header/resultCode")
    if code not in (None, "00", "000"):
        raise RuntimeError("API 오류 {}: {}".format(code, root.findtext("./header/resultMsg")))
    rows = []
    for it in root.iter("item"):
        dep = text(it, "deposit").replace(",", "")
        mon = text(it, "monthlyRent").replace(",", "")
        rows.append({
            "apt": text(it, "aptNm"), "umd": text(it, "umdNm"), "jibun": text(it, "jibun"),
            "built": int(text(it, "buildYear") or 0), "area": float(text(it, "excluUseAr") or 0),
            "floor": int(text(it, "floor") or 0),
            "deposit": int(dep or 0), "monthly": int(mon or 0),          # 만원
            "date": "{}-{:02d}-{:02d}".format(text(it, "dealYear"), int(text(it, "dealMonth") or 1), int(text(it, "dealDay") or 1)),
            "term": text(it, "contractTerm"), "kind": text(it, "contractType"),   # 신규/갱신
        })
    return rows, int(root.findtext("./body/totalCount") or 0)


def fetch_month(key, lawd, ym):
    rows, page = [], 1
    while True:
        r = requests.get(URL, params={"serviceKey": key, "LAWD_CD": lawd, "DEAL_YMD": ym, "pageNo": page, "numOfRows": 1000}, timeout=30)
        if r.status_code == 403 or "SERVICE_KEY_IS_NOT_REGISTERED" in r.text:
            raise SystemExit("전월세 API 활용신청이 안 되어 있습니다: https://www.data.go.kr/data/15126474/openapi.do 에서 활용신청 후 재시도")
        r.raise_for_status()
        got, total = parse(r.text)
        rows.extend(got)
        if len(rows) >= total or not got:
            break
        page += 1
        time.sleep(0.3)
    return rows


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--lawd", default="11440")
    ap.add_argument("--months", type=int, default=12)
    a = ap.parse_args()
    key = os.environ.get("DATA_GO_KR_KEY", "")
    if not key:
        raise SystemExit("DATA_GO_KR_KEY 없음")
    os.makedirs(RAW, exist_ok=True)
    for ym in month_list(a.months):
        out = os.path.join(RAW, "rent_{}_{}.json".format(a.lawd, ym))
        if os.path.exists(out) and ym != month_list(1)[0]:
            continue
        rows = fetch_month(key, a.lawd, ym)
        json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False)
        print("{} {} 전월세 {}건".format(a.lawd, ym, len(rows)))
        time.sleep(0.5)


if __name__ == "__main__":
    sys.exit(main())
