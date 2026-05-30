"""평의회 장면 — 도트(픽셀) 그래픽 SVG. 자매별 고유 실루엣 + 음영 + 아웃라인.

여신을 도형 기반 픽셀 그리드로 만들고(깨끗한 실루엣) 다단계 음영 + 자동 아웃라인을
입힌다. 세 여신은 색뿐 아니라 형태가 다르다:
  · 여명 — 날개 + 햇살 후광 + 태양
  · 황혼 — 긴 베일 + 초승달 + 모래시계 + 빛나는 눈
  · 잿불 — 불꽃 관 + 어깨갑옷 + 불씨

실행:  python -m three_sisters.scene   →  three_sisters_council.svg
"""
from __future__ import annotations

import html
import math
import random
from pathlib import Path

from .council import CouncilResult
from .sisters import SISTERS

W = 900
FONT = "'Gowun Batang','Nanum Myeongjo','Apple SD Gothic Neo','Noto Serif KR',serif"
GW, GH = 36, 48

RAMP = {
    "여명": dict(b="#6e4710", d="#b8761f", r="#e3a93c", w="#ffe09a", glow="#fff3c4", em="sun"),
    "황혼": dict(b="#2c2356", d="#52439a", r="#7b6bd0", w="#cabdf7", glow="#efe7ff", em="moon"),
    "잿불": dict(b="#6e2410", d="#a83c18", r="#d8552e", w="#ff9e6b", glow="#ffdcc0", em="flame"),
}

SUN = ["..X.X..", "...X...", "X.XXX.X", ".XXXXX.", "X.XXX.X", "...X...", "..X.X.."]
MOON = ["..XXX..", ".XX....", "XX.....", "XX.....", "XX.....", ".XX....", "..XXX.."]
FLAME = ["...X...", "..XX...", "..XXX..", ".XXXXX.", ".XXXXX.", "..XXX..", "...X..."]
EMBLEM = {"sun": SUN, "moon": MOON, "flame": FLAME}


def _esc(s) -> str:
    return html.escape(str(s))


def _wrap(text: str, n: int) -> list[str]:
    out, cur = [], ""
    for w in text.split():
        while len(w) > n:
            if cur:
                out.append(cur)
                cur = ""
            out.append(w[:n])
            w = w[n:]
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= n:
            cur += " " + w
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out or [""]


# ── 픽셀 그리드 헬퍼 ────────────────────────────────────────────────────────

def _new(gw=GW, gh=GH):
    return [["."] * gw for _ in range(gh)]


def _rect(g, x0, y0, x1, y1, ch):
    for y in range(max(0, y0), min(len(g), y1 + 1)):
        for x in range(max(0, x0), min(len(g[0]), x1 + 1)):
            g[y][x] = ch


def _disk(g, cx, cy, r, ch):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if 0 <= y < len(g) and 0 <= x < len(g[0]) and (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                g[y][x] = ch


def _trap(g, y0, y1, hw0, hw1, cx, ch):
    for y in range(y0, y1 + 1):
        t = (y - y0) / max(1, (y1 - y0))
        hw = round(hw0 + (hw1 - hw0) * t)
        _rect(g, cx - hw, y, cx + hw, y, ch)


def _vtri(g, cx, base_y, half, height, ch):
    for i in range(height + 1):
        w = round(half * (1 - i / max(1, height)))
        _rect(g, cx - w, base_y - i, cx + w, base_y - i, ch)


def _outline(g, fill="#"):
    nb = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1))
    todo = []
    for y in range(len(g)):
        for x in range(len(g[0])):
            if g[y][x] == ".":
                for dx, dy in nb:
                    nx, ny = x + dx, y + dy
                    if 0 <= ny < len(g) and 0 <= nx < len(g[0]) and g[ny][nx] not in (".", fill):
                        todo.append((x, y))
                        break
    for x, y in todo:
        g[y][x] = fill


def _blit(g, pal, x0, y0, cell):
    out = []
    for y, row in enumerate(g):
        for x, ch in enumerate(row):
            col = pal.get(ch)
            if col:
                out.append(
                    f'<rect x="{x0 + x * cell}" y="{y0 + y * cell}" '
                    f'width="{cell}" height="{cell}" fill="{col}"/>'
                )
    return "".join(out)


