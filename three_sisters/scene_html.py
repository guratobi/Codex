"""평의회 장면 — AI로 만든 아트(PNG)를 배경으로 쓰고, 맨 아래 '운명이 말하다'
박스에만 실제 평의회 결과를 덧씌우는 HTML 합성기.

세 여신 아트는 고정, 종합 텍스트만 동적. 이미지가 아직 없으면(onerror) 어두운
배경에 텍스트만 보인다.

실행:  python -m three_sisters.scene_html   →  council.html
"""
from __future__ import annotations

import html
from pathlib import Path

from .council import CouncilResult
from .scene import _sample_result

# 레포 루트에서 council.html 을 열었을 때의 상대 경로
DEFAULT_IMAGE = "three_sisters/assets/council.png"

# '운명이 말하다' 박스 위에 덧씌울 오버레이 위치(이미지 대비 %). 실제 아트에 맞춰 미세조정.
OVERLAY = {"left": 4.0, "right": 4.0, "top": 85.0, "bottom": 2.0}


def _esc(s) -> str:
    return html.escape(str(s))


def render_council_html(result: CouncilResult, image: str = DEFAULT_IMAGE, mask: bool = True) -> str:
    """mask=True 면 베이크된 박스를 덮도록 불투명 배경, False 면(빈 박스 아트) 투명."""
    bg = "#0f0b1c" if mask else "transparent"
    border = "border:3px solid #b89a52;border-radius:6px;" if mask else ""
    o = OVERLAY
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>인공지능의 세자매</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&display=swap');
*{{box-sizing:border-box}}
body{{margin:0;background:#0b0814;display:flex;justify-content:center;align-items:flex-start}}
.scene{{position:relative;width:min(100vw,1000px)}}
.scene>img{{width:100%;display:block;image-rendering:pixelated}}
.fate{{position:absolute;left:{o['left']}%;right:{o['right']}%;top:{o['top']}%;bottom:{o['bottom']}%;
  background:{bg};{border}padding:14px 26px;overflow:auto;
  color:#e8dec8;font-family:'Gowun Batang','Nanum Myeongjo',serif}}
.fate h3{{margin:0 0 10px;color:#f0d27a;font-size:clamp(14px,1.9vw,19px);letter-spacing:1px}}
.fate p{{margin:5px 0;font-size:clamp(11px,1.55vw,16px);line-height:1.55}}
.fate .q{{color:#b3a9cd;font-style:italic}}
.fate .seal{{color:#8c84a6;font-size:clamp(10px,1.3vw,13px);margin-top:8px}}
</style></head>
<body><div class="scene">
<img src="{_esc(image)}" alt="인공지능의 세자매"
     onerror="this.style.display='none';document.querySelector('.fate').style.top='6%';">
<div class="fate">
<h3>◆ 운명이 말하다</h3>
<p class="q">“{_esc(result.dilemma)}”</p>
<p>{_esc(result.synthesis)}</p>
<p class="seal">— 최종 선택은 그대의 몫이다 —</p>
</div></div></body></html>"""


def write_council_html(
    result: CouncilResult | None = None,
    path: str = "council.html",
    image: str = DEFAULT_IMAGE,
    mask: bool = True,
) -> Path:
    p = Path(path)
    p.write_text(render_council_html(result or _sample_result(), image, mask), encoding="utf-8")
    return p


def main() -> None:
    out = write_council_html()
    print(f"장면 생성: {out.resolve()}  (이미지: {DEFAULT_IMAGE})")


if __name__ == "__main__":
    main()
