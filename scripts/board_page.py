"""실습 D 3절 — 바이어 리스크 보드 첫 화면(v1)을 만든다.

입력: labs/day3/lab-d/buyer_board.csv (읽기만)
출력: workbench/day3/outputs/buyer_board.html (HTML 한 장, 같은 입력이면 같은 결과)
실행: uv run python scripts/board_page.py

모양은 workbench/day3/outputs/design.md의 토큰만 쓴다(아래 TOKENS).
"""

import json
import sys
from pathlib import Path

import pandas as pd

# design.md 토큰 — 화면의 색 · 글꼴 · 크기 · 간격은 이 값만 쓴다.
TOKENS = {
    # 색 6개
    "--bg": "#F6F6F4",
    "--surface": "#FFFFFF",
    "--border": "#E3E3DF",
    "--text": "#1C1C1A",
    "--muted": "#5E615C",
    "--accent": "#0F5F63",
    # 막대용 회색(v1에서 더함)
    "--bar": "#8F918C",
    # 등급 색 4개
    "--grade-s": "#2E7D32",
    "--grade-a": "#8A9A1B",
    "--grade-b": "#E0A100",
    "--grade-c": "#C0392B",
    # 글꼴
    "--font": "'Noto Sans KR', sans-serif",
    # 글자 크기 6단계
    "--fs-1": "12px",
    "--fs-2": "14px",
    "--fs-3": "16px",
    "--fs-4": "20px",
    "--fs-5": "28px",
    "--fs-6": "40px",
    # 줄 높이(v1에서 더함)
    "--lh-tight": "1.2",
    "--lh-body": "1.5",
    # 간격(4의 배수)
    "--sp-1": "4px",
    "--sp-2": "8px",
    "--sp-3": "12px",
    "--sp-4": "16px",
    "--sp-5": "24px",
    "--sp-6": "32px",
    "--sp-7": "48px",
    # 모서리 · 그림자
    "--radius": "6px",
    "--shadow": "none",
    # 레이아웃(v1에서 더함)
    "--content-max": "1200px",
    "--card-min": "160px",
}
# 등급 라벨 글자색 — design.md 대비 표: S · C는 흰 글자, A · B는 진한 글자
GRADE_INK = {"S": "--surface", "A": "--text", "B": "--text", "C": "--surface"}

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "labs/day3/lab-d/buyer_board.csv"
OUT = ROOT / "workbench/day3/outputs/buyer_board.html"

AS_OF = "2026-09-30"
DEFAULT_LINE = 17  # 위험 선(%) 처음 값

COUNTRY_KO = {
    "ARE": "아랍에미리트", "BRA": "브라질", "CHN": "중국", "DEU": "독일",
    "EGY": "이집트", "GBR": "영국", "IDN": "인도네시아", "IND": "인도",
    "JPN": "일본", "MEX": "멕시코", "MYS": "말레이시아", "NGA": "나이지리아",
    "NLD": "네덜란드", "POL": "폴란드", "SAU": "사우디아라비아", "THA": "태국",
    "TUR": "튀르키예", "TWN": "대만", "USA": "미국", "VNM": "베트남",
}

# 지역 지도 칸: (region, CSS 격자 이름) — 대략의 지리 배치, 휴대폰은 이 순서(서 → 동)로 1열
REGION_TILES = [
    ("북미·중남미", "na"),
    ("서유럽", "we"),
    ("중동부유럽", "ce"),
    ("중동·아프리카", "me"),
    ("동아시아", "ea"),
    ("동남아·남아", "sa"),
]
TOP_COUNTRIES = 10  # 지도에 올릴 나라 수(C등급 채권 많은 순)


def grade_for(pd_30d: float, line_pct: int) -> str:
    """선 이상 C, 선의 절반 이상 B, 4분의 1 이상 A, 나머지 S (C부터 검사). JS의 gradeFor와 같다."""
    line = line_pct / 100
    if pd_30d >= line:
        return "C"
    if pd_30d >= line / 2:
        return "B"
    if pd_30d >= line / 4:
        return "A"
    return "S"