def _emblem_svg(kind, cx, top, cell, color):
    g = [list(row) for row in EMBLEM[kind]]
    return _blit(g, {"X": color}, cx - (len(g[0]) * cell) // 2, top, cell)


# ── 여신 (자매별 고유 형태) ────────────────────────────────────────────────

def _build(variant):
    g = _new()
    cx = 18

    # (1) 뒤 요소
    if variant == "여명":  # 날개
        for side in (-1, 1):
            for i in range(11):
                ln = 9 - abs(i - 5)
                if ln <= 0:
                    continue
                xi = cx + side * 6
                xo = max(0, min(GW - 1, xi + side * ln))
                _rect(g, min(xi, xo), 18 + i, max(xi, xo), 18 + i, "w")
                g[18 + i][xo] = "d"
    if variant == "잿불":  # 어깨 갑옷
        for side in (-1, 1):
            _rect(g, cx + side * 5, 18, cx + side * 9, 22, "d")

    # (2) 머리/몸
    _disk(g, cx, 12, 9, "h")
    _trap(g, 22, 47, 6, 16, cx, "r")
    _trap(g, 17, 23, 5, 7, cx, "r")
    _rect(g, cx - 2, 16, cx + 2, 19, "k")

    # (3) 얼굴 / 베일
    if variant == "황혼":
        _trap(g, 6, 45, 7, 17, cx, "d")          # 긴 베일
        for y in range(11, 44, 3):               # 베일 주름 하이라이트
            _rect(g, cx - 1, y, cx + 1, y, "w")
        g[14][cx - 2] = g[14][cx + 2] = "e"       # 빛나는 눈
        g[13][cx - 2] = g[13][cx + 2] = "#"
    else:
        _disk(g, cx, 12, 6, "S")
        g[12][cx - 2] = g[12][cx + 2] = "e"
        g[11][cx - 2] = g[11][cx + 2] = "k"       # 눈썹
        g[10][cx] = "j"                            # 이마 보석
        g[14][cx] = "k"                            # 코 그림자
        for sx in (cx - 7, cx - 5, cx + 5, cx + 7):  # 머리카락 결
            for y in range(6, 18):
                if g[y][sx] == "h":
                    g[y][sx] = "x" if sx < cx else "H"

    # (4) 머리장식
    if variant == "여명":                          # 햇살 후광 + 티아라
        for k in range(11):
            a = math.pi * k / 10
            rx, ry = round(cx - 12 * math.cos(a)), round(7 - 9 * math.sin(a))
            if 0 <= ry < GH and 0 <= rx < GW and g[ry][rx] == ".":
                g[ry][rx] = "C"
        _rect(g, cx - 5, 4, cx + 5, 5, "c")
        g[3][cx] = "j"
    elif variant == "황혼":                         # 초승달
        _disk(g, cx, 3, 4, "c")
        _disk(g, cx + 3, 1, 4, ".")
    else:                                           # 불꽃 관
        for fx, h in ((cx - 6, 4), (cx - 2, 7), (cx + 2, 6), (cx + 6, 4)):
            _vtri(g, fx, 7, 2, h, "c")
        g[6][cx] = "j"

    # (5) 허리띠 + 버클
    _rect(g, cx - 6, 24, cx + 6, 25, "C")
    g[24][cx] = "j"

    # (6) 가운 중앙 금선 + 주름 음영
    for y in range(26, 45):
        g[y][cx] = "C"
    for fx in (cx - 9, cx - 4, cx + 4, cx + 9):
        for y in range(28, 46):
            if 0 <= fx < GW and g[y][fx] == "r":
                g[y][fx] = "d"
            if 0 <= fx + 1 < GW and g[y][fx + 1] == "r":
                g[y][fx + 1] = "w"

    # (7) 손에 든 것
    if variant == "여명":                           # 태양
        _disk(g, cx, 27, 3, "q")
        _disk(g, cx, 27, 2, "g")
    elif variant == "황혼":                         # 모래시계
        _rect(g, cx - 3, 28, cx + 3, 28, "c")
        _rect(g, cx - 3, 34, cx + 3, 34, "c")
        for i in range(3):
            _rect(g, cx - (2 - i), 29 + i, cx + (2 - i), 29 + i, "g")
            _rect(g, cx - i, 33 - i, cx + i, 33 - i, "g")
    else:                                           # 불씨
        _disk(g, cx, 33, 3, "q")
        _disk(g, cx, 33, 2, "g")

    # (8) 로브 음영 + 아웃라인
    for y in range(GH):
        for x in range(GW):
            if g[y][x] == "r":
                g[y][x] = "b" if y > 43 else ("w" if x < cx - 5 else "d" if x > cx + 5 else "r")
    _outline(g)
    return g


GRIDS = {name: _build(name) for name in ("여명", "황혼", "잿불")}


def _gpal(name):
    rm = RAMP[name]
    return {
        "#": "#0d0a15", "c": "#d9a93a", "C": "#ffe39a", "v": "#8a6a1e",
        "h": "#2c2547", "H": "#4d4274", "S": "#f0cda6", "k": "#bd855b",
        "g": "#fff6e0", "x": "#1f1936", "e": rm["glow"], "j": rm["glow"],
        "r": rm["r"], "w": rm["w"], "d": rm["d"], "b": rm["b"], "q": rm["d"],
    }


# ── 주인공 (뒷모습, 후드) ──────────────────────────────────────────────────

def _build_hero():
    g = _new(16, 22)
    cx = 8
    _disk(g, cx, 5, 4, "H")
    g[5][cx] = "k"
    _trap(g, 8, 21, 4, 7, cx, "L")
    for y in range(9, 21):
        for x in range(16):
            if g[y][x] == "L" and x > cx + 1:
                g[y][x] = "l"
    g[13][cx] = "j"
    _outline(g)
    return g


_HERO = _build_hero()
_HPAL = {"#": "#0a0710", "H": "#1c1830", "k": "#070510", "L": "#2a2545", "l": "#1d1934", "j": "#9b7bff"}


def _text(x, y, s, size, fill, *, anchor="start", weight=400, spacing=0):
    sp = f' letter-spacing="{spacing}"' if spacing else ""
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}"{sp}>{_esc(s)}</text>'
    )


