"""GitHub Pages 배포: app/ 내용을 gh-pages 브랜치로 푸시하고 Pages 를 켠다.

  python pipeline/deploy_github_pages.py [--repo apt-map] [--owner mtmt88087044]

필요: .env 에 GITHUB_TOKEN (classic PAT: repo 스코프 / fine-grained: Contents RW + Pages RW + Administration RW).
- 저장소가 없으면 public 으로 만든다 (Pages 무료는 public 저장소만).
- master(소스)도 함께 푸시해 백업한다. gh-pages 는 app/ 만 담은 orphan 브랜치로 매번 새로 만든다.
- 토큰은 명령줄에 노출되지 않도록 임시 credential helper 로만 쓴다.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from fetch_trades import load_env  # noqa: E402


def run(cmd, cwd=ROOT, env=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    if check and r.returncode != 0:
        raise SystemExit("실패: {}\n{}".format(" ".join(cmd), r.stdout[-2000:]))
    return r.stdout


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", default="mtmt88087044")
    ap.add_argument("--repo", default="apt-map")
    ap.add_argument("--no-source", action="store_true", help="master 소스는 푸시하지 않음")
    a = ap.parse_args()
    tok = os.environ.get("GITHUB_TOKEN", "")
    if not tok:
        raise SystemExit("GITHUB_TOKEN 없음 (.env)")
    api = requests.Session()
    api.headers.update({"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})

    # 1) 저장소 확인/생성
    r = api.get("https://api.github.com/repos/{}/{}".format(a.owner, a.repo))
    if r.status_code == 404:
        r = api.post("https://api.github.com/user/repos", json={"name": a.repo, "private": False, "auto_init": False,
                                                              "description": "집콕맵 - 서울 아파트 실거래가·전세가율·학군·도로·생활편의 지도"})
        if r.status_code >= 300:
            raise SystemExit("저장소 생성 실패: {} {}".format(r.status_code, r.text[:300]))
        print("저장소 생성:", r.json()["html_url"])
    elif r.status_code >= 300:
        raise SystemExit("저장소 조회 실패: {} {}".format(r.status_code, r.text[:300]))
    else:
        print("저장소:", r.json()["html_url"])

    # 2) 토큰을 git 에 넘기는 임시 credential helper (프로세스 환경변수로만 전달)
    env = dict(os.environ, GIT_ASKPASS="", GH_TOKEN_FOR_PUSH=tok)
    helper = "!f() { echo username=x-access-token; echo password=$GH_TOKEN_FOR_PUSH; }; f"
    remote = "https://github.com/{}/{}.git".format(a.owner, a.repo)
    cred = ["-c", "credential.helper=", "-c", "credential.helper=" + helper]

    if not a.no_source:
        run(["git"] + cred + ["push", "--force", remote, "HEAD:master"], env=env)
        print("소스 푸시 완료 (master)")

    # 3) app/ 만 담은 orphan gh-pages 브랜치를 임시 디렉터리에서 만들어 푸시
    tmp = tempfile.mkdtemp(prefix="ghpages_")
    try:
        shutil.copytree(os.path.join(ROOT, "app"), os.path.join(tmp, "site"))
        site = os.path.join(tmp, "site")
        open(os.path.join(site, ".nojekyll"), "w").close()
        run(["git", "init", "-q"], cwd=site)
        run(["git", "-c", "user.name=deploy", "-c", "user.email=deploy@local", "add", "-A"], cwd=site)
        run(["git", "-c", "user.name=deploy", "-c", "user.email=deploy@local", "commit", "-qm", "deploy"], cwd=site)
        run(["git", "branch", "-M", "gh-pages"], cwd=site)
        run(["git"] + cred + ["push", "--force", remote, "gh-pages:gh-pages"], cwd=site, env=env)
        print("gh-pages 푸시 완료")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # 4) Pages 활성화 (이미 켜져 있으면 갱신)
    pages = "https://api.github.com/repos/{}/{}/pages".format(a.owner, a.repo)
    body = {"source": {"branch": "gh-pages", "path": "/"}}
    r = api.post(pages, json=body)
    if r.status_code == 409 or (r.status_code >= 400 and "already" in r.text.lower()):
        r = api.put(pages, json=body)
    if r.status_code >= 300 and r.status_code != 409:
        print("Pages 설정 응답:", r.status_code, r.text[:200])
    r = api.get(pages)
    url = r.json().get("html_url") if r.status_code == 200 else None
    print("Pages URL:", url or "https://{}.github.io/{}/".format(a.owner, a.repo), "(첫 배포는 1~2분 뒤 열림)")


if __name__ == "__main__":
    sys.exit(main())