def usd(n: float) -> str:
    return f"${round(n):,}"


def load() -> pd.DataFrame:
    df = pd.read_csv(SRC, encoding="utf-8-sig")
    unknown = sorted(set(df["country_code"]) - set(COUNTRY_KO))
    if unknown:
        raise SystemExit(f"한글 나라 이름이 없는 country_code: {unknown} — COUNTRY_KO에 더하세요")
    df["country_ko"] = df["country_code"].map(COUNTRY_KO)
    tiles = {r for r, _ in REGION_TILES}
    if set(df["region"]) != tiles:
        raise SystemExit(f"지도 칸과 region 값이 다릅니다: {sorted(set(df['region']) ^ tiles)} — REGION_TILES를 고치세요")
    if df.groupby("country_code")["region"].nunique().max() > 1:
        raise SystemExit("한 나라가 두 지역에 걸쳐 있습니다 — 나라 카드를 지역 칸에 놓을 수 없습니다")
    return df


def country_rank(df: pd.DataFrame, grades: pd.Series) -> pd.DataFrame:
    """C등급 채권 상위 나라: C등급 채권 합 많은 순, 같으면 나라 이름 순. JS의 나라 순위와 같다."""
    c = df[grades == "C"]
    g = c.groupby(["country_ko", "region"]).agg(
        c_ar=("open_ar_usd", "sum"), c_n=("buyer_id", "size"), c_od=("overdue_usd", "sum")).reset_index()
    g["ar_all"] = g["country_ko"].map(df.groupby("country_ko")["open_ar_usd"].sum())
    return g.sort_values(["c_ar", "country_ko"], ascending=[False, True]).head(TOP_COUNTRIES)


def top10_of(df: pd.DataFrame) -> pd.DataFrame:
    """위험 상위 10: pd_30d 높은 순, 같으면 buyer_id 순."""
    return df.sort_values(["pd_30d", "buyer_id"], ascending=[False, True]).head(10)


def page_data(df: pd.DataFrame) -> dict:
    """페이지에 넣을 데이터(필요한 열만). 빈칸은 null."""
    cols = ["buyer_id", "buyer_name", "country_ko", "region", "payment_method",
            "open_ar_usd", "overdue_usd", "pd_30d", "signal_1", "signal_2", "signal_3"]
    rows = df[cols].astype(object).where(df[cols].notna(), None)
    buyers = [
        {"id": r.buyer_id, "name": r.buyer_name, "country": r.country_ko, "region": r.region,
         "pay": r.payment_method, "ar": int(r.open_ar_usd), "od": int(r.overdue_usd), "pd": float(r.pd_30d),
         "sig": [r.signal_1, r.signal_2, r.signal_3]}
        for r in rows.itertuples(index=False)
    ]
    tiles = [{"region": r, "area": a} for r, a in REGION_TILES]
    return {"asOf": AS_OF, "defaultLine": DEFAULT_LINE, "topCountries": TOP_COUNTRIES, "buyers": buyers,
            "top10": top10_of(df)["buyer_id"].tolist(), "tiles": tiles}


def summary(df: pd.DataFrame, line_pct: int) -> dict:
    g = df["pd_30d"].map(lambda p: grade_for(p, line_pct))
    total = int(df["open_ar_usd"].sum())
    c_ar = int(df.loc[g == "C", "open_ar_usd"].sum())
    return {
        "counts": {k: int((g == k).sum()) for k in "SABC"},
        "ar_by_grade": {k: int(df.loc[g == k, "open_ar_usd"].sum()) for k in "SABC"},
        "c_ar": c_ar,
        "total_ar": total,
        "c_share": c_ar / total * 100 if total else 0.0,
        "overdue": int(df["overdue_usd"].sum()),
        "overdue_n": int((df["overdue_usd"] > 0).sum()),
        "grades": g,
    }


