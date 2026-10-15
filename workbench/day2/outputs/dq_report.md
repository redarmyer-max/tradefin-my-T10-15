# 바이어 정제 전·후 비교 (dq_report)

- 입력: `data/checkpoints/d2_start.xlsx` 시트 buyers (150행 × 28열) — 읽기만 함
- 출력: `workbench/day2/outputs/d2_buyers_clean.csv` (150행 × 25열)
- 규칙: `workbench/day2/rules/정제규칙.md` 1–7칸 · 코드: `scripts/clean_buyers.py`
- 기준일(AsOf): 2026-08-31

## 1. 통화 (규칙 1)

전 9종 → 후 4종

| ccy_clean | currency | 건수 |
|---|---|---|
| CNY | CNY | 5 |
| CNY | RMB | 2 |
| EUR | EUR | 18 |
| EUR | euro | 5 |
| JPY | JPY | 8 |
| JPY | yen | 2 |
| USD | US$ | 15 |
| USD | USD | 81 |
| USD | usd | 14 |

## 2. 숫자 변환 (규칙 2)

문자열 셀 13개를 숫자로 바꿨습니다. 셀 타입 전·후:

| 열 | 전 | 후 |
|---|---|---|
| ar_balance | int 140 + str 9 + float 1 | float 150 |
| ar_current | int 148 + str 2 | float 150 |
| ar_1_30 | int 148 + str 2 | float 150 |
| ar_31_60 | int 149 + float 1 | float 150 |
| ar_61_90 | int 150 | float 150 |
| ar_91p | int 150 | float 150 |

| buyer_id | 열 | 원래 값 | 변환 값 |
|---|---|---|---|
| B005 | ar_balance |  195900  | 195900.0 |
| B009 | ar_balance | CNY 317,000 | 317000.0 |
| B015 | ar_balance | 7,680 | 7680.0 |
| B034 | ar_balance | 200,520 | 200520.0 |
| B043 | ar_balance | 155,200 CNY | 155200.0 |
| B083 | ar_balance | 2,200 | 2200.0 |
| B086 | ar_balance | EUR 143,620 | 143620.0 |
| B114 | ar_balance |  1458000  | 1458000.0 |
| B141 | ar_balance | 47.0k | 47000.0 |
| B076 | ar_current | 51,970 | 51970.0 |
| B091 | ar_current | 7,980 | 7980.0 |
| B008 | ar_1_30 | 6,850 | 6850.0 |
| B072 | ar_1_30 | 8,320 | 8320.0 |

## 3. 단위 의심 · 잔액 보정 (규칙 4)

- `unit_flag`=1: 1건 — B072 (고치기 전 USD 환산 잔액 > 한도 × 10)
- 잔액 ≠ 버킷 합계 → 버킷 합계로 바꾼 행 2건(`amt_num`). 원래 값은 아래 `ar_balance_raw`:

| buyer_id | ccy_clean | ar_balance_raw | 숫자변환 | 버킷합계 |
|---|---|---|---|---|
| B072 | EUR | 8320000 | 8320000.0 | 8320.0 |
| B141 | EUR | 47.0k | 47000.0 | 47030.0 |

## 4. 결측 (규칙 3)

- `fin_missing`=1: 47건 (유동자산·유동부채·총부채·자기자본·매출 중 하나라도 빈칸)
- 재무 7열은 열별 중위수로 채웠습니다. 연체 3열은 규칙대로 채우지 않았습니다(빈칸 유지).

| 열 | 결측 전 | 결측 후 | 채운 값 |
|---|---|---|---|
| current_assets | 18 | 0 | 17,593,000 |
| current_liabilities | 39 | 0 | 11,560,000 |
| total_liabilities | 18 | 0 | 22,628,500 |
| equity | 34 | 0 | 14,948,000 |
| accounts_receivable | 39 | 0 | 6,499,000 |
| revenue | 18 | 0 | 44,007,000 |
| operating_income | 37 | 0 | 1,704,000 |
| avg_days_late_12m | 11 | 11 | 채우지 않음 |
| avg_dpd_last3m | 33 | 33 | 채우지 않음 |
| avg_dpd_prev3m | 42 | 42 | 채우지 않음 |

