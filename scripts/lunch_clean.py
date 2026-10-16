"""실습 C 「4. 정제 규칙」 — 점심 기록을 규칙 10개로 고쳐 깨끗한 표를 만든다.

규칙 표: workbench/day3/outputs/lunch_rules.md (이 코드는 그 표 그대로)
원본 labs/day3/lab-c/hanbit_lunch_log.csv 는 읽기만 하고,
결과 lunch_clean.csv 와 규칙별 줄 수 lunch_clean_log.md 를 workbench/day3/outputs/ 에 쓴다.
실행: uv run python scripts/lunch_clean.py
"""
import math
import re
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "labs/day3/lab-c/hanbit_lunch_log.csv"
OUT_DIR = ROOT / "workbench/day3/outputs"
OUT_CSV = OUT_DIR / "lunch_clean.csv"
OUT_LOG = OUT_DIR / "lunch_clean_log.md"

# 수강생 결정(프롬프트 그대로): '수기 집계' 줄은 뺀다
HANDWRITTEN = "뺀다"  # "뺀다" 또는 "×10 보정"

df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False)
COLS = list(df.columns)
n_start = len(df)
log = []  # (규칙, 할 일, 고친(뺀) 줄 수, 남은 줄 수)


def record(rule, what, n):
    log.append((rule, what, n, len(df)))


# R1 날짜를 YYYY-MM-DD로
def parse_date(s: str) -> date:
    s = s.strip()
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{1,2})월\s*(\d{1,2})일", s)
    if m:
        mon, day = int(m[1]), int(m[2])
        return date(2025 if mon >= 10 else 2026, mon, day)  # 연도 없으면 10–12월 2025 · 1–9월 2026
    raise ValueError(f"날짜를 읽지 못함: {s!r}")


new_date = df["날짜"].map(lambda s: parse_date(s).isoformat())
n = (new_date != df["날짜"]).sum()
df["날짜"] = new_date
record("R1", "날짜를 YYYY-MM-DD로", n)

# R2 요일을 날짜에서 다시 계산 — 적힌 요일이 실제 요일과 '달랐던' 줄만 센다
KO = "월화수목금토일"
EN = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


def written_weekday(s: str):
    s = s.strip()
    if s in EN:
        return EN[s]
    s = s.removesuffix("요일")
    return KO.index(s) if len(s) == 1 and s in KO else None


real = df["날짜"].map(lambda s: date.fromisoformat(s).weekday())
n = (df["요일"].map(written_weekday) != real).sum()
df["요일"] = real.map(lambda i: KO[i])
record("R2", "요일을 날짜에서 다시 계산(실제와 달랐던 줄)", n)

# R3 휴무 줄 빼기
mask = df["비고"].str.strip() == "휴무"
df = df[~mask]
record("R3", "비고 `휴무` 줄 빼기", mask.sum())

# R4 같은 날짜 두 줄 — `재집계` 줄, 없으면 나중 줄을 남긴다
df = df.reset_index(drop=True)
df["_재집계"] = df["비고"].str.contains("재집계")
df["_순서"] = range(len(df))
keep = (df.sort_values(["날짜", "_재집계", "_순서"]).groupby("날짜").tail(1).index)
before = len(df)
df = df.loc[sorted(keep)].drop(columns=["_재집계", "_순서"])
record("R4", "같은 날짜 두 줄 중 하나 빼기", before - len(df))

# R5 식수 빈칸 줄 빼기
mask = df["식수"].str.strip() == ""
df = df[~mask]
record("R5", "식수 빈칸 줄 빼기", mask.sum())

# R10 출근예정 빈칸 채우기 — 같은 요일 바로 앞 기록 4개(출근예정 있는 줄)의 median, 반올림
df = df.sort_values("날짜", kind="stable").reset_index(drop=True)
blank = df["출근예정"].str.strip() == ""
filled = []
for i in df.index[blank]:
    prev = df[(df.index < i) & (df["요일"] == df.at[i, "요일"]) & ~blank]
    vals = prev["출근예정"].astype(float).tail(4)
    med = vals.median()
    value = math.floor(med + 0.5)  # 반올림(0.5는 올림)
    filled.append((df.at[i, "날짜"], df.at[i, "요일"], list(vals.astype(int)), med, value))
    df.at[i, "출근예정"] = str(value)
record("R10", "출근예정 빈칸 채우기", blank.sum())

# R6 불가능해 보이는 식수 — 출근예정보다 많거나 20% 미만이면 빼기. `수기 집계` 줄은 수강생 결정대로
att = df["출근예정"].astype(float)
meal = df["식수"].astype(float)
hand = df["비고"].str.strip() == "수기 집계"
impossible = (meal > att) | (meal < att * 0.2)
removed6 = df[impossible | hand][["날짜", "출근예정", "식수", "비고"]]
if HANDWRITTEN == "×10 보정":
    df.loc[hand, "식수"] = (meal[hand] * 10).astype(int).astype(str)
    drop = impossible & ~hand
    n = (impossible | hand).sum()
else:  # "뺀다"
    drop = impossible | hand
    n = drop.sum()
df = df[~drop]
record("R6", f"불가능한 식수 빼기 · `수기 집계` 줄 = {HANDWRITTEN}", n)

