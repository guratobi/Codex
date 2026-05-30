"""저장한 메시지(Saved Messages) 자동 청소기.

텔레그램 '저장한 메시지'를 기기 간 공유 스테이션으로 쓰되, 오래된 건 주기적으로
지운다 — 민감한 파일이 클라우드에 쌓여 남지 않게, 받았으면 사라지는 컨베이어로.

중요: 이건 '봇'이 아니라 '네 계정으로 로그인한' 스크립트(Telethon/MTProto)다.
봇 API 로는 '저장한 메시지'에 접근할 수 없기 때문. 그래서 나비(봇)와는 별개 도구다.
  · 나비   = 오래 남는 기억·리마인더·장부 (장기 비서)
  · 이 도구 = 저장한 메시지를 잠깐 거쳐가게 하는 청소부 (단기 컨베이어)

설정(같은 폴더 cleaner.env 또는 환경변수):
  TG_API_ID     my.telegram.org 에서 발급 (필수)
  TG_API_HASH   my.telegram.org 에서 발급 (필수)
  TG_PHONE      +82109... 첫 로그인 편의 (선택)
  KEEP_DAYS     이 일수보다 오래된 것 삭제 (기본 3)
  ONLY_FILES    true=사진/문서만 삭제(텍스트·링크 북마크는 보존) / false=전부 (기본 true)
  DRY_RUN       true=삭제 않고 '몇 개 지울지'만 출력 (첫 실행 때 권장)
  TG_SESSION    세션 파일 경로 (기본 ~/.navi-saved/saved.session)

처음 한 번은 터미널에서 `python cleaner.py` 로 직접 실행해 로그인(코드·2FA 입력).
이후엔 systemd 타이머/크론이 무인으로 돌린다. (README.md 참고)
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _load_env_file() -> None:
    """같은 폴더 또는 현재 폴더의 cleaner.env 를 환경변수로 읽어온다(기존값 우선)."""
    for p in (Path(__file__).resolve().parent / "cleaner.env", Path("cleaner.env")):
        if p.exists():
            for line in p.read_text("utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
            break


_load_env_file()


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on", "y")


API_ID = os.environ.get("TG_API_ID", "").strip()
API_HASH = os.environ.get("TG_API_HASH", "").strip()
PHONE = os.environ.get("TG_PHONE", "").strip() or None
KEEP_DAYS = int(os.environ.get("KEEP_DAYS", "3") or "3")
ONLY_FILES = _bool("ONLY_FILES", True)
DRY_RUN = _bool("DRY_RUN", False)
SESSION = os.environ.get("TG_SESSION", "").strip() or str(
    Path("~/.navi-saved/saved.session").expanduser())


async def run() -> int:
    try:
        from telethon import TelegramClient
        from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto
    except ImportError:
        print("telethon 이 없어. `pip install telethon` 먼저. (가이드: README.md)",
              file=sys.stderr)
        return 1

    if not API_ID or not API_HASH:
        print("TG_API_ID / TG_API_HASH 가 필요해 (my.telegram.org). cleaner.env 참고.",
              file=sys.stderr)
        return 1

    Path(SESSION).parent.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    client = TelegramClient(SESSION, int(API_ID), API_HASH)
    await client.start(phone=PHONE)  # 첫 실행만 대화형(코드/2FA), 이후 세션 재사용

    try:
        # 'me' = 저장한 메시지(나와의 대화). 다른 채팅은 절대 건드리지 않는다.
        targets: list[int] = []
        scanned = 0
        async for msg in client.iter_messages("me"):
            scanned += 1
            if msg.date >= cutoff:
                continue  # 아직 보관 기간 안 — 더 오래된 걸 계속 본다
            if ONLY_FILES and not isinstance(
                    msg.media, (MessageMediaPhoto, MessageMediaDocument)):
                continue  # 파일만 모드: 텍스트·링크 북마크는 살린다
            targets.append(msg.id)

        kind = "사진/문서" if ONLY_FILES else "메시지"
        if not targets:
            print(f"[saved-cleaner] {KEEP_DAYS}일 지난 {kind} 없음 (스캔 {scanned}개)")
            return 0

        if DRY_RUN:
            print(f"[saved-cleaner] (DRY-RUN) 지울 {kind} {len(targets)}개"
                  f" / 스캔 {scanned}개. 실제 삭제는 안 함. 확인되면 DRY_RUN=false.")
            return 0

        deleted = 0
        for i in range(0, len(targets), 100):  # 텔레그램은 한 번에 ~100개까지
            chunk = targets[i:i + 100]
            await client.delete_messages("me", chunk)
            deleted += len(chunk)
        print(f"[saved-cleaner] {KEEP_DAYS}일 지난 {kind} {deleted}개 삭제 (스캔 {scanned}개)")
        return 0
    finally:
        await client.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
