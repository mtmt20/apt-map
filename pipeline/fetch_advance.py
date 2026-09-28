# -*- coding: utf-8 -*-
"""학교알리미 '졸업생의 진로 현황'(공시항목 06) -> data/raw/advance.json

  python pipeline/fetch_advance.py --sgg 11500              # 강서구만
  python pipeline/fetch_advance.py --knd 03 --budget 300    # 중학교, 요청 300건까지

왜 OpenAPI 가 아니라 여기인가:
  학교알리미 OpenAPI 에는 고등학교용 apiType 26개 어디에도 진학률이 없다(2024~2026 전부 확인).
  '공개용 데이터' 일괄 파일에도 없다. 진학률은 웹 공시정보에만 있다.

받는 경로 (2026-09-28 확인, 캡챠 없음 - 캡챠는 '첨부파일 다운로드'에만 걸려 있다):
  1) POST /ei/ss/pneiss_a05_s0/selectSchoolListLocation.do
     HG_JONGRYU_GB=04(고)/03(중), SIDO_CODE, SIGUNGU_CODE, SULRIP_GB=1,2,3, GS_HANGMOK_CD=06
     -> {"schoolList":[{SHL_IDF_CD(uuid), SHL_NM, SHL_CD, ADDR_CD_ID, ...}]}
  2) POST /ei/pp/Pneipp_b06_s0p.do
     SHL_IDF_CD, GS_HANGMOK_CD=06, GS_BURYU_CD=JG040, JG_BURYU_CD=JG130, JG_HANGMOK_CD=52,
     JG_YEAR=2025, JG_CHASU=4  -> HTML 표

고등학교 표: 졸업자 / 전문대학 / 대학교 / 국외진학 / 취업자 / 기타 + '비 율' 행
중학교 표:   졸업자 / 일반고 / 특성화고 / 특수목적고 / 자율고 / 기타

예의:
  정부 사이트다. 요청 간격을 넉넉히 두고, 받은 학교는 다시 받지 않는다.
  한 번에 다 긁지 말고 refresh.py 가 매일 예산만큼만 이어받게 한다.
"""
import argparse
import io
import json
import os
import re
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_trades import RAW, load_env  # noqa: E402  (load_env 는 쓰지 않지만 RAW 경로를 공유)

BASE = "https://www.schoolinfo.go.kr"
LIST_URL = BASE + "/ei/ss/pneiss_a05_s0/selectSchoolListLocation.do"
VIEW_URL = BASE + "/ei/pp/Pneipp_b06_s0p.do"
OUT = os.path.join(RAW, "advance.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 apt-map/0.1",
    "Referer": BASE + "/ei/ss/pneiss_a05_s0.do",
    "X-Requested-With": "XMLHttpRequest",
}

# 고등학교 졸업생 진로: 비율 행의 순서
HIGH_COLS = ["jncll", "univ", "ocnty", "emplo_sub", "emplo", "etc"]
# 중학교 졸업생 진로: 비율 행의 순서
MID_COLS = ["gnrl", "chrtr", "spcly", "slctl", "etc"]


def school_list(s, knd, sgg):
    """시군구 하나의 학교 목록(UUID 포함)."""
    sido = sgg[:2] + "00000000"
    data = [("HG_JONGRYU_GB", knd), ("SIDO_CODE", sido), ("SIGUNGU_CODE", sgg + "00000"),
            ("SULRIP_GB", "1"), ("SULRIP_GB", "2"), ("SULRIP_GB", "3"),
            ("GS_HANGMOK_CD", "06"), ("JG_HANGMOK_CD", "52")]
    r = s.post(LIST_URL, data=data, headers=HEADERS, timeout=40)
    try:
        return r.json().get("schoolList") or []
    except ValueError:
        return []


def nums(row_html):
    """표 한 행에서 숫자만 뽑는다."""
    cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S)
    out = []
    for c in cells:
        t = re.sub(r"<[^>]+>", "", c).replace(",", "").strip()
        if re.match(r"^-?\d+(\.\d+)?$", t):
            out.append(float(t))
    return out