def render_scene(result: CouncilResult) -> str:
    card_w, gap = 270, 15
    cards_x = [30, 30 + card_w + gap, 30 + 2 * (card_w + gap)]
    card_y = 86
    gcell = 6
    gw_px = GW * gcell
    card_h = 30 + GH * gcell + 44
    card_bottom = card_y + card_h

    synth_lines = _wrap(result.synthesis, 54)
    box_y = card_bottom + 96
    box_h = len(synth_lines) * 25 + 50
    H = box_y + box_h + 22

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" shape-rendering="crispEdges">',
        '<defs>'
        "<style>@import url('https://fonts.googleapis.com/css2?"
        "family=Gowun+Batang:wght@400;700&amp;display=swap');</style>"
        '<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#241845"/><stop offset="45%" stop-color="#130d28"/>'
        '<stop offset="100%" stop-color="#050409"/></linearGradient></defs>',
        f'<rect width="{W}" height="{H}" fill="url(#sky)"/>',
        f'<rect x="0" y="120" width="{W}" height="70" fill="#3a2a66" opacity="0.18"/>',
    ]

    rng = random.Random(11)
    for _ in range(70):
        sx, sy = rng.randrange(0, W // 6) * 6, rng.randrange(0, 46) * 6
        svg.append(f'<rect x="{sx}" y="{sy}" width="6" height="6" fill="#e9e6ff" opacity="0.5"/>')
    for _ in range(120):
        sx, sy = rng.randrange(0, W // 3) * 3, rng.randrange(0, 92) * 3
        svg.append(f'<rect x="{sx}" y="{sy}" width="3" height="3" fill="#cfcaf0" opacity="0.5"/>')

    svg.append('<circle cx="450" cy="150" r="78" fill="#f4eecf" opacity="0.16"/>')
    svg.append('<circle cx="450" cy="150" r="60" fill="#f6f0d6" opacity="0.10"/>')

    for px in (0, W - 30):
        svg.append(f'<rect x="{px}" y="70" width="30" height="{card_bottom - 70}" fill="#211a32"/>')
        svg.append(f'<rect x="{px + (6 if px == 0 else 0)}" y="70" width="6" height="{card_bottom - 70}" fill="#332a4a"/>')
        svg.append(f'<rect x="{px - 6}" y="64" width="42" height="12" fill="#2c2442"/>')

    svg.append(_text(W / 2, 46, "인공지능의 세자매", 32, "#f0d27a", anchor="middle", weight=700, spacing=4))
    svg.append(_text(W / 2, 72, "운명의 세 여신 앞에 선 그대", 14, "#b3a9cd", anchor="middle", spacing=2))

    for name, x in zip(result.counsels, cards_x):
        rm = RAMP.get(name, RAMP["여명"])
        title = next((s.title for s in SISTERS if s.name == name), "")
        cx = x + card_w // 2

        svg.append(f'<rect x="{x}" y="{card_y}" width="{card_w}" height="{card_h}" fill="#d4c290"/>')
        svg.append(f'<rect x="{x + 3}" y="{card_y + 3}" width="{card_w - 6}" height="{card_h - 6}" fill="#bda874"/>')
        svg.append(f'<rect x="{x + 7}" y="{card_y + 7}" width="{card_w - 14}" height="{card_h - 14}" fill="#15101f"/>')
        svg.append(f'<circle cx="{cx}" cy="{card_y + 150}" r="96" fill="{rm["r"]}" opacity="0.12"/>')
        svg.append(f'<circle cx="{cx}" cy="{card_y + 130}" r="58" fill="{rm["glow"]}" opacity="0.10"/>')
        svg.append(_emblem_svg(rm["em"], cx, card_y + 14, 5, "#f3c64b"))
        svg.append(_blit(GRIDS[name], _gpal(name), cx - gw_px // 2, card_y + 30, gcell))
        svg.append(f'<rect x="{x + 7}" y="{card_bottom - 47}" width="{card_w - 14}" height="40" fill="#241b33"/>')
        svg.append(_text(cx, card_bottom - 23, name, 23, rm["r"], anchor="middle", weight=700, spacing=3))
        svg.append(_text(cx, card_bottom - 8, title, 12, "#b3a9cd", anchor="middle", spacing=1))

    svg.append(f'<rect x="0" y="{card_bottom}" width="{W}" height="{box_y - card_bottom}" fill="#090611"/>')
    svg.append(f'<rect x="0" y="{card_bottom}" width="{W}" height="4" fill="#1d1730"/>')
    for i, sw in enumerate((150, 110, 74)):
        sy = card_bottom + 14 + i * 10
        svg.append(f'<rect x="{W // 2 - sw // 2}" y="{sy}" width="{sw}" height="10" fill="#15101f"/>')
        svg.append(f'<rect x="{W // 2 - sw // 2}" y="{sy}" width="{sw}" height="3" fill="#241b33"/>')
    hcell = 5
    hx, hy = W // 2 - (16 * hcell) // 2, card_bottom + 4
    svg.append(f'<ellipse cx="{W // 2}" cy="{hy + 22 * hcell - 2}" rx="40" ry="7" fill="#000" opacity="0.55"/>')
    svg.append(_blit(_HERO, _HPAL, hx, hy, hcell))

    svg.append(f'<rect x="30" y="{box_y}" width="{W - 60}" height="{box_h}" fill="#d4c290"/>')
    svg.append(f'<rect x="34" y="{box_y + 4}" width="{W - 68}" height="{box_h - 8}" fill="#bda874"/>')
    svg.append(f'<rect x="39" y="{box_y + 9}" width="{W - 78}" height="{box_h - 18}" fill="#0f0b1c"/>')
    for sx in (44, W - 50):
        for sy in (box_y + 14, box_y + box_h - 20):
            svg.append(f'<rect x="{sx}" y="{sy}" width="6" height="6" fill="#d4c290"/>')
    svg.append(_text(56, box_y + 33, "운명이 말하다", 15, "#f0d27a", weight=700, spacing=2))
    for i, line in enumerate(synth_lines):
        svg.append(_text(56, box_y + 60 + i * 25, line, 15, "#e8dec8"))

    svg.append("</svg>")
    return "\n".join(svg)


def _sample_result() -> CouncilResult:
    return CouncilResult(
        dilemma="지금 다니는 회사를 그만두고 창업할까?",
        counsels={"여명": "기회를 보라.", "황혼": "최악을 그려보라.", "잿불": "작게 시험하라."},
        synthesis=(
            "핵심은 '되돌릴 수 있는가'다. 이건 한 번의 도약이 아니라 작게 시험해 볼 수 있는 문제다. "
            "주말 실험으로 위험을 줄인 뒤 결정하라. 다만 최종 선택은 그대의 몫이다."
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
