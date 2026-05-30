# 나비 셋업 — 한 단계씩

대부분 한 번만 하면 끝. 순서대로 따라오면 된다.

> **빠른 길:** 검둥이에 코드를 받은 뒤 `navi/` 폴더에서 `./setup.sh` 를 실행하면
> 폴더 생성·설정 파일·24시간 등록까지 거의 자동이다. 토큰만 넣으면 끝.

---

## 1. 봇 토큰 준비 (1분)

이미 날씨 봇이 있으니 **그 토큰을 그대로 재사용**해도 된다.
(날씨 봇은 보내기만 하고, 나비는 받기+보내기 — 서로 안 부딪힌다.)

따로 깔끔하게 분리하고 싶으면 텔레그램 **@BotFather** → `/newbot` → 이름 정하고 토큰 받기.
> 분리하면 좋은 점: 날씨 알림과 나비 할 일 대화가 다른 방에서 안 섞임.
> 재사용하면 좋은 점: 추가 작업 0.

채팅 ID는 **안 구해도 된다.** 비워두면 나비가 처음 말 건 너를 주인으로 기억한다.

## 2. 우분투 박스에 코드 갖다놓기

이 레포를 박스에 클론(또는 git pull)하면 `navi/` 폴더가 같이 온다.
```bash
git clone <이 레포 주소> ~/Codex      # 이미 있으면 git -C ~/Codex pull
cd ~/Codex/navi
```

## 3. brain 레포 만들기 (장부가 쌓일 곳)

할 일/완료/로그가 저장되는 곳. **비공개** 깃 레포를 하나 파서 박스에 클론한다.
```bash
# 깃허브에서 navi-brain 이라는 private 레포 생성 후:
git clone <navi-brain 주소> ~/navi-brain
```
> 깃 없이 그냥 폴더로 써도 된다(그럼 회사 노트북 훅과 자동 동기화만 안 됨).
> 폴더 비어 있어도 OK — 나비가 inbox/home/work/done 파일을 알아서 만든다.

## 4. 설정 채우기
```bash
cp navi.env.example navi.env
nano navi.env
```
- `TELEGRAM_TOKEN` = 1번 토큰
- `NAVI_BRAIN_DIR` = `/home/너계정/navi-brain`
- 푸시 시각은 출퇴근 시간에 맞게 (기본 회사 08:50 / 집 19:00)

## 5. 처음 켜보기 (테스트)
```bash
python3 navi.py        # navi.env 를 자동으로 읽어옴 (윈도우면: python navi.py)
```
텔레그램에서 그 봇한테 `/start` 보내기 → 나비가 너를 주인으로 등록.
아무 줄이나 던져보고(`회사: 테스트`), `목록`, `끝 <id>` 까지 돌아가면 성공. `Ctrl+C` 로 멈춤.

## 6. 24시간 등록 (systemd)
```bash
sudo cp systemd/navi.service /etc/systemd/system/navi.service
sudo nano /etc/systemd/system/navi.service   # YOUR_USER 와 경로 수정
sudo systemctl daemon-reload
sudo systemctl enable --now navi
journalctl -u navi -f                         # 로그 확인
```
이제 박스가 재부팅돼도 나비는 알아서 살아난다.

## 7. 폰: 한 손 무음 캡처 (아이폰 12 Pro)

**설정 > 손쉬운 사용 > 터치 > 뒷면 탭 > 두 번 탭** → 단축어 지정.
단축어는 "앱 열기 → 텔레그램" (또는 나비 봇 대화 바로 열기) 하나면 충분.
→ 폰 뒤를 톡톡 두 번 = 나비 채팅 열림. 한 줄 치고 끝.

## 8. 회사 노트북: CC 세션 훅

회사에서 Claude Code 켤 때 회사 할 일이 화면 맨 위에 뜨게 한다.
그 노트북에도 brain 레포를 클론(`~/navi-brain`)하고, `.claude/settings.json` 에:
```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "NAVI_BRAIN_DIR=$HOME/navi-brain bash ~/Codex/navi/hooks/session-start.sh" }
        ]
      }
    ]
  }
}
```
경로는 그 노트북에 맞게. 이제 CC 켜면 회사 큐가 컨텍스트에 딱.

## 9. (옵션) 진짜 GPS 도착 푸시

기본은 '시간대 푸시'라 이건 안 해도 된다. 정밀하게 가고 싶을 때만.
1. `navi.env` 에 `NAVI_WEBHOOK_PORT` / `NAVI_WEBHOOK_SECRET` 채우고 나비 재시작.
2. 박스 웹훅을 폰에서 닿게 (무료 `cloudflared tunnel` 추천).
3. 아이폰 **단축어 > 개인용 자동화 > 도착** (집/회사 위치) → "URL 내용 가져오기"
   `https://<터널주소>/arrive?place=home&key=<시크릿>` (회사는 `place=work`).
   → 도착하는 순간 나비가 그 목록을 톡 쏴준다.

---

### 나비 명령어 치트시트
| 입력 | 동작 |
|---|---|
| `빨래 돌리기` | 자동 분류(집). 모르는 건 되물음 |
| `회사: KPI 경로 확정` | 회사 일로 바로 추가 |
| `공통: 여권 챙기기` | 집·회사 둘 다에 뜨게 |
| `집` / `회사` / `공통` | 그 목록 보기 |
| `끝 a1b2` | 그 일 완료 |
| `목록` | 집·회사·공통 전체 |
| `인박스` | 분류 대기 목록 |
| `집 a1b2` | 인박스의 a1b2 를 집으로 |
| `/help` | 사용법 |
