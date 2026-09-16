# -*- coding: utf-8 -*-
"""공유용 미리보기 이미지(og:image) 생성 -> app/og-<이름>.png

  python pipeline/make_og.py

카톡·커뮤니티에 링크를 붙였을 때 뜨는 카드 이미지. 1200x630.
페이지마다 실제 데이터(구별 학원비 등)를 그려 넣어 "대충 만든 링크" 로 보이지 않게 한다.
"""
import io
import json
import os
import statistics

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app")
BOLD = fm.FontProperties(fname="C:/Windows/Fonts/malgunbd.ttf")
REG = fm.FontProperties(fname="C:/Windows/Fonts/malgun.ttf")
BRAND = "#0369a1"
FG = "#111827"
MUTED = "#475569"


def canvas():
    fig = plt.figure(figsize=(12, 6.3), dpi=100)
    fig.patch.set_facecolor("#ffffff")
    return fig


def footer(fig):
    fig.text(0.06, 0.07, "jipkokmap.kr", fontproperties=BOLD, fontsize=17, color="#0ea5e9")
    fig.text(0.94, 0.07, "집콕맵", fontproperties=BOLD, fontsize=15, color="#94a3b8", ha="right")


def save(fig, name):
    p = os.path.join(APP, name)
    fig.savefig(p, dpi=100)
    plt.close(fig)
    print("  {} ({:,} bytes)".format(name, os.path.getsize(p)))


def load():
    return json.load(io.open(os.path.join(APP, "data", "complexes.json"), encoding="utf-8"))


def og_academy_fee(cs):
    by = {}
    for c in cs:
        if c.get("fee"):
            by.setdefault(c["sgg"], []).append(c["fee"])
    rows = sorted(((g, statistics.median(v)) for g, v in by.items()), key=lambda x: -x[1])
    top = rows[:6] + rows[-3:]
    fig = canvas()
    fig.text(0.06, 0.86, "우리 동네 학원비, 얼마일까?", fontproperties=BOLD, fontsize=36, color=FG)
    fig.text(0.06, 0.78, "서울 구별 과목당 월 교습비 중앙값 · 교육청 공시 자료", fontproperties=REG, fontsize=17, color=MUTED)
    ax = fig.add_axes([0.06, 0.16, 0.88, 0.56])
    names = [r[0] for r in top][::-1]
    vals = [r[1] / 10000 for r in top][::-1]
    colors = ["#dc2626" if v >= vals[-1] * 0.92 else "#3b82f6" for v in vals]
    colors[0] = colors[1] = colors[2] = "#16a34a"
    ax.barh(range(len(vals)), vals, color=colors, height=0.62)
    ax.set_yticks(range(len(vals)))
    ax.set_yticklabels(names, fontproperties=BOLD, fontsize=15)
    for i, v in enumerate(vals):
        ax.text(v + max(vals) * 0.015, i, "{:.0f}만원".format(v), va="center", fontproperties=BOLD, fontsize=14, color=FG)
    ax.set_xlim(0, max(vals) * 1.22)
    ax.set_xticks([])
    for s in ("top", "right", "bottom", "left"):
        ax.spines[s].set_visible(False)
    footer(fig)
    save(fig, "og-academy-fee.png")


def og_budget_school(cs):
    bands = ["5억 미만", "5~8억", "8~11억", "11~15억", "15~20억", "20억 이상"]
    fig = canvas()
    fig.text(0.06, 0.86, "내 예산으로 갈 수 있는", fontproperties=BOLD, fontsize=34, color=FG)
    fig.text(0.06, 0.75, "최고 학군은 어디일까?", fontproperties=BOLD, fontsize=34, color=BRAND)
    fig.text(0.06, 0.64, "같은 가격대 안에서만 학군을 줄 세웠습니다", fontproperties=REG, fontsize=17, color=MUTED)
    y = 0.50
    for b in bands:
        n = sum(1 for c in cs if c.get("budget_band") == b)
        fig.text(0.06, y, "·  {}".format(b), fontproperties=BOLD, fontsize=18, color=FG)
        fig.text(0.34, y, "{:,}개 단지".format(n), fontproperties=REG, fontsize=17, color=MUTED)
        y -= 0.068
    fig.text(0.62, 0.42, "서울 6,809개 단지\n실거래가 · 학군 · 학원비\n출퇴근 시간까지", fontproperties=BOLD, fontsize=20, color=BRAND, linespacing=1.9)
    footer(fig)
    save(fig, "og-budget-school.png")


def og_future_rail(cs):
    lines = {}
    for c in cs:
        f = c.get("fut")
        if f and f["dist"] <= 800:
            lines.setdefault(f["line"], set()).add(f["name"])
    fig = canvas()
    fig.text(0.06, 0.86, "공사 중인 지하철,", fontproperties=BOLD, fontsize=34, color=FG)
    fig.text(0.06, 0.75, "예정역 걸어갈 수 있는 아파트", fontproperties=BOLD, fontsize=34, color=BRAND)
    fig.text(0.06, 0.64, "동북선 · 월곶판교선 등 공사 중 노선 기준 (OpenStreetMap)", fontproperties=REG, fontsize=16, color=MUTED)
    y = 0.50
    for ln, sts in sorted(lines.items(), key=lambda x: -len(x[1]))[:5]:
        fig.text(0.06, y, "·  {}".format(ln), fontproperties=BOLD, fontsize=19, color=FG)
        fig.text(0.42, y, "예정역 {}곳".format(len(sts)), fontproperties=REG, fontsize=17, color=MUTED)
        y -= 0.075
    fig.text(0.06, 0.17, "개통 시기와 역 위치는 바뀔 수 있습니다", fontproperties=REG, fontsize=14, color="#94a3b8")
    footer(fig)
    save(fig, "og-future-rail.png")


def main():
    cs = load()
    print("공유 이미지 생성:")
    og_academy_fee(cs)
    og_budget_school(cs)
    og_future_rail(cs)


if __name__ == "__main__":
    main()
