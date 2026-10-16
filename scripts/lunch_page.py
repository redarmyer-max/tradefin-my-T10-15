"""실습 C 「5. 감 검증」 — 깨끗한 표로 영양사님 감을 검증해 페이지 한 장을 쓴다.

입력: workbench/day3/outputs/lunch_clean.csv · labs/day3/lab-c/nutritionist_memo.md (읽기만)
출력: workbench/day3/outputs/hanbit_lunch.html (손으로 고치지 않는다 — 이 스크립트가 쓴다)
지금 있는 구역: 머리 · 영양사님 감 검증 (다음 단계에서 구역을 더한다)
실행: uv run python scripts/lunch_page.py
"""
import html
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "workbench/day3/outputs/lunch_clean.csv"
MEMO = ROOT / "labs/day3/lab-c/nutritionist_memo.md"
OUT = ROOT / "workbench/day3/outputs/hanbit_lunch.html"

GAP = 2.0  # 100명당 2명 이상 차이 나면 '차이 있음'(사람이 정한 선)

df = pd.read_csv(CLEAN, encoding="utf-8-sig")
df["행사"] = df["행사"].fillna("")
df["per100"] = df["식수"] / df["출근예정"] * 100  # 출근 100명당 식수
period = (df["날짜"].min(), df["날짜"].max())

# 메모의 믿음 글(글자 그대로) — "1. **굵은 글.** 덧붙인 글"
beliefs_text = {}
for line in MEMO.read_text(encoding="utf-8").splitlines():
    m = re.match(r"(\d)\. \*\*(.+?)\*\*\s*(.*)", line)
    if m:
        beliefs_text[int(m[1])] = (m[2], m[3])


# ======================= 구역: 영양사님 감 검증 =======================
def group(mask) -> dict:
    """그 날들의 '출근 100명당 식수' 평균과 날 수."""
    s = df.loc[mask, "per100"]
    return {"mean": float(s.mean()), "n": int(len(s))}


def judge(hi: dict, lo: dict) -> tuple[str, float]:
    """믿음은 hi > lo. 차이 ≥ 2 → 맞음, 반대로 ≥ 2 → 틀림, 2 미만 → 반만."""
    d = hi["mean"] - lo["mean"]
    if abs(d) < GAP:
        return "반만", d
    return ("맞음" if d > 0 else "틀림"), d


def calc_beliefs() -> list[dict]:
    base = (df["행사"] == "") & (df["월급날"] == 0)  # 행사 없고 월급날 아닌 날만
    wd, w, t = df["요일"], df["날씨"], df["최고기온"]
    cards = []

    # 믿음 1 비 오는 날 vs 맑은 날 — 믿음: 비 > 맑음
    a, b = group(base & (w == "비")), group(base & (w == "맑음"))
    badge, d = judge(a, b)
    cards.append({"no": 1, "kind": "pair", "labels": ["비 오는 날", "맑은 날"], "groups": [a, b],
                  "badge": badge, "diff": d, "note": "비 오는 날 − 맑은 날"})

    # 믿음 2 금요일 vs 월–목 — 믿음: 금 < 월–목
    a, b = group(base & (wd == "금")), group(base & wd.isin(list("월화수목")))
    badge, d = judge(b, a)
    cards.append({"no": 2, "kind": "pair", "labels": ["금요일", "월–목"], "groups": [a, b],
                  "badge": badge, "diff": d, "note": "월–목 − 금요일"})

    # 믿음 3 메뉴별(높은 순) — 돈가스가 1등이고 2등보다 2명 이상 많으면 맞음
    menu = (df[base].groupby("메인메뉴")["per100"].agg(["mean", "count"])
            .sort_values("mean", ascending=False))
    top, second = menu.index[0], menu.index[1]
    pork = float(menu.loc["돈가스", "mean"])
    if top == "돈가스" and pork - float(menu.loc[second, "mean"]) >= GAP:
        badge = "맞음"
    elif float(menu.iloc[0]["mean"]) - pork < GAP:
        badge = "반만"
    else:
        badge = "틀림"
    rival = second if top == "돈가스" else top
    cards.append({"no": 3, "kind": "menu",
                  "labels": ["돈가스", f"{rival}({'2등' if top == '돈가스' else '1등'})"],
                  "groups": [{"mean": pork, "n": int(menu.loc["돈가스", "count"])},
                             {"mean": float(menu.loc[rival, "mean"]), "n": int(menu.loc[rival, "count"])}],
                  "badge": badge, "diff": pork - float(menu.loc[rival, "mean"]),
                  "rank": int(list(menu.index).index("돈가스")) + 1,
                  "menu": [{"name": k, "mean": float(r["mean"]), "n": int(r["count"])} for k, r in menu.iterrows()],
                  "note": f"돈가스 − {rival}"})

    # 믿음 4 최고기온 31도 이상 vs 25도 이상 31도 미만 — 믿음: 31도 이상 < 25–31도
    a, b = group(base & (t >= 31)), group(base & (t >= 25) & (t < 31))
    badge, d = judge(b, a)
    cards.append({"no": 4, "kind": "pair", "labels": ["31도 이상", "25도 이상 31도 미만"], "groups": [a, b],
                  "badge": badge, "diff": d, "note": "25–31도 − 31도 이상"})

    # 믿음 5 월요일 vs 화–목 — 믿음: 월 < 화–목
    a, b = group(base & (wd == "월")), group(base & wd.isin(list("화수목")))
    badge, d = judge(b, a)
    cards.append({"no": 5, "kind": "pair", "labels": ["월요일", "화–목"], "groups": [a, b],
                  "badge": badge, "diff": d, "note": "화–목 − 월요일"})

    # 메모에 없던 규칙: 월급날(월급날인 날 모두) vs 보통 날
    a, b = group(df["월급날"] == 1), group(base)
    d = a["mean"] - b["mean"]
    cards.append({"no": 0, "kind": "pair", "labels": ["월급날", "보통 날"], "groups": [a, b],
                  "badge": "메모에 없음", "diff": d, "note": "월급날 − 보통 날",
                  "verdict": ("차이 있음 — 월급날이 " + ("더 많음" if d > 0 else "더 적음")) if abs(d) >= GAP else "차이 2명 미만"})
    return cards


