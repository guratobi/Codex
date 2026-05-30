"""평의회 — 고민을 세 자매에게 올리고, 종합하고, 연대기에 새긴다."""
from __future__ import annotations

from dataclasses import dataclass, field

from .chronicle import Chronicle, Decision, derive_tags, now_iso
from .llm import CHRONICLE_MARK, DILEMMA_MARK, LLM, Message
from .sisters import SISTERS

# 모든 자매·종합 호출이 공유하는 고정 서문 → AnthropicLLM 이 이 블록을 캐싱한다.
PREAMBLE = (
    "이곳은 '인공지능의 세자매'의 평의회다. 한 사람이 현실의 결정을 청원으로 가져온다. "
    "세 자매(낙관·비관·실용)는 같은 고민을 서로 다른 천성으로 본다. "
    "자매들은 청원자를 대신해 결정하지 않는다 — 보는 것을 또렷이 말할 뿐, 최종 선택은 청원자의 몫이다. "
    "조언은 한국어로, 짧고 구체적으로 한다."
)

SYNTH_SYSTEM = (
    "[ROLE:synth] 너는 평의회의 서기다. 세 자매의 조언을 종합해, 청원자가 결정하기 쉽도록 "
    "핵심 트레이드오프를 1~2가지로 압축하고, '되돌릴 수 있는 결정인가'를 한 줄로 짚어라. "
    "대신 결정하지 말고, 선택은 청원자에게 남겨라. 한국어로 3~5문장."
)


@dataclass
class CouncilResult:
    dilemma: str
    counsels: dict              # 자매 이름 -> 조언
    synthesis: str
    recalled: list = field(default_factory=list)  # 회상한 과거 Decision


def _build_user_msg(dilemma: str, recalled: list[Decision]) -> str:
    lines = [f"{DILEMMA_MARK} {dilemma}", CHRONICLE_MARK]
    if recalled:
        lines.extend(f"- 과거 '{d.dilemma}' → 선택: {d.choice}" for d in recalled)
    else:
        lines.append("- (없음)")
    return "\n".join(lines)


class Council:
    def __init__(self, llm: LLM, chronicle: Chronicle):
        self.llm = llm
        self.chronicle = chronicle

    def deliberate(self, dilemma: str) -> CouncilResult:
        recalled = self.chronicle.recall(derive_tags(dilemma))
        user_msg = _build_user_msg(dilemma, recalled)

        counsels = {s.name: s.counsel(self.llm, PREAMBLE, user_msg) for s in SISTERS}

        synth_input = (
            user_msg
            + "\n\n세 자매의 조언:\n"
            + "\n".join(f"- {name}: {text}" for name, text in counsels.items())
        )
        synthesis = self.llm.complete(SYNTH_SYSTEM, [Message("user", synth_input)])

        return CouncilResult(
            dilemma=dilemma, counsels=counsels, synthesis=synthesis, recalled=recalled
        )

    def seal(self, result: CouncilResult, choice: str, rationale: str = "") -> Decision:
        decision = Decision(
            ts=now_iso(),
            dilemma=result.dilemma,
            choice=choice,
            rationale=rationale,
            tags=derive_tags(result.dilemma),
        )
        self.chronicle.record(decision)
        return decision