def fetch_one(s, uuid, name, year, knd):
    data = {"SHL_IDF_CD": uuid, "HG_NM": name, "GS_BURYU_CD": "JG040", "GS_HANGMOK_CD": "06",
            "JG_BURYU_CD": "JG130", "JG_HANGMOK_CD": "52", "GS_HANGMOK_NO": "13-다",
            "GS_HANGMOK_NM": "졸업생의 진로 현황", "JG_YEAR": str(year), "JG_CHASU": "4",
            "adminYN": "N", "SORT": "", "POP_YN": "", "PRE_JG_YEAR": str(year), "LOAD_TYPE": "single"}
    r = s.post(VIEW_URL, data=data, headers=HEADERS, timeout=40)
    if r.status_code != 200:
        return None
    html = r.text
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    grad = ratio = None
    for row in rows:
        txt = re.sub(r"<[^>]+>", " ", row)
        flat = re.sub(r"\s+", "", txt)
        if flat.startswith("합계") and grad is None:
            v = nums(row)
            if v:
                grad = int(v[0])          # 졸업자
        if flat.startswith("비율"):
            ratio = nums(row)
    if not ratio:
        return None
    cols = HIGH_COLS if knd == "04" else MID_COLS
    rec = {"grad": grad, "year": year}
    for i, c in enumerate(cols):
        if i < len(ratio):
            rec[c] = ratio[i]
    if knd == "04":
        # 총 진학률 = 전문대 + 대학교 + 국외진학
        rec["adv"] = round(sum(rec.get(k) or 0 for k in ("jncll", "univ", "ocnty")), 1)
    else:
        rec["adv_spcly"] = round((rec.get("spcly") or 0) + (rec.get("slctl") or 0), 1)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--knd", default="04", help="04 고등학교, 03 중학교")
    ap.add_argument("--year", default="2025")
    ap.add_argument("--sgg", default="", help="쉼표로 구분한 시군구 5자리. 비우면 전체")
    ap.add_argument("--budget", type=int, default=400, help="이번 실행에서 받을 학교 수")
    ap.add_argument("--sleep", type=float, default=1.2, help="요청 간격(초). 정부 사이트라 넉넉히")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    if a.sgg:
        sggs = [x.strip() for x in a.sgg.split(",") if x.strip()]
    else:
        from fetch_trades import SGG
        from gyeonggi_sgg import SGG as GG
        sggs = list(SGG) + list(GG)

    out = {}
    if os.path.exists(OUT):
        try:
            out = json.load(io.open(OUT, encoding="utf-8"))
        except Exception:
            out = {}

    s = requests.Session()
    s.get(BASE + "/ei/ss/pneiss_a05_s0.do", headers=HEADERS, timeout=30)   # 세션 쿠키

    got = skipped = 0
    for sgg in sggs:
        if got >= a.budget:
            break
        lst = school_list(s, a.knd, sgg)
        if not lst:
            print("  {} 학교 목록 없음".format(sgg))
            time.sleep(a.sleep)
            continue
        print("{} : 학교 {}개".format(sgg, len(lst)))
        for sc in lst:
            if got >= a.budget:
                print("  예산 소진. 남은 시군구는 다음 실행에서.")
                break
            uuid, name = sc.get("SHL_IDF_CD"), sc.get("SHL_NM")
            key = "{}_{}".format(a.knd, uuid)
            if not a.refresh and out.get(key, {}).get("year") == a.year:
                skipped += 1
                continue
            try:
                rec = fetch_one(s, uuid, name, a.year, a.knd)
            except requests.RequestException:
                time.sleep(5)
                continue
            got += 1
            if rec:
                rec.update(name=name, sgg=sgg, shl_cd=sc.get("SHL_CD"),
                           dong=sc.get("ADDR_CD_ID"), addr=sc.get("SHL_ROAD_NM_ADDR"))
                out[key] = rec
            else:
                out[key] = {"year": a.year, "name": name, "sgg": sgg, "skip": "자료 없음"}
            if got % 20 == 0:
                json.dump(out, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
                print("  {}개 수집".format(got))
            time.sleep(a.sleep)

    json.dump(out, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    ok = [v for v in out.values() if v.get("adv") is not None or v.get("adv_spcly") is not None]
    print("완료: 이번 {}개 · 건너뜀 {} · 누적 {}개 -> {}".format(got, skipped, len(ok), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