# R7 날씨 넷으로
WEATHER = {"맑": "맑음", "sunny": "맑음", "구름많음": "흐림", "cloudy": "흐림",
           "rain": "비", "우천": "비", "소나기": "비", "흐리고 비": "비", "snow": "눈", "": "모름"}
new = df["날씨"].str.strip().map(lambda s: WEATHER.get(s, s))
n = (new != df["날씨"]).sum()
df["날씨"] = new
bad = set(df["날씨"]) - {"맑음", "흐림", "비", "눈", "모름"}
assert not bad, f"규칙에 없는 날씨 표기: {bad}"
record("R7", "날씨를 맑음 · 흐림 · 비 · 눈(빈칸 → 모름)으로", n)

# R8 최고기온 단위 · 공백 떼기(빈칸은 빈칸)
new = df["최고기온"].str.replace("℃", "").str.replace("°C", "").str.replace(" ", "").str.strip()
n = (new != df["최고기온"]).sum()
df["최고기온"] = new
pd.to_numeric(df.loc[df["최고기온"] != "", "최고기온"], errors="raise")  # 남은 값이 모두 숫자인지 확인
record("R8", "최고기온 단위 · 공백 떼기", n)

# R9 메뉴 · 행사 이름 통일(따로 세어 더한다)
MENU = {"돈까스": "돈가스", "카레라이스": "카레", "제육": "제육볶음", "치킨마요덮밥": "치킨마요", "김치 찌개": "김치찌개"}
EVENT = {"외부손님": "외부 손님 방문", "전사교육": "전사 교육"}
n_menu = df["메인메뉴"].isin(MENU.keys()).sum()
n_event = df["행사"].isin(EVENT.keys()).sum()
df["메인메뉴"] = df["메인메뉴"].replace(MENU)
df["행사"] = df["행사"].replace(EVENT)
record("R9", f"메뉴 · 행사 이름 통일(메뉴 {n_menu} + 행사 {n_event})", n_menu + n_event)

# 마무리: 월급날 Y→1 · 빈칸→0, 출근예정 · 식수 정수, 날짜순, 열 10개, UTF-8 BOM
df["월급날"] = df["월급날"].str.strip().map({"Y": 1, "": 0})
assert df["월급날"].notna().all(), "월급날에 Y · 빈칸이 아닌 값이 있음"
df["출근예정"] = df["출근예정"].astype(float).round().astype(int)
df["식수"] = df["식수"].astype(float).round().astype(int)
df = df.sort_values("날짜").reset_index(drop=True)[COLS]
assert df["날짜"].is_unique
OUT_DIR.mkdir(parents=True, exist_ok=True)
df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

# ---------- 규칙별 줄 수 기록 ----------
L = ["# 정제 기록 — 규칙별 고친(뺀) 줄 수\n",
     "- 원본 `labs/day3/lab-c/hanbit_lunch_log.csv` → `workbench/day3/outputs/lunch_clean.csv` · 코드 `scripts/lunch_clean.py`",
     "- 세는 법: 그 규칙을 적용할 때 남아 있는 줄에서 센다. R2는 적힌 요일이 실제 요일과 달랐던 줄만, R9는 메뉴와 행사를 따로 세어 더한다.\n",
     f"처음 **{n_start}줄** → 남은 **{len(df)}줄**\n",
     "| 순서 | 규칙 | 할 일 | 고친(뺀) 줄 수 | 적용 뒤 남은 줄 수 |", "|---:|---|---|---:|---:|"]
for i, (rule, what, n, left) in enumerate(log, 1):
    L.append(f"| {i} | {rule} | {what} | {n} | {left} |")
L.append("\n## R10 — 채운 출근예정\n")
L.append("| 날짜 | 요일 | 앞 기록 4개 | median | 채운 값 |\n|---|---|---|---:|---:|")
for d, wd, vals, med, v in filled:
    L.append(f"| {d} | {wd} | {' · '.join(map(str, vals))} | {med:g} | {v} |")
L.append("\n## R6 — 뺀 줄\n")
L.append("| 날짜 | 출근예정 | 식수 | 비고 |\n|---|---:|---:|---|")
for _, r in removed6.iterrows():
    L.append(f"| {r['날짜']} | {r['출근예정']} | {r['식수']} | {r['비고'] or '(빈칸)'} |")
L.append(f"\n- `수기 집계` 줄 처리: 수강생 결정 '{HANDWRITTEN}'.")
OUT_LOG.write_text("\n".join(L) + "\n", encoding="utf-8")

# ---------- 콘솔 요약 ----------
print(f"처음 {n_start}줄 → 남은 {len(df)}줄 · 날짜 {df['날짜'].min()} ~ {df['날짜'].max()}")
for i, (rule, what, n, left) in enumerate(log, 1):
    print(f"  {i:>2}. {rule:<3} {what}: {n}  (남은 {left})")
for d, wd, vals, med, v in filled:
    print(f"  R10 채움 {d}({wd}) 앞 4개 {vals} median {med:g} → {v}")
print(f"  R6 뺀 줄: " + " / ".join(f"{r['날짜']} {r['출근예정']}명 중 {r['식수']} {r['비고']}" for _, r in removed6.iterrows()))
print(f"결과: {OUT_CSV.relative_to(ROOT)} · 기록: {OUT_LOG.relative_to(ROOT)}")
