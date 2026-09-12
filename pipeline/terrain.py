"""고도(DEM) 유틸 + 타일 미리받기. AWS Terrarium 타일(무료, 키 불필요, ~30m 해상도).

  python pipeline/terrain.py --bbox 37.425,126.760,37.705,127.190   # 서울 전체 z14 타일 캐시 (약 320장)

build.py 에서:
  from terrain import Terrain
  t = Terrain(); t.elev(lat, lng) -> m ; t.slope_pct(lat, lng, r_m=100) -> 반경 내 최대 고도차/거리 %
타일 캐시: data/raw/terrain/<z>/<x>/<y>.png. 캐시에 없는 타일은 필요 시 내려받는다.
"""
import argparse
import io
import math
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "..", "data", "raw", "terrain")
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
Z = 14


def tile_xy(lat, lng, z=Z):
    n = 2 ** z
    x = (lng + 180.0) / 360.0 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


class Terrain:
    def __init__(self, cache=CACHE, z=Z):
        self.cache, self.z, self.tiles = cache, z, {}
        from PIL import Image  # noqa
        self.Image = Image

    def _tile(self, tx, ty):
        key = (tx, ty)
        if key in self.tiles:
            return self.tiles[key]
        p = os.path.join(self.cache, str(self.z), str(tx), "{}.png".format(ty))
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            for _ in range(3):
                try:
                    r = requests.get(URL.format(z=self.z, x=tx, y=ty), timeout=30)
                    if r.status_code == 200:
                        open(p, "wb").write(r.content)
                        break
                except requests.RequestException:
                    pass
                time.sleep(2)
        if not os.path.exists(p):
            self.tiles[key] = None
            return None
        im = self.Image.open(p).convert("RGB")
        self.tiles[key] = im.load(), im.size
        return self.tiles[key]

    def elev(self, lat, lng):
        x, y = tile_xy(lat, lng, self.z)
        tx, ty = int(x), int(y)
        t = self._tile(tx, ty)
        if not t:
            return None
        px, (w, h) = t
        i, j = min(w - 1, int((x - tx) * w)), min(h - 1, int((y - ty) * h))
        r, g, b = px[i, j]
        return round((r * 256 + g + b / 256.0) - 32768, 1)

    def slope_pct(self, lat, lng, r_m=100):
        """반경 r_m 안 8방향 샘플과의 최대 고도차 / 거리 (%)"""
        e0 = self.elev(lat, lng)
        if e0 is None:
            return None
        dlat = r_m / 110540.0
        dlng = r_m / (111320.0 * math.cos(math.radians(lat)))
        best = 0.0
        for a in range(0, 360, 45):
            e = self.elev(lat + dlat * math.sin(math.radians(a)), lng + dlng * math.cos(math.radians(a)))
            if e is not None:
                best = max(best, abs(e - e0))
        return round(best / r_m * 100, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", default="37.425,126.760,37.705,127.190")
    a = ap.parse_args()
    s, w, n, e = [float(v) for v in a.bbox.split(",")]
    x0, y1 = tile_xy(s, w)
    x1, y0 = tile_xy(n, e)
    t = Terrain()
    total = (int(x1) - int(x0) + 1) * (int(y1) - int(y0) + 1)
    done = 0
    for tx in range(int(x0), int(x1) + 1):
        for ty in range(int(y0), int(y1) + 1):
            t._tile(tx, ty)
            done += 1
            if done % 50 == 0:
                print("  {}/{}".format(done, total))
    print("타일 {}장 캐시 -> {}".format(total, CACHE))
    print("검증 남산 정상 근처:", t.elev(37.5512, 126.9882), "m / 여의도:", t.elev(37.5219, 126.9245), "m")


if __name__ == "__main__":
    sys.exit(main())
