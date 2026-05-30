"""역할 에이전트: 기획자 → 실행가 → 검토자.

각 에이전트는 일하기 전에 일지에서 관련 교훈을 회상해 프롬프트에 넣고,
일을 마치면 회고 한 줄을 일지에 남긴다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .journal import Journal, JournalEntry, derive_tags, now_iso
from .llm import LESSONS_MARK, LLM, Message, PRIOR_MARK, TASK_MARK


def build_user_message(task: str, lessons: list[str], prior: str) -> str:
    lesson_block = "\n".join(f"- {l}" for l in lessons) if lessons else "- (없음)"
    return (
        f"{TASK_MARK} {task}\n"
        f"{LESSONS_MARK}\n{lesson_block}\n"
        f"{PRIOR_MARK}\n{prior or '(없음)'}"
    )


@dataclass
class AgentResult:
    output: str
    entry: JournalEntry
    lessons_used: list[str]


class Agent:
    role_key = "agent"
    title = "에이전트"
    role_desc = ""

    def __init__(self, llm: LLM, journal: Journal):
        self.llm = llm
        self.journal = journal

    def system_prompt(self) -> str:
        return f"[ROLE:{self.role_key}] 당신은 {self.title}입니다. {self.role_desc}"

    def reflect(self, task: str, output: str) -> tuple[str, str, str, str]:
        """(did, worked, stuck, lesson) 회고를 만든다. 역할별로 override."""
        raise NotImplementedError

    def run(self, task: str, prior: str = "", before: str | None = None) -> AgentResult:
        tags = derive_tags(task)
        recalled = self.journal.recall(tags, before=before)
        lessons = [e.lesson for e in recalled]
        user = build_user_message(task, lessons, prior)
        output = self.llm.complete(self.system_prompt(), [Message("user", user)])
        did, worked, stuck, lesson = self.reflect(task, output)
        entry = JournalEntry(
            ts=now_iso(),
            agent=self.title,
            task=task,
            did=did,
            worked=worked,
            stuck=stuck,
            lesson=lesson,
            tags=tags,
        )
        self.journal.record(entry)
        return AgentResult(output=output, entry=entry, lessons_used=lessons)


class Planner(Agent):
    role_key = "planner"
    title = "기획자"
    role_desc = "작업을 명확한 단계로 분해합니다."

    def reflect(self, task, output):
        return (
            f"'{task}'를 3단계 계획으로 분해",
            "단계 분해로 작업 범위가 명확해짐",
            "요구사항의 모호한 부분은 추정으로 메움",
            f"'{task}'류 작업은 목표→초안→검토 3단계로 쪼개면 매끄럽다.",
        )


class Worker(Agent):
    role_key = "worker"
    title = "실행가"
    role_desc = "계획에 따라 실제 산출물을 만듭니다."

    def reflect(self, task, output):
        return (
            f"'{task}' 1차 초안 작성",
            "핵심 요지를 앞에 둬 검토가 빨라짐",
            "세부 데이터는 추가 확인이 필요",
            f"'{task}' 초안은 핵심 요지를 맨 앞에 두면 검토가 빠르다.",
        )


class Reviewer(Agent):
    role_key = "reviewer"
    title = "검토자"
    role_desc = "품질을 점검하고, 전문 용어를 눈높이로 다듬고, 사람 결정이 필요한 지점을 표시합니다."

    def reflect(self, task, output):
        return (
            f"'{task}' 초안 검토 및 용어 정리",
            "전문 용어를 눈높이로 풀어 가독성이 올라감",
            "발행 톤·여부는 사람 결정이 필요",
            f"'{task}'는 발행 전 사람이 톤·발행 여부를 최종 결정한다.",
        )
