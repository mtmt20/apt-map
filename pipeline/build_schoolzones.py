"""학구도안내서비스(한국교육시설안전원) 공식 학구도 shp -> data/raw/schoolzones_seoul.json

  python pipeline/build_schoolzones.py [--sido 11]

입력 (data/raw/schoolzone/, schoolzone.emac.kr 공공데이터 목록에서 받은 zip 을 풀어둔 것)
  elem_zone/elem_zone.shp    초등학교 통학구역 및 공동통학구역 (EPSG:5186, 중부원점 2010)
  middle_zone/middle_zone.shp 중학교 학구 및 학군
  link/link.csv              학구ID <-> 학교ID/학교명
  school_loc/school_loc.csv  학교ID -> 위경도
출력
  {"base_date":..., "elem":[{id,name,shared,schools:[{id,name,lat,lng}],rings:[[[lng,lat],...],...]}], "middle":[...]}
좌표계 변환은 pyproj 없이 TM 역변환(GRS80) 을 직접 계산 (검증: 강릉 경포초 -> 37.8066, 128.8583).
"""
import argparse
import csv
import io
import json
import math
import os
import sys

import shapefile

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
D = os.path.join(RAW, "schoolzone")

# ---- EPSG:5186 (Korea 2000 / Central Belt 2010) 역변환 ----
A = 6378137.0
F = 1 / 298.257222101
E2 = F * (2 - F)
EP2 = E2 / (1 - E2)
K0, FE, FN = 1.0, 200000.0, 600000.0
LAT0, LON0 = math.radians(38.0), math.radians(127.0)


def _m(phi):
    e4, e6 = E2 * E2, E2 ** 3
    return A * ((1 - E2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi - (3 * E2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * phi)
                + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * phi) - (35 * e6 / 3072) * math.sin(6 * phi))


M0 = _m(LAT0)


def tm_inverse(x, y):
    mv = M0 + (y - FN) / K0
    e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
    mu = mv / (A * (1 - E2 / 4 - 3 * E2 * E2 / 64 - 5 * E2 ** 3 / 256))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 * e1 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    n1 = A / math.sqrt(1 - E2 * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = EP2 * math.cos(phi1) ** 2
    r1 = A * (1 - E2) / (1 - E2 * math.sin(phi1) ** 2) ** 1.5
    d = (x - FE) / (n1 * K0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (d * d / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 * c1 - 9 * EP2) * d ** 4 / 24
                                              + (61 + 90 * t1 + 298 * c1 + 45 * t1 * t1 - 252 * EP2 - 3 * c1 * c1) * d ** 6 / 720)
    lon = LON0 + (d - (1 + 2 * t1 + c1) * d ** 3 / 6 + (5 - 2 * c1 + 28 * t1 - 3 * c1 * c1 + 8 * EP2 + 24 * t1 * t1) * d ** 5 / 120) / math.cos(phi1)
    return math.degrees(lon), math.degrees(lat)


def simplify(pts, tol):
    """Douglas-Peucker (도 단위 tol)"""
    if len(pts) < 3:
        return pts
    def dseg(p, a, b):
        ax, ay, bx, by = a[0], a[1], b[0], b[1]
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return math.hypot(p[0] - ax, p[1] - ay)
        t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))
    stack, keep = [(0, len(pts) - 1)], [False] * len(pts)
    keep[0] = keep[-1] = True
    while stack:
        i, j = stack.pop()
        best, bi = 0.0, -1
        for k in range(i + 1, j):
            dd = dseg(pts[k], pts[i], pts[j])
            if dd > best:
                best, bi = dd, k
        if best > tol:
            keep[bi] = True
            stack.append((i, bi))
            stack.append((bi, j))
    return [p for p, k in zip(pts, keep) if k]


def read_csv(path):
    raw = open(path, "rb").read()
    txt = raw.decode("utf-8-sig") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("cp949")
    return list(csv.DictReader(io.StringIO(txt)))


def zones_from(shp_path, sido, link, loc, tol):
    sf = shapefile.Reader(shp_path, encoding="cp949")
    fields = [f[0] for f in sf.fields[1:]]
    out = []
    for i, rec in enumerate(sf.iterRecords()):
        rec = dict(zip(fields, list(rec)))
        if rec.get("SD_CD") != sido:
            continue
        shp = sf.shape(i)
        parts = list(shp.parts) + [len(shp.points)]
        rings = []
        for p in range(len(parts) - 1):
            ring = [tm_inverse(x, y) for x, y in shp.points[parts[p]:parts[p + 1]]]
            ring = simplify(ring, tol)
            if len(ring) >= 4:
                rings.append([[round(x, 5), round(y, 5)] for x, y in ring])
        if not rings:
            continue
        schools = []
        for sid, nm in link.get(rec["HAKGUDO_ID"], []):
            l = loc.get(sid)
            schools.append({"id": sid, "name": nm, "lat": l[0] if l else None, "lng": l[1] if l else None})
        out.append({"id": rec["HAKGUDO_ID"], "name": rec["HAKGUDO_NM"], "shared": rec.get("HAKGUDO_GB") == "1",
                    "sgg": rec.get("SGG_CD", ""), "edu": rec.get("EDU_NM", ""), "schools": schools, "rings": rings})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sido", default="11")
    ap.add_argument("--tol", type=float, default=0.00004, help="단순화 허용오차(도) ~4m")
    a = ap.parse_args()
    link = {}
    for r in read_csv(os.path.join(D, "link", "link.csv")):
        link.setdefault(r["학구ID"], []).append((r["학교ID"], r["학교명"]))
    loc = {}
    base = ""
    for r in read_csv(os.path.join(D, "school_loc", "school_loc.csv")):
        try:
            loc[r["학교ID"]] = (float(r["위도"]), float(r["경도"]))
        except ValueError:
            pass
        base = r.get("데이터기준일자", base)
    elem = zones_from(os.path.join(D, "elem_zone", "elem_zone"), a.sido, link, loc, a.tol)
    middle = zones_from(os.path.join(D, "middle_zone", "middle_zone"), a.sido, link, loc, a.tol)
    hp = os.path.join(D, "high_zone", "high_zone")
    high = zones_from(hp, a.sido, link, loc, a.tol) if os.path.exists(hp + ".shp") else []
    out = {"base_date": base, "sido": a.sido, "elem": elem, "middle": middle, "high": high}
    p = os.path.join(RAW, "schoolzones_seoul.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    pts = sum(len(r) for z in elem for r in z["rings"])
    print("초등 학구 {}개 (공동 {}), 중학교 학군 {}개, 고등학교 학교군 {}개, 좌표점 {} -> {} ({:.1f}MB)".format(
        len(elem), sum(1 for z in elem if z["shared"]), len(middle), len(high), pts, p, os.path.getsize(p) / 1e6))
    for z in high[:3]:
        print("  고교군:", z["name"], "학교", len(z["schools"]))
    no_school = [z["name"] for z in elem if not z["schools"]]
    print("학교 연계 없는 초등 학구:", len(no_school), no_school[:5])


if __name__ == "__main__":
    sys.exit(main())