CSS = """
:root{__TOKENS__}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{background:var(--bg);color:var(--text);font-family:var(--font);font-size:var(--fs-3);
  line-height:var(--lh-body);word-break:keep-all;overflow-wrap:break-word}
.wrap{max-width:var(--content-max);margin:0 auto;padding:var(--sp-7)}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.muted{color:var(--muted)}
h1{font-size:var(--fs-5);line-height:var(--lh-tight);font-weight:700;color:var(--text)}
h2{font-size:var(--fs-4);line-height:var(--lh-tight);font-weight:700;color:var(--text);margin-bottom:var(--sp-4)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:var(--sp-5)}
section{margin-top:var(--sp-7)}

/* 머리 */
.head{display:flex;justify-content:space-between;align-items:flex-start;gap:var(--sp-4);flex-wrap:wrap}
.head p{font-size:var(--fs-2);color:var(--muted);margin-top:var(--sp-2)}
.asof{font-size:var(--fs-2);color:var(--muted)}

/* KPI */
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--sp-5);margin-top:var(--sp-6)}
.kpi .label{font-size:var(--fs-2);color:var(--muted);font-weight:500}
.kpi .value{display:block;overflow:hidden;font-size:var(--fs-6);line-height:var(--lh-tight);font-weight:700;color:var(--text);margin-top:var(--sp-1)}
.kpi .sub{font-size:var(--fs-2);color:var(--muted);margin-top:var(--sp-1)}

/* 등급 분포 + 슬라이더 */
.dist{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);gap:var(--sp-6)}
.gbar{display:flex;height:var(--sp-5);border-radius:var(--radius);overflow:hidden;background:var(--border)}
.gbar span{display:block;height:100%}
.gbar span+span{border-left:1px solid var(--surface)}
.legend{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--sp-4);margin-top:var(--sp-4)}
.legend .row{display:flex;flex-direction:column;align-items:flex-start;gap:var(--sp-1)}
.legend .cnt{font-size:var(--fs-4);font-weight:700;color:var(--text);line-height:var(--lh-tight)}
.legend .amt{font-size:var(--fs-2);color:var(--muted)}
.badge{display:inline-block;font-size:var(--fs-1);font-weight:700;line-height:var(--lh-body);
  padding:0 var(--sp-2);border-radius:var(--radius);white-space:nowrap}
.g-S{background:var(--grade-s);color:var(__INK_S__)}
.g-A{background:var(--grade-a);color:var(__INK_A__)}
.g-B{background:var(--grade-b);color:var(__INK_B__)}
.g-C{background:var(--grade-c);color:var(__INK_C__)}
.line-top{display:flex;justify-content:space-between;align-items:baseline;gap:var(--sp-2)}
.line-top label{font-size:var(--fs-2);font-weight:500;color:var(--text)}
.line-val{font-size:var(--fs-5);font-weight:700;color:var(--accent);line-height:var(--lh-tight)}
input[type=range]{width:100%;accent-color:var(--accent);margin-top:var(--sp-3)}
.ends{display:flex;justify-content:space-between;font-size:var(--fs-1);color:var(--muted)}
.delta{font-size:var(--fs-2);color:var(--text);margin-top:var(--sp-3);font-weight:500}
.rule{font-size:var(--fs-1);color:var(--muted);margin-top:var(--sp-2)}

/* 이번 주 할 일 · 대표님이 정할 것 */
.brief{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--sp-6)}
.brief ol{list-style:none;display:flex;flex-direction:column;gap:var(--sp-3)}
.brief li{display:flex;gap:var(--sp-2);font-size:var(--fs-2);color:var(--text)}
.brief li b{font-weight:700;color:var(--accent);flex:none}
.note{font-size:var(--fs-1);color:var(--muted);margin-top:var(--sp-4)}

/* 위험 상위 10 지역 지도 */
.map{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--sp-3);
  grid-template-areas:"na we ce ea" "na me me sa"}
.tile{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:var(--sp-3);min-width:0}
.tile-head{display:flex;justify-content:space-between;align-items:baseline;gap:var(--sp-2);flex-wrap:wrap;margin-bottom:var(--sp-3)}
.tile-name{font-size:var(--fs-2);font-weight:700;color:var(--text)}
.tile-sum{font-size:var(--fs-1);color:var(--muted)}
.tile-empty{font-size:var(--fs-1);color:var(--muted)}
.tile-cards{list-style:none;display:grid;grid-template-columns:repeat(auto-fill,minmax(var(--card-min),1fr));gap:var(--sp-3)}
.bcard{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:var(--sp-3);min-width:0}
.b-top{display:flex;justify-content:space-between;align-items:flex-start;gap:var(--sp-2)}
.b-name{font-size:var(--fs-2);font-weight:700;color:var(--text)}
.b-meta{font-size:var(--fs-1);color:var(--muted);margin-top:var(--sp-1)}
.b-amt{display:flex;align-items:baseline;gap:var(--sp-2);flex-wrap:wrap;margin-top:var(--sp-2)}
.b-ar{font-size:var(--fs-4);font-weight:700;color:var(--text);line-height:var(--lh-tight)}
.b-od{font-size:var(--fs-1);color:var(--text)}
.b-sig{list-style:none;margin-top:var(--sp-2);padding-top:var(--sp-2);border-top:1px solid var(--border);display:flex;flex-direction:column;gap:var(--sp-1)}
.b-sig li{font-size:var(--fs-1);color:var(--muted)}
.b-sig li b{display:block;font-weight:500;color:var(--text)}

footer{margin-top:var(--sp-7);padding-top:var(--sp-4);border-top:1px solid var(--border);font-size:var(--fs-1);color:var(--muted)}

@media (max-width:720px){
  .wrap{padding:var(--sp-6) var(--sp-4)}
  section{margin-top:var(--sp-6)}
  .card{padding:var(--sp-4)}
  .kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--sp-3);margin-top:var(--sp-5)}
  .kpi .value{font-size:var(--fs-5)}
  .dist{grid-template-columns:minmax(0,1fr);gap:var(--sp-5)}
  .legend{grid-template-columns:repeat(2,minmax(0,1fr))}
  .brief{grid-template-columns:minmax(0,1fr);gap:var(--sp-5)}
  .map{grid-template-columns:minmax(0,1fr);grid-template-areas:"na" "we" "ce" "me" "ea" "sa"}
  .tile-cards{grid-template-columns:minmax(0,1fr)}
}
"""

