"""국토교통부 아파트 매매 실거래가 API -> data/raw/trades_<LAWD>_<YM>.json

사용:
  python pipeline/fetch_trades.py --lawd 11440 --months 24
  (11440 = 서울 마포구. 시군구 코드 5자리)

환경변수 DATA_GO_KR_KEY 필요 (공공데이터포털 > 국토교통부_아파트 매매 실거래가 자료 활용신청).
키가 없으면 안내만 출력하고 종료한다. 이 경우 build.py 는 demo_data.py 의 데모 데이터로 돈다.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import xml.etree.ElementTree as ET

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"


def load_env():
    p = os.path.join(HERE, "..", ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def month_list(n):
    today = dt.date.today().replace(day=1)
    out = []
    for i in range(n):
        y, m = today.year, today.month - i
        while m <= 0:
            y -= 1
            m += 12
        out.append("{:04d}{:02d}".format(y, m))
    return out


def text(item, tag):
    el = item.find(tag)
    return (el.text or "").strip() if el is not None else ""


def parse(xml_text):
    root = ET.fromstring(xml_text)
    code = root.findtext("./header/resultCode")
    if code not in (None, "00", "000"):
        raise RuntimeError("API 오류 {}: {}".format(code, root.findtext("./header/resultMsg")))
    rows = []
    for it in root.iter("item"):
        if text(it, "cdealType") == "O":      # 해제된 거래 제외
            continue
        amt = text(it, "dealAmount").replace(",", "")
        rows.append({
            "apt": text(it, "aptNm"),
            "umd": text(it, "umdNm"),
            "jibun": text(it, "jibun"),
            "sgg_cd": text(it, "sggCd"),
            "built": int(text(it, "buildYear") or 0),
            "area": float(text(it, "excluUseAr") or 0),
            "floor": int(text(it, "floor") or 0),
            "price": int(amt or 0),               # 만원
            "date": "{}-{:02d}-{:02d}".format(text(it, "dealYear"), int(text(it, "dealMonth") or 1), int(text(it, "dealDay") or 1)),
            "dong": text(it, "aptDong"),
            "kind": text(it, "dealingGbn"),       # 중개거래/직거래
        })
    total = int(root.findtext("./body/totalCount") or 0)
    return rows, total


def fetch_month(key, lawd, ym):
    rows, page = [], 1
    while True:
        r = requests.get(URL, params={
            "serviceKey": key, "LAWD_CD": lawd, "DEAL_YMD": ym, "pageNo": page, "numOfRows": 1000,
        }, timeout=30)
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
    ap.add_argument("--months", type=int, default=24)
    a = ap.parse_args()
    key = os.environ.get("DATA_GO_KR_KEY", "")
    if not key:
        print("DATA_GO_KR_KEY 가 없습니다. .env 에 키를 넣으면 실데이터를 받습니다. (지금은 데모 데이터로 빌드하세요: python pipeline/build.py)")
        return 0
    os.makedirs(RAW, exist_ok=True)
    for ym in month_list(a.months):
        out = os.path.join(RAW, "trades_{}_{}.json".format(a.lawd, ym))
        if os.path.exists(out) and ym != month_list(1)[0]:
            continue                                  # 지난 달은 캐시
        rows = fetch_month(key, a.lawd, ym)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
        print("{} {} {}건".format(a.lawd, ym, len(rows)))
        time.sleep(0.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
