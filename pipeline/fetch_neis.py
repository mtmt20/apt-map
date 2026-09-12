"""나이스 교육정보 개방포털 -> 학원·교습소 / 초·중학교 (좌표 포함)

  python pipeline/fetch_neis.py --gu 마포구 --neighbors 서대문구,용산구,영등포구,은평구,종로구,중구

출력
  data/raw/academies.json   [{name, realm, course, kind, addr, lat, lng}]  (개원 상태만)
  data/raw/schools_neis.json {"elem": [...], "middle": [...]}  각 {name, code, addr, lat, lng, gu, public, coedu}

NEIS_KEY (open.neis.go.kr), KAKAO_REST_API_KEY (주소 -> 좌표) 필요. 좌표는 data/raw/geocache_addr.json 에 캐시.
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

NEIS = "https://open.neis.go.kr/hub/"
KAKAO = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KW = "https://dapi.kakao.com/v2/local/search/keyword.json"
CACHE = os.path.join(RAW, "geocache_addr.json")


def neis(op, key, **params):
    rows, page = [], 1
    while True:
        r = requests.get(NEIS + op, params=dict(params, KEY=key, Type="json", pIndex=page, pSize=1000), timeout=30)
        j = r.json()
        if op not in j:
            msg = j.get("RESULT", {}).get("MESSAGE", str(j)[:200])
            if "해당하는 데이터가 없습니다" in msg:
                break
            raise SystemExit("NEIS {} 오류: {}".format(op, msg))
        rows += j[op][1]["row"]
        total = j[op][0]["head"][0]["list_total_count"]
        if len(rows) >= total:
            break
        page += 1
        time.sleep(0.2)
    return rows


class Geocoder:
    def __init__(self, key):
        self.key = key
        self.cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
        self.n = 0

    def get(self, addr, fallback_kw=None):
        addr = " ".join(addr.split())
        if addr in self.cache:
            return self.cache[addr]
        res = None
        for url, q in ((KAKAO, addr), (KAKAO_KW, fallback_kw)):
            if not q:
                continue
            r = requests.get(url, params={"query": q, "size": 1}, headers={"Authorization": "KakaoAK " + self.key}, timeout=15)
            if r.status_code == 200 and r.json().get("documents"):
                d = r.json()["documents"][0]
                res = {"lat": float(d["y"]), "lng": float(d["x"])}
                break
            time.sleep(0.05)
        self.cache[addr] = res
        self.n += 1
        if self.n % 50 == 0:
            self.save()
        time.sleep(0.06)
        return res

    def save(self):
        json.dump(self.cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--gu", default="마포구")
    ap.add_argument("--neighbors", default="서대문구,용산구,영등포구,은평구,종로구,중구")
    ap.add_argument("--office", default="B10", help="교육청 코드 (B10=서울)")
    ap.add_argument("--sido", default="서울특별시")
    a = ap.parse_args()
    key, kkey = os.environ.get("NEIS_KEY", ""), os.environ.get("KAKAO_REST_API_KEY", "")
    if not key or not kkey:
        raise SystemExit("NEIS_KEY / KAKAO_REST_API_KEY 필요 (.env)")
    geo = Geocoder(kkey)

    # 1) 학원·교습소 (대상 구만)
    rows = neis("acaInsTiInfo", os.environ.get("NEIS_KEY_ACADEMY") or key, ATPT_OFCDC_SC_CODE=a.office, ADMST_ZONE_NM=a.gu)
    rows = [r for r in rows if r.get("REG_STTUS_NM") == "개원"]
    print("학원·교습소 {}개 (개원)".format(len(rows)))
    acas, miss = [], 0
    for i, r in enumerate(rows):
        addr = (r.get("FA_RDNMA") or "").strip()
        if not addr:
            miss += 1
            continue
        g = geo.get(addr)
        if not g:
            miss += 1
            continue
        acas.append({
            "name": r["ACA_NM"], "kind": r.get("ACA_INSTI_SC_NM", ""), "realm": r.get("REALM_SC_NM", ""),
            "course": r.get("LE_CRSE_NM", ""), "subjects": r.get("LE_CRSE_LIST_NM", ""), "addr": addr,
            "capacity": r.get("TOFOR_SMTOT") or 0, "lat": g["lat"], "lng": g["lng"],
        })
        if (i + 1) % 200 == 0:
            print("  학원 좌표 {}/{}".format(i + 1, len(rows)))
    geo.save()
    json.dump(acas, open(os.path.join(RAW, "academies.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("학원 좌표 {}개 저장 (실패 {})".format(len(acas), miss))

    # 2) 초·중학교 (대상 구 + 이웃 구)
    gus = [a.gu] + [g for g in a.neighbors.split(",") if g]
    out = {"elem": [], "middle": []}
    for kind, k in (("초등학교", "elem"), ("중학교", "middle")):
        rows = neis("schoolInfo", key, ATPT_OFCDC_SC_CODE=a.office, SCHUL_KND_SC_NM=kind, LCTN_SC_NM=a.sido)
        for r in rows:
            addr = (r.get("ORG_RDNMA") or "").strip()
            gu = next((g for g in gus if g in addr), None)
            if not gu:
                continue
            g = geo.get(addr, fallback_kw=r["SCHUL_NM"])
            if not g:
                continue
            out[k].append({
                "name": r["SCHUL_NM"], "code": r["SD_SCHUL_CODE"], "addr": addr, "gu": gu,
                "public": r.get("FOND_SC_NM", ""), "coedu": r.get("COEDU_SC_NM", ""),
                "lat": g["lat"], "lng": g["lng"],
            })
        print("{} {}개 ({}권역)".format(kind, len(out[k]), "+".join(gus)))
    geo.save()
    json.dump(out, open(os.path.join(RAW, "schools_neis.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.exit(main())
