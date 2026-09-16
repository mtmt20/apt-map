"""IndexNow 로 검색엔진(빙·네이버·야후 등)에 URL 색인을 직접 요청한다.

  python pipeline/indexnow.py            # 허브/콘텐츠 페이지(sitemap-core.xml)
  python pipeline/indexnow.py --all      # 단지 페이지까지 (많으니 주의)

계정·인증 없이 동작하며, 사이트 루트에 있는 <키>.txt 파일로 소유권을 증명한다.
색인을 '보장'하지는 않고 크롤러에게 알리는 용도다.
"""
import argparse
import glob
import os
import re

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
BASE = "https://jipkokmap.kr"
ENDPOINT = "https://api.indexnow.org/IndexNow"


def find_key():
    for p in glob.glob(os.path.join(APP, "*.txt")):
        name = os.path.basename(p)[:-4]
        if re.fullmatch(r"[0-9a-f]{32}", name):
            return name
    raise SystemExit("키 파일(app/<32자리16진수>.txt)이 없습니다")


def urls_from(path):
    if not os.path.exists(path):
        return []
    return re.findall(r"<loc>([^<]+)</loc>", open(path, encoding="utf-8").read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="단지 페이지까지 포함")
    a = ap.parse_args()
    key = find_key()
    urls = urls_from(os.path.join(APP, "sitemap-core.xml"))
    if a.all:
        urls += urls_from(os.path.join(APP, "sitemap-apt.xml"))
    urls = [u for u in urls if u.startswith(BASE)][:10000]
    if not urls:
        raise SystemExit("보낼 URL 이 없습니다 (generate_content.py 먼저 실행)")
    body = {"host": "jipkokmap.kr", "key": key, "keyLocation": "{}/{}.txt".format(BASE, key), "urlList": urls}
    r = requests.post(ENDPOINT, json=body, headers={"Content-Type": "application/json; charset=utf-8"}, timeout=60)
    print("URL {}개 제출 -> HTTP {} {}".format(len(urls), r.status_code, (r.text or "")[:200]))
    print("  200/202 면 접수된 것입니다 (색인 보장은 아님)")


if __name__ == "__main__":
    main()
