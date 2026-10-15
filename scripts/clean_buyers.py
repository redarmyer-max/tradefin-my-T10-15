"""2일차 바이어 정제 — workbench/day2/rules/정제규칙.md 1–7칸을 코드로 옮긴 것.

실행:  uv run python scripts/clean_buyers.py
입력:  data/checkpoints/d2_start.xlsx (시트 buyers · fx_at_ref) · data/checkpoints/fx_krw_daily.csv — 읽기만 한다
출력:  workbench/day2/outputs/d2_buyers_clean.csv · workbench/day2/outputs/dq_report.md
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "data/checkpoints/d2_start.xlsx"
FX_DAILY = REPO / "data/checkpoints/fx_krw_daily.csv"
OUT_DIR = REPO / "workbench/day2/outputs"
OUT_CSV = OUT_DIR / "d2_buyers_clean.csv"
OUT_MD = OUT_DIR / "dq_report.md"

ASOF = pd.Timestamp("2026-08-31")

# 1. 통화 — 9종 → 4종 (map_ccy 시트가 비어 있어 규칙 문서의 매핑표를 쓴다)
CCY_MAP = {"USD": "USD", "usd": "USD", "US$": "USD", "EUR": "EUR", "euro": "EUR",
           "JPY": "JPY", "yen": "JPY", "CNY": "CNY", "RMB": "CNY"}
FX_KEY = {"USD": "USD", "EUR": "EUR", "CNY": "CNY", "JPY": "JPY100"}      # fx_at_ref의 ccy
FX_UNIT = {"USD": 1, "EUR": 1, "CNY": 1, "JPY": 100}                       # JPY는 100엔 단위
FX_DAILY_COL = {"USD": "usd_krw", "EUR": "eur_krw", "CNY": "cny_krw", "JPY": "jpy100_krw"}

AR_COLS = ["ar_balance", "ar_current", "ar_1_30", "ar_31_60", "ar_61_90", "ar_91p"]
BUCKETS = AR_COLS[1:]
FIN_COLS = ["current_assets", "current_liabilities", "total_liabilities", "equity",
            "accounts_receivable", "revenue", "operating_income"]
FIN_FLAG_COLS = ["current_assets", "current_liabilities", "total_liabilities", "equity", "revenue"]
DPD_COLS = ["avg_days_late_12m", "avg_dpd_last3m", "avg_dpd_prev3m"]   # 3. 채우지 않을 열

OUT_COLS = ["buyer_id", "payment_method", "ccy_clean", "amt_num", "ar_balance_usd",
            "pct_current", "pct_ar_31p", "pct_91plus", "max_dpd", "avg_days_late", "late_ratio",
            "dpd_trend", "dispute_ratio", "current_ratio", "debt_to_equity", "dso_buyer", "op_margin",
            "fin_missing", "neg_equity", "country_risk", "crc_unclassified", "unit_flag",
            "fx_chg_30d", "fx_chg_30d_lag30", "late_30d"]


class RuleStop(Exception):
    """규칙이 '멈추고 보고'라고 한 경우."""


# ---------------------------------------------------------------- 규칙 함수
def clean_ccy(v) -> str:
    """1. 통화: 공백 제거 후 매핑. 없는 표기는 멈춘다."""
    key = str(v).strip()
    if key not in CCY_MAP:
        raise RuleStop(f"매핑표에 없는 통화 표기: {v!r}")
    return CCY_MAP[key]


def to_number(v) -> float:
    """2. 숫자 변환: 공백·콤마·통화 문자 제거, 끝의 k는 ×1,000. 실패하면 멈춘다."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip()
    mult = 1
    if s.lower().endswith("k"):
        s, mult = s[:-1], 1000
    s = re.sub(r"(USD|US\$|EUR|JPY|CNY|RMB|usd|euro|yen)", "", s).replace(",", "").strip()
    try:
        return float(s) * mult
    except ValueError:
        raise RuleStop(f"숫자로 바꿀 수 없는 값: {v!r}") from None


def ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """분모가 0이거나 빈칸이면 NaN."""
    den = den.where(den != 0)
    return num / den


def fx_asof(daily: pd.DataFrame, col: str, day: pd.Timestamp) -> tuple[float, pd.Timestamp]:
    """day 당일 또는 그 직전 관측일의 값."""
    row = daily.loc[daily["date"] <= day].iloc[-1]
    return float(row[col]), row["date"]


