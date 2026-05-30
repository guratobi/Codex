"""평의회 장면 — 도트(픽셀) 그래픽 SVG.

거대한 '운명의 세 여신'(여명·황혼·잿불)이 타로 아르카나처럼 우뚝 서 있고,
그 앞에 작은 주인공(뒷모습)이 올려다본다. 외부 라이브러리 없이 인라인 SVG,
모든 도형은 픽셀 그리드에 정렬(crispEdges). 미리보기에 이미지로 뜬다.

실행:  python -m three_sisters.scene   →  three_sisters_council.svg
"""
from __future__ import annotations

import html
import random
from pathlib import Path

from .council import CouncilResult
from .sisters import SISTERS

W = 900
FONT = "'Galmuri11','DungGeunMo','NeoDunggeunmo','Press Start 2P',monospace"

# ── 스프라이트 (문자 = 팔레트 키, '.'/' ' = 투명) ──────────────────────────

GODDESS = [
    "         CC         ",
    "        CrrC        ",
    "       C OO C       ",
    "      C OrrO C      ",
    "       OCCCCCCO     ",
    "      OHHHHHHHHO    ",
    "     OHSSSSSSSSHO   ",
    "     OHSSSSSSSSHO   ",
    "     OSSSSSSSSSSO   ",
    "    OSSSeeSSeeSSSO  ",
    "    OSSSeeSSeeSSSO  ",
    "    OSSSSSSSSSSSSO  ",
    "    OHSSSSooSSSSHO  ",
    "     OHSSSSSSSSHO   ",
    "      OHHSSSSHHO    ",
    "       OOHHHHOO     ",
    "     OdrrwwwwrrdO   ",
    "    OdrrrwwwwrrrdO  ",
    "   OdrrrrCwwCrrrrdO ",
    "  OdrrrrrCwwCrrrrrdO",
    "  OrrrrrrwwwwrrrrrrO",
    "  OdrrrrrwwwwrrrrrdO",
    "  OddrrrrwwwwrrrrddO",
    "  OOddrrrrrrrrrrddOO",
    "    OOdddddddddOO   ",
    "      OOOOOOOOO     ",
]

HERO = [
    "..oooo..",
    ".oddddo.",
    ".odHHdo.",
    ".oddddo.",
    ".ohhhho.",
    "ohhhhhho",
    "ohhcchho",
    "ohhhhhho",
    ".oh..ho.",
    ".oo..oo.",
]

SUN = ["..X.X..", "...X...", "X.XXX.X", ".XXXXX.", "X.XXX.X", "...X...", "..X.X.."]
MOON = ["..XXX..", ".XX....", "XX.....", "XX.....", "XX.....", ".XX....", "..XXX.."]
FLAME = ["...X...", "..XX...", "..XXX..", ".XXXXX.", ".XXXXX.", "..XXX..", "...X..."]

# 자매 이름 -> (robe, robe-dark, robe-light, eye-glow, emblem)
VIS = {
    "여명": ("#e0a23a", "#9c6a22", "#ffd98a", "#fff4cf", SUN),
    "황혼": ("#7b6bd0", "#463a82", "#c6b9f6", "#efe7ff", MOON),
    "잿불": ("#d8552e", "#8c3216", "#ff9e6b", "#ffd9b6", FLAME),
}


def _esc(s) -> str:
    return html.escape(str(s))


def _wrap(text: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for w in text.split():
        while len(w) > max_chars:
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


def _blit(rows, palette, x, y, cell) -> str:
    out = []
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            col = palette.get(ch)
            if col:
                out.append(
                    f'<rect x="{x + c * cell}" y="{y + r * cell}" '
                    f'width="{cell}" height="{cell}" fill="{col}"/>'
                )
    return "".join(out)


def _goddess_palette(robe, dark, light, eye) -> dict:
    return {
        "O": "#15111d", "C": "#f3c64b", "S": "#ecd0ad", "H": "#2a2342",
        "e": eye, "o": "#6b5560", "r": robe, "d": dark, "w": light,
    }


def _text(x, y, s, size, fill, *, anchor="start", weight=400) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}">{_esc(s)}</text>'
    )


