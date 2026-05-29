"""에이전트 팀 관제 대시보드 — 실행 결과를 자기완결 HTML 한 장으로 그린다.

외부 라이브러리/폰트/스크립트 없이 인라인 CSS 만 쓴다. 브라우저로 바로 열림.

실행:  python -m agent_team.dashboard   →  agent_team_dashboard.html 생성
"""
from __future__ import annotations

import html
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .agents import build_user_message
from .drift import DriftReport, ROLE_MARKERS, diagnose
from .journal import Journal, JournalEntry
from .llm import DriftingMockLLM, Message, get_llm
from .team import Team, TeamResult

VERDICT_COLOR = {"안정": "#2ea043", "주의": "#d29922", "이탈": "#f85149"}


@dataclass
class DashboardData:
    task: str
    run1: TeamResult
    run2: TeamResult
    wisdom: list[str]
    entries: list[JournalEntry]
    drift_timeline: list[DriftReport]


def build_demo_data(task: str = "주간 팀 뉴스레터 작성") -> DashboardData:
    # 건강한 팀: 같은 작업을 두 번 → 지혜 누적이 보이게
    with tempfile.TemporaryDirectory() as d:
        journal = Journal(Path(d) / "j.jsonl")
        team = Team(get_llm(), journal)
        run1 = team.run(task)
        run2 = team.run(task)
        wisdom = journal.wisdom()
        entries = journal.all_entries()

    # 스트레스 시나리오: 실행가 역할이 점점 드리프트 → 진단기가 잡아냄
    drifting = DriftingMockLLM()
    msg = build_user_message(task, ["요지를 앞에", "톤은 사람 확정"], prior="")
    timeline: list[DriftReport] = []
    for _ in range(4):
        out = drifting.complete("[ROLE:worker] 실행가", [Message("user", msg)])
        timeline.append(
            diagnose("실행가", task, out, lessons_available=2, expect_markers=ROLE_MARKERS["실행가"])
        )

    return DashboardData(task, run1, run2, wisdom, entries, timeline)


def _esc(s) -> str:
    return html.escape(str(s))


def _first_line(text: str) -> str:
    return text.strip().splitlines()[0] if text.strip() else ""


def _pipeline_card(data: DashboardData) -> str:
    r = data.run2
    cols = []
    for emoji, res in (("🧭", r.plan), ("🛠", r.draft), ("🔎", r.review)):
        cols.append(
            f'<div class="pcol"><div class="ptitle">{emoji} {_esc(res.entry.agent)}</div>'
            f'<div class="pbody">{_esc(_first_line(res.output))}</div></div>'
        )
    return (
        '<section class="card"><h2>🤝 팀 파이프라인</h2>'
        '<div class="pipeline">' + '<div class="arrow">→</div>'.join(cols) + "</div></section>"
    )


def _wisdom_card(data: DashboardData) -> str:
    a1, a2 = data.run1.lessons_applied, data.run2.lessons_applied
    scale = max(a1, a2, 1)
    rows = ""
    for label, val in (("1차 실행", a1), ("2차 실행", a2)):
        pct = int(val / scale * 100)
        rows += (
            f'<div class="bar-row"><span class="bar-label">{label}</span>'
            f'<div class="track"><div class="fill grow" style="width:{pct}%"></div></div>'
            f'<span class="bar-val">{val}건</span></div>'
        )
    items = "".join(f"<li>{_esc(w)}</li>" for w in data.wisdom) or "<li>(아직 없음)</li>"
    return (
        '<section class="card"><h2>📈 지혜 누적 (적용한 과거 교훈)</h2>'
        f"{rows}"
        f'<div class="sub">누적된 지혜</div><ul class="wisdom">{items}</ul></section>'
    )


