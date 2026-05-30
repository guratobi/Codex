"""에이전트 팀 오케스트레이션.

기획자 → 실행가 → 검토자가 한 작업을 이어받아 처리하고, 셋 다 같은 일지를
공유한다. 이번 실행이 시작된 시각(before)을 기준으로 그 *이전* 일기만 회상하므로,
방금 자기 팀이 쓴 메모가 아니라 과거 세션의 지혜를 끌어온다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .agents import AgentResult, Planner, Reviewer, Worker
from .journal import Journal, now_iso
from .llm import LLM


def _indent(text: str, prefix: str = "   ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


@dataclass
class TeamResult:
    task: str
    plan: AgentResult
    draft: AgentResult
    review: AgentResult

    @property
    def lessons_applied(self) -> int:
        return (
            len(self.plan.lessons_used)
            + len(self.draft.lessons_used)
            + len(self.review.lessons_used)
        )

    @property
    def human_decisions(self) -> list[str]:
        return [
            line.strip()
            for line in self.review.output.splitlines()
            if line.strip().startswith("🧑")
        ]

    def render(self) -> str:
        lines = [
            f"📋 작업: {self.task}",
            f"   적용한 과거 교훈: {self.lessons_applied}건",
            "",
            f"🧭 [{self.plan.entry.agent}]",
            _indent(self.plan.output),
            f"🛠 [{self.draft.entry.agent}]",
            _indent(self.draft.output),
            f"🔎 [{self.review.entry.agent}]",
            _indent(self.review.output),
        ]
        if self.human_decisions:
            lines.append("")
            lines.append("🧑 사람이 결정할 것:")
            lines.extend(f"   {d}" for d in self.human_decisions)
        return "\n".join(lines)


class Team:
    def __init__(self, llm: LLM, journal: Journal):
        self.journal = journal
        self.planner = Planner(llm, journal)
        self.worker = Worker(llm, journal)
        self.reviewer = Reviewer(llm, journal)

    def run(self, task: str) -> TeamResult:
        before = now_iso()  # 이 시점 이전 일기만 회상 → 과거 세션의 지혜만 끌어옴
        plan = self.planner.run(task, before=before)
        draft = self.worker.run(task, prior=plan.output, before=before)
        review = self.reviewer.run(task, prior=draft.output, before=before)
        return TeamResult(task=task, plan=plan, draft=draft, review=review)
