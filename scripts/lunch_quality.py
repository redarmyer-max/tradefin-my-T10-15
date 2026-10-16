"""실습 C 「3. 데이터 진단」 — 점심 기록이 어디가 얼마나 엉망인지 센다.

원본 labs/day3/lab-c/hanbit_lunch_log.csv 는 읽기만 하고,
진단 보고서를 workbench/day3/outputs/lunch_quality.md 에 쓴다.
실행: uv run python scripts/lunch_quality.py
"""
import re
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "labs/day3/lab-c/hanbit_lunch_log.csv"
OUT = ROOT / "workbench/day3/outputs/lunch_quality.md"

# 모든 칸을 원본 글자 그대로(문자열) 읽는다. 빈칸 = ""
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False)
df.insert(0, "원본줄", range(2, len(df) + 2))  # 머리줄이 1번째 줄


# ---------- 날짜를 임시로 읽기(원본은 바꾸지 않는다) ----------
def parse_date(s: str):
    s = s.strip()
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{1,2})월\s*(\d{1,2})일", s)
    if m:
        mon, day = int(m[1]), int(m[2])
        return date(2025 if mon >= 10 else 2026, mon, day)  # 연도 없으면 10–12월 2025 · 1–9월 2026
    return None


df["_날짜"] = df["날짜"].map(parse_date)
unparsed = df[df["_날짜"].isna()]

# ---------- 요일 ----------
KO = "월화수목금토일"
EN = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


def weekday_of(s: str):
    s = s.strip()
    if s in EN:
        return EN[s]
    s = s.removesuffix("요일")
    return KO.index(s) if len(s) == 1 and s in KO else None


is_holiday = df["비고"].str.strip() == "휴무"
work = df[~is_holiday]


def ex(rows: pd.DataFrame, fmt) -> str:
    """예시 2개(원본 글자 그대로)."""
    return " / ".join(fmt(r) for _, r in rows.head(2).iterrows()) or "-"


def q(s: str) -> str:
    return f"`{s}`" if s != "" else "(빈칸)"


issues = []  # (종류, 줄 수, 예시, 덧붙임)

# 1) 날짜 형식 섞임
iso = df["날짜"].str.fullmatch(r"\d{4}-\d{2}-\d{2}")
bad_date = df[~iso]
n_slash = df["날짜"].str.contains("/").sum()
n_dot = df["날짜"].str.fullmatch(r"\d{4}\.\d{1,2}\.\d{1,2}").sum()
n_kor = df["날짜"].str.contains("월").sum()
issues.append(("날짜 형식 섞임", len(bad_date), ex(bad_date, lambda r: q(r["날짜"])),
               f"`/` {n_slash}줄 · `.` {n_dot}줄 · `N월 N일`(연도 없음) {n_kor}줄"))

# 2) 요일 표기 섞임
plain_wd = df["요일"].isin(list("월화수목금"))
bad_wd = df[~plain_wd]
n_yoil = df["요일"].str.endswith("요일").sum()
n_en = df["요일"].isin(EN.keys()).sum()
wd_written = df["요일"].map(weekday_of)
wd_real = df["_날짜"].map(lambda d: d.weekday() if d else None)
mismatch = df[wd_written.notna() & wd_real.notna() & (wd_written != wd_real)]
issues.append(("요일 표기 섞임", len(bad_wd), ex(bad_wd, lambda r: q(r["요일"])),
               f"`○요일` {n_yoil}줄 · 영어 {n_en}줄. 별도로 적힌 요일이 실제 요일과 **다른** 줄 {len(mismatch)}개: "
               + ", ".join(f"`{r['날짜']}` `{r['요일']}`(실제 {KO[r['_날짜'].weekday()]})" for _, r in mismatch.iterrows())))

# 3) 같은 날짜가 두 줄
dup_mask = df["_날짜"].notna() & df.duplicated("_날짜", keep=False)
dups = df[dup_mask]
n_dup_dates = dups["_날짜"].nunique()
same_all = df[dup_mask & df.duplicated(subset=[c for c in df.columns if c not in ("원본줄",)], keep=False)]
issues.append(("같은 날짜가 두 줄", len(dups),
               ex(dups, lambda r: f"`{r['날짜']}` 식수 `{r['식수']}` 비고 {q(r['비고'])}"),
               f"겹친 날짜 {n_dup_dates}개 · 그중 모든 칸이 똑같은 줄 {len(same_all)}개 · 비고에 `재집계`가 든 줄 {dups['비고'].str.contains('재집계').sum()}개"))

