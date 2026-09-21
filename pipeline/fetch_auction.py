"""온비드(캠코) 공매 물건 수집 -> data/raw/auction_onbid.json + auction_history.jsonl

  python pipeline/fetch_auction.py                 # 개찰 예정 공고에서 서울 주거용 물건 수집
  python pipeline/fetch_auction.py --days 60       # 개찰일 창 넓히기
  python pipeline/fetch_auction.py --budget 300    # 하루 호출 예산 줄이기

환경변수 DATA_GO_KR_KEY 를 쓴다. 아래 3건을 data.go.kr 에서 추가 활용신청해야 한다(무료·자동승인).
  - 한국자산관리공사_차세대 온비드 공고목록 조회서비스        (data.go.kr/data/15157216)
  - 한국자산관리공사_차세대 온비드 공고상세 물건정보 조회서비스 (data.go.kr/data/15157220)
  - 한국자산관리공사_차세대 온비드 부동산 물건상세 조회서비스  (data.go.kr/data/15157247)
2026-09-21 세 건 모두 승인 완료.

왜 공매(온비드)만 넣는가:
  법원경매(courtauction.go.kr)는 공식 오픈API가 없어서 화면을 긁어야 하는데, 사이트 이용약관이
  자동수집을 막고 있다. 네이버부동산과 같은 이유로 이 프로젝트는 법원경매를 수집하지 않는다.
  온비드 공매는 정부가 공식 API 로 개방한 자료라 약관 문제가 없다.

트래픽:
  개발계정은 서비스당 하루 1,000회다. 공고 하나에 물건이 200~1,200개씩 들어있어 100개씩
  페이징하면 금방 소진된다. 그래서 이미 받아본 공고는 auction_seen.json 에 기록해 두고
  새 공고만 받는다. 한 번 실행에 --budget 회까지만 호출하고, 남은 공고는 다음 날 이어받는다.

이력:
  실행할 때마다 물건별 스냅샷을 auction_history.jsonl 에 덧붙인다. 같은 물건의 최저입찰가가
  회차마다 떨어지는 과정이 쌓이면 유찰 횟수 대비 하락폭, 낙찰가율을 계산할 수 있다.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_trades import RAW, load_env  # noqa: E402

OUT = os.path.join(RAW, "auction_onbid.json")
SEEN = os.path.join(RAW, "auction_seen.json")
HIST = os.path.join(RAW, "auction_history.jsonl")
BASE = "https://apis.data.go.kr/B010003"
LIST_OP = "OnbidPbancListSrvc2/getPbancList2"
DTL_OP = "OnbidPbancCltrDtlSrvc2/getPbancCltrInf2"
RLST_OP = "OnbidRlstDtlSrvc2/getRlstDtlInf2"

# 재산유형: 압류재산(세금 체납)이 물량의 대부분이고, 금융권담보·수탁재산도 매각 물건이다.
PRPT = {"0007": "압류재산", "0003": "금융권담보재산", "0008": "수탁재산"}
# 주거용으로 볼 소분류 (cltrUsgSclsCtgrNm)
HOME_USE = ("아파트", "다세대주택", "연립주택", "도시형생활주택", "오피스텔", "기타주거용건물")


def get(key, op, params, timeout=30):
    r = requests.get("{}/{}".format(BASE, op), params=dict(params, serviceKey=key), timeout=timeout)
    body = r.text or ""
    if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in body:
        raise SystemExit("일일 트래픽(1,000회)을 다 썼습니다. 내일 이어서 받습니다.")
    if "SERVICE_KEY_IS_NOT_REGISTERED" in body or "NO_OPENAPI_SERVICE_ERROR" in body:
        raise SystemExit("활용신청이 안 된 서비스입니다: " + op)
    return body


def items(xml):
    return re.findall(r"<item>(.*?)</item>", xml, re.S)


def field(it, name):
    m = re.search(r"<{0}>([^<]*)</{0}>".format(name), it)
    return (m.group(1) or "").strip() if m else ""


def total(xml):
    m = re.search(r"<totalCount>(\d+)</totalCount>", xml)
    return int(m.group(1)) if m else 0


def ymd(v):
    return "{}-{}-{}".format(v[0:4], v[4:6], v[6:8]) if len(v) >= 8 else ""


def parse_unit(addr):
    """주소 끝의 '제101동 제1503호' 같은 부분만 떼어낸다."""
    m = re.search(r"(제?\s*\d+동)?\s*(제?\s*\d+호)\s*$", addr)
    return re.sub(r"\s+", "", m.group(0)) if m else ""


def norm(it, prpt_nm):
    adr = field(it, "cltrAdr") or field(it, "onbidCltrNm")
    return {
        "case": field(it, "cltrMngNo"),
        "cltr_no": field(it, "onbidCltrno"),
        "cdtn_no": field(it, "pbctCdtnNo"),
        "pbanc": field(it, "pbancMngNo"),
        "round": field(it, "pbctNsq"),
        "addr": adr,
        "unit": parse_unit(adr),
        "use": field(it, "cltrUsgSclsCtgrNm"),
        "kind": prpt_nm,
        "appraisal": int(field(it, "apslEvlAmt") or 0),                 # 감정가(원)
        "min_price": int(field(it, "lowstBidPrcIndctCont") or 0),       # 최저입찰가(원)
        "min_rate": int(field(it, "apslPrcCtrsLowstBidRto") or 0),      # 감정가 대비 %
        "bid_begin": ymd(field(it, "cltrBidBgngDt")),
        "bid_end": ymd(field(it, "cltrBidEndDt")),
        "status": field(it, "pbctStatNm"),
        "source": "온비드",
    }


def load(path, default):
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            pass
    return default


STATUS = {"0001": "입찰예정", "0002": "입찰중", "0011": "유찰", "0012": "낙찰", "0021": "취소"}


def enrich(key, rows, budget, today):
    """진행 중·예정 물건만 부동산 물건상세로 다시 받는다.

    공고상세 쪽 주소는 압류재산이면 ***** 로 가려져 있어 단지를 못 찾는다. 이 서비스는
    지번주소·도로명·법정동코드(PNU)·건물면적·유찰횟수까지 가려지지 않은 채로 준다.
    대신 '현재 입찰 중이거나 예정인 물건'만 조회되므로 대상이 적어 호출도 적게 든다.
    """
    used = 0
    for r in rows:
        if used >= budget or not r.get("case"):
            continue
        if r.get("status") == "취소" or (r.get("bid_end") or "") < today:
            continue
        if r.get("addr") and "*" not in r["addr"] and r.get("area"):
            continue
        try:
            xml = get(key, RLST_OP, {"numOfRows": 1, "pageNo": 1, "cltrMngNo": r["case"]}, timeout=25)
        except SystemExit:
            break
        used += 1
        its = items(xml)
        if not its:
            continue
        it = its[0]
        zadr = field(it, "zadrNm") or field(it, "onbidCltrNm")
        area = field(it, "bldSqms")
        r.update({
            "addr": zadr or r.get("addr", ""),
            "road_addr": field(it, "cltrRadr"),
            "unit": parse_unit(zadr) or r.get("unit", ""),
            "sgg": field(it, "lctnSggnm"),
            "umd": field(it, "lctnEmdNm"),
            "pnu": field(it, "ltnoPnu"),
            "fail_count": int(field(it, "usbdNft") or 0),
            "status": STATUS.get(field(it, "pbctStatCd"), r.get("status", "")),
            "appraised_at": field(it, "apslEvlYmd"),
            "note": field(it, "utlzPscdCont"),
        })
        if area:
            try:
                r["area"] = round(float(area), 2)
            except ValueError:
                pass
        time.sleep(0.12)
    return used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=45, help="개찰일 기준 오늘부터 며칠 뒤까지")
    ap.add_argument("--budget", type=int, default=700, help="이번 실행에서 쓸 최대 API 호출 수")
    ap.add_argument("--all-regions", action="store_true", help="서울 외 지역도 저장")
    a = ap.parse_args()

    load_env()
    key = os.environ.get("DATA_GO_KR_KEY")
    if not key:
        print(".env 의 DATA_GO_KR_KEY 가 없습니다.")
        return 1
    os.makedirs(RAW, exist_ok=True)

    today = dt.date.today()
    s, e = today.strftime("%Y%m%d"), (today + dt.timedelta(days=a.days)).strftime("%Y%m%d")
    seen = load(SEEN, {})
    rows = {r["cltr_no"]: r for r in load(OUT, []) if r.get("cltr_no")}
    calls = 0

    # 1) 개찰 예정 공고 목록
    pbancs = []
    for cd, nm in PRPT.items():
        page = 1
        while calls < a.budget:
            xml = get(key, LIST_OP, {"numOfRows": 100, "pageNo": page, "cltrTypeCd": "0001",
                                     "prptDivCd": cd, "opbdDtStart": s, "opbdDtEnd": e})
            calls += 1
            its = items(xml)
            for it in its:
                pbancs.append((field(it, "pbancMngNo"), nm))
            if page * 100 >= total(xml) or not its:
                break
            page += 1
            time.sleep(0.2)
    todo = [(m, nm) for m, nm in pbancs if m and m not in seen]
    print("공고 {}건 (새 공고 {}건), 목록 호출 {}회".format(len(pbancs), len(todo), calls))

    # 2) 새 공고의 물건 상세를 페이지 단위로 받는다. 예산이 떨어지면 남긴 채로 끝낸다.
    new_items, left = 0, 0
    for i, (mng, nm) in enumerate(todo):
        if calls >= a.budget:
            left = len(todo) - i
            break
        page, tot = 1, None
        while calls < a.budget:
            xml = get(key, DTL_OP, {"numOfRows": 100, "pageNo": page, "pbancMngNo": mng})
            calls += 1
            tot = total(xml) if tot is None else tot
            its = items(xml)
            for it in its:
                if field(it, "cltrUsgLclsCtgrNm") != "부동산" or field(it, "dspsMthodNm") != "매각":
                    continue
                adr = field(it, "cltrAdr") or field(it, "onbidCltrNm")
                if not a.all_regions and not adr.startswith("서울"):
                    continue
                if field(it, "cltrUsgSclsCtgrNm") not in HOME_USE:
                    continue
                r = norm(it, nm)
                if r["cltr_no"]:
                    if r["cltr_no"] not in rows:
                        new_items += 1
                    rows[r["cltr_no"]] = dict(rows.get(r["cltr_no"], {}), **r)
            if not its or page * 100 >= (tot or 0):
                seen[mng] = today.isoformat()
                break
            page += 1
            time.sleep(0.15)
    if left:
        print("예산 소진. 남은 공고 {}건은 다음 실행에서 받습니다.".format(left))

    # 3) 지난 물건 정리. 입찰 종료가 30일 넘게 지난 건 목록에서 뺀다(이력에는 남는다).
    cut = (today - dt.timedelta(days=30)).isoformat()
    keep = [r for r in rows.values() if not r["bid_end"] or r["bid_end"] >= cut]
    used = enrich(key, keep, 300, today.isoformat())
    live = [r for r in keep if r.get("status") != "취소" and (r.get("bid_end") or "") >= today.isoformat()]
    live.sort(key=lambda r: (r["bid_end"] or "", r["addr"]))
    json.dump(live, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(seen, open(SEEN, "w", encoding="utf-8"), ensure_ascii=False)
    with open(HIST, "a", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(dict(r, snap=today.isoformat()), ensure_ascii=False) + "\n")

    by_use = {}
    for r in live:
        by_use[r["use"]] = by_use.get(r["use"], 0) + 1
    print("서울 주거용 공매 진행 중 {}건 (수집 {}건), 상세 조회 {}회, 총 호출 {}회 -> {}".format(
        len(live), len(keep), used, calls + used, OUT))
    print("용도별:", ", ".join("{} {}".format(k, v) for k, v in sorted(by_use.items(), key=lambda x: -x[1])) or "없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
