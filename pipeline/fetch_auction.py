"""온비드(캠코) 공매 부동산 물건 수집 -> data/raw/auction_onbid.json

  python pipeline/fetch_auction.py --probe     # 서비스/오퍼레이션/응답 필드 확인 (활용신청 승인 직후 1회)
  python pipeline/fetch_auction.py             # 서울 아파트 공매 물건 수집

환경변수 DATA_GO_KR_KEY 를 쓴다. 단, 실거래가 API 와 별개로 아래 3건을 추가 활용신청해야 한다.
  - 한국자산관리공사_차세대 온비드 부동산 물건상세 조회서비스  (data.go.kr/data/15157247)
  - 한국자산관리공사_차세대 온비드 공고목록 조회서비스        (data.go.kr/data/15157216)
  - 한국자산관리공사_차세대 온비드 공고상세 물건정보 조회서비스 (data.go.kr/data/15157220)
모두 자동승인이고 무료다.

왜 공매(온비드)만 넣는가:
  법원경매(courtauction.go.kr)는 공식 오픈API가 없어서 화면을 긁어야 하는데, 사이트 이용약관이
  자동수집을 막고 있다. 네이버부동산과 같은 이유로 이 프로젝트는 법원경매를 수집하지 않는다.
  온비드 공매는 정부가 공식 API 로 개방한 자료라 약관 문제가 없다.
"""
import argparse
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_trades import RAW, load_env  # noqa: E402

OUT = os.path.join(RAW, "auction_onbid.json")
BASE = "https://apis.data.go.kr/B010003"

# data.go.kr 상세페이지에서 확인한 서비스/오퍼레이션.
# 승인 전에는 어느 조합이든 NO_OPENAPI_SERVICE_ERROR 라 구분이 안 되므로, 승인 후 --probe 로 확정한다.
SERVICES = {
    "pbanc_list": ("OnbidPbancListSrvc2", ["getPbancList"]),
    "pbanc_cltr": ("OnbidPbancCltrDtlSrvc2", ["getPbancCltrDtl", "getPbancCltrDtlInf"]),
    "rlst_detail": ("OnbidRlstDtlSrvc2", ["getRlstDtlInf"]),
    "rlst_list": ("OnbidRlstListSrvc2", ["getRlstList", "getRlstListInf", "getRlstLst"]),
    "bid_detail": ("OnbidCltrBidDtlSrvc2", ["getCltrBidDtl", "getCltrBidDtlInf"]),
}

SEOUL = "서울"
APT_WORDS = ("아파트", "연립", "다세대")


def call(key, svc, op, params=None, timeout=30):
    """(성공여부, 파싱된 응답 또는 에러문자열)"""
    p = {"serviceKey": key, "numOfRows": "10", "pageNo": "1", "type": "json"}
    p.update(params or {})
    url = "{}/{}/{}".format(BASE, svc, op)
    try:
        r = requests.get(url, params=p, timeout=timeout)
    except Exception as e:  # noqa
        return False, "요청 실패: {}".format(e)
    body = r.text or ""
    if "NO_OPENAPI_SERVICE_ERROR" in body:
        return False, "서비스 경로가 다르거나 활용신청이 안 됨"
    if "SERVICE_KEY_IS_NOT_REGISTERED" in body:
        return False, "이 서비스에 대한 활용신청 미승인"
    if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in body:
        return False, "일일 트래픽 초과"
    try:
        return True, r.json()
    except Exception:  # XML 로 돌아오는 경우
        return True, {"_raw_xml": body[:4000]}


def walk_keys(obj, prefix="", depth=0, acc=None):
    """응답 JSON 의 필드 경로를 모아 본다 (--probe 용)."""
    acc = acc if acc is not None else set()
    if depth > 6:
        return acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(prefix + k)
            walk_keys(v, prefix + k + ".", depth + 1, acc)
    elif isinstance(obj, list) and obj:
        walk_keys(obj[0], prefix, depth + 1, acc)
    return acc


