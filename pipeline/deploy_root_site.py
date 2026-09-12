"""사용자 루트 사이트(mtmt88087044-pixel.github.io) 배포: 검색엔진 소유확인 meta + /apt-map/ 로 리다이렉트

  python pipeline/deploy_root_site.py [--naver CODE] [--google CODE]

코드는 .env 의 NAVER_SITE_VERIFICATION / GOOGLE_SITE_VERIFICATION 에도 저장/사용한다.
저장소 <owner>.github.io 가 없으면 만들고 master 에 index.html, robots.txt 를 푸시한다 (Pages 는 자동 활성).
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from fetch_trades import load_env  # noqa: E402


def set_env(key, val):
    p = os.path.join(ROOT, ".env")
    s = open(p, encoding="utf-8").read()
    if re.search(r"^%s=" % key, s, re.M):
        s = re.sub(r"^%s=.*$" % key, lambda _: "{}={}".format(key, val), s, flags=re.M)
    else:
        s += "{}={}\n".format(key, val)
    open(p, "w", encoding="utf-8").write(s)


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", default="mtmt88087044-pixel")
    ap.add_argument("--naver", default="")
    ap.add_argument("--google", default="")
    a = ap.parse_args()
    if a.naver:
        set_env("NAVER_SITE_VERIFICATION", a.naver)
        os.environ["NAVER_SITE_VERIFICATION"] = a.naver
    if a.google:
        set_env("GOOGLE_SITE_VERIFICATION", a.google)
        os.environ["GOOGLE_SITE_VERIFICATION"] = a.google
    naver, google = os.environ.get("NAVER_SITE_VERIFICATION", ""), os.environ.get("GOOGLE_SITE_VERIFICATION", "")
    tok = os.environ.get("GITHUB_TOKEN", "")
    if not tok:
        raise SystemExit("GITHUB_TOKEN 없음")
    repo = "{}.github.io".format(a.owner)
    api = requests.Session()
    api.headers.update({"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json"})
    r = api.get("https://api.github.com/repos/{}/{}".format(a.owner, repo))
    if r.status_code == 404:
        r = api.post("https://api.github.com/user/repos", json={"name": repo, "private": False, "description": "집콕맵 루트 (apt-map 으로 이동)"})
        if r.status_code >= 300:
            raise SystemExit("저장소 생성 실패 {} {}".format(r.status_code, r.text[:200]))
        print("저장소 생성:", repo)
    metas = ""
    if naver:
        metas += '<meta name="naver-site-verification" content="{}">\n'.format(naver)
    if google:
        metas += '<meta name="google-site-verification" content="{}">\n'.format(google)
    html = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
{metas}<title>집콕맵</title><meta name="description" content="서울 아파트 실거래가·전세가율·학군·도로·생활편의 지도">
<link rel="canonical" href="https://{owner}.github.io/apt-map/">
<meta http-equiv="refresh" content="0; url=/apt-map/"><script>location.replace("/apt-map/" + location.search + location.hash);</script>
</head><body><p><a href="/apt-map/">집콕맵으로 이동</a></p></body></html>
""".format(metas=metas, owner=a.owner)
    tmp = tempfile.mkdtemp(prefix="rootsite_")
    try:
        open(os.path.join(tmp, "index.html"), "w", encoding="utf-8").write(html)
        open(os.path.join(tmp, "robots.txt"), "w", encoding="utf-8").write("User-agent: *\nAllow: /\nSitemap: https://{}.github.io/apt-map/sitemap.xml\n".format(a.owner))
        open(os.path.join(tmp, ".nojekyll"), "w").close()
        env = dict(os.environ, GH_TOKEN_FOR_PUSH=tok)
        helper = "!f() { echo username=x-access-token; echo password=$GH_TOKEN_FOR_PUSH; }; f"
        run = lambda cmd: subprocess.run(cmd, cwd=tmp, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        run(["git", "init", "-q"])
        run(["git", "-c", "user.name=deploy", "-c", "user.email=deploy@local", "add", "-A"])
        run(["git", "-c", "user.name=deploy", "-c", "user.email=deploy@local", "commit", "-qm", "root site"])
        run(["git", "branch", "-M", "master"])
        run(["git", "-c", "credential.helper=", "-c", "credential.helper=" + helper, "push", "--force", "https://github.com/{}/{}.git".format(a.owner, repo), "master:master"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    pages = "https://api.github.com/repos/{}/{}/pages".format(a.owner, repo)
    r = api.post(pages, json={"source": {"branch": "master", "path": "/"}})
    if r.status_code >= 300 and r.status_code != 409:
        api.put(pages, json={"source": {"branch": "master", "path": "/"}})
    print("루트 사이트 푸시 완료: https://{}.github.io/  (naver={}, google={})".format(a.owner, bool(naver), bool(google)))


if __name__ == "__main__":
    sys.exit(main())
