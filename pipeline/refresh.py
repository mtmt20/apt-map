"""주기 갱신 파이프라인 (Windows 작업 스케줄러에서 주 1회 실행)

  python pipeline/refresh.py [--full] [--no-deploy] [--skip-poi]

기본(주간): 실거래·전월세 이번달/지난달 재수집(25개 구) -> 새 단지 좌표 -> 새 단지 편의시설 -> build -> 페이지 -> GitHub Pages 배포
--full: K-apt, 학원(NEIS), 학교알리미까지 재수집 (분기 1회 정도)
로그: logs/refresh_YYYYMMDD_HHMM.log. 실패 단계가 있으면 종료코드 1 (다음 단계는 가능하면 계속).
"""
import argparse
import datetime as dt
import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from seoul_sgg import SGG  # noqa: E402

LOGDIR = os.path.join(ROOT, "logs")
PY = sys.executable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--no-deploy", action="store_true")
    ap.add_argument("--skip-poi", action="store_true")
    a = ap.parse_args()
    os.makedirs(LOGDIR, exist_ok=True)
    log_path = os.path.join(LOGDIR, "refresh_{}.log".format(dt.datetime.now().strftime("%Y%m%d_%H%M")))
    log = io.open(log_path, "w", encoding="utf-8")
    failed = []

    def step(name, cmd, must=False):
        t0 = time.time()
        log.write("\n=== {} ({})\n".format(name, " ".join(cmd)))
        log.flush()
        r = subprocess.run([PY] + cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = r.stdout.decode("utf-8", "replace")
        log.write(out[-4000:])
        log.write("\n--- exit {} in {:.0f}s\n".format(r.returncode, time.time() - t0))
        log.flush()
        print("{:28s} exit={} {:.0f}s".format(name, r.returncode, time.time() - t0))
        if r.returncode != 0:
            failed.append(name)
            if must:
                raise SystemExit("필수 단계 실패: {} (로그 {})".format(name, log_path))
        return r.returncode == 0

    for code, name in SGG.items():
        step("trades " + name, ["pipeline/fetch_trades.py", "--lawd", code, "--months", "24"])
        step("rent " + name, ["pipeline/fetch_rent.py", "--lawd", code, "--months", "12"])
        if a.full:
            step("kapt " + name, ["pipeline/fetch_kapt.py", "--sgg", code])
    step("geocode", ["pipeline/geocode.py"])
    if not a.skip_poi:
        step("kakao poi", ["pipeline/fetch_kakao_poi.py"])
    if a.full:
        for name in SGG.values():
            step("neis " + name, ["pipeline/fetch_neis.py", "--gu", name, "--neighbors", ""])
        for code in SGG:
            for y in (dt.date.today().year - 1, dt.date.today().year):
                step("schoolinfo {} {}".format(code, y), ["pipeline/fetch_schoolinfo.py", "--types", "0,10,62", "--knd", "02,03", "--year", str(y), "--sgg", code])
        if os.environ.get("SEOUL_KEY"):
            step("seoul apt", ["pipeline/fetch_seoul_apt.py"])
    step("build", ["pipeline/build.py"], must=True)
    step("pages", ["pipeline/generate_pages.py"], must=True)
    if not a.no_deploy:
        step("deploy", ["pipeline/deploy_github_pages.py"], must=True)
    log.write("\nFAILED: {}\n".format(failed))
    log.close()
    print("완료. 실패 단계:", failed or "없음", "| 로그:", log_path)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
