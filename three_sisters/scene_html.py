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

# '운명이 말하다' 박스 위 오버레이 위치(이미지 대비 %). 실제 아트에 맞춰 미세조정.
OVERLAY = {"left": 9.5, "right": 9.5, "top": 84.5, "bottom": 2.5}


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
.fate{position:absolute;padding:14px 26px;overflow:auto;color:#e8dec8;
  font-family:'Gowun Batang','Nanum Myeongjo',serif}
.fate h3{margin:0 0 10px;color:#f0d27a;font-size:clamp(14px,1.9vw,19px);letter-spacing:1px}
.fate p{margin:5px 0;font-size:clamp(11px,1.6vw,16px);line-height:1.55}
.fate .q{color:#b3a9cd;font-style:italic}
.fate .seal{color:#8c84a6;font-size:clamp(10px,1.3vw,13px);margin-top:8px}
</style></head><body><div class="scene">
"""

_FATE = """<div class="fate"{pos}>
<h3>◆ 운명이 말하다</h3>
<p class="q">“{dilemma}”</p>
<p>{synthesis}</p>
<p class="seal">— 최종 선택은 그대의 몫이다 —</p>
</div></div></body></html>"""


def render_council_html(result: CouncilResult, art: Path | None | bool = None) -> str:
    """art: Path=그 이미지 / None=assets 자동탐색 / False=강제 SVG 폴백."""
    if art is None:
        art = find_art()
    elif art is False:
        art = None

    if art and Path(art).is_file():
        # AI 아트 배경 + 하단 박스에 실제 결과 오버레이 (박스를 덮어 베이크된 글자 가림)
        o = OVERLAY
        pos = (
            f' style="left:{o["left"]}%;right:{o["right"]}%;top:{o["top"]}%;'
            f'bottom:{o["bottom"]}%;background:#0f0b1c;'
            'border:2px solid #b89a52;border-radius:6px"'
        )
        body = f'<img src="{_data_uri(Path(art))}" alt="인공지능의 세자매">\n'
    else:
        # 코드로 그린 SVG 장면(이미 실시간 텍스트 포함) — 별도 오버레이 불필요
        return _HEAD + render_scene(result) + "\n</div></body></html>"

    return _HEAD + body + _FATE.format(
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