def _drift_card(data: DashboardData) -> str:
    rows = ""
    for i, rep in enumerate(data.drift_timeline):
        color = VERDICT_COLOR.get(rep.verdict, "#888")
        note = _esc(" · ".join(rep.notes))
        rows += (
            '<div class="drift-row">'
            f'<span class="step">단계 {i}</span>'
            f'<div class="track"><div class="fill" style="width:{rep.score}%;background:{color}"></div></div>'
            f'<span class="score">{rep.score}</span>'
            f'<span class="badge" style="background:{color}">{_esc(rep.verdict)}</span>'
            f'<div class="note">{note}</div>'
            "</div>"
        )
    return (
        '<section class="card"><h2>🧠 드리프트 진단 (실행가 스트레스 테스트)</h2>'
        '<p class="sub">호출이 거듭될수록 주제·교훈·규약에서 이탈 → 진단기가 점수로 포착</p>'
        f"{rows}</section>"
    )


def _human_card(data: DashboardData) -> str:
    items = "".join(f"<li>{_esc(h)}</li>" for h in data.run2.human_decisions) or "<li>(없음)</li>"
    return f'<section class="card"><h2>🧑 사람 결정 대기열</h2><ul>{items}</ul></section>'


def _journal_card(data: DashboardData) -> str:
    rows = ""
    for e in data.entries:
        rows += (
            '<div class="jrow">'
            f'<span class="jagent">{_esc(e.agent)}</span>'
            f'<span class="jdid">{_esc(e.did)}</span>'
            f'<span class="jlesson">💡 {_esc(e.lesson)}</span>'
            "</div>"
        )
    return f'<section class="card"><h2>📓 공용 일지 ({len(data.entries)}건)</h2>{rows}</section>'


_CSS = """
*{box-sizing:border-box}body{margin:0;background:#0d1117;color:#e6edf3;
font-family:-apple-system,'Segoe UI',Roboto,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;
line-height:1.5}.wrap{max-width:860px;margin:0 auto;padding:28px 20px 56px}
header h1{margin:0 0 4px;font-size:24px}header .meta{color:#7d8590;font-size:13px}
.card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:18px 20px;margin-top:18px}
.card h2{margin:0 0 12px;font-size:16px}.sub{color:#7d8590;font-size:13px;margin:8px 0}
.pipeline{display:flex;align-items:stretch;gap:8px}.pcol{flex:1;background:#0d1117;border:1px solid #30363d;
border-radius:10px;padding:12px}.ptitle{font-weight:600;margin-bottom:6px}.pbody{color:#adbac7;font-size:13px}
.arrow{display:flex;align-items:center;color:#7d8590;font-size:20px}
.bar-row{display:flex;align-items:center;gap:10px;margin:8px 0}.bar-label{width:64px;color:#adbac7;font-size:13px}
.bar-val{width:40px;text-align:right;color:#adbac7;font-size:13px}
.track{flex:1;height:14px;background:#21262d;border-radius:8px;overflow:hidden}
.fill{height:100%;border-radius:8px;background:#388bfd;transition:width .6s}.fill.grow{background:#2ea043}
.wisdom{margin:6px 0 0;padding-left:20px}.wisdom li{margin:3px 0;color:#adbac7;font-size:13px}
.drift-row{display:grid;grid-template-columns:60px 1fr 34px 52px;align-items:center;gap:10px;margin:10px 0}
.drift-row .note{grid-column:1/-1;color:#7d8590;font-size:12px;margin-top:-2px}
.step{color:#adbac7;font-size:13px}.score{text-align:right;font-variant-numeric:tabular-nums}
.badge{color:#0d1117;font-weight:700;font-size:12px;text-align:center;border-radius:6px;padding:2px 0}
.jrow{display:grid;grid-template-columns:64px 1fr;gap:8px;padding:7px 0;border-top:1px solid #21262d;font-size:13px}
.jrow:first-of-type{border-top:none}.jagent{color:#388bfd}.jdid{color:#e6edf3}
.jlesson{grid-column:2;color:#7d8590}
"""


def render_html(data: DashboardData) -> str:
    ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    body = (
        _pipeline_card(data)
        + _wisdom_card(data)
        + _drift_card(data)
        + _human_card(data)
        + _journal_card(data)
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>에이전트 팀 관제 대시보드</title><style>{_CSS}</style></head>"
        '<body><div class="wrap"><header>'
        "<h1>🛰 AI 에이전트 팀 — 관제 대시보드</h1>"
        f'<div class="meta">작업: {_esc(data.task)} · 생성 {ts} · '
        "데이터: MockLLM(데모)</div></header>"
        f"{body}</div></body></html>"
    )


