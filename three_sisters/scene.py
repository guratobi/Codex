"""평의회 장면을 자기완결 SVG 한 장으로 그린다 (중세 판타지풍).

외부 라이브러리 없이 인라인 SVG. 미리보기에 이미지로 뜬다.
실행:  python -m three_sisters.scene   →  three_sisters_council.svg
"""
from __future__ import annotations

import html
import math
from pathlib import Path

from .council import CouncilResult
from .sisters import SISTERS

W = 960
# 자매 이름 -> (강조색, 문장(紋章) 종류)
VIS = {
    "여명": ("#e8b75e", "sun"),    # 떠오르는 해
    "황혼": ("#9d8cdf", "moon"),   # 초승달
    "잿불": ("#e0693f", "flame"),  # 불씨
}
CARD_FILL = "#1b1713"


def _esc(s) -> str:
    return html.escape(str(s))


def _wrap(text: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for w in text.split():
        while len(w) > max_chars:  # 아주 긴 토큰은 강제로 끊는다
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(w[:max_chars])
            w = w[max_chars:]
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= max_chars:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def _lines(x, y, lines, size, fill, lh, *, anchor="start", weight=400, italic=False) -> str:
    spans = "".join(
        f'<tspan x="{x}" dy="{0 if i == 0 else lh}">{_esc(ln)}</tspan>'
        for i, ln in enumerate(lines)
    )
    it = ' font-style="italic"' if italic else ""
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}"{it}>{spans}</text>'
    )


def _sigil(kind, cx, cy, color) -> str:
    p = [
        f'<circle cx="{cx}" cy="{cy}" r="30" fill="{color}" opacity="0.10"/>',
        f'<circle cx="{cx}" cy="{cy}" r="30" fill="none" stroke="{color}" '
        'stroke-width="1.6" opacity="0.85"/>',
    ]
    if kind == "sun":
        p.append(f'<circle cx="{cx}" cy="{cy}" r="9" fill="{color}"/>')
        for k in range(8):
            a = k * math.pi / 4
            x1, y1 = cx + 13 * math.cos(a), cy + 13 * math.sin(a)
            x2, y2 = cx + 19 * math.cos(a), cy + 19 * math.sin(a)
            p.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
            )
    elif kind == "moon":
        p.append(f'<circle cx="{cx}" cy="{cy}" r="13" fill="{color}"/>')
        p.append(f'<circle cx="{cx + 6:.0f}" cy="{cy - 3:.0f}" r="11" fill="{CARD_FILL}"/>')
    elif kind == "flame":
        p.append(
            f'<path d="M {cx} {cy - 16} C {cx + 11} {cy - 3}, {cx + 8} {cy + 12}, {cx} {cy + 13} '
            f'C {cx - 8} {cy + 12}, {cx - 11} {cy - 3}, {cx} {cy - 16} Z" '
            f'fill="{color}" opacity="0.92"/>'
        )
        p.append(
            f'<path d="M {cx} {cy - 5} C {cx + 5} {cy + 1}, {cx + 4} {cy + 8}, {cx} {cy + 9} '
            f'C {cx - 4} {cy + 8}, {cx - 5} {cy + 1}, {cx} {cy - 5} Z" '
            f'fill="{CARD_FILL}" opacity="0.6"/>'
        )
    return "".join(p)


