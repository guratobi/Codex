"""에이전트 자기학습 일지.

작업을 끝낼 때마다 '무엇을 했고/통했고/막혔고/다음엔 이렇게'를 한 줄 일기로 적고,
다음 작업 전에 관련 일기를 꺼내(recall) 프롬프트에 주입한다. 시간이 쌓이면
교훈이 누적되어 같은 실수를 덜 반복하게 된다. (append-only JSONL 파일)
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def derive_tags(text: str, limit: int = 6) -> list[str]:
    """작업 문장에서 2글자 이상 토큰을 뽑아 태그로. 같은 작업 → 같은 태그 → 회상 적중."""
    seen: list[str] = []
    for tok in re.findall(r"[0-9A-Za-z가-힣]+", text):
        if len(tok) >= 2 and tok not in seen:
            seen.append(tok)
    return seen[:limit]


@dataclass
class JournalEntry:
    ts: str       # ISO 타임스탬프
    agent: str    # 어떤 역할이 적었나
    task: str
    did: str      # 무엇을 했나
    worked: str   # 무엇이 통했나
    stuck: str    # 무엇이 막혔나
    lesson: str   # 다음을 위한 교훈
    tags: list[str] = field(default_factory=list)


class Journal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, entry: JournalEntry) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    def all_entries(self) -> list[JournalEntry]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(JournalEntry(**json.loads(line)))
        return out

    def recall(self, tags, limit: int = 5, before: str | None = None) -> list[JournalEntry]:
        """태그가 겹치는 과거 일기를 (겹침 수, 최신순)으로.

        before 가 주어지면 그 시각 *이전* 일기만 본다 → 현재 작업 세션이 방금
        자기가 쓴 메모를 다시 읽는 일을 막는다.
        """
        wanted = set(tags)
        scored = []
        for e in self.all_entries():
            if before is not None and not (e.ts < before):
                continue
            overlap = len(wanted & set(e.tags))
            if overlap:
                scored.append((overlap, e.ts, e))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [e for _, _, e in scored[:limit]]

    def wisdom(self) -> list[str]:
        """누적된 교훈(중복 제거, 최신 우선)."""
        seen, out = set(), []
        for e in reversed(self.all_entries()):
            if e.lesson and e.lesson not in seen:
                seen.add(e.lesson)
                out.append(e.lesson)
        return out
