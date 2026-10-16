"""실습 C 「5. 감 검증」 — 깨끗한 표로 영양사님 감을 검증해 페이지 한 장을 쓴다.

입력: workbench/day3/outputs/lunch_clean.csv · labs/day3/lab-c/nutritionist_memo.md · next_week_plan.csv (읽기만)
출력: workbench/day3/outputs/hanbit_lunch.html (손으로 고치지 않는다 — 이 스크립트가 쓴다)
지금 있는 구역: 머리 · 다음 주 예보 · 예보 성적표 · 영양사님 감 검증
실행: uv run python scripts/lunch_page.py
"""
import html
import json
import math
import re
from pathlib import Path

import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.linear_model import LinearRegression

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "workbench/day3/outputs/lunch_clean.csv"
MEMO = ROOT / "labs/day3/lab-c/nutritionist_memo.md"
PLAN = ROOT / "labs/day3/lab-c/next_week_plan.csv"
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


# ======================= 구역: 예보 성적표 =======================
TEST_START = "2026-09-14"  # 이 날부터 시험 기간(배울 때 쓰지 않는다)
BUFFER = 10                # AI 준비 = 예보 + 10
COST = 4500                # 1인분 원가(가정)
TEXT_COLS = ["요일", "날씨", "메인메뉴", "행사"]
FEATURES = ["요일", "날씨", "최고기온", "메인메뉴", "행사", "월급날", "출근예정"]
MENU_MULT = {"돈가스": 1.1, "카레": 1.1, "샐러드": 0.9}  # 나머지 1.0
EVENT_DAYS = {"2026-09-23": "추석 연휴 전날 · 돈가스", "2026-09-30": "비 오는 수요일 · 카레"}


def half_up(x: float) -> int:
    """반올림(0.5는 올림)."""
    return int(math.floor(x + 0.5))


def make_X(frame: pd.DataFrame, temp_median: float, cols: list[str] | None = None) -> pd.DataFrame:
    """재료 열 → 0/1 열(drop_first 없이). cols가 있으면 배울 때와 같은 열로 맞추고 없는 열은 0."""
    x = frame[FEATURES].copy()
    x["최고기온"] = x["최고기온"].fillna(temp_median)   # 빈칸은 배우는 기간의 가운데 값
    x["행사"] = x["행사"].replace("", "없음").fillna("없음")
    x = pd.get_dummies(x, columns=TEXT_COLS).astype(float)
    if cols is not None:
        x = x.reindex(columns=cols, fill_value=0.0)
    return x


def train_forecasters() -> dict:
    """배우는 기간으로 예보관 두 명을 배우고, 시험 기간 성적으로 '우리 예보관'을 고른다."""
    train, test = df[df["날짜"] < TEST_START], df[df["날짜"] >= TEST_START]
    assert len(test) == 20, f"시험 기간이 20일이 아님: {len(test)}"
    temp_median = float(train["최고기온"].median())
    X_train = make_X(train, temp_median)
    cols = list(X_train.columns)
    X_test = make_X(test, temp_median, cols)
    y_train, y_test = train["식수"].to_numpy(), test["식수"].to_numpy()

    models = {
        "선형 회귀": LinearRegression(),
        "LightGBM": LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=15,
                                  min_child_samples=5, random_state=42, verbose=-1),
    }
    preds, scores = {}, {}
    for name, m in models.items():
        if name == "LightGBM":  # 한글 열 이름 대신 숫자 배열로 배운다(같은 열 순서)
            m.fit(X_train.to_numpy(), y_train)
            p = m.predict(X_test.to_numpy())
        else:
            m.fit(X_train, y_train)
            p = m.predict(X_test)
        preds[name] = p
        scores[name] = float(abs(p - y_test).mean())  # 하루 평균 몇 인분 차이
    best = min(scores, key=scores.get)
    return {"models": models, "cols": cols, "temp_median": temp_median, "test": test,
            "preds": preds, "scores": scores, "best": best, "n_train": len(train)}


def formula(day: str, weekday: str, menu: str) -> dict:
    """영양사님 공식: 그날 전 같은 요일 실제 식수 4개(가장 가까운 날부터)의 평균 × 메뉴 배수."""
    prev = df[(df["날짜"] < day) & (df["요일"] == weekday)].sort_values("날짜").tail(4)
    mean4 = float(prev["식수"].mean())
    mult = MENU_MULT.get(menu, 1.0)
    return {"mean4": mean4, "mult": mult, "value": half_up(mean4 * mult)}