BODY = """
<div class="wrap">
  <header class="head">
    <div>
      <h1>바이어 리스크 한눈에</h1>
      <p>(가상) 한빛정밀(주) 바이어 150곳 · 합성 데이터</p>
    </div>
    <div class="asof">기준일 <span class="num">__ASOF__</span></div>
  </header>

  <div class="kpis" aria-label="핵심 숫자">
    <div class="card kpi"><div class="label">위험 바이어</div><div class="value num fit" id="k-c-n"></div><div class="sub" id="k-c-n-sub"></div></div>
    <div class="card kpi"><div class="label">C등급 채권</div><div class="value num fit" id="k-c-ar"></div><div class="sub" id="k-c-ar-sub"></div></div>
    <div class="card kpi"><div class="label">전체 채권</div><div class="value num fit" id="k-ar"></div><div class="sub" id="k-ar-sub"></div></div>
    <div class="card kpi"><div class="label">연체 금액</div><div class="value num fit" id="k-od"></div><div class="sub" id="k-od-sub"></div></div>
  </div>

  <section class="card" aria-label="이번 주 할 일과 대표님이 정할 것">
    <div class="brief">
      <div><h2>이번 주 할 일</h2><ol id="actions"></ol></div>
      <div><h2>대표님이 정할 것</h2><ol id="decisions"></ol></div>
    </div>
    <p class="note">표의 숫자로 만든 초안입니다. 위험 선을 움직이면 숫자가 같이 바뀝니다. 최종 판단은 우리 팀이 합니다.</p>
  </section>

  <section class="card dist" aria-label="신호등 등급 분포와 위험 선">
    <div>
      <h2>신호등 등급 분포</h2>
      <div class="gbar" id="gbar" role="img"></div>
      <div class="legend" id="legend"></div>
    </div>
    <div>
      <div class="line-top"><label for="line">위험 선</label><span class="line-val num" id="line-val"></span></div>
      <input type="range" id="line" min="5" max="30" step="1" value="__LINE__" aria-describedby="delta">
      <div class="ends"><span class="num">5%</span><span class="num">30%</span></div>
      <p class="delta" id="delta"></p>
      <p class="rule">위험 점수가 선 이상이면 C, 선의 절반 이상이면 B, 4분의 1 이상이면 A, 나머지는 S입니다.</p>
    </div>
  </section>

  <section class="card" aria-label="C등급 채권 상위 나라 지도">
    <h2>C등급 채권 상위 10개 나라 · 지도</h2>
    <div class="map" id="map"></div>
    <p class="note">금액은 지금 선에서 C등급인 바이어의 채권을 나라별로 더한 값(크게)과 그 연체입니다. 칸 아래는 그 나라 C등급 바이어와 위험 신호입니다. 이 신호들은 확인해 볼 이유이지, 연체의 원인이라는 뜻은 아닙니다.</p>
  </section>

  <footer>(가상) 합성 데이터 · 기준일 <span class="num">__ASOF__</span> · 위험 점수는 판단을 돕는 값이고 결정은 사람이 합니다</footer>
</div>
"""