# 4) 휴무 줄
hol = df[is_holiday]
issues.append(("휴무 줄", len(hol), ex(hol, lambda r: f"`{r['날짜']}` 출근예정 `{r['출근예정']}` 식수 `{r['식수']}` 비고 `{r['비고']}`"),
               "출근예정 · 식수가 0으로 적혀 있음"))

# 5) 식수 빈칸
meal_blank = df[df["식수"].str.strip() == ""]
issues.append(("식수 빈칸", len(meal_blank), ex(meal_blank, lambda r: f"`{r['날짜']}` 식수 (빈칸) 비고 {q(r['비고'])}"), ""))

# 6) 불가능해 보이는 식수(휴무 제외, 출근예정 · 식수 둘 다 있는 줄)
num = work[(work["출근예정"].str.strip() != "") & (work["식수"].str.strip() != "")].copy()
num["_출근"] = num["출근예정"].astype(float)
num["_식수"] = num["식수"].astype(float)
too_many = num["_식수"] > num["_출근"]
too_few = num["_식수"] < num["_출근"] * 0.2
impossible = num[too_many | too_few]
issues.append(("불가능해 보이는 식수", len(impossible),
               ex(impossible, lambda r: f"`{r['날짜']}` 출근예정 `{r['출근예정']}` 식수 `{r['식수']}`"),
               f"출근예정보다 많음 {too_many.sum()}줄 · 출근예정의 20% 미만 {too_few.sum()}줄(출근예정이 빈칸인 줄은 판단 못 함)"))

# 7) 날씨 표기 섞임(휴무 제외)
STD_WEATHER = {"맑음", "흐림", "비", "눈"}
w_blank = work[work["날씨"].str.strip() == ""]
w_bad = work[(work["날씨"].str.strip() != "") & ~work["날씨"].isin(STD_WEATHER)]
w_counts = w_bad["날씨"].value_counts()
issues.append(("날씨 표기 섞임", len(w_bad), ex(w_bad, lambda r: q(r["날씨"])),
               "표기별: " + " · ".join(f"`{k}` {v}" for k, v in w_counts.items())
               + f". 별도로 날씨 빈칸(휴무 제외) {len(w_blank)}줄"))

# 8) 최고기온 단위와 빈칸(휴무 제외)
t = work["최고기온"]
t_c1 = work[t.str.contains("℃")]
t_c2 = work[t.str.contains("°C")]
t_blank = work[t.str.strip() == ""]
t_unit = work[t.str.contains("℃") | t.str.contains("°C")]
t_nonnum = work[(t.str.strip() != "")
                & pd.to_numeric(t.str.replace("℃", "").str.replace("°C", "").str.strip(), errors="coerce").isna()]
issues.append(("최고기온 단위(℃ · °C)와 빈칸", len(t_unit) + len(t_blank),
               ex(t_c1, lambda r: q(r["최고기온"])).split(" / ")[0] + " / " + ex(t_c2, lambda r: q(r["최고기온"])).split(" / ")[0],
               f"`℃` {len(t_c1)}줄 · `°C` {len(t_c2)}줄 · 빈칸(휴무 제외) {len(t_blank)}줄"
               + (f" · 단위를 떼도 숫자가 아닌 줄 {len(t_nonnum)}줄" if len(t_nonnum) else "")))

# 9) 메뉴 · 행사 이름 섞임(4절 R9 목록의 변형)
MENU_VAR = ["돈까스", "카레라이스", "제육", "치킨마요덮밥", "김치 찌개"]
EVENT_VAR = ["외부손님", "전사교육"]
m_bad = df[df["메인메뉴"].isin(MENU_VAR)]
e_bad = df[df["행사"].isin(EVENT_VAR)]
issues.append(("메뉴 · 행사 이름 섞임", len(m_bad) + len(e_bad),
               ex(m_bad, lambda r: q(r["메인메뉴"])).split(" / ")[0] + " / " + ex(e_bad, lambda r: q(r["행사"])).split(" / ")[0],
               "메뉴 " + str(len(m_bad)) + "줄(" + " · ".join(f"`{k}` {v}" for k, v in m_bad["메인메뉴"].value_counts().items()) + ") · "
               + "행사 " + str(len(e_bad)) + "줄(" + " · ".join(f"`{k}` {v}" for k, v in e_bad["행사"].value_counts().items()) + ")"))