def calc_scorecard(fc: dict) -> dict:
    test = fc["test"]
    best_pred = fc["preds"][fc["best"]]
    rows = []
    for (_, r), p in zip(test.iterrows(), best_pred):
        f = formula(r["날짜"], r["요일"], r["메인메뉴"])
        ai_prep = half_up(p) + BUFFER
        rows.append({"date": r["날짜"], "wd": r["요일"], "menu": r["메인메뉴"], "actual": int(r["식수"]),
                     "ai": float(p), "ai_prep": ai_prep, "formula": f["value"]})

    def result(prep_key: str) -> dict:
        left = [max(x[prep_key] - x["actual"], 0) for x in rows]
        short = [max(x["actual"] - x[prep_key], 0) for x in rows]
        return {"left": sum(left), "left_won": sum(left) * COST,
                "short": sum(short), "short_days": sum(1 for s in short if s > 0)}

    ai, fm = result("ai_prep"), result("formula")
    ai["mae"] = fc["scores"][fc["best"]]
    fm["mae"] = sum(abs(x["formula"] - x["actual"]) for x in rows) / len(rows)
    return {"scores": fc["scores"], "best": fc["best"], "rows": rows, "ai": ai, "formula": fm,
            "events": [{"date": d, "label": lab, **next(x for x in rows if x["date"] == d)}
                       for d, lab in EVENT_DAYS.items()]}


def section_scorecard(sc: dict) -> str:
    best = sc["best"]
    judges = "".join(
        f'<div class="judge{" chosen" if n == best else ""}"><span class="lbl">{html.escape(n)}</span>'
        f'<span class="big">{s:.1f}</span><span class="unit">인분 차이 / 하루</span>'
        + ('<span class="pick">우리 예보관</span>' if n == best else "") + "</div>"
        for n, s in sc["scores"].items())

    def ev_line(e):
        ai_gap, fm_gap = e["ai_prep"] - e["actual"], e["formula"] - e["actual"]
        word = lambda g: f"{g}인분 남음" if g > 0 else (f"{-g}인분 모자람" if g < 0 else "딱 맞음")
        return (f'<li><b>{e["date"][5:].replace("-", "/")}({e["wd"]}) {html.escape(e["label"])}</b> — '
                f'실제 {e["actual"]}명 · AI 준비 {e["ai_prep"]}인분({word(ai_gap)}) · '
                f'영양사님 공식 {e["formula"]}인분({word(fm_gap)})</li>')

    a, f = sc["ai"], sc["formula"]

    def pair(title, ai_main, fm_main, ai_sub="", fm_sub="", better=None):
        cls = lambda side: ' class="win"' if better == side else ""
        return (f'<article class="card stat"><h3>{title}</h3><div class="nums">'
                f'<div{cls("ai")}><span class="lbl">AI({html.escape(best)})</span><span class="big">{ai_main}</span>'
                f'<span class="unit">{ai_sub}</span></div>'
                f'<div{cls("fm")}><span class="lbl">영양사님 공식</span><span class="big">{fm_main}</span>'
                f'<span class="unit">{fm_sub}</span></div></div></article>')

    better = lambda x, y: "ai" if x < y else ("fm" if y < x else None)
    cards = (
        pair("하루 평균 몇 인분 차이", f'{a["mae"]:.1f}', f'{f["mae"]:.1f}', "인분", "인분", better(a["mae"], f["mae"]))
        + pair("남은 밥(20일 합계)", f'{a["left"]:,}', f'{f["left"]:,}',
               f'인분 · {a["left_won"]:,}원', f'인분 · {f["left_won"]:,}원', better(a["left"], f["left"]))
        + pair("모자란 밥(20일 합계)", f'{a["short"]:,}', f'{f["short"]:,}',
               f'인분 · 모자란 날 {a["short_days"]}일', f'인분 · 모자란 날 {f["short_days"]}일',
               better(a["short"], f["short"])))
    return (
        '<section id="scorecard"><h2>예보 성적표</h2>'
        f'<p class="lead">{TEST_START} 전 기록으로 배운 AI 예보관 두 명을, 배울 때 보여 주지 않은 최근 {len(sc["rows"])}일로 시험했습니다. '
        '성적은 날마다 예보와 실제의 차이를 크기만 재어 낸 평균입니다(작을수록 좋음).</p>'
        f'<div class="judges">{judges}</div>'
        '<p class="note"><b>복잡한 쪽이 늘 이기지는 않는다 — 시험으로 고른다.</b> 예보관 설정은 모두 같은 결과를 보려고 고정했습니다.</p>'
        f'<h3 class="sub">시험 {len(sc["rows"])}일 — 실제 · 우리 예보관 · 영양사님 공식</h3>'
        '<div class="card"><div class="chart line"><canvas id="chart-test"></canvas></div>'
        '<ul class="events">' + "".join(ev_line(e) for e in sc["events"]) + "</ul></div>"
        f'<h3 class="sub">AI 준비(예보 + {BUFFER}인분)와 영양사님 공식 준비, 20일 결과</h3>'
        f'<div class="grid three">{cards}</div>'
        f'<p class="note">1인분 원가 {COST:,}원(가정). 모자란 밥은 컵라면을 드신 분 수입니다. 진한 쪽이 더 적은(나은) 쪽입니다.</p>'
        "</section>")