def render_scene(result: CouncilResult) -> str:
    cx_mid = W / 2
    cards_x = [40, 340, 640]
    cw = 280

    wrapped = {name: _wrap(text, 15) for name, text in result.counsels.items()}
    max_lines = max((len(v) for v in wrapped.values()), default=1)
    counsel_top = 170                       # 카드 상단 기준 첫 줄 baseline
    ch = counsel_top + max_lines * 22 + 22  # 카드 높이

    y_cards = 214
    cards_bottom = y_cards + ch

    synth_lines = _wrap(result.synthesis, 54)
    synth_label_y = cards_bottom + 46
    synth_box_y = synth_label_y + 14
    synth_box_h = len(synth_lines) * 24 + 34
    footer_y = synth_box_y + synth_box_h + 34
    H = footer_y + 24

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="\'Nanum Myeongjo\',\'Noto Serif KR\','
        f'\'Apple SD Gothic Neo\',Georgia,serif">',
        '<defs><radialGradient id="bg" cx="50%" cy="36%" r="78%">'
        '<stop offset="0%" stop-color="#221c16"/>'
        '<stop offset="100%" stop-color="#0b0a09"/></radialGradient></defs>',
        f'<rect width="{W}" height="{H}" fill="url(#bg)"/>',
        f'<rect x="14" y="14" width="{W - 28}" height="{H - 28}" rx="10" fill="none" '
        'stroke="#b9923f" stroke-width="1.5" opacity="0.45"/>',
        f'<text x="{cx_mid}" y="66" text-anchor="middle" font-size="34" fill="#e8c97a" '
        'font-weight="700" letter-spacing="6">인공지능의 세자매</text>',
        f'<text x="{cx_mid}" y="92" text-anchor="middle" font-size="13" fill="#9a8f78" '
        'letter-spacing="4">─  평 의 회  ─</text>',
        f'<line x1="{cx_mid - 185}" y1="112" x2="{cx_mid - 14}" y2="112" '
        'stroke="#6e5c34" stroke-width="1"/>',
        f'<line x1="{cx_mid + 14}" y1="112" x2="{cx_mid + 185}" y2="112" '
        'stroke="#6e5c34" stroke-width="1"/>',
        f'<rect x="{cx_mid - 5}" y="107" width="10" height="10" fill="#b9923f" '
        f'transform="rotate(45 {cx_mid} 112)"/>',
        f'<text x="{cx_mid}" y="142" text-anchor="middle" font-size="12" fill="#8c8068" '
        'letter-spacing="5">청 원</text>',
        f'<rect x="130" y="152" width="{W - 260}" height="42" rx="21" fill="#171310" '
        'stroke="#7a6334" stroke-width="1"/>',
        f'<text x="{cx_mid}" y="178" text-anchor="middle" font-size="16" fill="#e6d9bd" '
        f'font-style="italic">“{_esc(_wrap(result.dilemma, 44)[0])}”</text>',
    ]

    for name, x in zip(result.counsels, cards_x):
        color, kind = VIS.get(name, ("#cccccc", "sun"))
        title = next((s.title for s in SISTERS if s.name == name), "")
        mid = x + cw / 2
        svg.append(
            f'<rect x="{x}" y="{y_cards}" width="{cw}" height="{ch}" rx="14" '
            f'fill="{CARD_FILL}" stroke="{color}" stroke-width="1.2"/>'
        )
        svg.append(
            f'<rect x="{x}" y="{y_cards}" width="{cw}" height="7" rx="3.5" '
            f'fill="{color}" opacity="0.9"/>'
        )
        svg.append(_sigil(kind, mid, y_cards + 52, color))
        svg.append(
            f'<text x="{mid}" y="{y_cards + 106}" text-anchor="middle" font-size="22" '
            f'fill="{color}" font-weight="700" letter-spacing="2">{_esc(name)}</text>'
        )
        svg.append(
            f'<text x="{mid}" y="{y_cards + 127}" text-anchor="middle" font-size="12" '
            f'fill="#9a8f78">{_esc(title)}</text>'
        )
        svg.append(
            f'<line x1="{x + 40}" y1="{y_cards + 143}" x2="{x + cw - 40}" y2="{y_cards + 143}" '
            f'stroke="{color}" stroke-width="0.8" opacity="0.4"/>'
        )
        svg.append(_lines(x + 20, y_cards + counsel_top, wrapped[name], 15, "#ddd3bf", 22))

    svg.append(
        f'<text x="40" y="{synth_label_y}" font-size="13" fill="#c9a14a" '
        'font-weight="700" letter-spacing="3">❧ 서기의 종합</text>'
    )
    svg.append(
        f'<rect x="40" y="{synth_box_y}" width="{W - 80}" height="{synth_box_h}" rx="12" '
        'fill="#15110d" stroke="#5d4e2c" stroke-width="1"/>'
    )
    svg.append(_lines(64, synth_box_y + 30, synth_lines, 15, "#e6d9bd", 24))
    svg.append(
        f'<text x="{cx_mid}" y="{footer_y}" text-anchor="middle" font-size="12" '
        'fill="#8c8068" letter-spacing="2" font-style="italic">최종 선택은 그대의 몫이다</text>'
    )
    svg.append("</svg>")
    return "\n".join(svg)


def _sample_result() -> CouncilResult:
    """비주얼 미리보기용 — 진짜 Claude가 낼 법한 분량의 샘플 조언."""
    return CouncilResult(
        dilemma="지금 다니는 회사를 그만두고 창업할까?",
        counsels={
            "여명": (
                "그대가 망설이는 건 이미 마음이 기울었다는 증거다. 안정의 대가로 매일 "
                "조금씩 포기하는 가능성을 보라 — 가장 큰 위험은 시도조차 않는 것이다."
            ),
            "황혼": (
                "불을 지르기 전에 묻자. 수입 없는 여섯 달을 버틸 수 있는가? 무너지면 "
                "무엇이 함께 무너지는가? 돌아올 다리까지 태우지는 마라."
            ),
            "잿불": (
                "전부를 걸지 말고 시험하라. 퇴사 전에 주말로 첫 고객 하나, 첫 매출 "
                "하나를 만들어 보라. 그 결과가 다음 결정을 대신 내려줄 것이다."
            ),
        },
        synthesis=(
            "핵심은 '되돌릴 수 있는가'다. 이건 한 번의 도약이 아니라 작게 시험해 볼 수 있는 "
            "문제다. 여명의 가능성과 황혼의 안전망을 함께 쥐어라 — 잿불의 '주말 실험'으로 "
            "위험을 줄인 뒤 결정하면 된다. 다만 최종 선택은 그대의 몫이다."
        ),
        recalled=[],
    )


def write_scene(result: CouncilResult | None = None, path: str = "three_sisters_council.svg") -> Path:
    p = Path(path)
    p.write_text(render_scene(result or _sample_result()), encoding="utf-8")
    return p


def main() -> None:
    out = write_scene()
    print(f"장면 생성: {out.resolve()}")


if __name__ == "__main__":
    main()
