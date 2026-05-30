"""드리프트 진단 — 에이전트가 '정신줄을 놓는' 정도를 점수화한다.

영상 4번 아이디어("AI의 정신적 상태(드리프트)를 진단하는 직업군")의 최소 구현.
세 가지 신호를 보고 0(건강)~100(심각) 점수와 판정을 낸다. 결정적이며 외부 호출 없음.

  - off_topic        : 작업 키워드가 출력에서 사라진 정도 (주제 이탈)
  - lesson_neglect   : 회상한 교훈이 있는데도 반영하지 않은 정도
  - convention_break : 역할이 지켜야 할 표식(예: 검토자의 사람-결정 표시)을 빠뜨린 정도
"""
from __future__ import annotations

from dataclasses import dataclass

from .journal import derive_tags

# 합성 가중치 (합 = 1.0)
W_OFF_TOPIC = 0.4
W_LESSON = 0.3
W_CONVENTION = 0.3

# 판정 임계값
STABLE_BELOW = 25     # < 25  : 안정
CAUTION_BELOW = 55    # < 55  : 주의, 그 이상: 이탈

# 역할(title) → 출력에 있어야 할 표식
ROLE_MARKERS = {
    "기획자": ("단계",),
    "실행가": ("초안",),
    "검토자": ("🧑",),
}


@dataclass
class DriftSignals:
    off_topic: float        # 0~1
    lesson_neglect: float   # 0~1
    convention_break: float # 0~1


@dataclass
class DriftReport:
    agent: str
    score: int              # 0~100
    verdict: str            # "안정"/"주의"/"이탈"
    signals: DriftSignals
    notes: list[str]


def _verdict(score: int) -> str:
    if score < STABLE_BELOW:
        return "안정"
    if score < CAUTION_BELOW:
        return "주의"
    return "이탈"


def diagnose(
    agent: str,
    task: str,
    output: str,
    *,
    lessons_available: int = 0,
    expect_markers: tuple[str, ...] = (),
) -> DriftReport:
    tags = derive_tags(task)
    present = sum(1 for t in tags if t in output)
    off_topic = 1.0 - present / len(tags) if tags else 0.0

    if lessons_available > 0:
        lesson_neglect = 0.0 if "교훈" in output else 1.0
    else:
        lesson_neglect = 0.0

    if expect_markers:
        missing = [m for m in expect_markers if m not in output]
        convention_break = len(missing) / len(expect_markers)
    else:
        missing = []
        convention_break = 0.0

    score = round(
        100
        * (
            W_OFF_TOPIC * off_topic
            + W_LESSON * lesson_neglect
            + W_CONVENTION * convention_break
        )
    )

    notes: list[str] = []
    if off_topic > 0:
        notes.append(f"주제 이탈: 작업 키워드 {present}/{len(tags)}만 등장")
    if lesson_neglect > 0:
        notes.append("회상한 교훈을 반영하지 않음")
    if missing:
        notes.append(f"역할 규약 누락: {', '.join(missing)}")
    if not notes:
        notes.append("주제·교훈·규약 모두 유지")

    return DriftReport(
        agent=agent,
        score=score,
        verdict=_verdict(score),
        signals=DriftSignals(off_topic, lesson_neglect, convention_break),
        notes=notes,
    )
