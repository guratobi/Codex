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
import json
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


# ── 인터랙티브 버전: 브라우저에서 직접 고민을 입력 → 세 자매가 답 ──────────
# 서버 없이 클라이언트(JS)에서 목(mock) 두뇌로 응답. 아트의 하단 박스는 통째로
# 다시 그려 겹침을 없애고, 세 자매의 답은 그림 아래 넉넉한 패널에 크게 보여준다.

_INTERACTIVE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>인공지능의 세자매</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&display=swap');
*{box-sizing:border-box}
body{margin:0;background:#0b0814;color:#e8dec8;
 font-family:'Gowun Batang','Nanum Myeongjo','Apple SD Gothic Neo',serif;
 display:flex;flex-direction:column;align-items:center;padding:0 0 48px}
.scene{position:relative;width:min(100vw,1000px)}
.scene>img{width:100%;display:block;image-rendering:pixelated}
.fate{position:absolute;left:9.3%;right:9.3%;top:81.8%;bottom:3.3%;
 background:#12101f;border:2px solid #b89a52;border-radius:6px;padding:10px 26px;
 display:flex;flex-direction:column;justify-content:center;overflow:auto}
.fate h3{margin:0 0 6px;color:#f0d27a;font-size:clamp(13px,1.7vw,18px);letter-spacing:1px}
.fate p{margin:0;color:#f3ead4;font-size:clamp(12px,1.8vw,18px);line-height:1.5}
.ask{width:min(94vw,1000px);display:flex;gap:8px;margin-top:18px}
.ask input{flex:1;padding:13px 15px;background:#14111f;border:2px solid #4a3f6e;
 border-radius:10px;color:#f3ead4;font-family:inherit;font-size:16px}
.ask button{padding:13px 22px;background:linear-gradient(#d3ab50,#9f7c2c);border:0;
 border-radius:10px;color:#1a1208;font-family:inherit;font-weight:700;font-size:16px;cursor:pointer}
.sisters{width:min(94vw,1000px);display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:16px}
.sis{background:#12101f;border:1px solid #2a2342;border-top:4px solid var(--c);border-radius:10px;padding:14px 16px}
.sis h4{margin:0 0 8px;color:var(--c);font-size:16px}
.sis p{margin:0;font-size:15px;line-height:1.6;color:#ddd3bf}
.hint{color:#8c84a6;font-size:13px;margin-top:16px;max-width:min(94vw,1000px);text-align:center;line-height:1.6}
.hint b{color:#cdbff0;font-weight:700}
.recall{color:#9b86d6;font-size:13px;margin-top:12px;max-width:min(94vw,1000px);text-align:center;line-height:1.5}
.ask button[disabled]{opacity:.6;cursor:default}
@media(max-width:620px){.sisters{grid-template-columns:1fr}}
</style></head><body>
<div class="scene">
<img src="__ART__" alt="인공지능의 세자매">
<div class="fate"><h3>◆ 운명이 말하다</h3><p id="synth"></p></div>
</div>
<form class="ask" onsubmit="return ask(event)">
<input id="q" autocomplete="off" placeholder="그대의 고민을 말하라…">
<button id="go">평의회에 묻다</button>
</form>
<div id="recall" class="recall"></div>
<div class="sisters">
<div class="sis" style="--c:#e0a23a"><h4>여명 · 낙관의 자매</h4><p id="dawn"></p></div>
<div class="sis" style="--c:#9d8cdf"><h4>황혼 · 경계의 자매</h4><p id="dusk"></p></div>
<div class="sis" style="--c:#e0693f"><h4>잿불 · 실리의 자매</h4><p id="ember"></p></div>
</div>
<div class="hint"><b id="brain">목(mock) 두뇌</b> · 입력하면 세 자매가 답한다. 로컬 서버로 띄우면 진짜 Claude가 추론한다.</div>
<script>
// 백엔드(/api/ask)를 먼저 부르고, 없으면(예: 정적 호스팅) 클라이언트 목으로 폴백.
function council(d){d=(d||'').trim()||'그 고민';return{
dawn:"'"+d+"' — 이건 기회다. 잘 풀렸을 때 얻을 것을 보라. 망설임이 가장 큰 손해일 수 있다.",
dusk:"'"+d+"' — 잠깐, 최악을 그려보자. 무엇을 잃을 수 있고, 이 선택은 되돌릴 수 있는가?",
ember:"'"+d+"' — 감정을 걷고 비용과 실행을 재자. 지금 할 수 있는 가장 작은 첫 걸음은 무엇인가?",
synth:"핵심은 '되돌릴 수 있는가'다. 되돌릴 수 있다면 작게 시험하고, 없다면 더 신중하라. 다만 최종 선택은 그대의 몫이다."};}
function el(id){return document.getElementById(id);}
function setBrain(b){el('brain').textContent=(b==='claude')?'🔮 진짜 Claude 연결됨':'목(mock) 두뇌';}
function setBusy(b){var g=el('go');g.disabled=b;g.textContent=b?'세 자매가 숙고 중…':'평의회에 묻다';
 if(b){el('synth').textContent='세 자매가 그대의 고민을 숙고하고 있다…';el('dawn').textContent=el('dusk').textContent=el('ember').textContent='…';}}
function render(r){el('synth').textContent=r.synth;el('dawn').textContent=r.dawn;el('dusk').textContent=r.dusk;el('ember').textContent=r.ember;
 var rc=el('recall');rc.textContent=(r.recalled&&r.recalled.length)?('지난 결정을 기억함 — '+r.recalled.map(function(x){return '“'+x.dilemma+'” → '+x.choice;}).join('  ·  ')):'';}
async function ask(e){e.preventDefault();var d=(el('q').value||'').trim();if(!d)return false;setBusy(true);
 try{var res=await fetch('api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dilemma:d})});
  if(!res.ok)throw new Error('http '+res.status);var r=await res.json();render(r);setBrain(r.brain||'claude');}
 catch(err){render(council(d));setBrain('mock');}
 finally{setBusy(false);}return false;}
el('q').value=__DILEMMA__;render(council(el('q').value));            // 초기엔 네트워크 없이 샘플만 표시
fetch('api/health').then(function(r){return r.ok?r.json():null;}).then(function(h){if(h)setBrain(h.brain);}).catch(function(){});
</script>
</body></html>"""


def render_interactive_html(result: CouncilResult | None = None, art: Path | None | bool = None) -> str:
    """브라우저에서 직접 고민을 입력하는 인터랙티브 페이지(클라이언트 목 두뇌)."""
    result = result or _sample_result()
    if art is None:
        art = find_art()
    elif art is False:
        art = None
    src = _data_uri(Path(art)) if (art and Path(art).is_file()) else ""
    return _INTERACTIVE.replace("__ART__", src).replace("__DILEMMA__", json.dumps(result.dilemma, ensure_ascii=False))


def write_interactive_html(
    result: CouncilResult | None = None,
    path: str = "docs/index.html",
    art: Path | None | bool = None,
) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_interactive_html(result, art), encoding="utf-8")
    return p


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