# 10) 출근예정 빈칸
att_blank = df[df["출근예정"].str.strip() == ""]
issues.append(("출근예정 빈칸", len(att_blank), ex(att_blank, lambda r: f"`{r['날짜']}` 출근예정 (빈칸) 식수 `{r['식수']}`"), ""))

# ---------- 비고 열 ----------
memo = df.loc[df["비고"].str.strip() != "", "비고"].value_counts()

# ---------- 사람이 정할 줄 ----------
decide = impossible.copy()


def why(r) -> str:
    if r["비고"].strip() == "수기 집계":
        return "식수가 출근예정의 20% 미만 · 비고 `수기 집계` — 한 자리 빠진 것인지(×10 보정) 뺄지 결정 필요"
    if r["_식수"] > r["_출근"]:
        return "식수가 출근예정보다 많음 — 뺄지 결정 필요"
    return "식수가 출근예정의 20% 미만 — 뺄지 결정 필요"


# ---------- 보고서 쓰기 ----------
dmin, dmax = df["_날짜"].dropna().min(), df["_날짜"].dropna().max()
L = []
L.append("# 점심 기록 데이터 진단 — 한빛식당(가상)\n")
L.append(f"- 원본: `labs/day3/lab-c/hanbit_lunch_log.csv`(읽기만 함) · 세는 코드: `scripts/lunch_quality.py`")
L.append("- 아래 숫자는 모두 위 스크립트가 센 값입니다. 예시는 원본 글자 그대로입니다.\n")

L.append("## 1. 줄 수 · 열 이름 · 날짜 범위\n")
L.append("| 항목 | 값 |\n|---|---|")
L.append(f"| 줄 수(머리줄 제외) | {len(df)} |")
L.append(f"| 열 이름({len(df.columns) - 2}개) | " + " · ".join(c for c in df.columns if c not in ("원본줄", "_날짜")) + " |")
L.append(f"| 날짜 범위 | {dmin} ~ {dmax} (날짜를 임시로 읽어 계산 · 연도 없는 `N월 N일`은 10–12월=2025, 1–9월=2026) |")
L.append(f"| 날짜로 못 읽은 줄 | {len(unparsed)} |\n")

L.append("## 2. 엉망인 곳 — 종류별\n")
L.append("| 종류 | 줄 수 | 예시 2개(원본 그대로) | 덧붙임 |\n|---|---:|---|---|")
for kind, n, e, note in issues:
    L.append(f"| {kind} | {n} | {e} | {note} |")
L.append("")
L.append("- 날씨 · 최고기온은 휴무 줄(모든 칸이 빈칸)을 빼고 셌습니다. 불가능한 식수 기준 '너무 적음'은 4절 R6와 같은 '출근예정의 20% 미만'입니다.\n")

L.append("## 3. 비고 열에 나오는 글\n")
L.append("| 비고(원본 그대로) | 줄 수 |\n|---|---:|")
for k, v in memo.items():
    L.append(f"| {k} | {v} |")
L.append(f"| (빈칸) | {(df['비고'].str.strip() == '').sum()} |\n")

L.append("## 4. 사람이 정해야 할 줄\n")
L.append("| 원본 줄 | 날짜 | 출근예정 | 식수 | 비고 | 왜 |\n|---:|---|---:|---:|---|---|")
for _, r in decide.iterrows():
    L.append(f"| {r['원본줄']} | {r['날짜']} | {r['출근예정']} | {r['식수']} | {r['비고'] or '(빈칸)'} | {why(r)} |")
L.append("")
L.append("- `수기 집계` 줄을 '뺀다'로 할지 '×10 보정'으로 할지는 다음 단계(정제) 프롬프트에서 수강생이 정합니다.")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(L) + "\n", encoding="utf-8")

# ---------- 콘솔 요약 ----------
print(f"줄 수 {len(df)} · 날짜 범위 {dmin} ~ {dmax} · 날짜로 못 읽은 줄 {len(unparsed)}")
for kind, n, _, note in issues:
    print(f"  {kind}: {n}  ({note})" if note else f"  {kind}: {n}")
print("비고:", " · ".join(f"{k} {v}" for k, v in memo.items()))
print("사람이 정할 줄:")
for _, r in decide.iterrows():
    print(f"  {r['날짜']} 출근예정 {r['출근예정']} 식수 {r['식수']} 비고 {r['비고'] or '(빈칸)'}")
print(f"보고서: {OUT.relative_to(ROOT)}")