## 5. 자본잠식 (규칙 5) · 국가위험 (규칙 6)

- `neg_equity`=1: 2건 — B013, B048 (채우기 전 equity ≤ 0). 이 행의 `debt_to_equity`는 빈칸
- `oecd_crc` 셀 타입 전: int 93 + str 57 → 후 `country_risk`: int 150
- `crc_unclassified`=1: 57건 ('-' → 0)

## 6. 환율 (규칙 7)

기준일 2026-08-31 행만 사용(9/30 행 제외). `fx_chg_30d_lag30` = 2026-08-01 시점(직전 관측일)의 30일 변화(일별 환율).
검산: 같은 방식으로 일별 환율에서 기준일 30일 변화를 다시 계산해 fx_at_ref 값과 견줬습니다.

| ccy | 1통화=USD | chg_30d(fx_at_ref) | chg_30d(일별 재계산) | lag30 | lag 관측일 |
|---|---|---|---|---|---|
| USD | 1.0 | -0.0477 | -0.0477 | -0.0658 | 07-02 → 07-31 |
| EUR | 1.161703 | -0.0396 | -0.0396 | -0.06 | 07-02 → 07-31 |
| CNY | 0.148818 | -0.0433 | -0.0433 | -0.0606 | 07-02 → 07-31 |
| JPY | 0.00626 | -0.0512 | -0.0512 | -0.0556 | 07-02 → 07-31 |

## 7. 결과 열 정의와 결측

| 열 | 정의 | 결측 |
|---|---|---|
| buyer_id | 원본 그대로 | 0 |
| payment_method | 원본 그대로 | 0 |
| ccy_clean | 규칙 1 | 0 |
| amt_num | 잔액(원통화) — 규칙 2 변환, 버킷 합계와 다르면 버킷 합계(규칙 4) | 0 |
| ar_balance_usd | amt_num × 기준일 환율(통화→USD) | 0 |
| pct_current | ar_current ÷ amt_num | 51 |
| pct_ar_31p | (ar_31_60 + ar_61_90 + ar_91p) ÷ amt_num | 51 |
| pct_91plus | ar_91p ÷ amt_num | 51 |
| max_dpd | 원본 그대로 | 0 |
| avg_days_late | avg_days_late_12m (채우지 않음) | 11 |
| late_ratio | late_invoices_12m ÷ invoices_12m | 11 |
| dpd_trend | avg_dpd_last3m − avg_dpd_prev3m | 55 |
| dispute_ratio | dispute_cnt_12m ÷ invoices_12m | 11 |
| current_ratio | 유동자산 ÷ 유동부채(채운 뒤) | 0 |
| debt_to_equity | 총부채 ÷ 자기자본(채운 뒤), 자본잠식이면 빈칸 | 2 |
| dso_buyer | 매출채권 ÷ 매출 × 365 | 0 |
| op_margin | 영업이익 ÷ 매출 | 0 |
| fin_missing | 규칙 3 | 0 |
| neg_equity | 규칙 5 | 0 |
| country_risk | 규칙 6 | 0 |
| crc_unclassified | 규칙 6 | 0 |
| unit_flag | 규칙 4 | 0 |
| fx_chg_30d | fx_at_ref 기준일 행의 chg_30d | 0 |
| fx_chg_30d_lag30 | 규칙 7 | 0 |
| late_30d | 라벨 — 원본 그대로 | 0 |

분모가 0이면 비율은 빈칸입니다(잔액 0 → pct_* 빈칸, 인보이스 0건 → late_ratio · dispute_ratio 빈칸).
