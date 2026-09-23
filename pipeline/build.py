"""단지/실거래/학군/도로/경매를 합쳐 앱용 JSON을 만든다.

  python pipeline/build.py

입력
  data/raw/trades_*.json   (fetch_trades.py, 있으면 실데이터 모드)
  app/data/roads.geojson   (fetch_roads.py, 없으면 도로 관련 판단 생략)
  pipeline/demo_data.py    (학군/경매/역 정보, 실거래 없을 땐 단지+거래도 데모)
출력
  app/data/complexes.json, schools.geojson, auctions.json, meta.json
"""
import datetime as dt
import glob
import json
import math
import re
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import demo_data  # noqa: E402
try:
    from terrain import Terrain  # noqa: E402
except Exception:  # PIL 없으면 지형 생략
    Terrain = None

ROOT = os.path.join(HERE, "..")
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "app", "data")
PY = 3.3058
SCHOOL_STATS = {}
TERRAIN = None
MIDDLE_ZONES_OFFICIAL = []
HIGH_ZONES_OFFICIAL = []
HIGH_SCHOOLS = {}
NUISANCE = {}
AMENITIES = {}


# ---------- geo utils ----------
def dist_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def point_in_ring(lng, lat, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            x = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if x > lng:
                inside = not inside
    return inside


def seg_dist_m(lat, lng, a, b):
    """점(lat,lng)과 선분 a-b([lng,lat]) 거리(m), 로컬 평면 근사."""
    kx = 111320.0 * math.cos(math.radians(lat))
    ky = 110540.0
    px, py = lng * kx, lat * ky
    ax, ay = a[0] * kx, a[1] * ky
    bx, by = b[0] * kx, b[1] * ky
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


GRID = 0.01   # 약 1.1km 격자


def grid_index(items, coords_of):
    """items -> {(gx,gy): [item]} ; coords_of(item) 는 [(lng,lat),...]"""
    idx = {}
    for it in items:
        for lng, lat in coords_of(it):
            idx.setdefault((int(lng / GRID), int(lat / GRID)), set()).add(id(it))
    byid = {id(it): it for it in items}
    return {k: [byid[i] for i in v] for k, v in idx.items()}


def grid_near(idx, lng, lat, r=1):
    gx, gy = int(lng / GRID), int(lat / GRID)
    out, seen = [], set()
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            for it in idx.get((gx + dx, gy + dy), ()):
                if id(it) not in seen:
                    seen.add(id(it))
                    out.append(it)
    return out


_ROAD_IDX = {}
_ACA_IDX = {}
_SEOUL_IDX = {}


def nearest_major_road(lat, lng, roads):
    if id(roads) not in _ROAD_IDX:
        _ROAD_IDX.clear()
        _ROAD_IDX[id(roads)] = grid_index([f for f in roads if f["properties"]["class"] == "major"],
                                          lambda f: f["geometry"]["coordinates"][:: max(1, len(f["geometry"]["coordinates"]) // 8)] + [f["geometry"]["coordinates"][-1]])
    best, name = 1e9, ""
    for f in grid_near(_ROAD_IDX[id(roads)], lng, lat):
        cs = f["geometry"]["coordinates"]
        for i in range(len(cs) - 1):
            d = seg_dist_m(lat, lng, cs[i], cs[i + 1])
            if d < best:
                best, name = d, f["properties"].get("name", "")
    return (round(best) if best < 1e9 else None), name


def voronoi_zones(schools, bbox):
    """초등학교 점 -> 최근접 기준 통학구역 추정 폴리곤 (bbox 로 클리핑). schools: [{name,lat,lng}]"""
    import numpy as np
    from scipy.spatial import Voronoi
    s, w, n, e = bbox
    lat0 = (s + n) / 2
    kx, ky = 111320.0 * math.cos(math.radians(lat0)), 110540.0
    pts = np.array([[(sc["lng"] - w) * kx, (sc["lat"] - s) * ky] for sc in schools])
    W, H = (e - w) * kx, (n - s) * ky
    # 무한 영역을 막기 위해 멀리 떨어진 가짜 점 4개 추가
    far = 50 * max(W, H)
    aug = np.vstack([pts, [[-far, -far], [far, -far], [-far, far], [far, far]]])
    vor = Voronoi(aug)
    clip = [(0, 0), (W, 0), (W, H), (0, H)]

    def clip_poly(poly):
        def inside(p, a, b):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0

        def inter(p1, p2, a, b):
            x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
            x3, y3, x4, y4 = a[0], a[1], b[0], b[1]
            den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4) or 1e-12
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
            return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
        out = poly
        for i in range(4):
            a, b = clip[i], clip[(i + 1) % 4]
            inp, out = out, []
            if not inp:
                break
            sp = inp[-1]
            for pt in inp:
                if inside(pt, a, b):
                    if not inside(sp, a, b):
                        out.append(inter(sp, pt, a, b))
                    out.append(pt)
                elif inside(sp, a, b):
                    out.append(inter(sp, pt, a, b))
                sp = pt
        return out

    zones = []
    for i, sc in enumerate(schools):
        region = vor.regions[vor.point_region[i]]
        if not region or -1 in region:
            continue
        poly = clip_poly([tuple(vor.vertices[v]) for v in region])
        if len(poly) < 3:
            continue
        ring = [[round(w + x / kx, 5), round(s + y / ky, 5)] for x, y in poly]
        ring.append(ring[0])
        zones.append({"name": sc["name"], "ring": ring})
    return zones


def load_schoolinfo():
    """학교알리미 -> 학교명 -> {students, students_prev, chg_pct, class_size, move_in, move_out, net_move, year}"""
    d = os.path.join(RAW, "schoolinfo")
    if not os.path.isdir(d):
        return {}
    by_year = {}
    for fp in glob.glob(os.path.join(d, "*_*_*_*.json")):
        t, knd, sgg, yr = os.path.basename(fp)[:-5].split("_")
        for r in json.load(open(fp, encoding="utf-8")):
            rec = by_year.setdefault(r["SCHUL_NM"], {}).setdefault(int(yr), {"knd": knd})
            if t == "62":
                tot = str(r.get("COL_FGR_SUM", "0")).split("(")[0]
                rec["students"] = int(tot or 0)
                rec["class_size"] = float(r.get("AVG_FGR_SUM") or 0)
                rec["classes"] = str(r.get("COL_SUM", "")).split("(")[0]
            elif t == "10":
                rec["move_in"] = int(r.get("MVIN_SUM") or 0)
                rec["move_out"] = int(r.get("MVT_SUM") or 0)
                rec["students10"] = int(r.get("STDNT_SUM") or 0)
    out = {}
    for name, yrs in by_year.items():
        ys = sorted(y for y, v in yrs.items() if v.get("students"))
        if not ys:
            continue
        cur, prev = yrs[ys[-1]], (yrs[ys[-2]] if len(ys) > 1 else None)
        chg = round((cur["students"] / prev["students"] - 1) * 100, 1) if prev and prev.get("students") else None
        mi, mo = cur.get("move_in"), cur.get("move_out")
        out[name] = {
            "year": ys[-1], "students": cur["students"], "chg_pct": chg, "class_size": cur.get("class_size"),
            "classes": cur.get("classes", ""), "move_in": mi, "move_out": mo,
            "net_move": (mi - mo) if mi is not None and mo is not None else None,
            "net_move_pct": round((mi - mo) / cur["students"] * 100, 1) if mi is not None and mo is not None and cur["students"] else None,
        }
    return out


def load_high_schools():
    """고등학교: 나이스 유형(일반/자율/특목/특성화) + 학교알리미 좌표(type 0, knd 04) + 진학률(type 51)"""
    p = os.path.join(RAW, "high_schools_neis.json")
    if not os.path.exists(p):
        return {}
    hs = {h["name"]: dict(h) for h in json.load(open(p, encoding="utf-8"))}
    for fp in glob.glob(os.path.join(RAW, "schoolinfo", "0_04_*_*.json")):
        for r in json.load(open(fp, encoding="utf-8")):
            h = hs.setdefault(r["SCHUL_NM"], {"name": r["SCHUL_NM"], "type": "", "track": ""})
            try:
                h["lat"], h["lng"] = float(r.get("LTTUD") or 0), float(r.get("LGTUD") or 0)
            except (TypeError, ValueError):
                pass
            h.setdefault("public", r.get("FOND_SC_CODE", ""))
            h.setdefault("coedu", {"남": "남", "여": "여"}.get(r.get("COEDU_SC_CODE", ""), "남여공학"))
    grad = {}
    for fp in sorted(glob.glob(os.path.join(RAW, "schoolinfo", "51_04_*_*.json"))):
        yr = int(os.path.basename(fp)[:-5].split("_")[-1])
        for r in json.load(open(fp, encoding="utf-8")):
            tot = int(r.get("ALL_SUM") or 0)
            adv = int(r.get("SUPRTI_GRDTN_BOYST_FGR") or 0) or (int(r.get("PRTI_GRDTN_BOYST_FGR") or 0) + int(r.get("PRTI_GRDTN_FES_FGR") or 0))
            if tot:
                prev = grad.get(r["SCHUL_NM"])
                if not prev or prev["year"] < yr:
                    grad[r["SCHUL_NM"]] = {"year": yr, "grads": tot, "adv_pct": round(adv / tot * 100)}
    for n, g in grad.items():
        if n in hs:
            hs[n]["adv"] = g
    return {n: h for n, h in hs.items() if h.get("lat")}


NUISANCE_KINDS = {
    "substation": ("변전소", 300), "powerline": ("고압 송전선", 100), "landfill": ("매립·소각·폐기물 시설", 1000),
    "wastewater": ("하수·분뇨 처리장", 800), "crematorium": ("화장장·장례식장", 300), "prison": ("교도소·구치소", 500),
    "military": ("군부대", 300), "fuel": ("주유소·충전소", 150), "nightlife": ("유흥·성인 업소", 200), "motel": ("모텔", 200),
    "rail": ("지상 철도", 100), "motorway": ("고속도로·자동차전용도로", 150),
    "adult_biz": ("유흥주점·단란주점", 200), "lodging": ("숙박업소", 200),
}


AMENITY_KINDS = {"hospital": "병원", "clinic_ped": "소아과", "mart": "대형마트·백화점", "kindergarten": "어린이집·유치원", "library": "도서관",
                 "park": "공원", "university": "대학", "playground": "놀이터", "police": "경찰서·파출소", "emergency": "응급실"}


def load_amenities():
    p = os.path.join(RAW, "amenities_osm.json")
    if not os.path.exists(p):
        return {}
    d = json.load(open(p, encoding="utf-8"))
    for kind, items in d.items():
        d[kind] = {"points": items, "pidx": grid_index(items, lambda x: [(x["lng"], x["lat"])])}
    return d


def amenities_near(am, lat, lng):
    """종류별 최근접 시설 이름·거리 (2km 내)"""
    res = {}
    for kind, d in am.items():
        best = None
        for x in grid_near(d["pidx"], lng, lat, r=2):
            dd = dist_m(lat, lng, x["lat"], x["lng"])
            if dd <= 2000 and (best is None or dd < best[0]):
                best = (dd, x)
        if best:
            res[kind] = {"label": AMENITY_KINDS.get(kind, kind), "name": best[1].get("name", ""), "dist": round(best[0]), "area_m2": best[1].get("area_m2")}
    return res


def crosses_major_road(lat1, lng1, lat2, lng2, roads_idx):
    """두 점을 잇는 직선이 큰길과 교차하는지 (통학로 큰길 횡단 여부, 근사)"""
    def ccw(A, B, C):
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
    def inter(A, B, C, D):
        return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)
    A, B = (lng1, lat1), (lng2, lat2)
    mlng, mlat = (lng1 + lng2) / 2, (lat1 + lat2) / 2
    for f in grid_near(roads_idx, mlng, mlat, r=1):
        cs = f["geometry"]["coordinates"]
        for i in range(len(cs) - 1):
            if inter(A, B, tuple(cs[i]), tuple(cs[i + 1])):
                return True
    return False


# 주유소·모텔은 서울 어디에나 있어 "여기만 그렇다"는 신호가 되지 못한다. 2026-09-23 제외.
NUISANCE_SKIP = {"fuel", "motel"}


def load_nuisance():
    """OSM + LOCALDATA 기피시설 -> {kind: {"points": [...], "lines": [...]}} + 격자 인덱스"""
    out = {}
    p = os.path.join(RAW, "nuisance_osm.json")
    if os.path.exists(p):
        for kind, items in json.load(open(p, encoding="utf-8")).items():
            if kind in NUISANCE_SKIP:
                continue
            if items and "coords" in items[0]:
                out[kind] = {"lines": items, "points": []}
            else:
                out[kind] = {"lines": [], "points": items}
    p2 = os.path.join(RAW, "nuisance_localdata.json")
    if os.path.exists(p2):
        for kind, items in json.load(open(p2, encoding="utf-8")).items():
            if kind in NUISANCE_SKIP:
                continue
            out[kind] = {"lines": [], "points": items}
    for kind, d in out.items():
        d["pidx"] = grid_index(d["points"], lambda x: [(x["lng"], x["lat"])])
        d["lidx"] = grid_index(d["lines"], lambda l: l["coords"][:: max(1, len(l["coords"]) // 12)] + [l["coords"][-1]])
    return out


def nuisance_near(nz, lat, lng):
    """단지 기준 종류별 최근접 거리(m)와 반경 내 개수"""
    res = {}
    for kind, d in nz.items():
        label, radius = NUISANCE_KINDS.get(kind, (kind, 300))
        best, cnt, name = None, 0, ""
        for x in grid_near(d["pidx"], lng, lat):
            dd = dist_m(lat, lng, x["lat"], x["lng"])
            if dd <= radius:
                cnt += 1
            if best is None or dd < best:
                best, name = dd, x.get("name", "")
        for l in grid_near(d["lidx"], lng, lat):
            cs = l["coords"]
            for i in range(len(cs) - 1):
                dd = seg_dist_m(lat, lng, cs[i], cs[i + 1])
                if best is None or dd < best:
                    best, name = dd, l.get("name", "")
        if best is not None and best <= max(radius, 1000):
            res[kind] = {"label": label, "dist": round(best), "count": cnt, "name": name, "radius": radius, "within": best <= radius}
    return res


def load_poi():
    p = os.path.join(RAW, "poi.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding="utf-8"))
    s, w, n, e = [float(x) for x in d["bbox"].split(",")]
    d["bbox"] = (s, w, n, e)
    d["middle"], d["academies"] = [], []
    np_ = os.path.join(RAW, "schools_neis.json")
    if os.path.exists(np_):                       # 나이스 공식 목록이 있으면 초등은 그걸로 (병설/분교 제외 처리됨)
        ns = json.load(open(np_, encoding="utf-8"))
        if ns.get("elem"):
            d["elem_schools"] = [{"name": x["name"], "lat": x["lat"], "lng": x["lng"], "public": x.get("public", "")} for x in ns["elem"]]
        d["middle"] = ns.get("middle", [])
    # 학교알리미 학교기본정보(apiType 0)에 좌표가 있어 서울 전체 초·중학교를 여기서 보강 (없는 학교만 추가)
    si = {}
    for fp in glob.glob(os.path.join(RAW, "schools_neis_alimi.json")) + glob.glob(os.path.join(RAW, "schoolinfo", "0_0[23]_*_*.json")):
        for r in json.load(open(fp, encoding="utf-8")):
            try:
                lat, lng = float(r.get("LTTUD") or 0), float(r.get("LGTUD") or 0)
            except (TypeError, ValueError):
                continue
            if not lat or "분교" in r.get("SCHUL_NM", ""):
                continue
            si[(r["SCHUL_KND_SC_CODE"], r["SCHUL_NM"])] = {"name": r["SCHUL_NM"], "lat": lat, "lng": lng, "code": r.get("SCHUL_CODE", ""),
                                                          "public": r.get("FOND_SC_CODE", ""), "coedu": {"남": "남", "여": "여"}.get(r.get("COEDU_SC_CODE", ""), "남여공학")}
    have_e = {x["name"] for x in d["elem_schools"]}
    have_m = {x["name"] for x in d["middle"]}
    d["elem_schools"] += [v for (k, n), v in si.items() if k == "02" and n not in have_e]
    d["middle"] += [v for (k, n), v in si.items() if k == "03" and n not in have_m]
    for ap_ in glob.glob(os.path.join(RAW, "academies*.json")):
        d["academies"] += json.load(open(ap_, encoding="utf-8"))
    zp = os.path.join(RAW, "schoolzones_seoul.json")
    d["official"] = None
    if os.path.exists(zp):
        off = json.load(open(zp, encoding="utf-8"))
        d["official"] = off
        # 공식 통학구역: zones 형식(name, ring)으로 변환. 링은 첫 파트를 외곽으로 사용, 학교 여러 곳이면 공동학구
        zones = []
        for z in off["elem"]:
            names = [sc["name"] for sc in z["schools"]] or [z["name"].replace("통학구역", "")]
            for ring in z["rings"]:
                zones.append({"name": " · ".join(names), "ring": ring, "schools": z["schools"], "shared": z["shared"], "zone_id": z["id"]})
        d["zones"] = zones
        d["zone_note"] = "학구도안내서비스 {} 기준 (교육청 공식)".format(off.get("base_date", ""))
        # 공식 학교 좌표로 초등 목록 보강 (이름 기준)
        have = {x["name"] for x in d["elem_schools"]}
        for z in off["elem"]:
            for sc in z["schools"]:
                if sc["name"] not in have and sc.get("lat"):
                    d["elem_schools"].append({"name": sc["name"], "lat": sc["lat"], "lng": sc["lng"]})
                    have.add(sc["name"])
    else:
        d["zones"] = voronoi_zones(d["elem_schools"], d["bbox"])
    return d


import re as _re
_STRIP = _re.compile(r"(아파트|APT|apt|\(.*?\)|\s|·|-|_|,)")


def _norm(n):
    return _STRIP.sub("", n).lower()


def load_kapt():
    """K-apt 기본정보 (fetch_kapt.py). norm(name) -> [rec]"""
    p = os.path.join(RAW, "kapt.json")
    if not os.path.exists(p):
        return {}
    out = {}
    for rec in json.load(open(p, encoding="utf-8")).values():
        out.setdefault(rec["norm"], []).append(rec)
    return out


def kapt_lookup(kapt, apt, umd):
    key = _norm(apt)
    cands = kapt.get(key) or kapt.get(_norm(umd[:-1] + apt)) or []
    if not cands:
        for k, v in kapt.items():
            if len(key) >= 4 and (key in k or k in key):
                cands += v
    for c in cands:
        if umd and (umd in (c.get("addr") or "") or umd in (c.get("as3") or "")):
            return c
    return cands[0] if len(cands) == 1 else None


def load_seoul_apt():
    p = os.path.join(RAW, "seoul_apt.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


def seoul_lookup(seoul, name, umd, lat, lng):
    """좌표 200m 이내 후보 중 이름이 가장 비슷한 서울시 공동주택 레코드"""
    import difflib
    key = _norm(name)
    best, best_s = None, 0.0
    if id(seoul) not in _SEOUL_IDX:
        _SEOUL_IDX.clear()
        _SEOUL_IDX[id(seoul)] = grid_index([r for r in seoul if r["lat"]], lambda r: [(r["lng"], r["lat"])])
    for r in grid_near(_SEOUL_IDX[id(seoul)], lng, lat):
        if abs(r["lat"] - lat) > 0.0025 or abs(r["lng"] - lng) > 0.003:
            continue
        if dist_m(lat, lng, r["lat"], r["lng"]) > 200:
            continue
        rk = _norm(r["name"])
        sc = 1.0 if (key == rk or key in rk or rk in key) else difflib.SequenceMatcher(None, key, rk).ratio()
        if umd and umd == r.get("umd"):
            sc += 0.1
        if sc > best_s:
            best, best_s = r, sc
    return best if best_s >= 0.6 else None


def load_rent():
    """전월세 raw (fetch_rent.py). key -> [rows]"""
    out = {}
    for fp in glob.glob(os.path.join(RAW, "rent_*.json")):
        for r in json.load(open(fp, encoding="utf-8")):
            out.setdefault("{}|{}|{}".format(r["umd"], r["apt"], r["jibun"]), []).append(r)
    return out


# ---------- 데이터 소스 ----------
def load_real_complexes():
    files = sorted(glob.glob(os.path.join(RAW, "trades_*.json")))
    if not files:
        return None
    geo_path = os.path.join(RAW, "geocode.json")
    geo = json.load(open(geo_path, encoding="utf-8")) if os.path.exists(geo_path) else {}
    groups = {}
    for fp in files:
        for r in json.load(open(fp, encoding="utf-8")):
            key = "{}|{}|{}".format(r["umd"], r["apt"], r["jibun"])
            g = groups.setdefault(key, {"apt": r["apt"], "umd": r["umd"], "jibun": r["jibun"], "built": r["built"], "trades": []})
            g["trades"].append({"date": r["date"], "area": r["area"], "floor": r["floor"], "price": r["price"], "kind": r["kind"]})
    kapt, rent, seoul = load_kapt(), load_rent(), load_seoul_apt()
    kp = os.path.join(RAW, "kakao_poi.json")
    kpoi = json.load(open(kp, encoding="utf-8")) if os.path.exists(kp) else {}
    out = []
    for key, g in groups.items():
        loc = geo.get(key)
        if not loc:
            continue                      # geocode.py 로 좌표를 먼저 채워야 함
        cid = re.sub(r'[\/:*?"<>|#%&\s]+', "-", key.lower()).strip("-")
        areas = sorted({t["area"] for t in g["trades"]})
        k = kapt_lookup(kapt, g["apt"], g["umd"]) if kapt else None
        sa = seoul_lookup(seoul, g["apt"], g["umd"], loc["lat"], loc["lng"]) if seoul else None
        if sa:   # 서울시 공동주택 정보로 빈 값 보강 (K-apt 없는 소규모 단지 포함)
            k = dict(k or {})
            sa = dict(sa, hh_type={"임대+분양": "혼합"}.get(sa.get("hh_type"), sa.get("hh_type")))
            for a_, b_ in (("households", "households"), ("top_floor", None), ("dongs", "dongs"), ("hall", "hall"), ("heat", "heat"), ("sale_type", "hh_type")):
                if b_ and not k.get(a_) and sa.get(b_):
                    k[a_] = sa[b_]
            k["parking"] = sa.get("parking", 0)
            k["hh_by_area"] = {"~60": sa["hh_60"], "60~85": sa["hh_85"], "85~135": sa["hh_135"], "135~": sa["hh_136"]}
        out.append({
            "id": cid, "name": g["apt"], "sgg": loc.get("sgg", ""), "umd": g["umd"], "jibun": g["jibun"],
            "addr": loc.get("addr", ""), "lat": loc["lat"], "lng": loc["lng"],
            "households": (k or {}).get("households") or loc.get("households", 0), "built": g["built"],
            "max_floor": (k or {}).get("top_floor") or loc.get("max_floor", 0), "dongs": (k or {}).get("dongs", 0),
            "far": loc.get("far", 0), "areas": areas, "trades": sorted(g["trades"], key=lambda t: t["date"]),
            "rents": sorted(rent.get(key, []), key=lambda r: r["date"]),
            "sale_type": (k or {}).get("sale_type", ""), "hall": (k or {}).get("hall", ""), "heat": (k or {}).get("heat", ""),
            "life": kpoi.get(key), "parking": (k or {}).get("parking", 0), "hh_by_area": (k or {}).get("hh_by_area"), "ask": None,
        })
    return out


# ---------- 파생 지표 ----------
def ppy(t):
    return t["price"] / (t["area"] / PY)


def median_ppy(trades):
    return statistics.median([ppy(t) for t in trades]) if trades else None


def months_ago(d, n):
    y, m = d.year, d.month - n
    while m <= 0:
        y -= 1
        m += 12
    return dt.date(y, m, 1)


# 요약 JSON 은 단지마다 같은 키 이름을 6,800번 반복해 파일의 절반이 키였다(6.6MB 중 3MB).
# 키를 한 번만 적고 값은 순서대로 늘어놓는다. 앱이 받아서 원래 모양으로 되돌린다.
PACK_SUB = {
    "by_area": ("area", "latest", "latest_date", "count", "jeonse_ratio"),
    "station": ("name", "walk_min", "dist", "lines"),
    "school": ("elem", "elem_walk_min", "chopuma", "class_size"),
    "terrain": ("elev", "station_dh", "slope_pct"),
}


def pack_summary(summary):
    keys = sorted({k for sm in summary for k in sm})
    rows = []
    for sm in summary:
        row = []
        for k in keys:
            v = sm.get(k)
            sub = PACK_SUB.get(k)
            if sub and isinstance(v, dict):
                v = [v.get(x) for x in sub]
            elif sub and isinstance(v, list):
                v = [[a.get(x) for x in sub] for a in v]
            row.append(v)
        rows.append(row)
    return {"k": keys, "sub": {k: list(v) for k, v in PACK_SUB.items()}, "list": ["by_area"], "r": rows}


SEOUL_GU = {"종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구", "도봉구",
            "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구", "구로구", "금천구", "영등포구",
            "동작구", "관악구", "서초구", "강남구", "송파구", "강동구"}


def area_label(cs):
    """메타의 지역 표기. 경기 출퇴근권이 들어오면 '서울 전체'라고 쓰면 거짓말이 된다."""
    gus = {c["sgg"] for c in cs if c.get("sgg")}
    seoul, gg = gus & SEOUL_GU, sorted(gus - SEOUL_GU)
    if not gg:
        return "서울 전체 ({}개 구)".format(len(seoul)) if len(seoul) > 3 else "서울 " + "·".join(sorted(seoul))
    if len(seoul) >= 20:
        return "서울 전체 + 경기 출퇴근권 {}곳".format(len(gg))
    return "·".join(sorted(seoul) + gg)


def load_auctions(cs):
    """fetch_auction.py 가 받아둔 온비드 공매 물건을 단지에 붙인다.

    주소가 '서울특별시 노원구 상계동 1309 한일유앤아이아파트 제103동 제1704호' 형태라
    법정동 + 지번으로 단지를 찾는다. 같은 지번에 단지가 여럿이면 이름이 겹치는 쪽을 고른다.
    파일이 없으면 데모 경매 데이터로 돌아간다(키 없이 화면만 볼 때).
    """
    p = os.path.join(RAW, "auction_onbid.json")
    if not os.path.exists(p):
        return demo_data.auctions()
    rows = json.load(open(p, encoding="utf-8"))
    by_key = {}
    for c in cs:
        by_key.setdefault((c["umd"], str(c["jibun"])), []).append(c)
    out = []
    for r in rows:
        if not r.get("umd") or not r.get("area"):
            continue
        m = re.search(r"{}\s+(\d+(?:-\d+)?)".format(re.escape(r["umd"])), r.get("addr", ""))
        cands = by_key.get((r["umd"], m.group(1)), []) if m else []
        if len(cands) > 1:
            nm = re.sub(r"[^가-힣A-Za-z]", "", r.get("addr", ""))
            cands = sorted(cands, key=lambda c: -sum(1 for ch in set(c["name"]) if ch in nm))
        if not cands:
            continue
        out.append({
            "case": r["case"], "complex_id": cands[0]["id"], "unit": r.get("unit", ""),
            "area": r["area"], "appraisal": r["appraisal"] // 10000, "min_price": r["min_price"] // 10000,
            "min_rate": r.get("min_rate"), "fail_count": r.get("fail_count", 0),
            "sale_date": r.get("bid_end", ""), "court": "{} · {}".format(r.get("source", "온비드"), r.get("kind", "")),
            "use": r.get("use", ""), "status": r.get("status", ""),
        })
    return out


FUTURE_RAIL = {"lines": None, "stations": []}   # fetch_future_rail.py 결과 (main 에서 채움)


def enrich(c, roads, today, stations, schools, zones, middle=None, academies=None):
    tr = c["trades"]
    recent = [t for t in tr if dt.date.fromisoformat(t["date"]) >= months_ago(today, 3)]
    if len(recent) < 3:
        recent = tr[-5:]
    y_ago = [t for t in tr if months_ago(today, 14) <= dt.date.fromisoformat(t["date"]) < months_ago(today, 10)]
    if len(y_ago) < 2:
        y_ago = tr[:5]
    now_ppy = median_ppy(recent)
    c["ppy"] = int(now_ppy) if now_ppy else None
    # 1년 변동률: 같은 전용면적(정수 ㎡) 안에서 최근 3~6개월 vs 10~14개월 전 평당가 중앙값. 표본 많은 면적 우선.
    def area_chg():
        best = None
        for a in sorted({int(t["area"]) for t in tr}):
            ts = [t for t in tr if int(t["area"]) == a]
            rec = [t for t in ts if dt.date.fromisoformat(t["date"]) >= months_ago(today, 6)]
            old = [t for t in ts if months_ago(today, 15) <= dt.date.fromisoformat(t["date"]) < months_ago(today, 9)]
            if len(rec) >= 2 and len(old) >= 2:
                v = round((median_ppy(rec) / median_ppy(old) - 1) * 100, 1)
                if best is None or len(ts) > best[0]:
                    best = (len(ts), v)
        return best[1] if best else None
    c["chg_1y"] = area_chg()
    c["trade_count_1y"] = sum(1 for t in tr if dt.date.fromisoformat(t["date"]) >= months_ago(today, 12))

    # 평형별 최근가
    by_area = {}
    for t in tr:
        by_area.setdefault(int(t["area"]), []).append(t)   # 84.9 -> 84 (관행 표기)
    c["by_area"] = []
    for a, ts in sorted(by_area.items()):
        ts.sort(key=lambda t: t["date"])
        last3 = ts[-3:]
        js = [r["deposit"] for r in c.get("rents", []) if int(r["area"]) == a and r["monthly"] == 0
              and dt.date.fromisoformat(r["date"]) >= months_ago(today, 6)]
        jeonse = int(statistics.median(js)) if len(js) >= 2 else None
        c["by_area"].append({
            "area": a, "pyeong": round(a * 1.32 / PY),   # 공급면적 기준 평형(관행), 전용 84 -> 34평형
            "latest": last3[-1]["price"], "latest_date": last3[-1]["date"],
            "avg_recent": int(statistics.mean(t["price"] for t in last3)), "count": len(ts),
            "jeonse": jeonse, "jeonse_n": len(js),
            "jeonse_ratio": round(jeonse / statistics.median(t["price"] for t in last3) * 100) if jeonse and len(ts) >= 2 else None,
        })
    c["jeonse_ratio"] = next((b["jeonse_ratio"] for b in sorted(c["by_area"], key=lambda b: -b["count"]) if b["jeonse_ratio"]), None)
    rents = c.get("rents", [])
    c["rent_count_12m"] = sum(1 for r in rents if dt.date.fromisoformat(r["date"]) >= months_ago(today, 12))
    c["rent_turnover"] = round(c["rent_count_12m"] / c["households"] * 100) if c.get("households") else None
    c.pop("rents", None)

    # 역
    st = sorted(((dist_m(c["lat"], c["lng"], s["lat"], s["lng"]), s) for s in stations), key=lambda x: x[0])
    near = [(round(d), s["name"], s["line"]) for d, s in st if d <= 600]
    d0, s0 = st[0]
    c["station"] = {"name": s0["name"], "line": s0["line"], "lines": s0.get("lines") or [], "dist": round(d0), "walk_min": max(1, round(d0 / 70)),
                    "within_600": [{"name": n, "line": l, "dist": d} for d, n, l in near]}
    # 공사 중 노선 예정역 (1km 이내 가장 가까운 곳)
    fut = sorted(((dist_m(c["lat"], c["lng"], s["lat"], s["lng"]), s) for s in FUTURE_RAIL["stations"]), key=lambda x: x[0])
    if fut and fut[0][0] <= 1000:
        fd, fs = fut[0]
        c["future"] = {"name": fs["name"], "line": fs["line"], "dist": round(fd), "walk_min": max(1, round(fd / 70))}

    # 초등 배정 (통학구역 폴리곤 포함 여부 -> 없으면 최근접)
    by_name = {sc["name"]: sc for sc in schools}
    elem, elem_shared, zone_hit = None, [], None
    for z in zones:
        if point_in_ring(c["lng"], c["lat"], z["ring"][:-1]):
            zone_hit = z
            cands = [sc for sc in z.get("schools", []) if sc.get("lat")] or ([by_name[z["name"]]] if z["name"] in by_name else [])
            if cands:
                cands.sort(key=lambda sc: dist_m(c["lat"], c["lng"], sc["lat"], sc["lng"]))
                elem = cands[0]
                elem_shared = [sc["name"] for sc in cands] if len(cands) > 1 else []
            break
    if not elem:
        elem = min(schools, key=lambda sc: dist_m(c["lat"], c["lng"], sc["lat"], sc["lng"]))
    de = dist_m(c["lat"], c["lng"], elem["lat"], elem["lng"])
    mid_zone = next((z for z, ring in MIDDLE_ZONES_OFFICIAL if point_in_ring(c["lng"], c["lat"], ring[:-1])), None)
    mid_by_name = {m["name"]: m for m in middle}
    if mid_zone and mid_zone.get("schools"):
        cands = []
        for sc in mid_zone["schools"]:
            m = mid_by_name.get(sc["name"], {})
            lat, lng = (sc.get("lat") or m.get("lat")), (sc.get("lng") or m.get("lng"))
            if lat:
                cands.append((dist_m(c["lat"], c["lng"], lat, lng), sc["name"], m))
        cands.sort(key=lambda x: x[0])
        mids = [n for _, n, _ in cands[:6]]
        mid_detail = [{"name": n, "dist": round(d), "public": m.get("public", ""), "coedu": m.get("coedu", "")} for d, n, m in cands[:6]]
        mid_note = "{} 소속 중학교 {}곳 중 가까운 순 (학교군 내 추첨 배정, 학구도안내서비스 기준)".format(mid_zone["name"], len(cands))
        gcount = {"공학": 0, "남": 0, "여": 0}
        for _, n, m in cands:
            ce = m.get("coedu") or "남여공학"
            gcount["남" if ce == "남" else "여" if ce == "여" else "공학"] += 1
        mid_gender = gcount
    elif middle:
        mid_gender = None
        near_mid = sorted(((dist_m(c["lat"], c["lng"], m["lat"], m["lng"]), m) for m in middle), key=lambda x: x[0])[:3]
        mids = [m["name"] for d, m in near_mid]
        mid_detail = [{"name": m["name"], "dist": round(d), "public": m.get("public", ""), "coedu": m.get("coedu", "")} for d, m in near_mid]
        mid_note = "가까운 중학교 3곳 (실제 배정은 학교군 내 추첨)"
    else:
        mid_gender = None
        mids, mid_detail, mid_note = demo_data.MIDDLE_ZONES.get(c["umd"], []), [], "중학교는 학교군 단위 배정 + 추첨 (특정 학교 확정 아님)"
    for m in mid_detail:
        st = (SCHOOL_STATS or {}).get(m["name"])
        if st:
            m["stats"] = {k: st[k] for k in ("students", "chg_pct", "class_size", "net_move", "net_move_pct")}
    # 고등학교: 소속 학교군의 일반고(가까운 순 5) + 반경 3km 자율/특목고
    high = None
    if HIGH_SCHOOLS:
        hz = next((z for z, ring in HIGH_ZONES_OFFICIAL if point_in_ring(c["lng"], c["lat"], ring[:-1])), None)
        zone_names = {sc["name"] for sc in (hz or {}).get("schools", [])}
        gen = []
        for n, h in HIGH_SCHOOLS.items():
            d = dist_m(c["lat"], c["lng"], h["lat"], h["lng"])
            if (n in zone_names or (not hz and d <= 3000)) and h.get("type", "일반고") in ("일반고", ""):
                gen.append((d, h))
        gen.sort(key=lambda x: x[0])
        spec = sorted(((dist_m(c["lat"], c["lng"], h["lat"], h["lng"]), h) for h in HIGH_SCHOOLS.values() if h.get("type") in ("자율고", "특목고")), key=lambda x: x[0])
        spec = [(d, h) for d, h in spec if d <= 3000][:4]
        fmt = lambda d, h: {"name": h["name"], "dist": round(d), "type": h.get("type", ""), "public": h.get("public", ""), "coedu": h.get("coedu", ""),
                            "special": h.get("special", "")}
        hg = {"공학": 0, "남": 0, "여": 0}
        for _, h in gen:
            ce = h.get("coedu") or "남여공학"
            hg["남" if ce == "남" else "여" if ce == "여" else "공학"] += 1
        high = {"zone": hz["name"] if hz else None, "zone_total": len(zone_names) if hz else None, "gender": hg,
                "general": [fmt(d, h) for d, h in gen[:5]], "special": [fmt(d, h) for d, h in spec]}
    c["school"] = {
        "high": high,
        "elem": elem["name"], "elem_dist": round(de), "elem_walk_min": max(1, round(de / 60)),
        "chopuma": de <= 300, "elem_stats": (SCHOOL_STATS or {}).get(elem["name"]),
        "elem_shared": elem_shared, "elem_official": zone_hit is not None and "zone_id" in zone_hit,
        "middle_zone": mid_zone["name"] if mid_zone else None,
        "middle": mids, "middle_detail": mid_detail, "middle_note": mid_note, "middle_gender": mid_gender,
    }
    # 학원 밀집도 (반경 1km): 전체 / 입시·보습 교과
    if academies:
        if id(academies) not in _ACA_IDX:
            _ACA_IDX.clear()
            _ACA_IDX[id(academies)] = grid_index(academies, lambda x: [(x["lng"], x["lat"])])
        near = [x for x in grid_near(_ACA_IDX[id(academies)], c["lng"], c["lat"]) if dist_m(c["lat"], c["lng"], x["lat"], x["lng"]) <= 1000]
        fees = [x["fee"] for x in near if x.get("fee") and "입시" in (x.get("realm") or "")]
        c["edu"] = {"aca_1km": len(near), "exam_1km": sum(1 for x in near if "입시" in (x.get("realm") or "")),
                    "art_1km": sum(1 for x in near if "예능" in (x.get("realm") or "")),
                    # 교습비는 공개한 학원만 집계돼 표본이 적으면 흔들린다 -> 5곳 미만이면 쓰지 않는다
                    "fee_med": int(statistics.median(fees)) if len(fees) >= 5 else None, "fee_n": len(fees)}
    else:
        c["edu"] = None

    # 도로
    if roads:
        d, name = nearest_major_road(c["lat"], c["lng"], roads)
        c["road"] = {"major_dist": d, "major_name": name, "roadside": d is not None and d < 60}
    else:
        c["road"] = {"major_dist": None, "major_name": "", "roadside": False}

    # 지형: 해발고도, 반경 100m 경사, 역/초등과의 고도차
    c["terrain"] = None
    if TERRAIN:
        e0 = TERRAIN.elev(c["lat"], c["lng"])
        if e0 is not None:
            st_e = TERRAIN.elev(s0["lat"], s0["lng"])
            el_e = TERRAIN.elev(elem["lat"], elem["lng"])
            c["terrain"] = {"elev": e0, "slope_pct": TERRAIN.slope_pct(c["lat"], c["lng"]),
                            "station_dh": round(e0 - st_e) if st_e is not None else None,
                            "elem_dh": round(e0 - el_e) if el_e is not None else None}

    # 기피시설
    c["nuisance"] = nuisance_near(NUISANCE, c["lat"], c["lng"]) if NUISANCE else {}
    # 주요시설 최근접 + 통학로 큰길 횡단 여부
    c["amen"] = amenities_near(AMENITIES, c["lat"], c["lng"]) if AMENITIES else {}
    c["school"]["cross_major"] = bool(roads and _ROAD_IDX and crosses_major_road(c["lat"], c["lng"], elem["lat"], elem["lng"], list(_ROAD_IDX.values())[0]))

    # 위험·상승 신호 (자체 실거래/전월세 데이터)
    age = today.year - c["built"]
    sig = {"risk": [], "up": []}
    by_a = {}
    for t in tr:
        by_a.setdefault(int(t["area"]), []).append(t)
    main_area = max(by_a.items(), key=lambda kv: len(kv[1]))[0] if by_a else None
    if main_area:
        ts = sorted(by_a[main_area], key=lambda t: t["date"])
        recent = [t for t in ts if dt.date.fromisoformat(t["date"]) >= months_ago(today, 6)]
        peak = max(t["price"] for t in ts)
        last = ts[-1]["price"]
        # 신고가: 최근 6개월 거래가 이 평형 역대(24개월) 최고가
        if recent and max(t["price"] for t in recent) >= peak and len(ts) >= 4:
            sig["up"].append("최근 6개월 신고가 경신 ({}㎡ {:,}만)".format(main_area, peak))
        # 하락: 최근 3건 중앙값이 최고가 대비 -10% 이상 (신고가 경신 중이면 제외)
        last3 = statistics.median(t["price"] for t in ts[-3:])
        if len(ts) >= 4 and last3 <= peak * 0.9 and not (recent and max(t["price"] for t in recent) >= peak):
            sig["risk"].append("{}㎡ 최근 시세가 최고가 대비 {:.0f}%".format(main_area, (last3 / peak - 1) * 100))
    # 거래 절벽 / 거래 증가: 최근 6개월 vs 그 이전 12개월 월평균
    r6 = sum(1 for t in tr if dt.date.fromisoformat(t["date"]) >= months_ago(today, 6))
    p12 = sum(1 for t in tr if months_ago(today, 18) <= dt.date.fromisoformat(t["date"]) < months_ago(today, 6))
    if p12 >= 6:
        ratio = (r6 / 6.0) / (p12 / 12.0)
        if ratio <= 0.4:
            sig["risk"].append("거래 급감 (최근 6개월 월평균 {:.1f}건, 이전 {:.1f}건)".format(r6 / 6.0, p12 / 12.0))
        elif ratio >= 1.8 and r6 >= 6:
            sig["up"].append("거래 활발 (최근 6개월 월평균 {:.1f}건, 이전 {:.1f}건)".format(r6 / 6.0, p12 / 12.0))
    # 환금성
    if c.get("households") and c["households"] < 300 and c["trade_count_1y"] <= 3:
        sig["risk"].append("환금성 낮음 (소규모 {}세대, 1년 거래 {}건)".format(c["households"], c["trade_count_1y"]))
    # 노후 + 주차
    if age >= 25 and c.get("parking_per_hh") and c["parking_per_hh"] < 0.7:
        sig["risk"].append("노후 {}년차 + 세대당 주차 {}대".format(age, c["parking_per_hh"]))
    # 깡통
    if c["jeonse_ratio"] and c["jeonse_ratio"] >= 90:
        sig["risk"].append("전세가율 {}% (깡통전세 위험)".format(c["jeonse_ratio"]))
    # 갭 축소: 전세가율 70%↑ 이면서 최근 전세 상승
    ba_main = next((b for b in c["by_area"] if b["area"] == main_area), None)
    if ba_main and ba_main.get("jeonse_ratio") and 70 <= ba_main["jeonse_ratio"] < 90:
        sig["up"].append("전세가율 {}% (갭 {})".format(ba_main["jeonse_ratio"], "{:.1f}억".format((ba_main["latest"] - ba_main["jeonse"]) / 10000)))
    if c.get("school", {}).get("elem_stats", {}) and (c["school"]["elem_stats"].get("net_move_pct") or 0) >= 3:
        sig["up"].append("배정 초등 순전입 +{}% (젊은 가족 유입)".format(c["school"]["elem_stats"]["net_move_pct"]))
    if age >= 30 and (c.get("far") or 0) and c["far"] <= 200:
        sig["up"].append("준공 30년↑ + 용적률 {}% (재건축 사업성 참고)".format(c["far"]))
    elif age >= 30:
        sig["up"].append("준공 30년↑ (재건축 연한 충족)")
    c["signals"] = sig
    # 국면 한 줄: 최근 6개월 평당가 vs 이전 12개월, 거래량
    def _ppy_med(ts_):
        return statistics.median(ppy(t) for t in ts_) if ts_ else None
    rec6 = [t for t in tr if dt.date.fromisoformat(t["date"]) >= months_ago(today, 6)]
    prev12 = [t for t in tr if months_ago(today, 18) <= dt.date.fromisoformat(t["date"]) < months_ago(today, 6)]
    m6, m12 = _ppy_med(rec6), _ppy_med(prev12)
    if m6 and m12 and len(rec6) >= 2 and len(prev12) >= 3:
        d = (m6 / m12 - 1) * 100
        vol = (len(rec6) / 6.0) / (len(prev12) / 12.0)
        if d >= 5 and vol >= 1.0:
            ph = "상승 지속 (최근 6개월 평당가 {:+.0f}%, 거래 활발)".format(d)
        elif d >= 5:
            ph = "가격은 올랐지만 거래 감소 (평당가 {:+.0f}%)".format(d)
        elif d <= -5:
            ph = "조정 국면 (최근 6개월 평당가 {:+.0f}%)".format(d)
        elif vol <= 0.5:
            ph = "거래 위축, 가격 횡보 ({:+.0f}%)".format(d)
        else:
            ph = "횡보 (최근 6개월 평당가 {:+.0f}%)".format(d)
    else:
        ph = None
    c["phase"] = ph

    # 아이 키우기 점수 (0~100, 6축)
    def clamp(v):
        return max(0, min(100, int(round(v))))
    sch = c["school"]
    ax = {}
    de_ = sch["elem_dist"]
    ax["초등 접근"] = 100 if de_ <= 300 else 75 if de_ <= 500 else 45 if de_ <= 800 else 15
    ax["학군"] = clamp(c.get("edu_score") or 40)
    lf = c.get("life") or {}
    care = 0
    dc = lf.get("daycare")
    if dc is not None:
        care += 50 if dc >= 20 else 35 if dc >= 10 else 20 if dc >= 5 else 5
    pd_ = lf.get("pediatric")
    if pd_ is not None:
        care += 30 if pd_ >= 3 else 20 if pd_ >= 1 else 0
    if (lf.get("hospital") or 0) >= 10 and (lf.get("pharmacy") or 0) >= 3:
        care += 20
    ax["보육·의료"] = clamp(care if lf else 50)
    tr_ = c.get("terrain") or {}
    sl, dh = tr_.get("slope_pct"), tr_.get("station_dh")
    walk = 100 if (sl is not None and sl <= 2 and (dh is None or abs(dh) < 10)) else 70 if (sl is not None and sl <= 5) else 40 if (sl is not None and sl <= 8) else 15 if sl is not None else 50
    if c["road"].get("roadside"):
        walk -= 20
    ax["지형·보행"] = clamp(walk)
    nz_n = sum(1 for v in c.get("nuisance", {}).values() if v["within"])
    ax["환경·안전"] = 100 if nz_n == 0 else 60 if nz_n == 1 else 30 if nz_n == 2 else 5
    liv = 0
    pph = c.get("parking_per_hh")
    liv += 40 if (pph or 0) >= 1.2 else 25 if (pph or 0) >= 0.9 else 10 if pph else 20
    liv += 25 if (lf.get("park") or 0) >= 3 else 10
    liv += 15 if (lf.get("library") or 0) >= 1 else 0
    liv += 20 if (lf.get("mart") or 0) >= 1 else 5
    ax["생활 편의"] = clamp(liv)
    W = {"초등 접근": 0.20, "학군": 0.15, "보육·의료": 0.20, "지형·보행": 0.15, "환경·안전": 0.15, "생활 편의": 0.15}
    c["kid"] = {"score": clamp(sum(ax[k] * w for k, w in W.items())), "axes": ax}

    # 장단점
    age = today.year - c["built"]
    pros, cons = [], []
    if c["households"] >= 1500:
        pros.append("대단지 {:,}세대".format(c["households"]))
    elif c["households"] and c["households"] < 500:
        cons.append("소단지 {}세대".format(c["households"]))
    if age <= 5:
        pros.append("신축 {}년차".format(age))
    elif age <= 12:
        pros.append("준신축 {}년차".format(age))
    elif age >= 20:
        cons.append("구축 {}년차".format(age))
    if c.get("future") and c["future"]["dist"] <= 800:
        pros.append("{} {}역 예정(공사 중) 도보 {}분".format(c["future"]["line"], c["future"]["name"], c["future"]["walk_min"]))
    if len(c["station"].get("lines") or []) >= 2 and c["station"]["dist"] <= 800:
        pros.append("환승역 {} ({}) 도보 {}분".format(c["station"]["name"], "·".join(c["station"]["lines"]), c["station"]["walk_min"]))
    if len(c["station"]["within_600"]) >= 2:
        pros.append("더블 역세권")
    elif c["station"]["dist"] <= 500:
        pros.append("{} 도보 {}분".format(c["station"]["name"], c["station"]["walk_min"]))
    elif c["station"]["dist"] > 800:
        cons.append("역까지 도보 {}분".format(c["station"]["walk_min"]))
    if c["school"]["chopuma"]:
        pros.append("초품아 ({})".format(c["school"]["elem"]))
    elif c["school"]["elem_dist"] > 600:
        cons.append("초등학교 도보 {}분".format(c["school"]["elem_walk_min"]))
    if c["road"]["roadside"]:
        cons.append("대로변 소음 가능성")
    elif c["road"]["major_dist"] and c["road"]["major_dist"] > 150:
        pros.append("이면 조용한 입지")
    if c["far"] and c["far"] >= 280:
        cons.append("용적률 {}% (동간 간격 촘촘)".format(c["far"]))
    elif c["far"] and c["far"] <= 240:
        pros.append("용적률 {}% (쾌적)".format(c["far"]))
    if c["chg_1y"] is not None and c["chg_1y"] >= 8:
        pros.append("1년 평당가 +{}%".format(c["chg_1y"]))
    if c["trade_count_1y"] <= 3:
        cons.append("최근 1년 거래 {}건 (가격 확인 어려움)".format(c["trade_count_1y"]))
    life = c.get("life") or {}
    if life.get("daycare") is not None and life["daycare"] >= 20:      # 마포구 중앙값 14
        pros.append("어린이집·유치원 700m 내 {}곳 (많음)".format(life["daycare"]))
    elif life.get("daycare") is not None and life["daycare"] <= 5:
        cons.append("어린이집·유치원 700m 내 {}곳 (적음)".format(life["daycare"]))
    if life.get("pediatric") is not None and life["pediatric"] == 0:
        cons.append("1km 내 소아과 없음")
    if c["school"].get("cross_major") and c["school"]["elem_dist"] <= 800:
        cons.append("초등 통학로에 큰길 횡단 (직선 기준)")
    elif c["school"]["chopuma"] and not c["school"].get("cross_major"):
        pros.append("통학로 큰길 없음")
    nz_hits = [v for v in c["nuisance"].values() if v["within"]]
    nz_hits.sort(key=lambda v: v["dist"])
    for v in nz_hits[:2]:
        cons.append("{} {}m".format(v["label"], v["dist"]) + (" ({}곳)".format(v["count"]) if v["count"] > 1 else ""))
    for x in c["signals"]["risk"][:1]:
        cons.append(x)
    for x in c["signals"]["up"][:1]:
        pros.append(x)
    tr_ = c.get("terrain") or {}
    if tr_.get("station_dh") is not None and tr_["station_dh"] >= 30:
        cons.append("언덕 위 단지 (역보다 {}m 높음)".format(tr_["station_dh"]))
    elif tr_.get("slope_pct") is not None and tr_["slope_pct"] >= 8:
        cons.append("주변 경사 가파름 ({}%)".format(tr_["slope_pct"]))
    elif tr_.get("slope_pct") is not None and tr_["slope_pct"] <= 2 and tr_.get("station_dh") is not None and abs(tr_["station_dh"]) < 10:
        pros.append("평지 (역과 고도차 {}m)".format(abs(tr_["station_dh"])))
    if c.get("parking") and c.get("households"):
        c["parking_per_hh"] = round(c["parking"] / c["households"], 2)
        if c["parking_per_hh"] >= 1.3:
            pros.append("세대당 주차 {}대".format(c["parking_per_hh"]))
        elif c["parking_per_hh"] < 0.8:
            cons.append("세대당 주차 {}대 (부족)".format(c["parking_per_hh"]))
    if c["jeonse_ratio"] and c["jeonse_ratio"] >= 90:
        cons.append("전세가율 {}% (깡통전세 주의)".format(c["jeonse_ratio"]))
    # 중립 정보 (사람들이 잘 모르는 것)
    notes = []
    if c.get("sale_type") == "혼합":
        notes.append("분양·임대 혼합단지 (소셜믹스)")
    elif c.get("sale_type") == "임대":
        notes.append("임대 단지")
    if c["rent_turnover"] is not None and c["rent_turnover"] >= 20:
        notes.append("세입자 비중 높은 편 (1년 전월세 거래 {}건 = 세대수의 {}%)".format(c["rent_count_12m"], c["rent_turnover"]))
    if c.get("hall") and c["hall"] != "계단식":
        notes.append("{} 구조".format(c["hall"]))
    if age >= 30:
        notes.append("준공 30년 경과 (재건축 연한 충족)")
    c["pros"], c["cons"], c["notes"] = pros[:4], cons[:4], notes[:4]

    # 호가 갭
    if c.get("ask") and c["ppy"]:
        mid = (c["ask"]["low_ppy"] + c["ask"]["high_ppy"]) / 2
        c["ask"]["gap_pct"] = round((mid / c["ppy"] - 1) * 100, 1)
    return c


def main():
    today = dt.date.today()
    raw_roads = sorted(glob.glob(os.path.join(RAW, "roads_*.json")))
    roads = []
    if raw_roads:
        for rp in raw_roads:
            roads += [f for f in json.load(open(rp, encoding="utf-8"))["features"] if f["properties"]["class"] == "major"]
    else:
        roads_path = os.path.join(OUT, "roads.geojson")
        roads = json.load(open(roads_path, encoding="utf-8"))["features"] if os.path.exists(roads_path) else []

    real = load_real_complexes()
    poi = load_poi() if real else None
    mode = "real" if real else "demo"
    cs = real or demo_data.complexes()
    if poi:
        stations, schools, zones = poi["stations"], poi["elem_schools"], poi["zones"]
        zone_note = poi.get("zone_note") or "최근접 학교 기준 추정 (공식 학구도 반영 전)"
    # 지하철 노선 (fetch_subway.py): 역마다 실제 노선 목록과 대표 색을 붙인다
    subway = None
    sp = os.path.join(RAW, "subway.json")
    if poi and os.path.exists(sp):
        subway = json.load(open(sp, encoding="utf-8"))
        norm_st = lambda n: (lambda m: m[:-1] if m.endswith("역") and len(m) > 2 else m)(re.sub(r"\(.*?\)", "", n or "").strip())
        for s in stations:
            ls = subway["station_lines"].get(norm_st(s["name"]), [])
            if ls:
                s["lines"] = ls
                s["line"] = "·".join(ls)
                s["color"] = subway["colors"].get(ls[0])
        # OSM 의 station=subway 태그만으로는 수인분당선·경의중앙선 역이 많이 빠진다(서현·수내·영통 등).
        # 노선 관계에서 만든 그래프 노드에는 그 역들이 좌표까지 들어 있으므로 없는 역만 채워 넣는다.
        have = {norm_st(s["name"]) for s in stations}
        added = 0
        for name, lat, lng in (subway.get("graph") or {}).get("nodes", []):
            key = norm_st(name)
            if key in have:
                continue
            ls = subway["station_lines"].get(key, [])
            stations.append({"name": key + "역", "line": "·".join(ls), "lines": ls,
                             "lat": lat, "lng": lng, "color": subway["colors"].get(ls[0]) if ls else None})
            have.add(key)
            added += 1
        if added:
            print("지하철역 {}개 보강 (노선 그래프 기준) -> 총 {}개".format(added, len(stations)))
    else:
        stations = [{"name": n, "line": l, "lat": la, "lng": lo} for n, l, la, lo in demo_data.STATIONS]
        schools = [{"name": n, "lat": la, "lng": lo} for n, la, lo, _ in demo_data.ELEM_SCHOOLS]
        zones = [{"name": n, "ring": poly + [poly[0]]} for n, _, _, poly in demo_data.ELEM_SCHOOLS]
        zone_note = "데모 경계"
    middle, academies = (poi or {}).get("middle") or [], (poi or {}).get("academies") or []
    global MIDDLE_ZONES_OFFICIAL
    MIDDLE_ZONES_OFFICIAL = [(z, ring) for z in ((poi or {}).get("official") or {}).get("middle", []) for ring in z["rings"]]
    global SCHOOL_STATS, TERRAIN, HIGH_ZONES_OFFICIAL, HIGH_SCHOOLS, NUISANCE, AMENITIES
    NUISANCE = load_nuisance() if real else {}
    AMENITIES = load_amenities() if real else {}
    HIGH_ZONES_OFFICIAL = [(z, ring) for z in ((poi or {}).get("official") or {}).get("high", []) for ring in z["rings"]]
    HIGH_SCHOOLS = load_high_schools() if real else {}
    SCHOOL_STATS = load_schoolinfo() if real else {}
    if Terrain and os.path.isdir(os.path.join(RAW, "terrain")):
        TERRAIN = Terrain()
    # 초등 순전입/학생증가 구내 순위 -> 장단점
    elem_rank = {}
    if SCHOOL_STATS:
        el = [(n, v) for n, v in SCHOOL_STATS.items() if v.get("net_move_pct") is not None and any(x["name"] == n for x in schools)]
        el.sort(key=lambda x: -(x[1]["net_move_pct"] or 0))
        for i, (n, v) in enumerate(el):
            elem_rank[n] = (i + 1, len(el))
    fp = os.path.join(RAW, "future_rail.json")
    if poi and os.path.exists(fp):
        fr = json.load(open(fp, encoding="utf-8"))
        FUTURE_RAIL["lines"], FUTURE_RAIL["stations"] = fr["lines"], fr["stations"]
    cs = [enrich(c, roads, today, stations, schools, zones, middle, academies) for c in cs]
    cs = [c for c in cs if c["by_area"]]
    for c in cs:
        st = c["school"].get("elem_stats")
        if st:
            rk = elem_rank.get(c["school"]["elem"])
            c["school"]["elem_rank"] = rk
            if st.get("chg_pct") is not None and st["chg_pct"] >= 3:
                c["pros"].append("배정 초등 학생 수 증가 (전년 대비 +{}%)".format(st["chg_pct"]))
            elif st.get("chg_pct") is not None and st["chg_pct"] <= -8:
                c["cons"].append("배정 초등 학생 수 감소 (전년 대비 {}%)".format(st["chg_pct"]))
            if st.get("class_size") and st["class_size"] >= 24:
                c["cons"].append("배정 초등 학급당 {}명 (수도권 중앙값 18명)".format(st["class_size"]))
            if rk and rk[0] <= max(3, rk[1] // 5):
                c["pros"].append("배정 초등 전입 선호도 상위 (권역 {}위/{})".format(rk[0], rk[1]))
            c["pros"], c["cons"] = c["pros"][:5], c["cons"][:5]
    # 학군 지수 (0~100): 교과학원 밀집 40 + 초등 전입 선호 25 + 초등 학생 증감 15 + 중학교 규모/과밀 20
    def pct_rank(vals, v, higher_better=True):
        if not vals or v is None:
            return None
        below = sum(1 for x in vals if (x < v if higher_better else x > v))
        return below / max(1, len(vals) - 1) * 100
    ex_vals = [c["edu"]["exam_1km"] for c in cs if c.get("edu")]
    nm_vals = [c["school"]["elem_stats"]["net_move_pct"] for c in cs if c["school"].get("elem_stats") and c["school"]["elem_stats"].get("net_move_pct") is not None]
    ch_vals = [c["school"]["elem_stats"]["chg_pct"] for c in cs if c["school"].get("elem_stats") and c["school"]["elem_stats"].get("chg_pct") is not None]
    def mid_score(c):
        ms = [m["stats"] for m in c["school"].get("middle_detail", []) if m.get("stats")]
        if not ms:
            return None
        # 학생 수 많고(선호) 학급당 적정(<=27)인 학교가 많을수록 높게
        return sum(min(1.0, m["students"] / 700.0) * (1.0 if (m.get("class_size") or 0) <= 27 else 0.7) for m in ms) / len(ms) * 100
    md_vals = [v for v in (mid_score(c) for c in cs) if v is not None]
    scored = []
    for c in cs:
        st = c["school"].get("elem_stats") or {}
        parts = [
            (pct_rank(ex_vals, c["edu"]["exam_1km"]) if c.get("edu") else None, 0.40),
            (pct_rank(nm_vals, st.get("net_move_pct")), 0.25),
            (pct_rank(ch_vals, st.get("chg_pct")), 0.15),
            (pct_rank(md_vals, mid_score(c)), 0.20),
        ]
        avail = [(v, w) for v, w in parts if v is not None]
        if not avail:
            c["edu_score"] = None
            continue
        c["edu_score"] = round(sum(v * w for v, w in avail) / sum(w for _, w in avail))
        scored.append(c["edu_score"])
    scored.sort(reverse=True)
    for c in cs:
        if c.get("edu_score") is not None:
            c["edu_rank"] = scored.index(c["edu_score"]) + 1
            c["edu_top_pct"] = max(1, int(round(c["edu_rank"] / len(scored) * 100)))
            if c["edu_top_pct"] <= 10:
                c["pros"].insert(0, "학군 지수 {} (구 상위 {}%)".format(c["edu_score"], c["edu_top_pct"]))
                c["pros"] = c["pros"][:5]
    # 예산 대비 학군: 같은 가격대 안에서의 학군 순위
    #   "대치동이 좋은 건 누구나 안다. 내 예산으로 갈 수 있는 최고 학군은 어디냐"에 답하는 지표.
    BANDS = [(0, 50000, "5억 미만"), (50000, 80000, "5~8억"), (80000, 110000, "8~11억"),
             (110000, 150000, "11~15억"), (150000, 200000, "15~20억"), (200000, 10 ** 9, "20억 이상")]

    def rep_price(c):
        """대표 실거래가(만원): 84㎡급(70~100㎡) 우선, 없으면 거래 많은 평형."""
        ba = [a for a in c.get("by_area") or [] if a.get("latest")]
        if not ba:
            return None
        mid = [a for a in ba if 70 <= a["area"] < 100]
        pick = max(mid or ba, key=lambda a: a["count"])
        return pick["latest"]

    for c in cs:
        c["rep_price"] = rep_price(c)
        c["budget_band"] = next((lbl for lo, hi, lbl in BANDS if c["rep_price"] and lo <= c["rep_price"] < hi), None)
    for lo, hi, lbl in BANDS:
        grp = [c for c in cs if c.get("budget_band") == lbl and c.get("edu_score") is not None]
        if len(grp) < 5:
            continue
        vals = sorted((c["edu_score"] for c in grp), reverse=True)
        for c in grp:
            r_ = vals.index(c["edu_score"]) + 1
            c["edu_band_pct"] = max(1, int(round(r_ / len(vals) * 100)))
            c["edu_band_n"] = len(vals)
            # 카드 태그(app.js)와 단지 페이지에서 따로 보여주므로 pros 에는 넣지 않는다 (중복 방지)

    # 동네 학원비: 비싼 순 백분위 (상위 10% = 서울에서 가장 비싼 축)
    fee_vals = sorted((c["edu"]["fee_med"] for c in cs if c.get("edu") and c["edu"].get("fee_med")), reverse=True)
    for c in cs:
        fm = c["edu"].get("fee_med") if c.get("edu") else None
        if not fm:
            continue
        c["fee_top_pct"] = max(1, int(round((fee_vals.index(fm) + 1) / len(fee_vals) * 100)))
        man = round(fm / 10000)
        if c["fee_top_pct"] <= 10:
            c["cons"].append("학원비 비싼 편 (1km 내 교과학원 월 중앙값 {}만원, 수도권 상위 {}%)".format(man, c["fee_top_pct"]))
        elif c["fee_top_pct"] >= 60 and (c.get("edu_score") or 0) >= 55:
            c["pros"].append("학군 대비 학원비 저렴 (월 중앙값 {}만원)".format(man))
            c["pros"] = c["pros"][:5]

    # 아이 키우기 점수 순위
    ks = sorted((c["kid"]["score"] for c in cs if c.get("kid")), reverse=True)
    for c in cs:
        if c.get("kid"):
            r_ = ks.index(c["kid"]["score"]) + 1
            c["kid"]["rank"], c["kid"]["top_pct"] = r_, max(1, int(round(r_ / len(ks) * 100)))
            if c["kid"]["top_pct"] <= 10:
                c["pros"].insert(0, "아이 키우기 점수 {} (수도권 상위 {}%)".format(c["kid"]["score"], c["kid"]["top_pct"]))
                c["pros"] = c["pros"][:5]
    # 학원 밀집도 구내 백분위 (교과학원 기준)
    vals = sorted(c["edu"]["exam_1km"] for c in cs if c.get("edu"))
    for c in cs:
        if not c.get("edu"):
            continue
        v = c["edu"]["exam_1km"]
        pct = 100 - int(round(sum(1 for x in vals if x <= v) / len(vals) * 100))     # 0 = 최상위
        c["edu"]["exam_top_pct"] = max(1, pct if pct > 0 else 1)
        if pct <= 20 and v >= 15:
            c["pros"].insert(0, "학원가 인접 (1km 내 교과학원 {}개, 구 상위 {}%)".format(v, c["edu"]["exam_top_pct"]))
            c["pros"] = c["pros"][:4]
        elif v <= 2:
            c["cons"].append("주변 교과학원 적음 (1km 내 {}개)".format(v))
            c["cons"] = c["cons"][:4]

    aucs = load_auctions(cs)
    by_id = {c["id"]: c for c in cs}
    for a in aucs:
        c = by_id.get(a["complex_id"])
        if c:
            a.update({"name": c["name"], "lat": c["lat"], "lng": c["lng"]})
            a["discount_pct"] = round((1 - a["min_price"] / a["appraisal"]) * 100, 1)
            recent = [t for t in c["trades"] if abs(t["area"] - a["area"]) < 3]
            a["recent_trade"] = recent[-1]["price"] if recent else None
            # 시세 대비 최저입찰가. 경매 앱은 시세를 모르고 부동산 앱은 경매를 모른다 - 이게 우리 자리다.
            if a["recent_trade"]:
                a["vs_trade_pct"] = round((1 - a["min_price"] / a["recent_trade"]) * 100, 1)
            c.setdefault("auctions", []).append(a["case"])

    os.makedirs(OUT, exist_ok=True)
    dump = lambda name, obj: json.dump(obj, open(os.path.join(OUT, name), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    # 요약(목록/핀용)은 complexes.json, 전체(거래내역 등)는 c/<id>.json 으로 분리 -> 서울 전체에서도 첫 로딩 가볍게
    SUMMARY_KEYS = ("id", "name", "sgg", "umd", "addr", "lat", "lng", "households", "built", "ppy", "chg_1y", "trade_count_1y",
                    "jeonse_ratio", "sale_type", "edu_score", "edu_top_pct", "edu_rank", "pros", "cons", "notes",
                    "rep_price", "budget_band", "edu_band_pct", "edu_band_n")
    cdir = os.path.join(OUT, "c")
    os.makedirs(cdir, exist_ok=True)
    for f in os.listdir(cdir):
        os.remove(os.path.join(cdir, f))
    summary = []
    for c in cs:
        sm = {k: c.get(k) for k in SUMMARY_KEYS if k not in ("addr", "notes", "edu_rank")}
        sm["lat"], sm["lng"] = round(c["lat"], 5), round(c["lng"], 5)
        sm["pros"], sm["cons"] = c["pros"][:2], c["cons"][:1]
        ba = sorted(c["by_area"], key=lambda a: -a["count"])[:3]
        sm["by_area"] = [{k: a.get(k) for k in ("area", "latest", "latest_date", "count", "jeonse_ratio")} for a in sorted(ba, key=lambda a: a["area"])]
        sm["station"] = {k: c["station"].get(k) for k in ("name", "walk_min", "dist", "lines")}
        if c.get("terrain"):
            sm["terrain"] = {k: c["terrain"].get(k) for k in ("elev", "station_dh", "slope_pct")}
        sm["nz"] = sum(1 for v in c.get("nuisance", {}).values() if v["within"])
        sm["risk_n"], sm["up_n"] = len(c["signals"]["risk"]), len(c["signals"]["up"])
        sm["kid"] = c["kid"]["score"] if c.get("kid") else None
        sm["kid_pct"] = c["kid"].get("top_pct") if c.get("kid") else None
        sm["stn"] = c["station"]["name"]
        if c.get("future"):
            sm["fut"] = c["future"]
        mg = c["school"].get("middle_gender") or {}
        sm["mg"] = [mg.get("공학", 0) + mg.get("남", 0), mg.get("공학", 0) + mg.get("여", 0)]   # [아들 기준, 딸 기준] 지원 가능 중학교 수
        sm["school"] = {k: c["school"][k] for k in ("elem", "elem_walk_min", "chopuma")}
        st_ = c["school"].get("elem_stats") or {}
        sm["school"]["class_size"] = st_.get("class_size")
        if c.get("edu") and c["edu"].get("fee_med"):
            sm["fee"], sm["fee_pct"], sm["fee_n"] = c["edu"]["fee_med"], c.get("fee_top_pct"), c["edu"]["fee_n"]
        summary.append(sm)
        json.dump(c, open(os.path.join(cdir, c["id"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    dump("complexes.json", pack_summary(summary))
    feats = []
    for z in zones:
        feats.append({"type": "Feature", "properties": {"name": z["name"], "kind": "zone", "note": zone_note, "shared": bool(z.get("shared"))},
                      "geometry": {"type": "Polygon", "coordinates": [z["ring"]]}})
    # 초·중·고를 모두 올린다. 옆에 붙는 숫자는 학급당 평균 인원(학교알리미 공시).
    # 학업성취도는 2017년 이후 비공개라 쓸 수 없고, 고교 진로 현황의 비율 필드는 전부 100%로
    # 나와(졸업생 구성 합계) 진학률로 쓸 수 없었다. 학급당 인원이 유일하게 해석이 분명한 숫자다.
    def cls_size(name):
        st = (SCHOOL_STATS or {}).get(name) or {}
        v = st.get("class_size")
        return round(v, 1) if v else None

    seen_school = set()

    def add_school(name, lat, lng, level, extra=None):
        if not name or not lat or not lng or name in seen_school:
            return
        seen_school.add(name)
        props = {"name": name, "kind": "school", "level": level, "class_size": cls_size(name)}
        props.update(extra or {})
        feats.append({"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": [lng, lat]}})

    for sc in schools:
        add_school(sc["name"], sc.get("lat"), sc.get("lng"), "elem")
    for m in middle:
        add_school(m.get("name"), m.get("lat"), m.get("lng"), "middle",
                   {"coedu": m.get("coedu", "")})
    for h in (HIGH_SCHOOLS or {}).values():
        add_school(h.get("name"), h.get("lat"), h.get("lng"), "high",
                   {"coedu": h.get("coedu", ""), "hstype": h.get("type", "")})
    dump("schools.geojson", {"type": "FeatureCollection", "features": feats})
    nfeats = []
    for kind, d in NUISANCE.items():
        label = NUISANCE_KINDS.get(kind, (kind, 0))[0]
        for x in d["points"]:
            nfeats.append({"type": "Feature", "properties": {"kind": kind, "label": label, "name": x.get("name", "")}, "geometry": {"type": "Point", "coordinates": [x["lng"], x["lat"]]}})
        for l in d["lines"]:
            nfeats.append({"type": "Feature", "properties": {"kind": kind, "label": label, "name": l.get("name", "")}, "geometry": {"type": "LineString", "coordinates": l["coords"]}})
    dump("nuisance.geojson", {"type": "FeatureCollection", "features": nfeats})
    # 지도 표시는 랜드마크급만 남긴다. 점수 계산에는 전체 AMENITIES 를 그대로 쓴다.
    BIG_PARK_M2 = 30000          # 3만㎡ = 축구장 4개. 서울에 266곳.
    MART_BRANDS = ("이마트", "트레이더스", "홈플러스", "Homeplus", "롯데마트", "코스트코", "Costco",
                   "백화점", "스타필드", "타임스퀘어", "코엑스", "IFC", "더현대", "아울렛", "롯데월드몰")
    MAP_KINDS = {"park", "mart", "emergency", "university"}
    BIG_ACADEMY = 300            # 정원 300명 이상 입시·보습 학원. 서울에 1,740곳.

    # "케이마트"·"오케이마트"가 "이마트"로 걸리지 않게 앞이 글자가 아닐 때만 인정한다.
    mart_re = re.compile(r"(?:^|[\s(\[/·\-])(" + "|".join(map(re.escape, MART_BRANDS)) + ")")

    def landmark(kind, x):
        if kind == "park":
            return (x.get("area_m2") or 0) >= BIG_PARK_M2
        if kind == "mart":
            return bool(mart_re.search(x.get("name") or ""))
        return True

    afeats = []
    for kind, d in AMENITIES.items():
        if kind not in MAP_KINDS:
            continue
        label = AMENITY_KINDS.get(kind, kind)
        for x in d["points"]:
            if not landmark(kind, x):
                continue
            afeats.append({"type": "Feature", "properties": {"kind": kind, "label": label, "name": x.get("name", ""), "area": x.get("area_m2")},
                           "geometry": {"type": "Point", "coordinates": [x["lng"], x["lat"]]}})
            if x.get("ring"):
                afeats.append({"type": "Feature", "properties": {"kind": "park_area", "name": x.get("name", "")}, "geometry": {"type": "Polygon", "coordinates": [x["ring"]]}})
    # 대형 입시학원도 랜드마크다. 대치동·중계동 학원가가 어디인지 지도에서 바로 보인다.
    # 원격학원은 정원이 수십만으로 잡혀 있어 이름으로 걸러낸다(실제 건물이 아니다).
    seen_ac = set()
    for a_ in academies or []:
        cap = a_.get("capacity") or 0
        nm = a_.get("name") or ""
        if not a_.get("lat") or nm in seen_ac or "원격" in nm:
            continue
        if a_.get("kind") != "학원" or (a_.get("realm") or "") != "입시.검정 및 보습":
            continue
        if not (BIG_ACADEMY <= cap <= 6000):
            continue
        seen_ac.add(nm)
        afeats.append({"type": "Feature",
                       "properties": {"kind": "academy", "label": "대형 입시학원", "name": nm, "cap": cap},
                       "geometry": {"type": "Point", "coordinates": [a_["lng"], a_["lat"]]}})
    dump("amenities.geojson", {"type": "FeatureCollection", "features": afeats})

    # 구 경계 + 구별 통계 + 대장 아파트 (줌 아웃 뷰)
    try:
        from build_schoolzones import simplify as _simp
    except Exception:
        _simp = lambda pts, tol: pts
    dfeats = []
    by_gu = {}
    for c in cs:
        by_gu.setdefault(c["sgg"], []).append(c)
    for bp in sorted(glob.glob(os.path.join(RAW, "boundary_*.geojson"))):
        gu = os.path.basename(bp)[len("boundary_"):-len(".geojson")]
        ring = json.load(open(bp, encoding="utf-8"))["geometry"]["coordinates"][0]
        ring = [[round(x, 5), round(y, 5)] for x, y in _simp([tuple(p) for p in ring], 0.0004)]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        members = by_gu.get(gu, [])
        ppys = sorted(c["ppy"] for c in members if c.get("ppy"))
        med = ppys[len(ppys) // 2] if ppys else None
        # 대장: 세대수 300+(또는 미상) 이고 1년 거래 5건+ 인 단지 중 평당가 최고 3개
        pool = [c for c in members if c.get("ppy") and c["trade_count_1y"] >= 5 and (not c.get("households") or c["households"] >= 300)]
        pool.sort(key=lambda c: -c["ppy"])
        top = [{"id": c["id"], "name": c["name"], "ppy": c["ppy"], "lat": c["lat"], "lng": c["lng"],
                "latest": (sorted(c["by_area"], key=lambda b: -b["count"])[0]["latest"] if c["by_area"] else None),
                "area": (sorted(c["by_area"], key=lambda b: -b["count"])[0]["area"] if c["by_area"] else None)} for c in pool[:3]]
        lngs, lats = [p[0] for p in ring], [p[1] for p in ring]
        dfeats.append({"type": "Feature", "properties": {"name": gu, "n": len(members), "ppy_med": med, "top": top,
                                                          "center": [round(sum(lngs) / len(lngs), 5), round(sum(lats) / len(lats), 5)]},
                       "geometry": {"type": "Polygon", "coordinates": [ring]}})
    if FUTURE_RAIL["lines"]:
        fl = FUTURE_RAIL["lines"]
        fl = {"type": "FeatureCollection", "features": fl["features"] + [
            {"type": "Feature", "properties": {"name": s["name"], "line": s["line"], "kind": "station"},
             "geometry": {"type": "Point", "coordinates": [s["lng"], s["lat"]]}} for s in FUTURE_RAIL["stations"]]}
        dump("future_rail.geojson", fl)
    if subway:
        dump("subway_lines.geojson", subway["lines"])
        if subway.get("graph"):
            dump("subway_graph.json", subway["graph"])
    dump("stations.geojson", {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"name": s["name"], "line": s.get("line") or "", "color": s.get("color") or "#0EA5E9",
                                           "transfer": len(s.get("lines") or []) >= 2},
         "geometry": {"type": "Point", "coordinates": [round(s["lng"], 6), round(s["lat"], 6)]}} for s in stations]})
    dump("districts.geojson", {"type": "FeatureCollection", "features": dfeats})
    dump("auctions.json", [a for a in aucs if "lat" in a])
    dump("meta.json", {
        "mode": mode, "built_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "area": (area_label(cs) if mode == "real" else "서울 마포구 (공덕·아현·염리 데모)"),
        "complexes": len(cs), "roads": len(roads),
        "center": [round(sum(c["lng"] for c in cs) / len(cs), 5), round(sum(c["lat"] for c in cs) / len(cs), 5)],
        "zone_note": zone_note, "stations": len(stations), "schools": len(schools), "academies": len(academies),
    })
    print("mode={} 단지 {}개, 도로 {}개, 경매 {}건 -> {}".format(mode, len(cs), len(roads), len(aucs), OUT))
    for c in cs[:5]:
        print("  {:14s} 평당 {:>6,}만 1y {:+.1f}%  초등 {} {}m  역 {} {}m  대로 {}m | {} / {}".format(
            c["name"][:14], c["ppy"] or 0, c["chg_1y"] or 0, c["school"]["elem"], c["school"]["elem_dist"],
            c["station"]["name"], c["station"]["dist"], c["road"]["major_dist"], ", ".join(c["pros"]), ", ".join(c["cons"])))


if __name__ == "__main__":
    main()