BADGE_CLASS = {"맞음": "ok", "반만": "half", "틀림": "bad", "메모에 없음": "new"}


def section_beliefs(cards: list[dict]) -> str:
    out = []
    for c in cards:
        if c["no"]:
            head, tail = beliefs_text[c["no"]]
            title = f'<p class="belief-no">믿음 {c["no"]}</p><h3>{html.escape(head)}</h3><p class="quote">{html.escape(tail)}</p>'
        else:
            title = '<p class="belief-no">메모에 없던 규칙</p><h3>월급날엔 덜 올까, 더 올까?</h3><p class="quote">메모에는 없지만 기록에서 함께 살펴본 것</p>'
        (la, lb), (ga, gb) = c["labels"], c["groups"]
        nums = (f'<div class="nums"><div><span class="lbl">{html.escape(la)}</span>'
                f'<span class="big">{ga["mean"]:.1f}</span><span class="unit">명 · {ga["n"]}일</span></div>'
                f'<div><span class="lbl">{html.escape(lb)}</span>'
                f'<span class="big">{gb["mean"]:.1f}</span><span class="unit">명 · {gb["n"]}일</span></div></div>')
        if c["kind"] == "menu":
            extra = f'돈가스는 {len(c["menu"])}개 메뉴 중 {c["rank"]}등'
        elif c["no"] == 0:
            extra = c["verdict"]
        else:
            extra = ""
        sign = "+" if c["diff"] >= 0 else "−"
        verdict = (f'<p class="diff">{html.escape(c["note"])} = {sign}{abs(c["diff"]):.1f}명'
                   + (f' · {html.escape(extra)}' if extra else "") + "</p>")
        out.append(
            f'<article class="card"><div class="card-top">{title}'
            f'<span class="badge {BADGE_CLASS[c["badge"]]}">{c["badge"]}</span></div>'
            f'{nums}<div class="chart {"tall" if c["kind"] == "menu" else ""}"><canvas id="chart-{c["no"]}"></canvas></div>{verdict}</article>')
    return (
        '<section id="beliefs"><h2>영양사님 감 검증</h2>'
        '<p class="lead">출근 인원이 다른 날도 견줄 수 있게 <b>출근 100명당 식수</b>(식수 ÷ 출근예정 × 100, 날마다 구해 평균)로 비교했습니다. '
        f'행사가 없고 월급날이 아닌 날만 썼습니다. 100명당 {GAP:.0f}명 이상 차이 나면 \'차이 있음\'으로 봅니다(사람이 정한 선).</p>'
        '<div class="grid">' + "".join(out) + "</div></section>")


# ======================= 머리 =======================
def section_header() -> str:
    return ('<header><h1>한빛식당 밥 예보</h1>'
            f'<p>(가상) 한빛정밀(주) 본사 구내식당 · 기록 기간 {period[0]} ~ {period[1]} · 만든 사람 총무팀 최 대리(가상)</p></header>')


