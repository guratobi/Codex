#!/usr/bin/env bash
# 나비 설치 도우미 — 검둥이(우분투)에서 navi/ 폴더 안에서 실행한다.
#   ./setup.sh            기본 설치 (설정 파일 준비 + brain 폴더 생성)
#   ./setup.sh --service  추가로 systemd 에 24시간 서비스 등록 (sudo 필요)
set -uo pipefail
cd "$(dirname "$0")"
HERE="$(pwd)"

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "⚠️  sudo 없이 그냥  ./setup.sh  로 실행해 (필요할 때만 안에서 sudo 씀)"
  exit 1
fi

echo "🧚 나비 설치 도우미"
echo

# 1) 파이썬 확인
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 가 없어. 먼저:  sudo apt install -y python3"
  exit 1
fi
echo "✅ python3: $(python3 --version)"

# 2) navi.env 준비 (이미 있으면 안 건드림)
if [[ -f navi.env ]]; then
  echo "✅ navi.env 이미 있음 (그대로 둠)"
else
  cp navi.env.example navi.env
  echo "📄 navi.env 만들었어 — TELEGRAM_TOKEN 을 넣어야 함"
fi

# 3) brain 폴더 (navi.env 의 NAVI_BRAIN_DIR, 없으면 ~/navi-brain)
BRAIN="$HOME/navi-brain"
if grep -q '^NAVI_BRAIN_DIR=' navi.env 2>/dev/null; then
  v="$(grep '^NAVI_BRAIN_DIR=' navi.env | head -1 | cut -d= -f2-)"
  [[ -n "$v" ]] && BRAIN="${v/#\~/$HOME}"
fi
mkdir -p "$BRAIN"
echo "✅ brain 폴더: $BRAIN"

# 4) 훅 실행권한
chmod +x hooks/session-start.sh 2>/dev/null || true

# 5) systemd 등록 (옵션)
if [[ "${1:-}" == "--service" ]]; then
  if ! grep -q '^TELEGRAM_TOKEN=.\+' navi.env; then
    echo "⚠️  navi.env 의 TELEGRAM_TOKEN 이 비었어. 토큰 먼저 넣고 다시 --service 로."
    exit 1
  fi
  echo
  echo "⏳ systemd 서비스 등록 (sudo 비밀번호 물어볼 수 있음)…"
  sudo bash -c "cat > /etc/systemd/system/navi.service" <<EOF
[Unit]
Description=Navi — personal assistant agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HERE
EnvironmentFile=$HERE/navi.env
ExecStart=$(command -v python3) $HERE/navi.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable --now navi
  echo "✅ 24시간 등록 끝. 로그:  journalctl -u navi -f"
  exit 0
fi

echo
echo "── 다음 할 일 ───────────────────────────"
echo "1) navi.env 열어서 토큰 넣기:        nano navi.env"
echo "2) 테스트:  set -a && source navi.env && set +a && python3 navi.py"
echo "3) 텔레그램서 봇한테 /start → 한 줄 던져보기"
echo "4) 잘 되면 24시간 등록:               ./setup.sh --service"