def write_dashboard(path: str | Path = "agent_team_dashboard.html") -> Path:
    p = Path(path)
    p.write_text(render_html(build_demo_data()), encoding="utf-8")
    return p


# --- SVG 버전 (의존성 없이 이미지로 미리보기 가능) ---------------------------

def _svg_bar(x: int, y: int, w: int, h: int, pct: float, color: str) -> str:
    fillw = int(w * max(0, min(pct, 100)) / 100)
    r = h // 2
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="#21262d"/>'
        f'<rect x="{x}" y="{y}" width="{fillw}" height="{h}" rx="{r}" fill="{color}"/>'
    )


def render_svg(data: DashboardData) -> str:
    W = 760
    rows = data.drift_timeline
    H = 274 + 30 * len(rows)
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="-apple-system,Segoe UI,Roboto,sans-serif">',
        f'<rect width="{W}" height="{H}" fill="#0d1117"/>',
        '<text x="24" y="40" fill="#e6edf3" font-size="22" font-weight="700">'
        'AI 에이전트 팀 — 관제 대시보드</text>',
        f'<text x="24" y="62" fill="#7d8590" font-size="12">'
        f'작업: {_esc(data.task)} · 데모(MockLLM)</text>',
    ]

    y = 100
    p.append(
        f'<text x="24" y="{y}" fill="#e6edf3" font-size="15" font-weight="600">'
        '지혜 누적 (적용한 과거 교훈)</text>'
    )
    a1, a2 = data.run1.lessons_applied, data.run2.lessons_applied
    scale = max(a1, a2, 1)
    for label, val in (("1차", a1), ("2차", a2)):
        y += 28
        p.append(f'<text x="24" y="{y + 13}" fill="#adbac7" font-size="13">{label}</text>')
        p.append(_svg_bar(70, y, 560, 16, val / scale * 100, "#2ea043"))
        p.append(f'<text x="642" y="{y + 13}" fill="#adbac7" font-size="13">{val}건</text>')

    y += 44
    p.append(
        f'<text x="24" y="{y}" fill="#e6edf3" font-size="15" font-weight="600">'
        '드리프트 진단 (실행가 스트레스 테스트)</text>'
    )
    for i, rep in enumerate(rows):
        y += 30
        color = VERDICT_COLOR.get(rep.verdict, "#888")
        p.append(f'<text x="24" y="{y + 12}" fill="#adbac7" font-size="13">단계 {i}</text>')
        p.append(_svg_bar(90, y, 460, 16, rep.score, color))
        p.append(f'<text x="560" y="{y + 13}" fill="#e6edf3" font-size="13">{rep.score}</text>')
        p.append(f'<rect x="600" y="{y}" width="64" height="16" rx="4" fill="{color}"/>')
        p.append(
            f'<text x="632" y="{y + 12}" fill="#0d1117" font-size="11" font-weight="700" '
            f'text-anchor="middle">{_esc(rep.verdict)}</text>'
        )

    y += 40
    p.append(
        f'<text x="24" y="{y}" fill="#7d8590" font-size="12">'
        f'누적 지혜 {len(data.wisdom)}건 · 공용 일지 {len(data.entries)}건</text>'
    )
    p.append("</svg>")
    return "\n".join(p)


def write_dashboard_svg(path: str | Path = "agent_team_dashboard.svg") -> Path:
    p = Path(path)
    p.write_text(render_svg(build_demo_data()), encoding="utf-8")
    return p


if __name__ == "__main__":
    data = build_demo_data()
    html_path = Path("agent_team_dashboard.html")
    svg_path = Path("agent_team_dashboard.svg")
    html_path.write_text(render_html(data), encoding="utf-8")
    svg_path.write_text(render_svg(data), encoding="utf-8")
    print(f"대시보드 생성: {html_path.resolve()}")
    print(f"             {svg_path.resolve()}")
