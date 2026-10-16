"""실습 D 2절 — design.md 색 토큰의 글자/바탕 대비를 계산한다(WCAG 2.x 상대 휘도).

실행: uv run python scripts/contrast_check.py
표준 라이브러리만 쓴다. 결과 Markdown 표를 design.md 5번에 옮긴다.
"""

import sys

COLORS = {
    "--bg": "#F6F6F4",
    "--surface": "#FFFFFF",
    "--border": "#E3E3DF",
    "--text": "#1C1C1A",
    "--muted": "#5E615C",
    "--accent": "#0F5F63",
    "--grade-s": "#2E7D32",
    "--grade-a": "#8A9A1B",
    "--grade-b": "#E0A100",
    "--grade-c": "#C0392B",
    "--bar": "#8F918C",  # v1에서 더함 — 막대 전용(글자 아님)
}

# 글자가 아닌 막대는 WCAG 비텍스트 기준 3 : 1로 본다.
NONTEXT_PAIRS = [
    ("지역 막대 회색 몫 / 카드 면", "--bar", "--surface"),
]
NONTEXT_MIN = 3.0

# (쓰는 곳, 글자 토큰, 바탕 토큰)
PAIRS = [
    ("본문 글자 / 배경", "--text", "--bg"),
    ("본문 글자 / 카드 면", "--text", "--surface"),
    ("보조 글자 / 배경", "--muted", "--bg"),
    ("보조 글자 / 카드 면", "--muted", "--surface"),
    ("강조색 글자 / 카드 면", "--accent", "--surface"),
    ("강조색 바탕 위 흰 글자", "--surface", "--accent"),
    ("등급 S 라벨(흰 글자)", "--surface", "--grade-s"),
    ("등급 A 라벨(진한 글자)", "--text", "--grade-a"),
    ("등급 B 라벨(진한 글자)", "--text", "--grade-b"),
    ("등급 C 라벨(흰 글자)", "--surface", "--grade-c"),
]

MIN_RATIO = 4.5

# 진한 바탕(등급 S·C, 강조색) 위 흰 글자는 따로 토큰을 두지 않고 --surface(#FFFFFF)를 쓴다.


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    rgb = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(fg: str, bg: str) -> float:
    l1, l2 = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔에서도 한글이 깨지지 않게
    print("| 쓰는 곳 | 글자 | 바탕 | 대비 | 4.5 이상 |")
    print("|---|---|---|---:|---|")
    lowest = None
    for name, fg, bg in PAIRS:
        r = contrast(COLORS[fg], COLORS[bg])
        ok = "예" if r >= MIN_RATIO else "아니오"
        print(f"| {name} | `{fg}` {COLORS[fg]} | `{bg}` {COLORS[bg]} | {r:.2f} : 1 | {ok} |")
        if lowest is None or r < lowest[1]:
            lowest = (name, r)
    print(f"\n가장 낮은 값: {lowest[0]} {lowest[1]:.2f} : 1")

    print("\n| 막대(글자 아님) | 색 | 바탕 | 대비 | 3 이상 |")
    print("|---|---|---|---:|---|")
    for name, fg, bg in NONTEXT_PAIRS:
        r = contrast(COLORS[fg], COLORS[bg])
        ok = "예" if r >= NONTEXT_MIN else "아니오"
        print(f"| {name} | `{fg}` {COLORS[fg]} | `{bg}` {COLORS[bg]} | {r:.2f} : 1 | {ok} |")


if __name__ == "__main__":
    main()
