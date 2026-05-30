"""터미널 연출 — 평의회의 방 장면 (ANSI, 비-TTY면 평문)."""
from __future__ import annotations

import sys

_TTY = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _TTY else text


SISTER_COLOR = {"여명": "33", "황혼": "35", "잿불": "36"}  # amber / violet / cyan


def intro(out=print) -> None:
    out("")
    out(_c("1;37", "═══  인공지능의 세자매  ═══"))
    out(_c("2;37", "낙관·비관·실용, 세 자매가 그대의 결정을 함께 본다."))
    out(_c("2;37", "자매들은 조언할 뿐, 선택은 그대의 몫이다."))


def render(result, out=print) -> None:
    if result.recalled:
        out(_c("2;37", f"\n(연대기에서 {len(result.recalled)}건의 옛 결정을 떠올린다)"))
    out("")
    out(_c("1;37", "── 평의회가 열린다 ──"))
    for name, text in result.counsels.items():
        color = SISTER_COLOR.get(name, "37")
        out("")
        out(_c(f"1;{color}", f"  {name}"))
        out(f"  {text}")
    out("")
    out(_c("1;37", "── 서기의 종합 ──"))
    out(f"  {result.synthesis}")
