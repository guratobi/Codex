"""연대기(Chronicle) — 평의회에 올랐던 결정들의 기록.

각 결정을 append-only JSONL 로 남기고, 새 고민이 오면 태그가 겹치는 과거 결정을
회상해 자매들에게 참고로 건넨다. (영상 #5의 '과거 결정·결과 학습')
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
    """고민 문장에서 2글자 이상 토큰을 뽑아 태그로. 같은 주제 → 같은 태그 → 회상 적중."""
    seen: list[str] = []
    for tok in re.findall(r"[0-9A-Za-z가-힣]+", text):
        if len(tok) >= 2 and tok not in seen:
            seen.append(tok)
    return seen[:limit]


@dataclass
class Decision:
    ts: str
    dilemma: str
    choice: str
    rationale: str
    tags: list[str] = field(default_factory=list)


class Chronicle:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, decision: Decision) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(decision), ensure_ascii=False) + "\n")

    def all(self) -> list[Decision]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(Decision(**json.loads(line)))
        return out

    def recall(self, tags, limit: int = 3) -> list[Decision]:
        """태그가 겹치는 과거 결정을 (겹침 수, 최신순)으로."""
        wanted = set(tags)
        scored = []
        for d in self.all():
            overlap = len(wanted & set(d.tags))
            if overlap:
                scored.append((overlap, d.ts, d))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [d for _, _, d in scored[:limit]]
