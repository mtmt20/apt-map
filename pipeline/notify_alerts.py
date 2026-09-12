"""찜 단지 실거래 알림 메일 발송 (refresh.py 의 build 이후 단계)

  python pipeline/notify_alerts.py [--dry]

- 워커 /admin/alerts 에서 알림 등록(이메일별 단지 id 목록)을 받는다 (ADMIN_KEY 필요).
- data/raw/alert_state.json 에 단지별 '마지막으로 알린 거래 시각(date)' 을 기록하고, app/data/c/<id>.json 의 거래 중
  그보다 새로운 거래가 있으면 메일로 보낸다 (첫 실행은 기준만 저장하고 보내지 않음).
- SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD/ALERT_FROM_EMAIL 이 없으면 발송을 건너뛰고 로그만 남긴다.
"""
import argparse
import json
import os
import smtplib
import sys
from email.mime.text import MIMEText
from email.utils import formataddr

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from fetch_trades import load_env, RAW  # noqa: E402

STATE = os.path.join(RAW, "alert_state.json")
CDIR = os.path.join(ROOT, "app", "data", "c")
SITE = "https://mtmt88087044-pixel.github.io/apt-map"


def fmt(v):
    return "{:.1f}억".format(v / 10000).replace(".0억", "억") if v >= 10000 else "{:,}만".format(v)


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    api = os.environ.get("APT_API_BASE") or "https://aptmap-api.jipkokmap.workers.dev"
    key = os.environ.get("ADMIN_KEY", "")
    if not key:
        raise SystemExit("ADMIN_KEY 없음")
    alerts = requests.get("{}/admin/alerts?key={}".format(api, key), timeout=30).json().get("alerts", [])
    state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    first_run = not state
    wanted = sorted({i for al in alerts for i in al["ids"]})
    print("알림 등록 {}명, 대상 단지 {}개".format(len(alerts), len(wanted)))
    news = {}
    for cid in wanted:
        p = os.path.join(CDIR, cid + ".json")
        if not os.path.exists(p):
            continue
        c = json.load(open(p, encoding="utf-8"))
        last = state.get(cid, "")
        fresh = [t for t in c["trades"] if t["date"] > last] if last else []
        if c["trades"]:
            state[cid] = max(t["date"] for t in c["trades"])
        if fresh and not first_run:
            news[cid] = (c, sorted(fresh, key=lambda t: t["date"], reverse=True)[:5])
    json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if first_run:
        print("첫 실행: 기준일만 저장 (발송 없음)")
        return 0
    smtp = {k: os.environ.get(k, "") for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "ALERT_FROM_EMAIL")}
    sent = 0
    for al in alerts:
        hits = [(cid, news[cid]) for cid in al["ids"] if cid in news]
        if not hits:
            continue
        lines = ["찜한 단지에 새 실거래가 등록됐어요.\n"]
        for cid, (c, fresh) in hits:
            lines.append("■ {} ({})".format(c["name"], c["addr"]))
            for t in fresh:
                lines.append("   {} · {}㎡ {}층 · {}".format(t["date"], int(t["area"]), t["floor"], fmt(t["price"])))
            lines.append("   {}/index.html?id={}\n".format(SITE, cid))
        lines.append("수신 해제: {}/alerts/unsub?email={}&t={}".format(api, al["email"], al["token"]))
        body = "\n".join(lines)
        subject = "[집콕맵] 찜한 단지 {}곳에 새 실거래".format(len(hits))
        if a.dry or not all(smtp.values()):
            print("--- (미발송) to {}\n{}".format(al["email"], body[:600]))
            continue
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"], msg["From"], msg["To"] = subject, formataddr(("집콕맵", smtp["ALERT_FROM_EMAIL"])), al["email"]
        try:
            with smtplib.SMTP(smtp["SMTP_HOST"], int(smtp["SMTP_PORT"]), timeout=30) as s:
                s.starttls()
                s.login(smtp["SMTP_USER"], smtp["SMTP_PASSWORD"])
                s.sendmail(smtp["ALERT_FROM_EMAIL"], [al["email"]], msg.as_string())
            sent += 1
        except Exception as e:  # noqa
            print("발송 실패", al["email"], e)
    print("발송 {}건".format(sent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
