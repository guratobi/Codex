# 🧹 저장한 메시지 청소기 (saved-cleaner)

텔레그램 **저장한 메시지**를 기기 간 공유 스테이션으로 쓰되, 오래된 건 **주기적으로 자동 삭제**해
민감한 파일이 클라우드에 쌓여 남지 않게 한다. (받았으면 사라지는 컨베이어)

> **나비와 역할 분담**
> · 나비 = 오래 남는 기억·리마인더·장부 (장기 비서)
> · 이 도구 = 저장한 메시지를 잠깐 거쳐가게 하는 청소부 (단기 컨베이어)

## 왜 봇이 아니라 '계정 로그인'인가
봇 API 는 네 **저장한 메시지**에 접근할 수 없다(봇은 자기한테 온 것만 봄).
그래서 이건 **네 계정으로 로그인한** 스크립트(Telethon)다. 그만큼 다루는 데 주의가 필요하다 → 맨 아래 보안.

---

## 셋업 (검둥이에서)

### 1. API 키 발급
1. https://my.telegram.org 접속 → 로그인
2. **API development tools** → 앱 아무 이름으로 생성
3. **api_id** 와 **api_hash** 를 받아둔다

### 2. 설정 파일
```bash
cd ~/Codex/saved-cleaner
cp cleaner.env.example cleaner.env
nano cleaner.env      # TG_API_ID, TG_API_HASH, TG_PHONE 채우기
```
`KEEP_DAYS`(기본 3), `ONLY_FILES`(기본 true: 사진·문서만 지움), `DRY_RUN`(첫 실행 true 권장)도 확인.

### 3. 설치 & 첫 로그인 (대화형 1회)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python cleaner.py          # 코드(+2FA) 입력 → 로그인 1회
```
- `DRY_RUN=true` 면 **몇 개 지울지만** 알려준다. 숫자 확인하고 안전하면 `cleaner.env` 에서 `DRY_RUN=false`.
- ⚠️ 첫 실행은 그동안 쌓인 **백로그 전체**가 대상일 수 있다 → DRY-RUN 으로 꼭 먼저 확인.

### 4. 매일 자동 실행
**크론(간단):**
```bash
crontab -e
# 매일 04:30 실행 (경로는 본인 것으로)
30 4 * * * /home/<유저>/Codex/saved-cleaner/.venv/bin/python /home/<유저>/Codex/saved-cleaner/cleaner.py >> /home/<유저>/.navi-saved/clean.log 2>&1
```
**또는 systemd 타이머:**
```bash
sed -i "s/REPLACE_USER/$USER/g" systemd/saved-cleaner.service
sudo cp systemd/saved-cleaner.service systemd/saved-cleaner.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now saved-cleaner.timer
systemctl list-timers saved-cleaner.timer   # 다음 실행 확인
```

---

## 설정 값
| 키 | 뜻 | 기본 |
|---|---|---|
| `KEEP_DAYS` | 이 일수보다 오래된 것 삭제 | `3` |
| `ONLY_FILES` | `true`=사진/문서만 삭제(텍스트·링크 북마크 보존), `false`=전부 | `true` |
| `DRY_RUN` | `true`=삭제 않고 개수만 출력 | (예시는 `true`) |
| `TG_SESSION` | 세션 파일 경로 | `~/.navi-saved/saved.session` |

> **주의:** `ONLY_FILES=false` 로 두면 저장한 메시지에 적어둔 메모·북마크도 오래되면 지워진다.
> 보관하고 싶은 게 저장한 메시지에 있다면 `true`(기본) 유지 또는 그건 다른 곳에 둘 것.

## 보안
- `cleaner.env` 와 `*.session` 은 **절대 커밋 금지**(이미 .gitignore 처리). 세션 파일은 곧 **계정 접근 권한**이다.
- 검둥이가 털리면 계정도 위험 → 세션 파일 권한 잠그기: `chmod 600 ~/.navi-saved/saved.session`
- 의심되면 텔레그램 **설정 → 기기(Devices)** 에서 해당 세션 종료(로그아웃).
- 이 도구는 **삭제만** 한다(되돌릴 수 없음). 그래서 첫 실행 DRY-RUN 이 중요.
