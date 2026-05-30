"""인공지능의 세자매 — 세 AI 자매가 함께 결정을 보는 평의회."""
from .chronicle import Chronicle, Decision, derive_tags, now_iso
from .council import Council, CouncilResult, PREAMBLE
from .llm import LLM, AnthropicLLM, Message, MockLLM, get_llm
from .sisters import DAWN, DUSK, EMBER, SISTERS, Sister

# 장면 렌더러는 진입점 모듈이라 패키지 __init__ 에서 끌어오지 않는다
# (python -m three_sisters.scene 실행 시 중복 import 경고 방지).
# 필요하면:  from three_sisters.scene import render_scene, write_scene

__all__ = [
    "Chronicle",
    "Decision",
    "derive_tags",
    "now_iso",
    "Council",
    "CouncilResult",
    "PREAMBLE",
    "LLM",
    "AnthropicLLM",
    "Message",
    "MockLLM",
    "get_llm",
    "Sister",
    "SISTERS",
    "DAWN",
    "DUSK",
    "EMBER",
]
