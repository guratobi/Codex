"""인공지능의 세자매 — 터미널 평의회 루프."""
from __future__ import annotations

from . import narrate
from .chronicle import Chronicle
from .council import Council
from .llm import LLM, get_llm

DEFAULT_CHRONICLE = "chronicle.jsonl"


def run(
    llm: LLM | None = None,
    chronicle_path: str = DEFAULT_CHRONICLE,
    input_fn=input,
    output_fn=print,
) -> None:
    """대화 루프. 테스트/데모를 위해 input_fn/output_fn 을 주입할 수 있다."""
    llm = llm or get_llm()
    council = Council(llm, Chronicle(chronicle_path))

    narrate.intro(output_fn)
    while True:
        try:
            dilemma = input_fn("\n그대의 고민을 말하라 (빈 줄이면 끝): ").strip()
        except EOFError:
            break
        if not dilemma:
            break

        result = council.deliberate(dilemma)
        narrate.render(result, output_fn)

        choice = input_fn("\n\U0001F772 그대의 결정은? (건너뛰려면 빈 줄): ").strip()
        if choice:
            rationale = input_fn("   이유 한 줄 (선택): ").strip()
            council.seal(result, choice, rationale)
            output_fn("   …연대기에 새겨졌다.")

    output_fn("\n평의회를 마친다.")
