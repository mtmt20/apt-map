"""K-apt 공동주택 관리비 -> data/raw/mgmt_cost.json (단지코드 -> 세대당 월 부담액)

  python pipeline/fetch_mgmt_cost.py                 # 하루 예산만큼 이어서 수집
  python pipeline/fetch_mgmt_cost.py --budget 400    # 호출 예산 줄이기
  python pipeline/fetch_mgmt_cost.py --month 202606  # 기준 월 지정

data.go.kr 활용신청 2건 필요 (키는 실거래가와 동일, 2026-09-28 승인 완료):
  - 국토교통부_공동주택관리비(공용관리비)   https://www.data.go.kr/data/15057937/openapi.do
  - 국토교통부_공동주택관리비(개별사용료)   https://www.data.go.kr/data/15059469/openapi.do

왜 이렇게 쪼개 받나:
  공용관리비 API 는 인건비·청소비·경비비 등 **17개 오퍼레이션으로 나뉘어 있다.**
  단지 하나의 총액을 구하려면 17번을 불러야 하고, 단지가 3,400개라 5만 8천 번이 된다.
  개발계정 한도는 하루 1,000번이다. 그래서
    (1) 금액이 큰 항목만 고른다 - 인건비·경비·청소·위탁수수료가 공용관리비의 대부분이다
    (2) 개별사용료는 수도·전기·가스·난방만 받는다 (사용자 요청: 수도·가스 포함)
    (3) 받은 단지는 mgmt_cost.json 에 남겨 다시 받지 않는다. 관리비는 월 단위 자료다
  결과적으로 단지당 8번, 하루 예산만큼만 돌면서 며칠에 걸쳐 전체를 채운다.

주의:
  **일부 항목만 합한 값이므로 실제 고지서 금액보다 적다.** 화면에 그 사실을 적어야 한다.
"""
import argparse
import datetime as dt
import io
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_trades import RAW, load_env  # noqa: E402

OUT = os.path.join(RAW, "mgmt_cost.json")
KAPT = os.path.join(RAW, "kapt.json")
CMN = "https://apis.data.go.kr/1613000/AptCmnuseManageCostServiceV3/"
IND = "https://apis.data.go.kr/1613000/AptIndvdlzManageCostServiceV3/"

# 공용관리비: 금액이 큰 항목만. (전체 17개를 다 받으면 단지당 17콜이라 한도를 넘는다)
CMN_OPS = [
    ("인건비", "getHsmpLaborCostInfoV3"),
    ("경비비", "getHsmpGuardCostInfoV3"),
    ("청소비", "getHsmpCleaningCostInfoV3"),
    ("위탁수수료", "getHsmpConsignManageFeeInfoV3"),
]
# 개별사용료: 수도·전기·가스·난방
IND_OPS = [
    ("수도", "getHsmpWaterCostInfoV3"),
    ("전기", "getHsmpElectricityCostInfoV3"),
    ("가스", "getHsmpGasRentalFeeInfoV3"),
    ("난방", "getHsmpHeatCostInfoV3"),
]


def call(key, url, kapt_code, ym):
    """한 번 끊겼다고 전체가 죽으면 며칠치 수집이 날아간다. 세 번까지 다시 시도한다."""
    body, r = "", None
    for attempt in range(3):
        try:
            r = requests.get(url, params={"serviceKey": key, "kaptCode": kapt_code, "searchDate": ym}, timeout=30)
            body = r.text or ""
            break
        except requests.RequestException:
            if attempt == 2:
                return None
            time.sleep(3 * (attempt + 1))
    if r is None:
        return None
    if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in body:
        raise SystemExit("일일 트래픽(1,000회)을 다 썼습니다. 내일 이어서 받습니다.")
    if r.status_code != 200 or "NO_OPENAPI" in body:
        return None
    try:
        item = r.json()["response"]["body"].get("item")
    except Exception:
        return None
    if not isinstance(item, dict):
        return None
    total = 0
    for k, v in item.items():
        if k in ("kaptCode", "kaptName"):
            continue
        sv = str(v).strip()
        if sv.lstrip("-").isdigit():
            total += int(sv)
    return total


def load(path, default):
    if os.path.exists(path):
        try:
            return json.load(io.open(path, encoding="utf-8"))
        except Exception:
            pass
    return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=900, help="이번 실행에서 쓸 최대 호출 수")
    ap.add_argument("--month", default="", help="기준 월 YYYYMM (기본: 두 달 전)")
    ap.add_argument("--refresh", action="store_true", help="이미 받은 단지도 다시 받기")
    a = ap.parse_args()
    load_env()
    key = os.environ.get("DATA_GO_KR_KEY")
    if not key:
        print(".env 의 DATA_GO_KR_KEY 가 없습니다.")
        return 1

    # 관리비 공시는 두어 달 늦게 올라온다
    if a.month:
        ym = a.month
    else:
        d = dt.date.today().replace(day=1) - dt.timedelta(days=62)
        ym = d.strftime("%Y%m")

    kapt = load(KAPT, {})
    if not kapt:
        print("data/raw/kapt.json 이 없습니다. fetch_kapt.py 를 먼저 돌리세요.")
        return 1
    out = load(OUT, {})
    todo = [c for c in kapt if a.refresh or c not in out or out[c].get("ym") != ym]
    print("단지 {}개 중 받을 것 {}개 (기준 {})".format(len(kapt), len(todo), ym))

    calls = ok = 0
    per = len(CMN_OPS) + len(IND_OPS)
    for code in todo:
        if calls + per > a.budget:
            print("예산 소진. 남은 {}개는 다음 실행에서 받습니다.".format(len(todo) - ok))
            break
        hh = (kapt[code].get("households") or 0)
        if hh < 1:
            out[code] = {"ym": ym, "skip": "세대수 없음"}
            continue
        cmn, ind, miss = 0, 0, 0
        for _, op in CMN_OPS:
            v = call(key, CMN + op, code, ym)
            calls += 1
            if v is None:
                miss += 1
            else:
                cmn += v
            time.sleep(0.08)
        for _, op in IND_OPS:
            v = call(key, IND + op, code, ym)
            calls += 1
            if v is None:
                miss += 1
            else:
                ind += v
            time.sleep(0.08)
        if miss == per or (cmn + ind) == 0:
            out[code] = {"ym": ym, "skip": "자료 없음"}
            continue
        out[code] = {
            "ym": ym, "hh": hh,
            "cmn_hh": round(cmn / hh),          # 세대당 월 공용관리비(주요 항목 합)
            "ind_hh": round(ind / hh),          # 세대당 월 개별사용료(수도·전기·가스·난방)
            "total_hh": round((cmn + ind) / hh),
        }
        ok += 1
        if ok % 25 == 0:
            json.dump(out, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
            print("  {}개 수집 (호출 {})".format(ok, calls))

    json.dump(out, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    got = [v for v in out.values() if v.get("total_hh")]
    if got:
        vals = sorted(v["total_hh"] for v in got)
        print("완료: 이번에 {}개 · 누적 {}개 · 호출 {}회".format(ok, len(got), calls))
        print("세대당 월 관리비 중앙값 {:,}원 (최저 {:,} · 최고 {:,})".format(
            vals[len(vals) // 2], vals[0], vals[-1]))
    else:
        print("완료: 수집된 단지가 없습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
