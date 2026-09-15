"""Cloudflare Workers + KV 로 집콕맵 API 배포 (wrangler 없이 REST API 만 사용)

  python pipeline/deploy_worker.py [--name aptmap-api]

필요: .env 의 CLOUDFLARE_API_TOKEN (템플릿 "Edit Cloudflare Workers" 권한: Workers Scripts Edit, Workers KV Storage Edit, Account Settings Read)
결과: https://<name>.<계정 subdomain>.workers.dev  -> app/config.js 의 API_BASE 에 기록
"""
import argparse
import json
import os
import re
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from fetch_trades import load_env  # noqa: E402

API = "https://api.cloudflare.com/client/v4"


def cf(s, method, path, **kw):
    r = s.request(method, API + path, **kw)
    try:
        j = r.json()
    except ValueError:
        raise SystemExit("CF {} {} -> {} {}".format(method, path, r.status_code, r.text[:300]))
    if not j.get("success"):
        raise SystemExit("CF {} {} 실패: {}".format(method, path, json.dumps(j.get("errors"), ensure_ascii=False)[:400]))
    return j.get("result")


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="aptmap-api")
    ap.add_argument("--kv", default="aptmap")
    a = ap.parse_args()
    tok = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not tok:
        raise SystemExit("CLOUDFLARE_API_TOKEN 없음 (.env)")
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + tok

    accounts = cf(s, "GET", "/accounts")
    if not accounts:
        raise SystemExit("계정을 찾지 못함 (토큰 권한에 Account Settings:Read 필요)")
    acc = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or accounts[0]["id"]
    print("계정:", accounts[0].get("name"), acc)

    # KV namespace
    ns = cf(s, "GET", "/accounts/{}/storage/kv/namespaces?per_page=100".format(acc))
    kv = next((n for n in ns if n["title"] == a.kv), None)
    if not kv:
        kv = cf(s, "POST", "/accounts/{}/storage/kv/namespaces".format(acc), json={"title": a.kv})
        print("KV 생성:", kv["id"])
    else:
        print("KV:", kv["id"])

    # Worker upload (module syntax + binding)
    src = open(os.path.join(ROOT, "worker", "worker.js"), encoding="utf-8").read()
    meta = {"main_module": "worker.js", "compatibility_date": "2025-01-01",
            "bindings": [{"type": "kv_namespace", "name": "APT", "namespace_id": kv["id"]},
                         {"type": "secret_text", "name": "ADMIN_KEY", "text": os.environ.get("ADMIN_KEY", "")}]}
    files = {
        "metadata": ("metadata.json", json.dumps(meta), "application/json"),
        "worker.js": ("worker.js", src, "application/javascript+module"),
    }
    cf(s, "PUT", "/accounts/{}/workers/scripts/{}".format(acc, a.name), files=files)
    print("워커 업로드:", a.name)

    # workers.dev subdomain
    sub = cf(s, "GET", "/accounts/{}/workers/subdomain".format(acc))
    subdomain = (sub or {}).get("subdomain")
    if not subdomain:
        raise SystemExit("workers.dev 서브도메인이 없습니다. 대시보드 > Workers & Pages 에서 한 번만 서브도메인을 정해주세요.")
    cf(s, "POST", "/accounts/{}/workers/scripts/{}/subdomain".format(acc, a.name), json={"enabled": True, "previews_enabled": False})
    base = "https://{}.{}.workers.dev".format(a.name, subdomain)
    print("API:", base)

    cfg = os.path.join(ROOT, "app", "config.js")
    cur = open(cfg, encoding="utf-8").read() if os.path.exists(cfg) else ""
    if "API_BASE" in cur:   # 다른 설정(COURT_LINK 등)은 보존하고 API_BASE 값만 교체
        cur = re.sub(r'API_BASE:\s*"[^"]*"', 'API_BASE: "%s"' % base, cur)
    else:
        cur = 'window.APT_CONFIG = { API_BASE: "%s" };\n' % base
    open(cfg, "w", encoding="utf-8").write(cur)
    print("app/config.js 갱신 -> 재배포(deploy_github_pages.py) 필요")
    r = requests.get(base + "/health", timeout=20)
    print("health:", r.status_code, r.text[:80])


if __name__ == "__main__":
    sys.exit(main())