def render_scene(result: CouncilResult) -> str:
    PX = 6
    card_w, gap = 264, 24
    cards_x = [30, 30 + card_w + gap, 30 + 2 * (card_w + gap)]
    card_y, card_h = 96, 392

    synth_lines = _wrap(result.synthesis, 58)
    box_y = 556
    box_h = len(synth_lines) * 24 + 46
    H = box_y + box_h + 22

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" shape-rendering="crispEdges">',
        '<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#1a1330"/>'
        '<stop offset="55%" stop-color="#100a1e"/>'
        '<stop offset="100%" stop-color="#05040a"/></linearGradient></defs>',
        f'<rect width="{W}" height="{H}" fill="url(#sky)"/>',
    ]

    # 별 (시드 고정 → 결정적)
    rng = random.Random(7)
    for _ in range(90):
        sx = rng.randrange(0, W // PX) * PX
        sy = rng.randrange(0, (card_y + 60) // PX) * PX
        size = PX if rng.random() < 0.25 else PX // 2
        op = rng.choice(["0.9", "0.6", "0.4"])
        svg.append(f'<rect x="{sx}" y="{sy}" width="{size}" height="{size}" fill="#e8e6ff" opacity="{op}"/>')

    # 제목
    svg.append(_text(W / 2, 48, "인공지능의 세자매", 30, "#f0d27a", anchor="middle", weight=700))
    svg.append(_text(W / 2, 76, "─  운명의 세 여신 앞에 선 그대  ─", 13, "#9a8fb8", anchor="middle"))

    names = list(result.counsels)
    for name, x in zip(names, cards_x):
        robe, dark, light, eye, emblem = VIS.get(name, ("#ccc", "#888", "#fff", "#fff", SUN))
        title = next((s.title for s in SISTERS if s.name == name), "")
        cx = x + card_w // 2

        # 타로 카드 프레임 (픽셀 테두리)
        svg.append(f'<rect x="{x}" y="{card_y}" width="{card_w}" height="{card_h}" fill="#cdbb8e"/>')
        svg.append(
            f'<rect x="{x + 6}" y="{card_y + 6}" width="{card_w - 12}" height="{card_h - 12}" fill="#14101f"/>'
        )
        # 후광
        svg.append(
            f'<rect x="{cx - 96}" y="{card_y + 60}" width="192" height="192" fill="{robe}" opacity="0.10"/>'
        )
        svg.append(
            f'<rect x="{cx - 66}" y="{card_y + 90}" width="132" height="132" fill="{eye}" opacity="0.08"/>'
        )
        # 아르카나 상징
        svg.append(_blit(emblem, {"X": "#f3c64b"}, cx - (7 * PX) // 2, card_y + 18, PX))
        # 여신 (거대)
        gpal = _goddess_palette(robe, dark, light, eye)
        svg.append(_blit(GODDESS, gpal, cx - 110, card_y + 70, 11))
        # 이름 띠
        svg.append(
            f'<rect x="{x + 6}" y="{card_y + card_h - 52}" width="{card_w - 12}" height="46" fill="#221a30"/>'
        )
        svg.append(_text(cx, card_y + card_h - 28, name, 22, robe, anchor="middle", weight=700))
        svg.append(_text(cx, card_y + card_h - 12, title, 12, "#9a8fb8", anchor="middle"))

    # 바닥 + 주인공(뒷모습, 작게)
    floor_y = card_y + card_h - 6
    svg.append(f'<rect x="0" y="{floor_y}" width="{W}" height="{box_y - floor_y}" fill="#0a0712"/>')
    hx = W // 2 - 24
    hy = floor_y + 7  # 카드 아래 바닥에 세움 (가운데 여신 가리지 않게)
    svg.append(f'<ellipse cx="{W // 2}" cy="{hy + 62}" rx="34" ry="7" fill="#000000" opacity="0.5"/>')
    hero_pal = {"o": "#0d0b14", "d": "#3a3350", "H": "#08070d", "h": "#211d36", "c": "#9b7bff"}
    svg.append(_blit(HERO, hero_pal, hx, hy, PX))

    # 운명의 말 (대화 상자)
    svg.append(f'<rect x="30" y="{box_y}" width="{W - 60}" height="{box_h}" fill="#cdbb8e"/>')
    svg.append(
        f'<rect x="{30 + 5}" y="{box_y + 5}" width="{W - 70}" height="{box_h - 10}" fill="#100b1c"/>'
    )
    svg.append(_text(50, box_y + 28, "▶ 운명이 말하다", 14, "#f0d27a", weight=700))
    for i, line in enumerate(synth_lines):
        svg.append(_text(50, box_y + 54 + i * 24, line, 15, "#e6dcc6"))

    svg.append("</svg>")
    return "\n".join(svg)


def _sample_result() -> CouncilResult:
    return CouncilResult(
        dilemma="지금 다니는 회사를 그만두고 창업할까?",
        counsels={
            "여명": "가장 큰 위험은 시도조차 않는 것이다.",
            "황혼": "돌아올 다리까지 태우지는 마라.",
            "잿불": "퇴사 전에 주말로 첫 매출 하나를 만들어 보라.",
        },
        synthesis=(
            "핵심은 '되돌릴 수 있는가'다. 이건 한 번의 도약이 아니라 작게 시험해 볼 수 있는 문제다. "
            "잿불의 '주말 실험'으로 위험을 줄인 뒤 결정하라. 다만 최종 선택은 그대의 몫이다."
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
