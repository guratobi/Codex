# 날씨 알림 봇 (weather_notify)

내일의 **날씨·미세먼지·꽃가루** 요약을 매일 저녁 텔레그램으로 보내주는 작은 자동화 스크립트입니다.
GitHub Actions cron 으로 동작하므로 PC가 꺼져 있어도 알림이 도착합니다.

## 동작 방식

- 매일 **21:00 (KST)** 에 `weather_notify.py` 가 실행됩니다 (`.github/workflows/daily-weather.yml`).
- OpenWeatherMap 에서 내일(0~24시) 3시간 단위 예보와 PM2.5 예보를 받아 요약합니다.
- (선택) Tomorrow.io 키가 있으면 꽃가루 지수도 포함합니다.
- **무음 모드(`QUIET_MODE`)**: 비/눈 없음 + 미세먼지 보통 이하 + 꽃가루 보통 이하 + 기온 변화 작음이면 알림을 생략합니다. 특이사항이 있는 날에만 울립니다.
- 미세먼지·꽃가루 호출이 실패해도 날씨 메시지는 보내며, 일시적 네트워크 오류는 자동으로 재시도합니다.

### 메시지 예시

```
🗓 5/30 Fri 이문동
☁️ 오전 맑음 → 오후 비, 체감 15~22°C
☔ 15~18시 보통 비
😷 미세먼지 나쁨 (76)
📉 오늘보다 6°C 추움
```

## 필요한 설정

GitHub 저장소 **Settings → Secrets and variables → Actions** 에 등록합니다.

| 종류 | 이름 | 설명 |
|------|------|------|
| Secret | `OWM_API_KEY` | OpenWeatherMap API 키 (필수) |
| Secret | `TELEGRAM_TOKEN` | 텔레그램 봇 토큰 (필수) |
| Secret | `TELEGRAM_CHAT_ID` | 메시지를 받을 채팅 ID (필수) |
| Secret | `TOMORROW_API_KEY` | Tomorrow.io 키 (선택, 꽃가루용) |
| Variable | `HOME_LAT` / `HOME_LON` / `HOME_LABEL` | 위치 (기본: 이문동 37.6018, 127.0537) |
| Variable | `QUIET_MODE` | `false` 면 평범한 날에도 발송 (기본 `true`) |

## 로컬 실행

의존성은 없습니다 (파이썬 표준 라이브러리만 사용). Python 3.10+ 권장.

```bash
export OWM_API_KEY=...
export TELEGRAM_TOKEN=...
export TELEGRAM_CHAT_ID=...
# 선택
export TOMORROW_API_KEY=...
export QUIET_MODE=false   # 테스트 시 무조건 발송

python weather_notify.py
```

워크플로우의 **Run workflow** 버튼(`workflow_dispatch`)으로 수동 실행하면 `force` 옵션으로 무음을 무시하고 바로 보낼 수 있습니다.

## 테스트

순수 로직(등급 계산·강수 표현·시간대 흐름·무음 판정 등)을 단위 테스트로 보호합니다. 외부 네트워크 없이 표준 라이브러리만으로 돌아갑니다.

```bash
python -m unittest discover -v
```

## 파일 구조

```
weather_notify.py            # 메인 스크립트
test_weather_notify.py       # 단위 테스트 (의존성 없음)
.github/workflows/
  daily-weather.yml          # 매일 21시 알림 cron
  test.yml                   # push/PR 시 테스트 실행
```

---

## 실험: AI 에이전트 팀 + 자기학습 일지

`agent_team/` 에 별도 프로토타입이 있습니다 → [agent_team/README.md](agent_team/README.md)

기획·실행·검토 에이전트가 팀으로 협업하고, 작업 경험을 일기로 남겨 다음 작업에 회상·재사용합니다(영상의 "스스로 지혜를 쌓는 구조"). 키 없이 도는 데모:

```bash
python -m agent_team.demo
```