def md_table(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |")
    return "\n".join(lines)


def type_mix(s: pd.Series) -> str:
    counts = s.map(lambda v: "NaN" if (isinstance(v, float) and pd.isna(v)) else type(v).__name__).value_counts()
    return " + ".join(f"{k} {v}" for k, v in counts.items())


# ---------------------------------------------------------------- 본 작업
def main() -> None:
    raw = pd.read_excel(SRC, sheet_name="buyers", dtype=object)
    fx_ref = pd.read_excel(SRC, sheet_name="fx_at_ref")
    daily = pd.read_csv(FX_DAILY, parse_dates=["date"]).sort_values("date")
    assert len(raw) == 150 and raw["buyer_id"].is_unique

    df = raw.copy()

    # 1. 통화
    df["ccy_clean"] = df["currency"].map(clean_ccy)

    # 2. 숫자 변환 — 문자열이었던 셀은 기록해 둔다
    converted = []
    for c in AR_COLS:
        for i, v in df[c].items():
            if isinstance(v, str):
                converted.append((df.at[i, "buyer_id"], c, v, to_number(v)))
        df[c] = df[c].map(to_number)

    # 7. 환율 — 기준일 2026-08-31 행만(9/30 행은 기준일 뒤 정보라 쓰지 않는다)
    fx = fx_ref[pd.to_datetime(fx_ref["ref_date"]) == ASOF].set_index("ccy")
    assert set(FX_KEY.values()) <= set(fx.index), "기준일 환율 행이 모자란다"
    usd_krw = fx.at["USD", "krw_close"]
    rate_usd = {c: fx.at[k, "krw_close"] / FX_UNIT[c] / usd_krw for c, k in FX_KEY.items()}   # 1 통화 = ? USD

    # 4. 단위 의심 — 고치기 전 잔액으로 판정
    bal_usd_before = df["ar_balance"] * df["ccy_clean"].map(rate_usd)
    df["unit_flag"] = (bal_usd_before > df["credit_limit_usd"] * 10).astype(int)
    bucket_sum = df[BUCKETS].sum(axis=1)
    mismatch = (df["ar_balance"] - bucket_sum).abs() > 0.005
    fixes = df.loc[mismatch, ["buyer_id", "ccy_clean"]].assign(
        ar_balance_raw=raw.loc[mismatch, "ar_balance"], 숫자변환=df.loc[mismatch, "ar_balance"],
        버킷합계=bucket_sum[mismatch])
    df["amt_num"] = df["ar_balance"].where(~mismatch, bucket_sum)
    df["ar_balance_usd"] = (df["amt_num"] * df["ccy_clean"].map(rate_usd)).round(2)

    # 에이징 비율 — 잔액 0이면 NaN(나눌 수 없음)
    amt = df["amt_num"]
    df["pct_current"] = ratio(df["ar_current"], amt)
    df["pct_ar_31p"] = ratio(df[["ar_31_60", "ar_61_90", "ar_91p"]].sum(axis=1), amt)
    df["pct_91plus"] = ratio(df["ar_91p"], amt)

    # 연체 — 3. 연체 3열은 채우지 않는다
    for c in DPD_COLS + ["max_dpd", "invoices_12m", "late_invoices_12m", "dispute_cnt_12m"]:
        df[c] = pd.to_numeric(df[c])
    df["avg_days_late"] = df["avg_days_late_12m"]
    df["late_ratio"] = ratio(df["late_invoices_12m"], df["invoices_12m"])
    df["dpd_trend"] = df["avg_dpd_last3m"] - df["avg_dpd_prev3m"]
    df["dispute_ratio"] = ratio(df["dispute_cnt_12m"], df["invoices_12m"])

    # 3. 결측 — 플래그를 먼저 만들고 재무 7열을 중위수로 채운다
    for c in FIN_COLS:
        df[c] = pd.to_numeric(df[c])
    fin_before = df[FIN_COLS].copy()
    df["fin_missing"] = df[FIN_FLAG_COLS].isna().any(axis=1).astype(int)
    medians = df[FIN_COLS].median()
    df[FIN_COLS] = df[FIN_COLS].fillna(medians)

    # 5. 자본잠식 — 채우기 전 원래 equity로 판정, D/E는 빈칸
    df["neg_equity"] = (fin_before["equity"] <= 0).astype(int)
    df["current_ratio"] = ratio(df["current_assets"], df["current_liabilities"])
    df["debt_to_equity"] = ratio(df["total_liabilities"], df["equity"]).where(df["neg_equity"] == 0)
    df["dso_buyer"] = ratio(df["accounts_receivable"], df["revenue"]) * 365
    df["op_margin"] = ratio(df["operating_income"], df["revenue"])

    # 6. 국가위험 — '-'·빈칸 → 0, 플래그
    crc = df["oecd_crc"].map(lambda v: None if (pd.isna(v) or str(v).strip() in ("-", "")) else v)
    df["crc_unclassified"] = crc.isna().astype(int)
    df["country_risk"] = pd.to_numeric(crc).fillna(0).astype(int)

    # 7. 환율 변화 — fx_chg_30d는 fx_at_ref, lag30은 일별 환율에서 2026-08-01 시점의 30일 변화
    chg30 = {c: fx.at[k, "chg_30d"] for c, k in FX_KEY.items()}
    lag_day, lag_base = ASOF - pd.Timedelta(days=30), ASOF - pd.Timedelta(days=60)
    lag30, fx_check = {}, []
    for c, col in FX_DAILY_COL.items():
        v1, d1 = fx_asof(daily, col, lag_day)
        v0, d0 = fx_asof(daily, col, lag_base)
        lag30[c] = round(v1 / v0 - 1, 4)
        # 검산: 같은 방식으로 기준일의 30일 변화를 만들어 fx_at_ref의 chg_30d와 견준다
        a1, ad1 = fx_asof(daily, col, ASOF)
        a0, _ = fx_asof(daily, col, lag_day)
        fx_check.append({"ccy": c, "1통화=USD": round(rate_usd[c], 6),
                         "chg_30d(fx_at_ref)": chg30[c], "chg_30d(일별 재계산)": round(a1 / a0 - 1, 4),
                         "lag30": lag30[c], "lag 관측일": f"{d0:%m-%d} → {d1:%m-%d}"})
    df["fx_chg_30d"] = df["ccy_clean"].map(chg30)
    df["fx_chg_30d_lag30"] = df["ccy_clean"].map(lag30)

    df["late_30d"] = pd.to_numeric(df["late_30d"]).astype(int)

    out = df[OUT_COLS]
    assert len(out) == 150 and out.columns[0] == "buyer_id" and out.columns[-1] == "late_30d"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    write_report(raw, df, out, converted, fixes, medians, fin_before, fx_check)
    print(f"저장: {OUT_CSV.relative_to(REPO).as_posix()} ({out.shape[0]}행 × {out.shape[1]}열)")
    print(f"저장: {OUT_MD.relative_to(REPO).as_posix()}")


# ---------------------------------------------------------------- 보고서
def write_report(raw, df, out, converted, fixes, medians, fin_before, fx_check) -> None:
    L = ["# 바이어 정제 전·후 비교 (dq_report)", "",
         f"- 입력: `{SRC.relative_to(REPO).as_posix()}` 시트 buyers ({raw.shape[0]}행 × {raw.shape[1]}열) — 읽기만 함",
         f"- 출력: `{OUT_CSV.relative_to(REPO).as_posix()}` ({out.shape[0]}행 × {out.shape[1]}열)",
         "- 규칙: `workbench/day2/rules/정제규칙.md` 1–7칸 · 코드: `scripts/clean_buyers.py`",
         f"- 기준일(AsOf): {ASOF:%Y-%m-%d}", ""]

    L += ["## 1. 통화 (규칙 1)", ""]
    cc = raw.assign(ccy_clean=df["ccy_clean"]).groupby(["ccy_clean", "currency"]).size().reset_index(name="건수")
    L += [f"전 {raw['currency'].nunique()}종 → 후 {df['ccy_clean'].nunique()}종", "", md_table(cc), ""]

    L += ["## 2. 숫자 변환 (규칙 2)", "",
          f"문자열 셀 {len(converted)}개를 숫자로 바꿨습니다. 셀 타입 전·후:", ""]
    tm = pd.DataFrame({"열": AR_COLS, "전": [type_mix(raw[c]) for c in AR_COLS],
                       "후": [type_mix(df[c]) for c in AR_COLS]})
    L += [md_table(tm), "", md_table(pd.DataFrame(converted, columns=["buyer_id", "열", "원래 값", "변환 값"])), ""]

    L += ["## 3. 단위 의심 · 잔액 보정 (규칙 4)", "",
          f"- `unit_flag`=1: {int(df['unit_flag'].sum())}건 — {', '.join(df.loc[df['unit_flag'] == 1, 'buyer_id'])}"
          " (고치기 전 USD 환산 잔액 > 한도 × 10)",
          f"- 잔액 ≠ 버킷 합계 → 버킷 합계로 바꾼 행 {len(fixes)}건(`amt_num`). 원래 값은 아래 `ar_balance_raw`:", "",
          md_table(fixes), ""]

    L += ["## 4. 결측 (규칙 3)", "",
          f"- `fin_missing`=1: {int(df['fin_missing'].sum())}건 (유동자산·유동부채·총부채·자기자본·매출 중 하나라도 빈칸)",
          "- 재무 7열은 열별 중위수로 채웠습니다. 연체 3열은 규칙대로 채우지 않았습니다(빈칸 유지).", ""]
    mt = pd.DataFrame({"열": FIN_COLS + DPD_COLS,
                       "결측 전": [int(fin_before[c].isna().sum()) for c in FIN_COLS] + [int(raw[c].isna().sum()) for c in DPD_COLS],
                       "결측 후": [int(df[c].isna().sum()) for c in FIN_COLS + DPD_COLS],
                       "채운 값": [f"{medians[c]:,.0f}" for c in FIN_COLS] + ["채우지 않음"] * len(DPD_COLS)})
    L += [md_table(mt), ""]

    L += ["## 5. 자본잠식 (규칙 5) · 국가위험 (규칙 6)", "",
          f"- `neg_equity`=1: {int(df['neg_equity'].sum())}건 — {', '.join(df.loc[df['neg_equity'] == 1, 'buyer_id'])}"
          " (채우기 전 equity ≤ 0). 이 행의 `debt_to_equity`는 빈칸",
          f"- `oecd_crc` 셀 타입 전: {type_mix(raw['oecd_crc'])} → 후 `country_risk`: {type_mix(df['country_risk'])}",
          f"- `crc_unclassified`=1: {int(df['crc_unclassified'].sum())}건 ('-' → 0)", ""]

    L += ["## 6. 환율 (규칙 7)", "",
          "기준일 2026-08-31 행만 사용(9/30 행 제외). `fx_chg_30d_lag30` = 2026-08-01 시점(직전 관측일)의 30일 변화(일별 환율).",
          "검산: 같은 방식으로 일별 환율에서 기준일 30일 변화를 다시 계산해 fx_at_ref 값과 견줬습니다.", "",
          md_table(pd.DataFrame(fx_check)), ""]

    L += ["## 7. 결과 열 정의와 결측", ""]
    defs = {
        "buyer_id": "원본 그대로", "payment_method": "원본 그대로", "ccy_clean": "규칙 1",
        "amt_num": "잔액(원통화) — 규칙 2 변환, 버킷 합계와 다르면 버킷 합계(규칙 4)",
        "ar_balance_usd": "amt_num × 기준일 환율(통화→USD)",
        "pct_current": "ar_current ÷ amt_num", "pct_ar_31p": "(ar_31_60 + ar_61_90 + ar_91p) ÷ amt_num",
        "pct_91plus": "ar_91p ÷ amt_num", "max_dpd": "원본 그대로", "avg_days_late": "avg_days_late_12m (채우지 않음)",
        "late_ratio": "late_invoices_12m ÷ invoices_12m", "dpd_trend": "avg_dpd_last3m − avg_dpd_prev3m",
        "dispute_ratio": "dispute_cnt_12m ÷ invoices_12m", "current_ratio": "유동자산 ÷ 유동부채(채운 뒤)",
        "debt_to_equity": "총부채 ÷ 자기자본(채운 뒤), 자본잠식이면 빈칸", "dso_buyer": "매출채권 ÷ 매출 × 365",
        "op_margin": "영업이익 ÷ 매출", "fin_missing": "규칙 3", "neg_equity": "규칙 5",
        "country_risk": "규칙 6", "crc_unclassified": "규칙 6", "unit_flag": "규칙 4",
        "fx_chg_30d": "fx_at_ref 기준일 행의 chg_30d", "fx_chg_30d_lag30": "규칙 7", "late_30d": "라벨 — 원본 그대로"}
    ct = pd.DataFrame({"열": OUT_COLS, "정의": [defs[c] for c in OUT_COLS],
                       "결측": [int(out[c].isna().sum()) for c in OUT_COLS]})
    L += [md_table(ct), "",
          "분모가 0이면 비율은 빈칸입니다(잔액 0 → pct_* 빈칸, 인보이스 0건 → late_ratio · dispute_ratio 빈칸).", ""]

    OUT_MD.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except RuleStop as e:
        raise SystemExit(f"정제를 멈췄습니다(규칙: 멈추고 보고) — {e}")
