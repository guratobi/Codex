"""나비 — 항상 켜져 있는 개인 비서 에이전트.

텔레그램으로 한 줄 던지면 '집/회사/공통'으로 분류해 기억해 두고,
정해진 시각(출근/퇴근 즈음)에 그 장소의 할 일을 먼저 알려준다.
끝낸 일은 시각과 함께 done 으로 옮기고, 모든 변화는 깃 + log.jsonl 에 장부로 남는다.

우분투 박스에서 24시간 돈다(systemd 권장). 외부 의존성 없음(파이썬 표준 라이브러리만).
젤다 '시간의 오카리나'의 요정 나비처럼, 곁에서 따라다니며 때맞춰 콕 찔러주는 게 목적.

필요한 환경변수:
  TELEGRAM_TOKEN      텔레그램 봇 토큰 (날씨 봇과 같은 걸 써도 됨)
선택 환경변수:
  TELEGRAM_CHAT_ID    비워두면 봇에게 처음 말 건 사람을 '주인'으로 기억한다
  NAVI_BRAIN_DIR      brain 폴더 경로 (기본: ~/navi-brain)
  NAVI_STATE_DIR      상태 파일 폴더 (기본: ~/.navi, brain 과 분리 — 깃에 안 올라감)
  NAVI_PUSH_WORK      회사 목록 푸시 시각 HH:MM (기본 08:50, 평일만). "off" 면 끔
  NAVI_PUSH_HOME      집 목록 푸시 시각 HH:MM (기본 19:00, 매일). "off" 면 끔
  NAVI_GIT            "off" 면 깃 커밋/푸시 끔 (기본 on, brain 이 깃 레포일 때만 동작)
  NAVI_WEBHOOK_PORT   GPS 도착 푸시용 포트 (설정하면 활성화, 미설정 시 끔)
  NAVI_WEBHOOK_SECRET 웹훅 보호용 키 (포트 켤 거면 반드시 설정)
  NAVI_CHAT_TTL_HOURS 이보다 오래된 텔레그램 채팅 메시지를 자동 삭제(시간). 0=끔,
                      최대 47 (텔레그램이 48시간 지난 메시지 삭제를 막음). 기본 12
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

KST = timezone(timedelta(hours=9))


def _load_env_file() -> None:
    """navi.py 옆이나 현재 폴더의 navi.env 를 환경변수로 읽어온다.
    이미 설정된 값은 덮지 않는다. 덕분에 OS 상관없이 `python navi.py` 만으로 동작."""
    for p in (Path(__file__).resolve().parent / "navi.env", Path("navi.env")):
        if p.exists():
            for line in p.read_text("utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())
            break


_load_env_file()

# --- 설정 (환경변수) -------------------------------------------------------
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
ENV_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
BRAIN_DIR = Path(os.environ.get("NAVI_BRAIN_DIR", "~/navi-brain")).expanduser()
STATE_DIR = Path(os.environ.get("NAVI_STATE_DIR", "~/.navi")).expanduser()
PUSH_WORK = os.environ.get("NAVI_PUSH_WORK", "08:50")
PUSH_HOME = os.environ.get("NAVI_PUSH_HOME", "19:00")
GIT_ON = os.environ.get("NAVI_GIT", "on").lower() != "off"
WEBHOOK_PORT = os.environ.get("NAVI_WEBHOOK_PORT", "").strip()
WEBHOOK_SECRET = os.environ.get("NAVI_WEBHOOK_SECRET", "").strip()
try:
    CHAT_TTL_HOURS = max(0, min(47, int(os.environ.get("NAVI_CHAT_TTL_HOURS", "12"))))
except ValueError:
    CHAT_TTL_HOURS = 12

API = f"https://api.telegram.org/bot{TOKEN}"
STATE_PATH = STATE_DIR / "state.json"
ABOUT_PATH = Path(__file__).resolve().parent / "ABOUT.md"

EMOJI = {"home": "🏠", "work": "🏢", "both": "🔁"}
NAME = {"home": "집", "work": "회사", "both": "공통"}

# 분류 키워드. '이직/이력서/면접'류는 일부러 집(개인) 쪽에 둔다 —
# 회사 노트북 화면(SessionStart 훅)에 절대 안 뜨게 하려는 의도.
WORK_KW = [
    "회사", "업무", "보고", "보고서", "kpi", "회의", "미팅", "결재", "품의",
    "팀", "프로젝트", "거래처", "출근", "사무실", "상사", "정산", "납기",
]
HOME_KW = [
    "청소", "빨래", "장보기", "쓰레기", "분리수거", "관리비", "택배",
    "가족", "주말", "요리", "설거지", "화분", "은행", "약국", "병원",
    "이직", "이력서", "면접", "공고", "연봉",
]

HELP = (
    "🧚 나비 사용법\n"
    "\n"
    "• 그냥 한 줄 던져 → 집/회사 자동 분류 (애매하면 내가 되물어봄)\n"
    "• 집: 빨래 돌리기      ← 집 일로 바로 추가\n"
    "• 회사: KPI 경로 확정  ← 회사 일로 바로 추가\n"
    "• 공통: 여권 챙기기    ← 집·회사 둘 다에 뜨게\n"
    "• 집 / 회사 / 공통     ← 그 목록 보기\n"
    "• 끝 a1b2             ← 그 일 완료 (id는 목록에 떠 있어)\n"
    "• 목록                ← 집·회사·공통 전체 보기\n"
    "• 인박스              ← 분류 대기 중인 거\n"
    "\n"
    "정해둔 시각엔 내가 먼저 그날 목록을 보내줄게."
)


# --- 상태 ------------------------------------------------------------------
state: dict = {}


def load_state() -> None:
    global state
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text("utf-8"))
            return
        except (json.JSONDecodeError, OSError):
            pass
    state = {}


def save_state() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False), "utf-8")


def owner_id() -> str | None:
    """주인 채팅 ID. 환경변수가 있으면 그게 우선, 없으면 학습된 값."""
    return ENV_CHAT_ID or state.get("owner")


# --- 텔레그램 --------------------------------------------------------------
def tg_call(method: str, params: dict, timeout: int = 35) -> dict:
    url = f"{API}/{method}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def tg_post(method: str, params: dict, timeout: int = 15) -> dict:
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(f"{API}/{method}", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def record_msg(mid: int, ts: int | None = None) -> None:
    """청소 대상으로 메시지 id 기록 (나비가 보낸 것 + 받은 것)."""
    state.setdefault("msgs", []).append([mid, int(ts or time.time())])
    save_state()


def send(text: str, chat_id: str | None = None, track: bool = True,
         silent: bool = False) -> int | None:
    target = chat_id or owner_id()
    if not target:
        print("[warn] 보낼 대상(주인)이 아직 없음", file=sys.stderr)
        return None
    try:
        params = {"chat_id": target, "text": text}
        if silent:
            params["disable_notification"] = "true"
        res = tg_post("sendMessage", params)
        mid = res.get("result", {}).get("message_id")
        if track and mid:
            record_msg(mid)
        return mid
    except Exception as exc:  # 전송 실패해도 루프는 살아 있어야 함
        print(f"[warn] sendMessage 실패: {exc}", file=sys.stderr)
        return None


def delete_message(mid: int) -> None:
    try:
        tg_call("deleteMessage", {"chat_id": owner_id(), "message_id": mid}, 10)
    except Exception:  # 48시간 지난 메시지 등은 못 지움 — 조용히 넘어간다
        pass


def pin_message(mid: int) -> None:
    try:
        tg_call("pinChatMessage",
                {"chat_id": owner_id(), "message_id": mid,
                 "disable_notification": "true"}, 10)
    except Exception as exc:
        print(f"[warn] pin 실패: {exc}", file=sys.stderr)


def unpin_message(mid: int) -> None:
    try:
        tg_call("unpinChatMessage", {"chat_id": owner_id(), "message_id": mid}, 10)
    except Exception:
        pass


def get_updates(offset: int) -> list[dict]:
    try:
        res = tg_call("getUpdates", {"offset": offset, "timeout": 25}, timeout=35)
        return res.get("result", []) if res.get("ok") else []
    except Exception as exc:
        print(f"[warn] getUpdates 실패: {exc}", file=sys.stderr)
        time.sleep(3)
        return []


# --- brain 파일 ------------------------------------------------------------
ITEM_RE = re.compile(
    r"^- \[(?P<done>[ x])\] \((?P<id>[0-9a-z]{4})\) (?P<text>.+?)(?:  ·.*)?$"
)


def path_for(place: str) -> Path:
    return BRAIN_DIR / f"{place}.md"


def ensure_brain() -> None:
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    titles = {"inbox": "📥 인박스 (분류 대기)", "home": "🏠 집", "work": "🏢 회사",
              "both": "🔁 공통(집·회사)", "done": "✅ 끝낸 일"}
    for place, title in titles.items():
        p = BRAIN_DIR / f"{place}.md"
        if not p.exists():
            p.write_text(f"# {title}\n\n", "utf-8")
    log = BRAIN_DIR / "log.jsonl"
    if not log.exists():
        log.touch()


def new_id() -> str:
    return os.urandom(2).hex()  # 4자리 16진수


def read_items(place: str) -> list[dict]:
    items = []
    for line in path_for(place).read_text("utf-8").splitlines():
        m = ITEM_RE.match(line)
        if m:
            items.append({"id": m["id"], "text": m["text"].strip(),
                          "done": m["done"] == "x", "raw": line})
    return items


def active_items(place: str) -> list[dict]:
    return [it for it in read_items(place) if not it["done"]]


def append_line(place: str, line: str) -> None:
    with path_for(place).open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_event(event: str, place: str, iid: str, text: str) -> None:
    rec = {"ts": datetime.now(KST).isoformat(timespec="seconds"),
           "event": event, "place": place, "id": iid, "text": text}
    with (BRAIN_DIR / "log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def git_sync(message: str) -> None:
    if not GIT_ON or not (BRAIN_DIR / ".git").exists():
        return
    try:
        subprocess.run(["git", "-C", str(BRAIN_DIR), "add", "-A"],
                       check=False, capture_output=True, timeout=15)
        subprocess.run(["git", "-C", str(BRAIN_DIR), "commit", "-m", message],
                       check=False, capture_output=True, timeout=15)
        subprocess.run(["git", "-C", str(BRAIN_DIR), "push"],
                       check=False, capture_output=True, timeout=30)
    except Exception as exc:  # 깃은 부가 — 실패해도 비서 본업은 계속
        print(f"[warn] git_sync 실패: {exc}", file=sys.stderr)


# --- 동작 ------------------------------------------------------------------
def token_place(tok: str) -> str | None:
    tok = tok.lower()
    if tok in ("집", "home"):
        return "home"
    if tok in ("회사", "work"):
        return "work"
    if tok in ("양쪽", "공통", "둘다", "both"):
        return "both"
    return None


def classify(text: str) -> str | None:
    low = text.lower()
    m = re.match(r"\s*(집|회사|양쪽|공통|둘다|home|work|both)\s*[:：]", low)
    if m:
        return token_place(m.group(1))
    work = any(k in low for k in WORK_KW)
    home = any(k in low for k in HOME_KW)
    if work and not home:
        return "work"
    if home and not work:
        return "home"
    return None  # 애매 → 되물음


def add_item(place: str, text: str) -> None:
    iid = new_id()
    now = datetime.now(KST)
    append_line(place, f"- [ ] ({iid}) {text}  · {now:%m-%d %H:%M}")
    log_event("add", place, iid, text)
    git_sync(f"navi: add {place} ({iid})")
    send(f"{EMOJI[place]} {NAME[place]}에 담았어  ·({iid})\n  {text}")


def add_inbox(text: str) -> str:
    iid = new_id()
    now = datetime.now(KST)
    append_line("inbox", f"- [ ] ({iid}) {text}  · {now:%m-%d %H:%M}")
    log_event("add", "inbox", iid, text)
    git_sync(f"navi: inbox ({iid})")
    return iid


def assign(iid: str, place: str) -> None:
    """인박스 항목을 집/회사/양쪽으로 이동."""
    lines = path_for("inbox").read_text("utf-8").splitlines()
    kept, moved_text = [], None
    for line in lines:
        m = ITEM_RE.match(line)
        if m and m["id"] == iid and not moved_text:
            moved_text = m["text"].strip()
        else:
            kept.append(line)
    if moved_text is None:
        send(f"인박스에 ({iid}) 가 없는데? '인박스'로 확인해봐.")
        return
    path_for("inbox").write_text("\n".join(kept) + "\n", "utf-8")
    now = datetime.now(KST)
    append_line(place, f"- [ ] ({iid}) {moved_text}  · {now:%m-%d %H:%M}")
    log_event("assign", place, iid, moved_text)
    if state.get("pending") == iid:
        state.pop("pending", None)
        save_state()
    git_sync(f"navi: assign {place} ({iid})")
    send(f"{EMOJI[place]} {NAME[place]}으로 보냈어  ·({iid})\n  {moved_text}")


def complete(iid: str) -> None:
    for place in ("home", "work", "both"):
        lines = path_for(place).read_text("utf-8").splitlines()
        kept, done_text = [], None
        for line in lines:
            m = ITEM_RE.match(line)
            if m and m["id"] == iid and m["done"] != "x" and done_text is None:
                done_text = m["text"].strip()
            else:
                kept.append(line)
        if done_text is not None:
            path_for(place).write_text("\n".join(kept) + "\n", "utf-8")
            now = datetime.now(KST)
            append_line("done",
                        f"- [x] ({iid}) {done_text}  · {NAME[place]} · 끝 {now:%m-%d %H:%M}")
            log_event("done", place, iid, done_text)
            git_sync(f"navi: done ({iid})")
            send(f"✅ 끝! {done_text}")
            return
    send(f"({iid}) 못 찾았어. '목록'으로 id 확인해봐.")


def render_list(place: str, include_shared: bool = False) -> str:
    own = active_items(place)
    shared = active_items("both") if include_shared and place in ("home", "work") else []
    total = len(own) + len(shared)
    head = f"{EMOJI[place]} {NAME[place]} 할 일 ({total})"
    if total == 0:
        return head + "\n• (없음)"
    lines = [head]
    lines += [f"• ({it['id']}) {it['text']}" for it in own]
    lines += [f"• ({it['id']}) {it['text']} 🔁" for it in shared]
    first = (own or shared)[0]["id"]
    lines.append(f"— 끝내려면: 끝 {first}")
    return "\n".join(lines)


def render_inbox() -> str:
    items = active_items("inbox")
    if not items:
        return "📥 인박스 비었음"
    lines = ["📥 인박스 (집/회사/공통 정해줘)"]
    lines += [f"• ({it['id']}) {it['text']}  → 집 {it['id']} / 회사 {it['id']} / 공통 {it['id']}"
              for it in items]
    return "\n".join(lines)


# --- 메시지 처리 -----------------------------------------------------------
def handle_text(text: str) -> None:
    t = text.strip()
    low = t.lower()
    if not t:
        return

    if low in ("/start", "/help", "help", "도움말"):
        send(HELP)
        return

    # 완료
    m = re.match(r"(?:끝|완료|done|ok|/done)\s+([0-9a-f]{4})\b", low)
    if m:
        complete(m.group(1))
        return
    if re.match(r"(?:끝|완료|/done)\s+\S", low):
        send("완료는 '끝 a1b2' 처럼 4자리 id로. (id는 목록에 떠 있어)")
        return

    # 전체 목록 (각 칸 따로 — 양쪽 항목은 중복 없이 한 번만)
    if low in ("/list", "목록", "전체", "all"):
        blocks = [render_list("work"), render_list("home")]
        if active_items("both"):
            blocks.append(render_list("both"))
        send("\n\n".join(blocks))
        return
    if low in ("/inbox", "인박스"):
        send(render_inbox())
        return

    # 집/회사/양쪽 단독 → pending 있으면 분류, 없으면 목록
    single = None
    if low in ("집", "home", "/home", "🏠"):
        single = "home"
    elif low in ("회사", "work", "/work", "🏢"):
        single = "work"
    elif low in ("양쪽", "공통", "둘다", "both", "/both", "🔁"):
        single = "both"
    if single:
        if state.get("pending"):
            assign(state["pending"], single)
        else:
            send(render_list(single, include_shared=single in ("home", "work")))
        return

    # "집 a1b2" / "회사 a1b2" / "양쪽 a1b2" → 인박스 항목 분류
    m = re.match(r"(집|회사|양쪽|공통|둘다|home|work|both)\s+([0-9a-f]{4})\b", low)
    if m:
        assign(m.group(2), token_place(m.group(1)))
        return

    # 명시적 추가 "집: ...", "회사: ...", "양쪽: ..."
    m = re.match(r"\s*(집|회사|양쪽|공통|둘다|home|work|both)\s*[:：]\s*(.+)", t,
                 re.IGNORECASE)
    if m:
        add_item(token_place(m.group(1)), m.group(2).strip())
        return

    # 일반 문장 → 자동 분류
    place = classify(t)
    if place:
        add_item(place, t)
        return

    # 분류 불가 → 인박스 + 되물음
    iid = add_inbox(t)
    state["pending"] = iid
    save_state()
    send(f"📥 받았어: “{t}”\n집이야 회사야, 공통이야? (집 / 회사 / 공통)")


def handle_update(u: dict) -> None:
    msg = u.get("message") or u.get("edited_message")
    if not msg:
        return
    sender = str(msg["chat"]["id"])

    # 주인 인증: 환경변수가 없으면 첫 발신자를 주인으로 학습
    if not ENV_CHAT_ID and not state.get("owner"):
        state["owner"] = sender
        save_state()
        print(f"[info] 주인 등록: {sender}")
        publish_intro()
    if sender != owner_id():
        return  # 남의 메시지는 무시

    record_msg(msg["message_id"], msg.get("date"))  # 받은 줄도 청소 대상
    text = msg.get("text")
    if text:
        handle_text(text)


# --- 시간대 푸시 ------------------------------------------------------------
def _time_on(val: str) -> bool:
    """푸시 시각 설정이 켜져 있나. off/none/-/빈값이면 끔(도착 트리거만 쓸 때)."""
    return bool(val) and val.strip().lower() not in ("off", "none", "-")


def maybe_push() -> None:
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    hhmm = now.strftime("%H:%M")

    # 회사: 평일(월~금)만 — 시각이 켜져 있을 때만
    if _time_on(PUSH_WORK) and now.weekday() < 5 and hhmm >= PUSH_WORK \
            and state.get("push_work") != today:
        state["push_work"] = today
        save_state()
        if active_items("work") or active_items("both"):
            send(render_list("work", include_shared=True))

    # 집: 매일 — 시각이 켜져 있을 때만
    if _time_on(PUSH_HOME) and hhmm >= PUSH_HOME and state.get("push_home") != today:
        state["push_home"] = today
        save_state()
        if active_items("home") or active_items("both"):
            send(render_list("home", include_shared=True))


# --- 자기소개 공지 / 채팅 청소 ---------------------------------------------
def publish_intro() -> None:
    """ABOUT.md 를 텔레그램에 고정 공지로 올린다. 내용이 바뀌었을 때만 갱신."""
    if not owner_id() or not ABOUT_PATH.exists():
        return
    text = ABOUT_PATH.read_text("utf-8").strip()
    if not text:
        return
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    if state.get("intro_hash") == digest and state.get("intro_msg_id"):
        return  # 이미 최신 소개가 고정돼 있음
    old = state.get("intro_msg_id")
    if old:
        unpin_message(old)
        delete_message(old)
    mid = send(text, track=False, silent=True)  # 고정 메시지는 청소 대상 아님
    if mid:
        pin_message(mid)
        state["intro_msg_id"] = mid
        state["intro_hash"] = digest
        save_state()
        print(f"[info] 자기소개 공지 갱신/고정 (msg {mid})")


def cleanup_chat() -> None:
    """TTL 보다 오래된 채팅 메시지를 지운다. 고정 공지는 건드리지 않는다."""
    if CHAT_TTL_HOURS <= 0:
        return
    ttl = CHAT_TTL_HOURS * 3600
    now = int(time.time())
    pinned = state.get("intro_msg_id")
    keep, changed = [], False
    for mid, ts in state.get("msgs", []):
        if mid == pinned:
            changed = True
            continue
        age = now - ts
        if age > ttl:
            if age < 48 * 3600:       # 텔레그램은 48시간 지난 건 못 지움
                delete_message(mid)
            changed = True            # 지웠거나, 너무 오래돼 포기 → 추적 종료
        else:
            keep.append([mid, ts])
    if changed:
        state["msgs"] = keep
        save_state()


# --- 도착 웹훅(옵션) --------------------------------------------------------
class ArriveHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path != "/arrive" or q.get("key", [""])[0] != WEBHOOK_SECRET:
            self.send_response(403)
            self.end_headers()
            return
        raw = q.get("place", ["home"])[0]
        place = "work" if raw in ("work", "회사") else "home"
        send(render_list(place, include_shared=True))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):  # 액세스 로그 끔
        pass


def start_webhook() -> None:
    if not WEBHOOK_PORT:
        return
    if not WEBHOOK_SECRET:
        print("[warn] NAVI_WEBHOOK_SECRET 없이는 웹훅 안 켬", file=sys.stderr)
        return
    srv = HTTPServer(("0.0.0.0", int(WEBHOOK_PORT)), ArriveHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"[info] 도착 웹훅 :{WEBHOOK_PORT} 대기 중")


# --- 메인 ------------------------------------------------------------------
def main() -> None:
    if not TOKEN:
        print("환경변수 TELEGRAM_TOKEN 이 비어 있음", file=sys.stderr)
        sys.exit(1)

    ensure_brain()
    load_state()
    start_webhook()
    print(f"[info] 나비 기동. brain={BRAIN_DIR} 회사푸시={PUSH_WORK} 집푸시={PUSH_HOME}")
    publish_intro()  # 자기소개를 고정 공지로 (내용 바뀐 경우에만 갱신)

    offset = state.get("offset", 0)
    while True:
        for u in get_updates(offset):
            offset = u["update_id"] + 1
            state["offset"] = offset
            save_state()
            try:
                handle_update(u)
            except Exception as exc:  # 한 메시지 처리 실패가 봇을 죽이면 안 됨
                print(f"[warn] handle_update 실패: {exc}", file=sys.stderr)
        maybe_push()
        cleanup_chat()


if __name__ == "__main__":
    main()