# ======================= 페이지 조립 =======================
CSS = """
:root{--bg:#f4f5f7;--card:#ffffff;--ink:#1d2330;--sub:#5d6573;--line:#e3e6eb;--accent:#1f6feb;--warn:#d1495b;--gray:#9aa1ab}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink)}
body{font-family:'Noto Sans KR',sans-serif;font-size:16px;line-height:1.6;word-break:keep-all;overflow-wrap:break-word}
main{max-width:1080px;margin:0 auto;padding:24px 16px 48px}
header h1{margin:0 0 4px;font-size:28px}
header p{margin:0;color:var(--sub)}
section{margin-top:32px}
h2{font-size:22px;margin:0 0 8px}
.lead{color:var(--sub);margin:0 0 16px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;min-width:0}
.card-top{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.belief-no{margin:0;font-size:14px;color:var(--sub)}
.card h3{margin:2px 0 2px;font-size:17px}
.quote{margin:0;font-size:14px;color:var(--sub)}
.badge{flex:none;font-size:14px;font-weight:700;padding:2px 10px;border-radius:999px;color:#fff;white-space:nowrap}
.badge.ok{background:var(--accent)}.badge.half{background:var(--gray)}.badge.bad{background:var(--warn)}
.badge.new{background:#fff;color:var(--ink);border:1px solid var(--gray)}
.nums{display:flex;gap:16px;margin:12px 0 8px}
.nums>div{flex:1;min-width:0}
.lbl{display:block;font-size:14px;color:var(--sub)}
.big{font-size:26px;font-weight:700}
.unit{font-size:14px;color:var(--sub);margin-left:4px}
.chart{position:relative;height:120px}
.chart.tall{height:300px}
.diff{margin:8px 0 0;font-size:14px;color:var(--sub)}
"""

JS = """
const data = JSON.parse(document.getElementById('page-data').textContent);
const css = getComputedStyle(document.documentElement);
const C = {accent: css.getPropertyValue('--accent').trim(), warn: css.getPropertyValue('--warn').trim(),
           gray: css.getPropertyValue('--gray').trim(), sub: css.getPropertyValue('--sub').trim()};
Chart.defaults.font.family = "'Noto Sans KR', sans-serif";
Chart.defaults.font.size = 14;
Chart.defaults.color = C.sub;
const BADGE = {'맞음': C.accent, '반만': C.gray, '틀림': C.warn, '메모에 없음': C.gray};
for (const c of data.beliefs) {
  const isMenu = c.kind === 'menu';
  const labels = isMenu ? c.menu.map(m => m.name) : c.labels;
  const values = isMenu ? c.menu.map(m => +m.mean.toFixed(1)) : c.groups.map(g => +g.mean.toFixed(1));
  const colors = isMenu ? c.menu.map(m => m.name === '돈가스' ? BADGE[c.badge] : C.gray + '66')
                        : [BADGE[c.badge], C.gray + '66'];
  new Chart(document.getElementById('chart-' + c.no), {
    type: 'bar',
    data: {labels, datasets: [{data: values, backgroundColor: colors, borderRadius: 4, barThickness: isMenu ? 16 : 22}]},
    options: {indexAxis: 'y', maintainAspectRatio: false, animation: false,
      plugins: {legend: {display: false}, tooltip: {callbacks: {label: x => '100명당 ' + x.raw + '명'}}},
      scales: {x: {beginAtZero: true, grid: {display: false}}, y: {grid: {display: false}}}}
  });
}
"""


def build_page(sections: list[str], payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>한빛식당 밥 예보</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<main>
{"".join(sections)}
</main>
<script id="page-data" type="application/json">{data}</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>{JS}</script>
</body>
</html>
"""


def rounded(cards: list[dict]) -> list[dict]:
    """페이지 JSON은 소수 둘째 자리까지(같은 입력이면 같은 페이지)."""
    def r(x):
        if isinstance(x, float):
            return round(x, 2)
        if isinstance(x, dict):
            return {k: r(v) for k, v in x.items()}
        if isinstance(x, list):
            return [r(v) for v in x]
        return x
    return r(cards)


if __name__ == "__main__":
    cards = calc_beliefs()
    # 구역 순서: 머리 → 영양사님 감 검증
    page = build_page([section_header(), section_beliefs(cards)], {"beliefs": rounded(cards)})
    OUT.write_text(page, encoding="utf-8")

    for c in cards:
        name = f"믿음 {c['no']}" if c["no"] else "월급날(메모에 없음)"
        (la, lb), (ga, gb) = c["labels"], c["groups"]
        print(f"{name}: {la} {ga['mean']:.1f}명({ga['n']}일) vs {lb} {gb['mean']:.1f}명({gb['n']}일) "
              f"· {c['note']} {c['diff']:+.1f} → {c['badge']}" + (f" · {c['verdict']}" if c["no"] == 0 else ""))
        if c["kind"] == "menu":
            print("   메뉴 순위: " + " · ".join(f"{m['name']} {m['mean']:.1f}({m['n']}일)" for m in c["menu"]))
    print(f"페이지: {OUT.relative_to(ROOT)}")