def probe(key):
    found = {}
    for name, (svc, ops) in SERVICES.items():
        for op in ops:
            ok, res = call(key, svc, op)
            label = "{}/{}".format(svc, op)
            if ok:
                keys = sorted(walk_keys(res))
                found[name] = {"path": label, "fields": keys[:80]}
                print("OK   {:14s} {}".format(name, label))
                print("     필드 {}개: {}".format(len(keys), ", ".join(keys[:12])))
                break
            print("--   {:14s} {}  ({})".format(name, label, res))
            time.sleep(0.5)
    p = os.path.join(RAW, "auction_probe.json")
    if not os.path.isdir(RAW):
        os.makedirs(RAW)
    json.dump(found, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)
    if not found:
        print("\n활용신청이 아직 승인되지 않았거나 서비스 경로가 바뀌었습니다.")
        print("data.go.kr 에서 '차세대 온비드' 로 검색해 서비스명과 오퍼레이션을 확인하세요.")
    return 0


def items_of(res):
    """공공데이터 응답에서 item 리스트만 꺼낸다 (구조가 서비스마다 조금씩 다름)."""
    if not isinstance(res, dict):
        return []
    body = res.get("response", {}).get("body") or res.get("body") or res
    items = body.get("items") if isinstance(body, dict) else None
    if isinstance(items, dict):
        items = items.get("item")
    if isinstance(items, dict):
        items = [items]
    return items or []


def is_seoul_apt(rec):
    text = " ".join(str(v) for v in rec.values() if isinstance(v, (str, int, float)))
    return SEOUL in text and any(w in text for w in APT_WORDS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="서비스/오퍼레이션/응답 필드 확인")
    ap.add_argument("--pages", type=int, default=20, help="목록 페이지 수")
    ap.add_argument("--rows", type=int, default=100, help="페이지당 건수")
    a = ap.parse_args()

    load_env()
    key = os.environ.get("DATA_GO_KR_KEY")
    if not key:
        print(".env 의 DATA_GO_KR_KEY 가 없습니다.")
        return 1

    if a.probe:
        return probe(key)

    pp = os.path.join(RAW, "auction_probe.json")
    if not os.path.exists(pp):
        print("먼저 활용신청 승인 후 `python pipeline/fetch_auction.py --probe` 를 한 번 돌리세요.")
        print("(서비스 경로와 응답 필드명을 확정해 auction_probe.json 에 저장합니다)")
        return 1
    spec = json.load(open(pp, encoding="utf-8"))

    src = spec.get("rlst_list") or spec.get("pbanc_cltr")
    if not src:
        print("물건목록 서비스가 auction_probe.json 에 없습니다. --probe 결과를 확인하세요.")
        return 1
    svc, op = src["path"].split("/")

    rows, seen = [], set()
    for page in range(1, a.pages + 1):
        ok, res = call(key, svc, op, {"pageNo": str(page), "numOfRows": str(a.rows)})
        if not ok:
            print("{}쪽에서 중단: {}".format(page, res))
            break
        items = items_of(res)
        if not items:
            break
        for it in items:
            if not isinstance(it, dict) or not is_seoul_apt(it):
                continue
            uid = str(it.get("cltrMngNo") or it.get("CLTR_MNG_NO") or len(rows))
            if uid in seen:
                continue
            seen.add(uid)
            rows.append(it)
        print("{:3d}쪽 누적 {}건".format(page, len(rows)))
        time.sleep(0.4)

    if not os.path.isdir(RAW):
        os.makedirs(RAW)
    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("서울 아파트·연립 공매 {}건 -> {}".format(len(rows), OUT))
    if not rows:
        print("0건입니다. 온비드 공매는 법원경매보다 물량이 훨씬 적어 서울 아파트는 시기에 따라 없을 수 있습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
