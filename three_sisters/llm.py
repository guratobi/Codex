"""LLM 계층 — 세 자매의 두뇌.

ANTHROPIC_API_KEY 가 있으면 진짜 Claude(AnthropicLLM)를, 없으면 키 없이 도는
결정적 MockLLM 을 쓴다. 인터페이스는 complete(system, messages) -> str.

system 은 str 한 덩어리이거나 [고정 서문, 가변 부분...] 리스트일 수 있다.
AnthropicLLM 은 앞쪽 고정 블록에 prompt caching 을 건다(공용 서문 재사용).
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

# 평의회 사용자 메시지의 구획 표시 (MockLLM 이 파싱)
DILEMMA_MARK = "고민:"
CHRONICLE_MARK = "지난 기록:"

# 모델 기본값. 사용자가 THREE_SISTERS_MODEL 로 바꿀 수 있음(예: claude-sonnet-4-6).
DEFAULT_MODEL = "claude-opus-4-8"


@dataclass
class Message:
    role: str   # "user" | "assistant"
    content: str


def _system_text(system) -> str:
    return system if isinstance(system, str) else "\n\n".join(system)


def _dilemma_of(messages: list[Message]) -> str:
    text = messages[-1].content if messages else ""
    for line in text.splitlines():
        if line.startswith(DILEMMA_MARK):
            return line[len(DILEMMA_MARK):].strip()
    return text.strip().splitlines()[0] if text.strip() else ""


class LLM:
    def complete(self, system, messages: list[Message]) -> str:
        raise NotImplementedError


class MockLLM(LLM):
    """키 없이 도는 가짜 두뇌. system 의 [ROLE:x] 로 자매를 구분해 정해진 대사를 돌려준다.

    '추론'은 하지 않는다 — 구조와 테스트, 키 없는 체험을 위한 스탠드인.
    """

    def complete(self, system, messages: list[Message]) -> str:
        role = "synth"
        m = re.search(r"\[ROLE:(\w+)\]", _system_text(system))
        if m:
            role = m.group(1)
        d = _dilemma_of(messages)
        if role == "optimist":
            return f"'{d}' — 이건 기회다. 잘 풀렸을 때 얻을 것을 보라. 망설임이 가장 큰 손해일 수 있다."
        if role == "pessimist":
            return f"'{d}' — 잠깐, 최악을 그려보자. 무엇을 잃을 수 있고, 이 선택은 되돌릴 수 있는가?"
        if role == "pragmatist":
            return f"'{d}' — 감정을 걷고 비용과 실행을 재자. 지금 할 수 있는 가장 작은 첫 걸음은 무엇인가?"
        return (
            f"세 자매의 말을 종합한다. '{d}'의 핵심 트레이드오프는 기회와 위험 사이다. "
            "되돌릴 수 있다면 작게 시도하고, 되돌릴 수 없다면 더 신중하라. 선택은 그대의 몫."
        )


class AnthropicLLM(LLM):
    """진짜 Claude. 앞쪽 고정 시스템 블록(공용 서문)에 prompt caching 을 건다."""

    def __init__(self, model: str | None = None, max_tokens: int = 1024):
        import anthropic  # 지연 임포트: 미설치/무키 환경에서도 모듈 임포트는 되게

        self._client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 자동 사용
        self.model = model or os.environ.get("THREE_SISTERS_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens

    def _system_blocks(self, system) -> list[dict]:
        parts = [system] if isinstance(system, str) else list(system)
        blocks: list[dict] = []
        for i, text in enumerate(parts):
            block = {"type": "text", "text": text}
            # 고정 서문(앞 블록)에 캐시 표시 → 자매/결정/세션을 가로질러 재사용.
            # 단일 블록이면 그 블록 자체를 캐싱.
            if i < len(parts) - 1 or len(parts) == 1:
                block["cache_control"] = {"type": "ephemeral"}
            blocks.append(block)
        return blocks

    def complete(self, system, messages: list[Message]) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self._system_blocks(system),
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()


def get_llm() -> LLM:
    """키가 있으면 진짜 Claude, 없으면 MockLLM. 연결/임포트 실패 시에도 목으로 폴백."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return AnthropicLLM()
        except Exception as exc:  # noqa: BLE001 - 어떤 실패든 체험은 이어가야 함
            print(f"[warn] Claude 연결 실패 → 목으로 대체: {exc}", file=sys.stderr)
    return MockLLM()