# ======================= 구역: 다음 주 예보 =======================
def calc_next_week(fc: dict, cards: list[dict]) -> list[dict]:
    """다음 주 계획을 우리 예보관에게 묻는다(배울 때와 같은 열 · 같은 빈칸 처리)."""
    plan = pd.read_csv(PLAN, encoding="utf-8-sig", dtype={"행사": str, "월급날": str})
    plan = plan.rename(columns={"날씨예보": "날씨", "최고기온예보": "최고기온"})
    plan["월급날"] = (plan["월급날"].fillna("").str.strip() == "Y").astype(int)  # Y → 1, 빈칸 → 0
    plan["행사"] = plan["행사"].fillna("")
    X = make_X(plan, fc["temp_median"], fc["cols"])
    model = fc["models"][fc["best"]]
    raw = model.predict(X.to_numpy() if fc["best"] == "LightGBM" else X)

    badge = {c["no"]: c["badge"] for c in cards}
    menu_rank = next(c["menu"] for c in cards if c["kind"] == "menu")
    last_menu = menu_rank[-1]["name"]
    days = []
    for (_, r), p in zip(plan.iterrows(), raw):
        f = formula(r["날짜"], r["요일"], r["메인메뉴"])
        fcst = half_up(p)
        days.append({"date": r["날짜"], "wd": r["요일"], "weather": r["날씨"], "temp": float(r["최고기온"]),
                     "menu": r["메인메뉴"], "event": r["행사"], "payday": int(r["월급날"]),
                     "att": int(r["출근예정"]), "raw": float(p), "fcst": fcst, "prep": fcst + BUFFER,
                     "formula": f["value"], "f_mean4": f["mean4"], "f_mult": f["mult"]})
    hi = max(days, key=lambda d: d["fcst"])["date"]
    lo = min(days, key=lambda d: d["fcst"])["date"]
    for d in days:
        d["mark"] = "most" if d["date"] == hi else ("least" if d["date"] == lo else "")
        d["comment"] = comment(d, badge, last_menu)
    return days


def comment(d: dict, badge: dict, last_menu: str) -> str:
    """영양사님께 드리는 한 줄 — 그날 조건과 영양사님 공식과의 차이(숫자는 계산값만)."""
    why = []
    if d["wd"] == "금" and badge[2] == "맞음":
        why.append("금요일이라 적게 오시는 편이에요")
    if d["wd"] == "월" and badge[5] == "틀림":
        why.append("월요일이지만 기록상 월요일에 덜 오시진 않았어요")
    if d["weather"] == "비" and badge[1] == "맞음":
        why.append("비 예보라 기록상 더 오시는 날이에요")
    if d["payday"]:
        why.append("월급날엔 기록상 덜 오셨어요")
    if d["menu"] == last_menu:
        why.append(f"{last_menu}는 가장 적게 드시는 메뉴였어요")
    if d["event"] == "전사 교육":
        why.append(f"전사 교육으로 출근이 {d['att']}명이에요")
    elif d["event"]:
        why.append(f"{d['event']}이 있어요")
    gap = d["prep"] - d["formula"]
    if gap <= -5:
        tail = f"공식({d['formula']}인분)보다 {-gap}인분 덜 준비하셔도 될 것 같아요."
    elif gap >= 5:
        tail = f"공식({d['formula']}인분)보다 {gap}인분 더 준비하시면 좋겠어요."
    else:
        tail = f"공식({d['formula']}인분)과 거의 같아요."
    return (" · ".join(why) + ". " if why else "") + tail


