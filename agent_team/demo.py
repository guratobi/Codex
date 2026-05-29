"""에이전트 팀 + 자기학습 일지 데모.

같은 작업을 두 번 돌린다. 1차엔 참고할 과거 일기가 없지만, 2차엔 1차에서 남긴
일기를 회상해 더 많은 교훈을 적용한다 → '스스로 지혜를 쌓는' 흐름을 눈으로 확인.

실행:  python -m agent_team.demo
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from .journal import Journal
from .llm import get_llm
from .team import Team


def main() -> None:
    task = "주간 팀 뉴스레터 작성"
    # 데모는 매번 깨끗한 일지로 시작(임시 파일). 실제로는 .agent_journal.jsonl 등에 영구 보관.
    with tempfile.TemporaryDirectory() as d:
        journal = Journal(Path(d) / "journal.jsonl")
        team = Team(get_llm(), journal)

        print("=== 1차 실행 ===")
        print(team.run(task).render())

        print("\n=== 2차 실행 (1차 일기를 회상) ===")
        print(team.run(task).render())

        print("\n=== 누적된 지혜 ===")
        wisdom = journal.wisdom()
        if not wisdom:
            print("(아직 없음)")
        for i, w in enumerate(wisdom, 1):
            print(f"{i}. {w}")
        print(f"\n일지에 쌓인 기록: {len(journal.all_entries())}건")


if __name__ == "__main__":
    main()
