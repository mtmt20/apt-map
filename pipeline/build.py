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


def load_nuisance():
    """OSM + LOCALDATA 기피시설 -> {kind: {"points": [...], "lines": [...]}} + 격자 인덱스"""
    out = {}
    p = os.path.join(RAW, "nuisance_osm.json")
    if os.path.exists(p):
        for kind, items in json.load(open(p, encoding="utf-8")).items():
            if items and "coords" in items[0]:
                out[kind] = {"lines": items, "points": []}
            else:
                out[kind] = {"lines": [], "points": items}
    p2 = os.path.join(RAW, "nuisance_localdata.json")
    if os.path.exists(p2):
        for kind, items in json.load(open(p2, encoding="utf-8")).items():
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
    c["station"] = {"name": s0["name"], "line": s0["line"], "dist": round(d0), "walk_min": max(1, round(d0 / 70)),
                    "within_600": [{"name": n, "line": l, "dist": d} for d, n, l in near]}

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
    elif middle:
        near_mid = sorted(((dist_m(c["lat"], c["lng"], m["lat"], m["lng"]), m) for m in middle), key=lambda x: x[0])[:3]
        mids = [m["name"] for d, m in near_mid]
        mid_detail = [{"name": m["name"], "dist": round(d), "public": m.get("public", ""), "coedu": m.get("coedu", "")} for d, m in near_mid]
        mid_note = "가까운 중학교 3곳 (실제 배정은 학교군 내 추첨)"
    else:
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
        high = {"zone": hz["name"] if hz else None, "zone_total": len(zone_names) if hz else None,
                "general": [fmt(d, h) for d, h in gen[:5]], "special": [fmt(d, h) for d, h in spec]}
    c["school"] = {
        "high": high,
        "elem": elem["name"], "elem_dist": round(de), "elem_walk_min": max(1, round(de / 60)),
        "chopuma": de <= 300, "elem_stats": (SCHOOL_STATS or {}).get(elem["name"]),
        "elem_shared": elem_shared, "elem_official": zone_hit is not None and "zone_id" in zone_hit,
        "middle_zone": mid_zone["name"] if mid_zone else None,
        "middle": mids, "middle_detail": mid_detail, "middle_note": mid_note,
    }
    # 학원 밀집도 (반경 1km): 전체 / 입시·보습 교과
    if academies:
        if id(academies) not in _ACA_IDX:
            _ACA_IDX.clear()
            _ACA_IDX[id(academies)] = grid_index(academies, lambda x: [(x["lng"], x["lat"])])
        near = [x for x in grid_near(_ACA_IDX[id(academies)], c["lng"], c["lat"]) if dist_m(c["lat"], c["lng"], x["lat"], x["lng"]) <= 1000]
        c["edu"] = {"aca_1km": len(near), "exam_1km": sum(1 for x in near if "입시" in (x.get("realm") or "")),
                    "art_1km": sum(1 for x in near if "예능" in (x.get("realm") or ""))}
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
    else:
        stations = [{"name": n, "line": l, "lat": la, "lng": lo} for n, l, la, lo in demo_data.STATIONS]
        schools = [{"name": n, "lat": la, "lng": lo} for n, la, lo, _ in demo_data.ELEM_SCHOOLS]
        zones = [{"name": n, "ring": poly + [poly[0]]} for n, _, _, poly in demo_data.ELEM_SCHOOLS]
        zone_note = "데모 경계"
    middle, academies = (poi or {}).get("middle") or [], (poi or {}).get("academies") or []
    global MIDDLE_ZONES_OFFICIAL
    MIDDLE_ZONES_OFFICIAL = [(z, ring) for z in ((poi or {}).get("official") or {}).get("middle", []) for ring in z["rings"]]
    global SCHOOL_STATS, TERRAIN, HIGH_ZONES_OFFICIAL, HIGH_SCHOOLS, NUISANCE
    NUISANCE = load_nuisance() if real else {}
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
            if st.get("class_size") and st["class_size"] >= 28:
                c["cons"].append("배정 초등 과밀 (학급당 {}명)".format(st["class_size"]))
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

    aucs = demo_data.auctions()
    by_id = {c["id"]: c for c in cs}
    for a in aucs:
        c = by_id.get(a["complex_id"])
        if c:
            a.update({"name": c["name"], "lat": c["lat"], "lng": c["lng"]})
            a["discount_pct"] = round((1 - a["min_price"] / a["appraisal"]) * 100, 1)
            recent = [t for t in c["trades"] if abs(t["area"] - a["area"]) < 3]
            a["recent_trade"] = recent[-1]["price"] if recent else None
            c.setdefault("auctions", []).append(a["case"])

    os.makedirs(OUT, exist_ok=True)
    dump = lambda name, obj: json.dump(obj, open(os.path.join(OUT, name), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    # 요약(목록/핀용)은 complexes.json, 전체(거래내역 등)는 c/<id>.json 으로 분리 -> 서울 전체에서도 첫 로딩 가볍게
    SUMMARY_KEYS = ("id", "name", "sgg", "umd", "addr", "lat", "lng", "households", "built", "ppy", "chg_1y", "trade_count_1y",
                    "jeonse_ratio", "sale_type", "edu_score", "edu_top_pct", "edu_rank", "pros", "cons", "notes")
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
        sm["station"] = {k: c["station"][k] for k in ("name", "walk_min", "dist")}
        if c.get("terrain"):
            sm["terrain"] = {k: c["terrain"].get(k) for k in ("elev", "station_dh", "slope_pct")}
        sm["nz"] = sum(1 for v in c.get("nuisance", {}).values() if v["within"])
        sm["risk_n"], sm["up_n"] = len(c["signals"]["risk"]), len(c["signals"]["up"])
        sm["school"] = {k: c["school"][k] for k in ("elem", "elem_walk_min", "chopuma")}
        summary.append(sm)
        json.dump(c, open(os.path.join(cdir, c["id"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    dump("complexes.json", summary)
    feats = []
    for z in zones:
        feats.append({"type": "Feature", "properties": {"name": z["name"], "kind": "zone", "note": zone_note, "shared": bool(z.get("shared"))},
                      "geometry": {"type": "Polygon", "coordinates": [z["ring"]]}})
    for sc in schools:
        feats.append({"type": "Feature", "properties": {"name": sc["name"], "kind": "school"},
                      "geometry": {"type": "Point", "coordinates": [sc["lng"], sc["lat"]]}})
    dump("schools.geojson", {"type": "FeatureCollection", "features": feats})
    nfeats = []
    for kind, d in NUISANCE.items():
        label = NUISANCE_KINDS.get(kind, (kind, 0))[0]
        for x in d["points"]:
            nfeats.append({"type": "Feature", "properties": {"kind": kind, "label": label, "name": x.get("name", "")}, "geometry": {"type": "Point", "coordinates": [x["lng"], x["lat"]]}})
        for l in d["lines"]:
            nfeats.append({"type": "Feature", "properties": {"kind": kind, "label": label, "name": l.get("name", "")}, "geometry": {"type": "LineString", "coordinates": l["coords"]}})
    dump("nuisance.geojson", {"type": "FeatureCollection", "features": nfeats})
    dump("auctions.json", [a for a in aucs if "lat" in a])
    dump("meta.json", {
        "mode": mode, "built_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "area": (("서울 전체 ({}개 구)".format(len({c["sgg"] for c in cs})) if len({c["sgg"] for c in cs}) > 3 else "서울 " + "·".join(sorted({c["sgg"] for c in cs if c.get("sgg")}))) if mode == "real" else "서울 마포구 (공덕·아현·염리 데모)"),
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
