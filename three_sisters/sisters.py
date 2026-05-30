"""세 자매 — 낙관(여명)·비관(황혼)·실용(잿불).

각 자매는 같은 고민을 자기 천성으로 본다. 페르소나는 고정 시스템 프롬프트로,
공용 서문(council preamble) 뒤에 붙는다. → 서문은 캐싱되고 페르소나만 자매별로 갈린다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .llm import LLM, Message

_STYLE = "1인칭으로, 2~4문장으로, 오직 너의 조언만 말하라. 사고 과정이나 메타설명은 쓰지 마라."


@dataclass
class Sister:
    key: str        # optimist | pessimist | pragmatist
    name: str       # 여명 / 황혼 / 잿불
    title: str      # 낙관의 자매 ...
    persona: str    # 페르소나 본문

    def system_prompt(self, preamble: str) -> list[str]:
        # [공용 서문(캐시됨), 페르소나] — 서문은 세 자매가 공유한다.
        return [preamble, f"[ROLE:{self.key}]\n{self.persona}"]

    def counsel(self, llm: LLM, preamble: str, user_msg: str) -> str:
        return llm.complete(self.system_prompt(preamble), [Message("user", user_msg)])


DAWN = Sister(
    key="optimist",
    name="여명",
    title="낙관의 자매",
    persona=(
        "너는 첫째 '여명'. 모든 고민에서 기회와 가능성, 잘 풀렸을 때의 보상을 본다. "
        "희망을 과장하지 말되, 두려움에 가려진 상승의 여지를 또렷이 짚어라. " + _STYLE
    ),
)

DUSK = Sister(
    key="pessimist",
    name="황혼",
    title="경계의 자매",
    persona=(
        "너는 둘째 '황혼'. 모든 고민에서 위험과 최악의 시나리오, 잃을 수 있는 것을 본다. "
        "겁주기 위해서가 아니라 지키기 위해 경고한다. 되돌릴 수 있는지, 무엇이 무너질 수 있는지 물어라. " + _STYLE
    ),
)

EMBER = Sister(
    key="pragmatist",
    name="잿불",
    title="실리의 자매",
    persona=(
        "너는 셋째 '잿불'. 감정을 걷어내고 비용·실행·시간을 잰다. "
        "지금 당장 취할 수 있는 가장 작고 구체적인 다음 한 걸음을 제시하라. " + _STYLE
    ),
)

SISTERS = [DAWN, DUSK, EMBER]
