"""LLM 추상화 계층.

에이전트가 '생각'하려면 뒤에서 언어모델을 호출해야 한다. 지금은 API 키 없이
도는 결정적(deterministic) MockLLM 만 제공한다. 실제 Claude 연결은 사용자가
ANTHROPIC_API_KEY 를 넣고 켤 때 get_llm() 한 곳만 바꿔 붙이면 된다
(그때 claude-api 스킬로 prompt caching 까지 갖춰 구현).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# 에이전트 → LLM 으로 넘기는 사용자 메시지의 구획 표시. MockLLM 이 이걸 파싱한다.
TASK_MARK = "작업:"
LESSONS_MARK = "참고 교훈:"
PRIOR_MARK = "이전 산출물:"


@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str


class LLM:
    """모든 백엔드가 따르는 최소 인터페이스."""

    def complete(self, system: str, messages: list[Message]) -> str:
        raise NotImplementedError


def _parse_user(text: str) -> tuple[str, list[str], str]:
    """build_user_message 가 만든 텍스트에서 (작업, 교훈목록, 이전산출물) 추출."""
    task, lessons, prior_lines = "", [], []
    section = None
    for line in text.splitlines():
        if line.startswith(TASK_MARK):
            task = line[len(TASK_MARK):].strip()
            section = "task"
        elif line.startswith(LESSONS_MARK):
            section = "lessons"
        elif line.startswith(PRIOR_MARK):
            section = "prior"
        elif section == "lessons":
            s = line.strip()
            if s.startswith("- "):
                v = s[2:].strip()
                if v and v != "(없음)":
                    lessons.append(v)
        elif section == "prior":
            prior_lines.append(line)
    return task, lessons, "\n".join(prior_lines).strip()


class MockLLM(LLM):
    """키 없이 도는 가짜 모델.

    system 프롬프트의 [ROLE:xxx] 태그로 역할을 알아내고, 작업/회상 교훈을 엮어
    역할에 맞는 결과를 정해진 형식으로 돌려준다. 구조와 테스트를 위한 스탠드인이며
    '추론'은 하지 않는다.
    """

    def complete(self, system: str, messages: list[Message]) -> str:
        m = re.search(r"\[ROLE:(\w+)\]", system)
        role = m.group(1) if m else "agent"
        user = messages[-1].content if messages else ""
        task, lessons, _prior = _parse_user(user)
        note = (
            f"(과거 교훈 {len(lessons)}건 반영: {lessons[0]})"
            if lessons
            else "(참고할 과거 교훈 없음)"
        )
        if role == "planner":
            return (
                f"[기획] '{task}' 를 3단계로 나눴습니다.\n"
                "1) 핵심 목표 정의\n2) 초안 작성\n3) 검토 및 사람 확인\n"
                f"{note}"
            )
        if role == "worker":
            return (
                f"[실행] 계획에 따라 '{task}' 초안을 작성했습니다.\n"
                "- 핵심 요지를 맨 앞에 배치\n"
                f"{note}"
            )
        if role == "reviewer":
            return (
                f"[검토] '{task}' 초안을 점검했습니다.\n"
                "- 용어 다듬기: 전문 용어를 일반 눈높이로 풀어 썼습니다.\n"
                "- 품질: 합격 기준 충족\n"
                "🧑 사람 결정 필요: 최종 발행 여부와 톤을 확정해 주세요.\n"
                f"{note}"
            )
        return f"[처리] '{task}' 완료.\n{note}"


def get_llm() -> LLM:
    """현재 백엔드를 돌려준다.

    지금은 항상 MockLLM. 진짜 Claude 를 켤 때 이 함수에서
    ANTHROPIC_API_KEY 유무를 보고 AnthropicLLM 을 돌려주도록 확장한다.
    """
    return MockLLM()
