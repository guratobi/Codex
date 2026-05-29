"""AI 에이전트 팀 + 자기학습 일지 프로토타입."""
from .agents import Agent, AgentResult, Planner, Reviewer, Worker
from .drift import DriftReport, DriftSignals, diagnose
from .journal import Journal, JournalEntry, derive_tags, now_iso
from .llm import LLM, DriftingMockLLM, Message, MockLLM, get_llm
from .team import Team, TeamResult

# 대시보드/데모는 진입점 모듈이므로 패키지 __init__ 에서 끌어오지 않는다
# (python -m agent_team.dashboard 실행 시 중복 import 경고 방지).

__all__ = [
    "Agent",
    "AgentResult",
    "Planner",
    "Reviewer",
    "Worker",
    "Journal",
    "JournalEntry",
    "derive_tags",
    "now_iso",
    "LLM",
    "Message",
    "MockLLM",
    "DriftingMockLLM",
    "get_llm",
    "Team",
    "TeamResult",
    "diagnose",
    "DriftReport",
    "DriftSignals",
]
