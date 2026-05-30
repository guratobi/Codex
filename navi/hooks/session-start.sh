#!/usr/bin/env bash
# 나비 — Claude Code 세션 시작 시 '회사 할 일'을 컨텍스트 맨 위에 띄운다.
#
# 회사 노트북의 .claude/settings.json SessionStart 훅에 등록해서 쓴다 (SETUP.md 참고).
# brain 이 깃 레포면 최신 상태로 당겨온 뒤 work.md 의 미완료 항목을 출력한다.
# (집/이직 항목은 안 띄운다. 단 '양쪽(both)' 항목은 회사 일과 함께 띄운다.)
set -uo pipefail

BRAIN_DIR="${NAVI_BRAIN_DIR:-$HOME/navi-brain}"
WORK="$BRAIN_DIR/work.md"
BOTH="$BRAIN_DIR/both.md"

git -C "$BRAIN_DIR" pull -q --no-rebase 2>/dev/null || true

echo "🧚 나비 — 오늘 회사서 처리할 것"
w=$(grep -E '^- \[ \]' "$WORK" 2>/dev/null | sed -E 's/^- \[ \] /  • /' || true)
b=$(grep -E '^- \[ \]' "$BOTH" 2>/dev/null | sed -E 's/^- \[ \] /  • /' || true)
if [[ -n "$w" || -n "$b" ]]; then
  [[ -n "$w" ]] && echo "$w"
  [[ -n "$b" ]] && { echo "  🔁 공통:"; echo "$b"; }
else
  echo "  • (없음)"
fi