def section_next_week(days: list[dict]) -> str:
    cards = []
    for d in days:
        mark = {"most": '<span class="mark most">이번 주 가장 많음</span>',
                "least": '<span class="mark least">이번 주 가장 적음</span>'}.get(d["mark"], "")
        tags = [f'{d["weather"]} · {d["temp"]:g}도', d["menu"]]
        if d["event"]:
            tags.append(d["event"])
        if d["payday"]:
            tags.append("월급날")
        cards.append(
            f'<article class="card day {d["mark"]}"><div class="day-top"><span class="date">'
            f'{int(d["date"][5:7])}/{int(d["date"][8:])} ({d["wd"]})</span>{mark}</div>'
            f'<p class="fcst">{d["fcst"]}<span>명</span></p>'
            f'<p class="prep">준비 <b>{d["prep"]}</b>인분</p>'
            f'<p class="formula">영양사님 공식이면 {d["formula"]}인분</p>'
            '<div class="tags">' + "".join(f'<span class="tag">{html.escape(t)}</span>' for t in tags) + "</div>"
            f'<p class="comment">{html.escape(d["comment"])}</p></article>')
    first, last = days[0]["date"], days[-1]["date"]
    return (
        '<section id="nextweek"><h2>다음 주 예보</h2>'
        f'<p class="lead">{int(first[5:7])}/{int(first[8:])} ~ {int(last[5:7])}/{int(last[8:])} 계획을 시험에서 이긴 예보관에게 물었습니다. '
        f'준비 인분 = 예보 + {BUFFER}인분. 준비량은 영양사님이 정해 주세요.</p>'
        f'<div class="week">{"".join(cards)}</div></section>')


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
.judges{display:flex;flex-wrap:wrap;gap:16px}
.judge{flex:1 1 200px;min-width:0;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.judge.chosen{border:2px solid var(--accent)}
.pick{display:inline-block;margin-left:8px;font-size:14px;font-weight:700;color:#fff;background:var(--accent);padding:2px 10px;border-radius:999px}
.note{color:var(--sub);font-size:14px;margin:12px 0 0}
h3.sub{font-size:17px;margin:24px 0 8px}
.chart.line{height:280px}
.events{margin:12px 0 0;padding-left:20px;font-size:14px}
.events li{margin-top:4px}
.grid.three{grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr))}
.stat h3{margin:0;font-size:17px}
.stat .nums>div{color:var(--sub)}
.stat .nums>div.win{color:var(--ink)}
.stat .nums>div.win .big{color:var(--accent)}
.week{display:grid;grid-template-columns:1fr;gap:12px}
@media (min-width:900px){.week{grid-template-columns:repeat(5,minmax(0,1fr))}}
.day{display:flex;flex-direction:column;gap:4px}
.day.most{border:2px solid var(--accent)}
.day.least{border:2px solid var(--gray)}
.day-top{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.date{font-weight:700}
.mark{font-size:14px;font-weight:700;padding:2px 8px;border-radius:999px;color:#fff;white-space:nowrap}
.mark.most{background:var(--accent)}.mark.least{background:var(--gray)}
.fcst{margin:4px 0 0;font-size:40px;font-weight:700;line-height:1.1}
.fcst span{font-size:18px;margin-left:2px}
.prep{margin:0;font-size:17px}
.prep b{color:var(--accent)}
.formula{margin:0;font-size:14px;color:var(--sub)}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.tag{font-size:14px;padding:1px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg)}
.comment{margin:8px 0 0;font-size:14px;color:var(--ink);border-top:1px solid var(--line);padding-top:8px}
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
if (data.scorecard) {
  const sc = data.scorecard, rows = sc.rows;
  const ink = css.getPropertyValue('--ink').trim();
  const marks = sc.events.map(e => rows.findIndex(r => r.date === e.date));
  const eventLines = {id: 'eventLines', afterDatasetsDraw(chart) {
    const {ctx, chartArea: a, scales: {x}} = chart;
    ctx.save(); ctx.setLineDash([4, 4]); ctx.strokeStyle = C.warn; ctx.fillStyle = C.warn;
    ctx.font = "700 14px 'Noto Sans KR', sans-serif"; ctx.textAlign = 'center';
    for (const i of marks) {
      const px = x.getPixelForValue(i);
      ctx.beginPath(); ctx.moveTo(px, a.top + 18); ctx.lineTo(px, a.bottom); ctx.stroke();
      ctx.fillText(rows[i].date.slice(5).replace('-', '/'), px, a.top + 12);
    }
    ctx.restore();
  }};
  new Chart(document.getElementById('chart-test'), {
    type: 'line',
    data: {labels: rows.map(r => r.date.slice(5).replace('-', '/') + '(' + r.wd + ')'),
      datasets: [
        {label: '실제', data: rows.map(r => r.actual), borderColor: ink, backgroundColor: ink, borderWidth: 2.5, pointRadius: 3},
        {label: '우리 예보관(' + sc.best + ')', data: rows.map(r => Math.round(r.ai)), borderColor: C.accent, backgroundColor: C.accent, borderWidth: 2, pointRadius: 2},
        {label: '영양사님 공식', data: rows.map(r => r.formula), borderColor: C.gray, backgroundColor: C.gray, borderWidth: 2, borderDash: [6, 4], pointRadius: 2}]},
    options: {maintainAspectRatio: false, animation: false, interaction: {mode: 'index', intersect: false},
      plugins: {legend: {position: 'bottom', labels: {boxWidth: 14}},
        tooltip: {callbacks: {label: x => x.dataset.label + ' ' + x.raw + '명'}}},
      scales: {x: {grid: {display: false}, ticks: {maxRotation: 0, autoSkip: true}}, y: {grid: {color: '#e3e6eb'}}}},
    plugins: [eventLines]
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
    fc = train_forecasters()
    sc = calc_scorecard(fc)
    nw = calc_next_week(fc, cards)
    # 구역 순서: 머리 → 다음 주 예보 → 예보 성적표 → 영양사님 감 검증
    page = build_page([section_header(), section_next_week(nw), section_scorecard(sc), section_beliefs(cards)],
                      {"beliefs": rounded(cards), "scorecard": rounded(sc), "nextweek": rounded(nw)})
    OUT.write_text(page, encoding="utf-8")

    print(f"다음 주 예보(우리 예보관 = {fc['best']}):")
    for d in nw:
        print(f"  {d['date']}({d['wd']}) {d['menu']} · {d['weather']} {d['temp']:g}도"
              f"{' · ' + d['event'] if d['event'] else ''}{' · 월급날' if d['payday'] else ''} · 출근 {d['att']}"
              f" → 예보 {d['fcst']}명(원값 {d['raw']:.1f}) · 준비 {d['prep']}인분 · 공식 {d['formula']}"
              f"(4주 평균 {d['f_mean4']:.2f} × {d['f_mult']}){'  [가장 많음]' if d['mark'] == 'most' else ''}"
              f"{'  [가장 적음]' if d['mark'] == 'least' else ''}")
        print(f"     코멘트: {d['comment']}")

    print(f"배우는 기간 {fc['n_train']}일 · 시험 기간 {len(sc['rows'])}일")
    for n, s in sc["scores"].items():
        print(f"예보관 {n}: 하루 평균 {s:.2f}인분 차이" + ("  ← 우리 예보관" if n == sc["best"] else ""))
    for e in sc["events"]:
        print(f"{e['date']} {e['label']}: 실제 {e['actual']} · AI 예보 {e['ai']:.1f}(준비 {e['ai_prep']}) · 공식 {e['formula']}")
    for side, k in (("AI", "ai"), ("공식", "formula")):
        r = sc[k]
        print(f"{side}: 평균 차이 {r['mae']:.2f} · 남은 밥 {r['left']}인분({r['left_won']:,}원) · "
              f"모자란 밥 {r['short']}인분 · 모자란 날 {r['short_days']}일")

    for c in cards:
        name = f"믿음 {c['no']}" if c["no"] else "월급날(메모에 없음)"
        (la, lb), (ga, gb) = c["labels"], c["groups"]
        print(f"{name}: {la} {ga['mean']:.1f}명({ga['n']}일) vs {lb} {gb['mean']:.1f}명({gb['n']}일) "
              f"· {c['note']} {c['diff']:+.1f} → {c['badge']}" + (f" · {c['verdict']}" if c["no"] == 0 else ""))
        if c["kind"] == "menu":
            print("   메뉴 순위: " + " · ".join(f"{m['name']} {m['mean']:.1f}({m['n']}일)" for m in c["menu"]))
    print(f"페이지: {OUT.relative_to(ROOT)}")
