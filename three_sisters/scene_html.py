"""평의회 장면 HTML 합성기.

three_sisters/assets/ 에 장면 아트(council.png 등 아무 이미지)가 있으면 그것을
배경으로 쓰고, 맨 아래 '운명이 말하다' 박스에만 실제 평의회 결과를 덧씌운다.
이미지가 없으면 코드로 그린 SVG 장면(scene.render_scene)을 자동 폴백으로 깐다.

→ 이미지를 assets/ 에 떨어뜨리는 순간(파일명 무관) 알아서 그 아트로 바뀐다.

실행:  python -m three_sisters.scene_html   →  council.html
"""
from __future__ import annotations

import base64
import html
import mimetypes
from pathlib import Path

from .council import CouncilResult
from .scene import _sample_result, render_scene

ASSETS = Path(__file__).resolve().parent / "assets"
_PREFERRED = ["council.png", "council.jpg", "council.jpeg", "council.webp", "council.gif"]
_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# '운명이 말하다' 박스에서 *본문 영역만* 덮는 위치(이미지 대비 %).
# council.png 를 픽셀 분석해 보정: 금색 헤더("◆ 운명이 말하다")는 아트 그대로
# 두고, 그 아래 본문 두 줄 자리에만 실제 종합을 얹는다.
# 다른 아트로 바꾸면 이 값만 다시 맞추면 된다.
OVERLAY = {"left": 11.0, "right": 11.5, "top": 88.2, "bottom": 4.3}
# 박스 내부 배경색(아트에서 샘플링) — 오버레이가 그림에 녹아들게.
OVERLAY_BG = "#11101d"


def _esc(s) -> str:
    return html.escape(str(s))


def find_art(assets: Path = ASSETS) -> Path | None:
    """assets/ 에서 장면 이미지를 찾는다. council.* 우선, 없으면 아무 이미지나."""
    if not assets.is_dir():
        return None
    for name in _PREFERRED:
        p = assets / name
        if p.is_file():
            return p
    imgs = sorted(p for p in assets.iterdir() if p.suffix.lower() in _EXTS)
    return imgs[0] if imgs else None


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


_HEAD = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>인공지능의 세자매</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&display=swap');
*{box-sizing:border-box}
body{margin:0;background:#0b0814;display:flex;justify-content:center;align-items:flex-start}
.scene{position:relative;width:min(100vw,1000px)}
.scene>img,.scene>svg{width:100%;height:auto;display:block;image-rendering:pixelated}
.fate{position:absolute;overflow:hidden;color:#e8dec8;
  display:flex;flex-direction:column;justify-content:center;
  padding:6px 28px;font-family:'Gowun Batang','Nanum Myeongjo',serif}
.fate p{margin:3px 0;font-size:clamp(11px,1.62vw,17px);line-height:1.5}
.fate .q{color:#b3a9cd;font-style:italic;font-size:clamp(10px,1.4vw,15px)}
</style></head><body><div class="scene">
"""

# 아트의 금색 헤더("◆ 운명이 말하다")와 하단 봉인 문구는 그대로 두고,
# 본문 영역에만 실제 종합을 얹는다.
_FATE_BODY = """<div class="fate"{pos}>
<p class="q">“{dilemma}”</p>
<p>{synthesis}</p>
</div></div></body></html>"""


def render_council_html(result: CouncilResult, art: Path | None | bool = None) -> str:
    """art: Path=그 이미지 / None=assets 자동탐색 / False=강제 SVG 폴백."""
    if art is None:
        art = find_art()
    elif art is False:
        art = None

    if art and Path(art).is_file():
        # AI 아트 배경 + 박스 본문 영역에 실제 결과 오버레이.
        # 아트의 금테/헤더 안에 딱 맞추므로 테두리 없이 내부 배경색만 맞춘다.
        o = OVERLAY
        pos = (
            f' style="left:{o["left"]}%;right:{o["right"]}%;top:{o["top"]}%;'
            f'bottom:{o["bottom"]}%;background:{OVERLAY_BG}"'
        )
        body = f'<img src="{_data_uri(Path(art))}" alt="인공지능의 세자매">\n'
    else:
        # 코드로 그린 SVG 장면(이미 실시간 텍스트 포함) — 별도 오버레이 불필요
        return _HEAD + render_scene(result) + "\n</div></body></html>"

    return _HEAD + body + _FATE_BODY.format(
        pos=pos, dilemma=_esc(result.dilemma), synthesis=_esc(result.synthesis)
    )


def write_council_html(
    result: CouncilResult | None = None,
    path: str = "council.html",
    art: Path | None | bool = None,
) -> Path:
    p = Path(path)
    p.write_text(render_council_html(result or _sample_result(), art), encoding="utf-8")
    return p


def main() -> None:
    out = write_council_html()
    art = find_art()
    src = f"아트: {art.name}" if art else "아트 없음 → SVG 폴백 (assets/ 에 이미지를 넣으면 자동 적용)"
    print(f"장면 생성: {out.resolve()}  ({src})")


if __name__ == "__main__":
    main()
