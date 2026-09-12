"""K-apt(공동주택관리정보시스템) 단지 목록 + 기본정보 -> data/raw/kapt.json
세대수 / 동수 / 최고층 / 사용승인일을 실거래 단지에 붙인다.

  python pipeline/fetch_kapt.py --sgg 11440

data.go.kr 에서 두 API 모두 활용신청 필요 (키는 동일):
  - 국토교통부_공동주택 단지 목록제공 서비스  https://www.data.go.kr/data/15057332/openapi.do
  - 국토교통부_공동주택 기본 정보제공 서비스  https://www.data.go.kr/data/15058453/openapi.do
서비스 경로가 개편으로 바뀌는 일이 있어 후보 URL 을 순서대로 시도한다.
"""
import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_trades import load_env, RAW  # noqa: E402

OUT = os.path.join(RAW, "kapt.json")
LIST_URLS = [
    "https://apis.data.go.kr/1613000/AptListService4/getSigunguAptList4",
    "https://apis.data.go.kr/1613000/AptListService3/getSigunguAptList3",
    "https://apis.data.go.kr/1613000/AptListService3/getSigunguAptList",
    "https://apis.data.go.kr/1613000/AptListService2/getSigunguAptList",
    "http://apis.data.go.kr/1611000/AptListService/getSigunguAptList",
]
BASIS_URLS = [
    "https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusBassInfoV5",
    "https://apis.data.go.kr/1613000/AptBasisInfoServiceV4/getAphusBassInfoV4",
    "https://apis.data.go.kr/1613000/AptBasisInfoServiceV3/getAphusBassInfoV3",
    "https://apis.data.go.kr/1613000/AptBasisInfoServiceV2/getAphusBassInfoV2",
    "http://apis.data.go.kr/1611000/AptBasisInfoService/getAphusBassInfo",
]
STRIP = re.compile(r"(아파트|APT|apt|\(.*?\)|\s|·|-|_|,)")


def norm(n):
    return STRIP.sub("", n).lower()


def items(resp_text):
    """XML 또는 JSON 응답에서 item 목록과 오류 여부를 뽑는다."""
    t = resp_text.strip()
    if t.startswith("{"):
        j = json.loads(t)
        hdr = j.get("OpenAPI_ServiceResponse", {}).get("cmmMsgHeader")
        if hdr:
            return [], 0, hdr.get("errMsg")
        body = (j.get("response") or {}).get("body") or {}
        its = body.get("items") if body.get("items") is not None else body.get("item")
        if isinstance(its, dict) and "item" in its:
            its = its["item"]
        if isinstance(its, dict):
            its = [its]
        return its or [], int(body.get("totalCount") or 0), None
    root = ET.fromstring(t)
    err = root.findtext(".//errMsg") or root.findtext(".//returnAuthMsg")
    if err:
        return [], 0, err
    out = []
    for it in root.iter("item"):
        out.append({c.tag: (c.text or "").strip() for c in it})
    return out, int(root.findtext(".//totalCount") or 0), None


def call(urls, key, params):
    last = None
    for url in urls:
        p = dict(params, serviceKey=key, _type="json")
        r = None
        for attempt in range(3):
            try:
                r = requests.get(url, params=p, timeout=30)
                if r.status_code < 500:
                    break
            except Exception as e:  # noqa
                last = "{} -> {}".format(url, e)
            time.sleep(1.5)
        if r is None:
            continue
        if r.status_code == 200 and "NO_OPENAPI_SERVICE_ERROR" not in r.text and "SERVICE_KEY_IS_NOT_REGISTERED" not in r.text:
            its, total, err = items(r.text)
            if err:
                last = "{} -> {}".format(url, err)
                continue
            return url, its, total
        last = "{} -> {} {}".format(url, r.status_code, r.text[:120].replace("\n", " "))
    raise SystemExit("K-apt API 실패 (활용신청 확인): {}".format(last))


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--sgg", default="11440")
    a = ap.parse_args()
    key = os.environ.get("DATA_GO_KR_KEY", "")
    if not key:
        raise SystemExit("DATA_GO_KR_KEY 없음")
    cache = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}

    # 1) 단지 목록
    url, its, total = call(LIST_URLS, key, {"sigunguCode": a.sgg, "pageNo": 1, "numOfRows": 1000})
    print("목록 API:", url, "총", total)
    page, allitems = 2, list(its)
    while len(allitems) < total and its:
        _, its, _ = call([url], key, {"sigunguCode": a.sgg, "pageNo": page, "numOfRows": 1000})
        allitems += its
        page += 1
    print("단지 {}개".format(len(allitems)))

    # 2) 기본정보 (캐시)
    burl = None
    for i, it in enumerate(allitems):
        code = it.get("kaptCode") or it.get("kaptcode")
        name = it.get("kaptName") or it.get("kaptname")
        if not code or code in cache:
            continue
        u, bits, _ = call([burl] if burl else BASIS_URLS, key, {"kaptCode": code})
        burl = u
        b = bits[0] if bits else {}
        g = lambda *ks: next((b[k] for k in ks if b.get(k) not in (None, "")), "")  # noqa: E731
        cache[code] = {
            "name": name, "norm": norm(name), "bjd": it.get("bjdCode") or it.get("bjdcode") or "",
            "as3": it.get("as3") or "", "addr": g("kaptAddr", "kaptaddr"),
            "households": int(float(g("kaptdaCnt", "kaptdacnt") or 0)), "dongs": int(float(g("kaptDongCnt", "kaptdongcnt") or 0)),
            "top_floor": int(str(g("kaptTopFloor", "kapttopfloor") or 0).split(".")[0] or 0),
            "usedate": g("kaptUsedate", "kaptusedate"),
            "sale_type": g("codeSaleNm", "codesalenm"),      # 분양 / 임대 / 혼합
            "heat": g("codeHeatNm", "codeheatnm"),
            "hall": g("codeHallNm", "codehallnm"),          # 계단식 / 복도식 / 혼합식
        }
        if (i + 1) % 25 == 0:
            json.dump(cache, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print("  {}/{}".format(i + 1, len(allitems)))
        time.sleep(0.1)
    json.dump(cache, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("기본정보 {}개 -> {}".format(len(cache), OUT))


if __name__ == "__main__":
    sys.exit(main())