JS = r"""
(function(){
  var D = JSON.parse(document.getElementById('board-data').textContent);
  var B = D.buyers, byId = {};
  B.forEach(function(b){ byId[b.id] = b; });
  var G = ['S','A','B','C'];
  var FS = ['--fs-6','--fs-5','--fs-4','--fs-3','--fs-2'];

  function gradeFor(p, linePct){        // board_page.py의 grade_for와 같다(C부터 검사)
    var line = linePct / 100;
    if (p >= line) return 'C';
    if (p >= line / 2) return 'B';
    if (p >= line / 4) return 'A';
    return 'S';
  }
  function usd(n){ return '$' + Math.round(n).toLocaleString('en-US'); }
  function signedUsd(n){ return (n < 0 ? '−' : '+') + usd(Math.abs(n)); }
  function signedN(n){ return (n < 0 ? '−' : '+') + Math.abs(n); }
  function pct(x){ return (x * 100).toFixed(1) + '%'; }
  function esc(s){ return s == null ? '–' : String(s).replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function badge(g){ return '<span class="badge g-' + g + '">' + g + '</span>'; }

  function summarize(linePct){
    var s = {n:{S:0,A:0,B:0,C:0}, ar:{S:0,A:0,B:0,C:0}, total:0, od:0, odN:0, grade:{}, payC:{}, ctyAr:{}, cty:{}};
    B.forEach(function(b){
      var g = gradeFor(b.pd, linePct);
      s.grade[b.id] = g; s.n[g]++; s.ar[g] += b.ar; s.total += b.ar;
      s.od += b.od; if (b.od > 0) s.odN++;
      s.ctyAr[b.country] = (s.ctyAr[b.country] || 0) + b.ar;
      if (g === 'C'){
        s.payC[b.pay] = (s.payC[b.pay] || 0) + 1;
        var c = s.cty[b.country] || (s.cty[b.country] = {name:b.country, region:b.region, ar:0, n:0, od:0, buyers:[]});
        c.ar += b.ar; c.n++; c.od += b.od; c.buyers.push(b);
      }
    });
    // C등급 채권 상위 나라: C등급 채권 많은 순, 같으면 나라 이름 순(board_page.py의 country_rank와 같다)
    s.rank = Object.keys(s.cty).map(function(k){ return s.cty[k]; }).sort(function(a, b){
      return b.ar - a.ar || (a.name < b.name ? -1 : 1);
    }).slice(0, D.topCountries);
    s.rank.forEach(function(c, i){
      c.rank = i + 1;
      c.buyers.sort(function(a, b){ return b.pd - a.pd || (a.id < b.id ? -1 : 1); });
    });
    return s;
  }
  var base = summarize(D.defaultLine);

  // 위험 상위 10 묶음(선과 무관) — 채권 · 연체 합, 나라별 곳 수
  var T = D.top10.map(function(id){ return byId[id]; });
  var tAr = 0, tOd = 0, tCty = {};
  T.forEach(function(b){
    tAr += b.ar; tOd += b.od;
    var r = tCty[b.country] || (tCty[b.country] = {n:0, ar:0});
    r.n++; r.ar += b.ar;
  });
  // 상위 10이 가장 많은 나라: 곳 수 → 채권 → 이름 순
  var tTop = Object.keys(tCty).sort(function(a, b){
    return tCty[b].n - tCty[a].n || tCty[b].ar - tCty[a].ar || (a < b ? -1 : 1);
  })[0];
  function li(i, html){ return '<li><b class="num">' + i + '.</b><span>' + html + '</span></li>'; }

  function fit(){                      // 숫자가 칸보다 길면 한 단계씩 줄인다(줄 바꿈 대신)
    var root = getComputedStyle(document.documentElement);
    var px = FS.map(function(v){ return parseFloat(root.getPropertyValue(v)); });
    var els = [].slice.call(document.querySelectorAll('.fit')), step = 0;
    els.forEach(function(el){
      el.style.fontSize = '';
      var i = px.indexOf(parseFloat(getComputedStyle(el).fontSize));
      if (i < 0) i = 0;
      while (el.scrollWidth > el.clientWidth && i < FS.length - 1){ i++; el.style.fontSize = 'var(' + FS[i] + ')'; }
      step = Math.max(step, i);
    });
    // KPI 4칸은 같은 크기로 맞춘다(가장 많이 줄인 칸에 맞춤)
    els.forEach(function(el){ el.style.fontSize = 'var(' + FS[step] + ')'; });
  }

  function render(linePct){
    var s = summarize(linePct);
    document.getElementById('line-val').textContent = linePct + '%';

    // KPI
    document.getElementById('k-c-n').textContent = s.n.C + '곳';
    document.getElementById('k-c-n-sub').textContent = 'C등급 · 위험 선 ' + linePct + '%';
    document.getElementById('k-c-ar').textContent = usd(s.ar.C);
    document.getElementById('k-c-ar-sub').textContent = '전체 채권의 ' + (s.total ? (s.ar.C / s.total * 100).toFixed(1) : '0.0') + '%';
    document.getElementById('k-ar').textContent = usd(s.total);
    document.getElementById('k-ar-sub').textContent = B.length + '곳';
    document.getElementById('k-od').textContent = usd(s.od);
    document.getElementById('k-od-sub').textContent = s.odN + '곳에서 연체';

    // 등급 분포
    var bar = '', leg = '';
    G.forEach(function(g){
      var w = s.n[g] / B.length * 100;
      if (s.n[g] > 0) bar += '<span class="g-' + g + '" style="width:' + w + '%"></span>';
      leg += '<div class="row">' + badge(g) + '<span class="cnt num">' + s.n[g] + '곳</span><span class="amt num">' + usd(s.ar[g]) + '</span></div>';
    });
    var gbar = document.getElementById('gbar');
    gbar.innerHTML = bar;
    gbar.setAttribute('aria-label', G.map(function(g){ return g + '등급 ' + s.n[g] + '곳'; }).join(', '));
    document.getElementById('legend').innerHTML = leg;

    // 처음 17%와 견준 차이
    var dn = s.n.C - base.n.C, da = s.ar.C - base.ar.C;
    document.getElementById('delta').textContent =
      '처음 ' + D.defaultLine + '%보다 C등급 ' + signedN(dn) + '곳 · ' + signedUsd(da);

    // 이번 주 할 일 3
    var tC = T.filter(function(b){ return s.grade[b.id] === 'C'; }).length;
    document.getElementById('actions').innerHTML =
      li(1, '위험 상위 10곳에 전화해 결제 계획을 확인합니다. 채권 <span class="num">' + usd(tAr) + '</span> · 연체 <span class="num">' + usd(tOd) +
        '</span>이고, 지금 선에서 이 중 C등급은 <span class="num">' + tC + '곳</span>입니다.') +
      li(2, '상위 10곳이 가장 많은 나라 ' + esc(tTop) + ' <span class="num">' + tCty[tTop].n + '곳</span>(채권 <span class="num">' +
        usd(tCty[tTop].ar) + '</span>)의 연체 상황을 먼저 확인합니다.') +
      li(3, '연체가 있는 <span class="num">' + s.odN + '곳</span>(<span class="num">' + usd(s.od) + '</span>)의 회수 일정을 확인합니다.');

    // 대표님이 정할 것 3
    var d1;
    if (linePct > 5){
      var lo = summarize(linePct - 1);
      d1 = '위험 선을 <span class="num">' + linePct + '%</span>로 둘지 정합니다. 1%p 낮추면 C등급 <span class="num">' +
        signedN(lo.n.C - s.n.C) + '곳 · ' + signedUsd(lo.ar.C - s.ar.C) + '</span>입니다.';
    } else {
      d1 = '위험 선을 <span class="num">5%</span>로 둘지 정합니다. 지금이 가장 낮은 선입니다.';
    }
    var pays = Object.keys(s.payC).sort(function(a, b){ return s.payC[b] - s.payC[a] || (a < b ? -1 : 1); });
    var d2 = s.n.C
      ? 'C등급 <span class="num">' + s.n.C + '곳</span>과의 결제 조건을 지금대로 둘지 정합니다. 지금 조건은 ' +
        pays.map(function(p){ return esc(p) + ' <span class="num">' + s.payC[p] + '곳</span>'; }).join(', ') + '입니다.'
      : '지금 선에서는 C등급이 없어 결제 조건을 다시 볼 곳이 없습니다.';
    var c1 = s.rank[0];
    var d3 = c1
      ? 'C등급 채권이 가장 많은 나라 ' + esc(c1.name) + '의 C등급 채권 <span class="num">' + usd(c1.ar) + '</span>(그 나라 채권의 <span class="num">' +
        (c1.ar / s.ctyAr[c1.name] * 100).toFixed(1) + '%</span>)을 어떻게 다룰지 정합니다.'
      : '지금 선에서는 C등급 채권이 있는 나라가 없습니다.';
    document.getElementById('decisions').innerHTML = li(1, d1) + li(2, d2) + li(3, d3);

    // C등급 채권 상위 나라 지도 — 지역 칸은 위치 틀이고, 금액은 나라 카드에만
    var map = '';
    D.tiles.forEach(function(t){
      var inT = s.rank.filter(function(c){ return c.region === t.region; });
      map += '<div class="tile" style="grid-area:' + t.area + '">' +
        '<div class="tile-head"><span class="tile-name">' + esc(t.region) + '</span></div>';
      if (!inT.length){ map += '<p class="tile-empty">상위 ' + D.topCountries + '개 나라 없음</p></div>'; return; }
      map += '<ul class="tile-cards">';
      inT.forEach(function(c){
        map += '<li class="bcard"><div class="b-top"><span class="b-name">' + esc(c.name) + '</span>' +
          '<span class="b-meta num">' + c.rank + '위</span></div>' +
          '<div class="b-amt"><span class="b-ar num">' + usd(c.ar) + '</span><span class="b-od">연체 <span class="num">' + usd(c.od) + '</span></span></div>' +
          '<div class="b-meta">' + badge('C') + ' <span class="num">' + c.n + '곳</span></div>' +
          '<ul class="b-sig">' + c.buyers.map(function(b){
            var sig = b.sig.filter(function(v){ return v != null && v !== ''; });
            return '<li><b>' + esc(b.name) + '</b>' + sig.map(esc).join(' / ') + '</li>';
          }).join('') + '</ul></li>';
      });
      map += '</ul></div>';
    });
    document.getElementById('map').innerHTML = map;

    fit();
  }

  var slider = document.getElementById('line');
  slider.addEventListener('input', function(){ render(parseInt(slider.value, 10)); });
  window.addEventListener('resize', fit);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);
  render(parseInt(slider.value, 10));
})();
"""

HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>바이어 리스크 한눈에</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<style>__CSS__</style>
</head>
<body>
__BODY__
<script type="application/json" id="board-data">__DATA__</script>
<script>__JS__</script>
</body>
</html>
"""


def build_html(data: dict) -> str:
    tokens = "".join(f"{k}:{v};" for k, v in TOKENS.items())
    css = CSS.replace("__TOKENS__", tokens)
    for g, ink in GRADE_INK.items():
        css = css.replace(f"__INK_{g}__", ink)
    body = BODY.replace("__ASOF__", AS_OF).replace("__LINE__", str(DEFAULT_LINE))
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (HTML.replace("__CSS__", css).replace("__BODY__", body)
            .replace("__JS__", JS).replace("__DATA__", blob))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    df = load()
    s = summary(df, DEFAULT_LINE)

    mismatch = df[df["grade"] != s["grades"]]
    print(f"읽은 표: {len(df)}행 × {df.shape[1] - 1}열")
    print(f"grade 열 vs {DEFAULT_LINE}% 규칙: {len(df) - len(mismatch)}/{len(df)}줄 일치"
          + ("" if mismatch.empty else f" — 다른 줄: {mismatch['buyer_id'].tolist()}"))
    print("\n| 등급 | 곳 수 | 채권 |")
    print("|---|---:|---:|")
    for k in "SABC":
        print(f"| {k} | {s['counts'][k]} | {usd(s['ar_by_grade'][k])} |")
    print(f"\nC등급 채권 {usd(s['c_ar'])} / 전체 채권 {usd(s['total_ar'])} = {s['c_share']:.1f}%")
    print(f"연체 금액 {usd(s['overdue'])} · {s['overdue_n']}곳")

    # 지도 · '할 일 / 정할 것' 상자의 숫자(선 17%) — 화면 값과 대조용
    t = top10_of(df)
    print(f"\n위험 상위 10: 채권 {usd(t['open_ar_usd'].sum())} · 연체 {usd(t['overdue_usd'].sum())}")
    tc = t.groupby("country_ko").agg(n=("buyer_id", "size"), ar=("open_ar_usd", "sum")).reset_index()
    top = tc.sort_values(["n", "ar", "country_ko"], ascending=[False, False, True]).iloc[0]
    print(f"상위 10곳이 가장 많은 나라: {top.country_ko} {top.n}곳 · 채권 {usd(top.ar)}")

    cr = country_rank(df, s["grades"])
    print(f"\nC등급 채권 상위 {TOP_COUNTRIES}개 나라 (지도)")
    print("| 순위 | 나라 | 지역 | C등급 채권 | C등급 곳 수 | 연체 | 나라 채권 대비 |")
    print("|---:|---|---|---:|---:|---:|---:|")
    for i, r in enumerate(cr.itertuples(), 1):
        print(f"| {i} | {r.country_ko} | {r.region} | {usd(r.c_ar)} | {r.c_n} | {usd(r.c_od)} | {r.c_ar / r.ar_all * 100:.1f}% |")
    print(f"합계 C등급 채권 {usd(cr['c_ar'].sum())} · {int(cr['c_n'].sum())}곳")
    lo = summary(df, DEFAULT_LINE - 1)
    print(f"선 {DEFAULT_LINE - 1}%: C등급 {lo['counts']['C'] - s['counts']['C']:+d}곳 · "
          f"{'+' if lo['c_ar'] >= s['c_ar'] else '-'}{usd(abs(lo['c_ar'] - s['c_ar']))}")
    c = df[s["grades"] == "C"]
    print("C등급 결제방식:", c["payment_method"].value_counts().to_dict())

    OUT.write_text(build_html(page_data(df)), encoding="utf-8", newline="\n")
    print(f"\n썼다: {OUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
