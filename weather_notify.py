"""내일 날씨, 미세먼지, 꽃가루, 강수 정보를 텔레그램으로 보내는 스크립트.

GitHub Actions cron으로 매일 한 번 실행되어 PC가 꺼져 있어도 알림이 도착한다.
필요한 환경변수:
  OWM_API_KEY        OpenWeatherMap API 키
  TELEGRAM_TOKEN     텔레그램 봇 토큰
  TELEGRAM_CHAT_ID   메시지를 받을 채팅 ID
선택 환경변수:
  HOME_LAT/HOME_LON/HOME_LABEL   위치 (기본: 이문동)
  TOMORROW_API_KEY               Tomorrow.io 키 (있으면 꽃가루/알레르기 지수 포함)
  QUIET_MODE                     "false" 로 두면 평범한 날에도 알림 발송 (기본: true=무음)
"""
from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))

# 한국 환경부 PM2.5 µg/m³ 등급 (좋음/보통/나쁨/매우나쁨)
PM25_BREAKS = [(15, "좋음"), (35, "보통"), (75, "나쁨"), (float("inf"), "매우나쁨")]

# Tomorrow.io 꽃가루 지수 0~5 등급 라벨
POLLEN_LABELS = {0: "없음", 1: "매우낮음", 2: "낮음", 3: "보통", 4: "높음", 5: "매우높음"}

# 어제 시점에 만든 "내일=오늘" 예보를 저장해 두고 다음날 비교에 쓴다.
CACHE_PATH = Path(".cache/last_forecast.json")


def grade(value: float, breaks: list[tuple[float, str]]) -> str:
    for limit, label in breaks:
        if value <= limit:
            return label
    return "알수없음"


# 일시적 오류(네트워크 끊김·타임아웃·깨진 응답)는 재시도 대상
RETRYABLE = (urllib.error.URLError, TimeoutError, json.JSONDecodeError)


def http_get_json(url: str, *, retries: int = 3, backoff: float = 2.0) -> dict:
    """GET 후 JSON 파싱. 일시적 오류는 지수 백오프(2s, 4s)로 재시도한다."""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # 4xx(키 오류·잘못된 요청)는 재시도해도 소용없으니 즉시 전파
            if exc.code < 500 or attempt == retries - 1:
                raise
        except RETRYABLE:
            if attempt == retries - 1:
                raise
        time.sleep(backoff * (2 ** attempt))
    raise RuntimeError("unreachable")  # pragma: no cover


def fetch_forecast(lat: str, lon: str, key: str) -> dict:
    qs = urllib.parse.urlencode(
        {"lat": lat, "lon": lon, "appid": key, "units": "metric", "lang": "kr"}
    )
    return http_get_json(f"https://api.openweathermap.org/data/2.5/forecast?{qs}")


def fetch_air_pollution(lat: str, lon: str, key: str) -> dict:
    qs = urllib.parse.urlencode({"lat": lat, "lon": lon, "appid": key})
    return http_get_json(
        f"https://api.openweathermap.org/data/2.5/air_pollution/forecast?{qs}"
    )


def fetch_pollen(lat: str, lon: str, key: str) -> dict | None:
    """Tomorrow.io 의 일별 꽃가루 지수. 키가 없거나 호출 실패 시 None."""
    if not key:
        return None
    qs = urllib.parse.urlencode(
        {
            "location": f"{lat},{lon}",
            "fields": "treeIndex,grassIndex,weedIndex",
            "timesteps": "1d",
            "units": "metric",
            "timezone": "Asia/Seoul",
            "apikey": key,
        }
    )
    try:
        return http_get_json(f"https://api.tomorrow.io/v4/timelines?{qs}")
    except Exception as exc:  # 꽃가루는 부가 정보라 실패해도 메시지 자체는 보내야 함
        print(f"[warn] pollen fetch failed: {exc}", file=sys.stderr)
        return None


def tomorrow_window() -> tuple[datetime, datetime]:
    now_kst = datetime.now(KST)
    start = (now_kst + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def filter_tomorrow(items: list[dict], time_key: str = "dt") -> list[dict]:
    start, end = tomorrow_window()
    out = []
    for it in items:
        ts = datetime.fromtimestamp(it[time_key], tz=KST)
        if start <= ts < end:
            out.append({**it, "_kst": ts})
    return out


def rain_text(total_mm: float, slot_count: int) -> str:
    if total_mm < 1:
        return "약한 비"
    avg_per_slot = total_mm / max(slot_count, 1)
    if slot_count <= 1 and avg_per_slot >= 4:
        return "소나기"
    if total_mm < 5:
        return "약한 비"
    if total_mm < 15:
        return "보통 비"
    if total_mm < 30:
        return "강한 비"
    return "매우 강한 비"


TIME_BUCKETS = [
    (0, 6, "새벽"),
    (6, 12, "오전"),
    (12, 18, "오후"),
    (18, 24, "저녁"),
]


def bucket_for(hour: int) -> str:
    for lo, hi, name in TIME_BUCKETS:
        if lo <= hour < hi:
            return name
    return "저녁"


def time_of_day_flow(slots: list[dict]) -> str:
    """3시간 슬롯들을 시간대별로 묶어 '오전 흐림 → 오후 비' 식으로 표현."""
    buckets: dict[str, dict[str, int]] = {}
    order: list[str] = []
    for s in slots:
        name = bucket_for(s["_kst"].hour)
        if name not in buckets:
            buckets[name] = {}
            order.append(name)
        desc = s["weather"][0]["description"]
        buckets[name][desc] = buckets[name].get(desc, 0) + 1

    sequence = [(n, max(buckets[n], key=buckets[n].get)) for n in order]

    merged: list[tuple[list[str], str]] = []
    for name, desc in sequence:
        if merged and merged[-1][1] == desc:
            merged[-1][0].append(name)
        else:
            merged.append(([name], desc))

    if len(merged) == 1:
        names, desc = merged[0]
        if len(names) == len(order):
            return desc
        return f"{'·'.join(names)} {desc}"
    return " → ".join(f"{'·'.join(ns)} {d}" for ns, d in merged)


def summarize_weather(slots: list[dict]) -> dict:
    feels = [s["main"]["feels_like"] for s in slots]

    rain_slots = []
    for s in slots:
        rain_mm = s.get("rain", {}).get("3h", 0) or 0
        snow_mm = s.get("snow", {}).get("3h", 0) or 0
        pop = s.get("pop", 0)
        if rain_mm > 0 or snow_mm > 0 or pop >= 0.5:
            rain_slots.append(
                {
                    "time": s["_kst"],
                    "rain_mm": rain_mm,
                    "snow_mm": snow_mm,
                    "pop": pop,
                }
            )

    return {
        "feels_min": min(feels) if feels else None,
        "feels_max": max(feels) if feels else None,
        "flow": time_of_day_flow(slots) if slots else "정보없음",
        "rain_slots": rain_slots,
        "max_pop": max((s.get("pop", 0) for s in slots), default=0),
    }


def summarize_pollen(payload: dict | None) -> dict:
    if not payload:
        return {}
    intervals = (
        payload.get("data", {}).get("timelines", [{}])[0].get("intervals", [])
    )
    start, end = tomorrow_window()
    for iv in intervals:
        try:
            ts = datetime.fromisoformat(iv["startTime"]).astimezone(KST)
        except (KeyError, ValueError):
            continue
        if start <= ts < end:
            v = iv.get("values", {})
            return {
                "tree": int(v.get("treeIndex", 0)),
                "grass": int(v.get("grassIndex", 0)),
                "weed": int(v.get("weedIndex", 0)),
            }
    return {}


def summarize_air(items: list[dict]) -> dict:
    if not items:
        return {}
    pm25_max = max(it["components"]["pm2_5"] for it in items)
    return {
        "pm25_max": pm25_max,
        "pm25_grade": grade(pm25_max, PM25_BREAKS),
    }


def umbrella_line(weather: dict) -> str | None:
    """비/눈 예상 시에만 한 줄. 평소엔 None."""
    rain_slots = weather["rain_slots"]
    if not rain_slots:
        return None
    first = rain_slots[0]["time"]
    last = rain_slots[-1]["time"] + timedelta(hours=3)
    total_rain = sum(s["rain_mm"] for s in rain_slots)
    total_snow = sum(s["snow_mm"] for s in rain_slots)
    when = f"{first.strftime('%H')}~{last.strftime('%H')}시"
    if total_snow:
        return f"☔ {when} 눈"
    return f"☔ {when} {rain_text(total_rain, len(rain_slots))}"


def pollen_line(pollen: dict) -> str | None:
    """꽃가루가 '높음' 이상일 때만 한 줄."""
    if not pollen:
        return None
    items = [("나무", pollen["tree"]), ("잔디", pollen["grass"]), ("잡초", pollen["weed"])]
    peak_name, peak_val = max(items, key=lambda x: x[1])
    if peak_val < 4:
        return None
    return f"🌳 {peak_name} 꽃가루 {POLLEN_LABELS[peak_val]}"


def air_line(air: dict) -> str | None:
    """미세먼지가 '나쁨' 이상일 때만 한 줄."""
    if not air or air["pm25_grade"] in ("좋음", "보통"):
        return None
    return f"😷 미세먼지 {air['pm25_grade']} ({air['pm25_max']:.0f})"


def diff_line(today_feels_max: float | None, tomorrow_feels_max: float) -> str | None:
    """오늘 대비 5°C 이상 변할 때만 한 줄."""
    if today_feels_max is None:
        return None
    delta = tomorrow_feels_max - today_feels_max
    if abs(delta) < 5:
        return None
    if delta > 0:
        return f"📈 오늘보다 {delta:.0f}°C 따뜻"
    return f"📉 오늘보다 {abs(delta):.0f}°C 추움"


def build_message(home: dict, today_feels_max: float | None) -> str:
    start, _ = tomorrow_window()
    date_str = start.strftime("%-m/%-d %a")  # "4/30 Wed"

    weather = home["weather"]
    header = f"🗓 *{date_str}* {home['label']}"
    feels = (
        f"체감 {weather['feels_min']:.0f}~{weather['feels_max']:.0f}°C"
        if weather["feels_min"] is not None
        else ""
    )
    summary = f"☁️ {weather['flow']}, {feels}".rstrip(", ")

    lines = [header, summary]
    for line in (
        umbrella_line(weather),
        air_line(home["air"]),
        pollen_line(home["pollen"]),
        diff_line(today_feels_max, weather["feels_max"]) if weather["feels_max"] is not None else None,
    ):
        if line:
            lines.append(line)
    return "\n".join(lines)


def is_routine_day(weather: dict, air: dict, pollen: dict, today_feels_max: float | None) -> bool:
    """평범한 날 = 비/눈 없음, 미세먼지 보통 이하, 꽃가루 보통 이하, 기온 변화 작음."""
    if weather["rain_slots"] or weather["max_pop"] >= 0.3:
        return False
    if air and air["pm25_grade"] not in ("좋음", "보통"):
        return False
    if pollen:
        peak = max(pollen["tree"], pollen["grass"], pollen["weed"])
        if peak >= 4:
            return False
    if today_feels_max is not None and weather["feels_max"] is not None:
        if abs(weather["feels_max"] - today_feels_max) >= 5:
            return False
    return True


def load_today_feels_max() -> float | None:
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    if data.get("for_date") != today_str:
        return None
    return data.get("feels_max")


def save_tomorrow_feels_max(feels_max: float | None) -> None:
    if feels_max is None:
        return
    start, _ = tomorrow_window()
    payload = {"for_date": start.strftime("%Y-%m-%d"), "feels_max": feels_max}
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(payload))


def send_telegram(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    ).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"Telegram API error: {resp.status} {resp.read()!r}")


def require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"환경변수 {name} 가 비어 있음", file=sys.stderr)
        sys.exit(1)
    return val


def gather_location(lat: str, lon: str, label: str, owm_key: str, pollen_key: str) -> dict | None:
    # 예보는 필수. 실패 시 예외를 그대로 올려 main 에서 처리한다.
    forecast = fetch_forecast(lat, lon, owm_key)
    weather_slots = filter_tomorrow(forecast.get("list", []))
    if not weather_slots:
        return None

    # 미세먼지는 부가 정보라 호출이 실패해도 날씨 메시지는 보낸다.
    air: dict = {}
    try:
        pollution = fetch_air_pollution(lat, lon, owm_key)
        air = summarize_air(filter_tomorrow(pollution.get("list", [])))
    except Exception as exc:  # noqa: BLE001 - 부가 정보라 광범위 캐치 의도적
        print(f"[warn] air pollution fetch failed: {exc}", file=sys.stderr)

    return {
        "label": label,
        "weather": summarize_weather(weather_slots),
        "air": air,
        "pollen": summarize_pollen(fetch_pollen(lat, lon, pollen_key)),
    }


def main() -> None:
    owm_key = require_env("OWM_API_KEY")
    tg_token = require_env("TELEGRAM_TOKEN")
    tg_chat = require_env("TELEGRAM_CHAT_ID")
    pollen_key = os.environ.get("TOMORROW_API_KEY", "")
    quiet_mode = os.environ.get("QUIET_MODE", "true").lower() != "false"

    lat = os.environ.get("HOME_LAT", "37.6018")
    lon = os.environ.get("HOME_LON", "127.0537")
    label = os.environ.get("HOME_LABEL", "이문동")

    try:
        home = gather_location(lat, lon, label, owm_key, pollen_key)
    except Exception as exc:  # noqa: BLE001 - 어떤 실패든 사용자에겐 알려야 함
        print(f"[error] 예보 조회 실패: {exc}", file=sys.stderr)
        send_telegram(tg_token, tg_chat, "⚠️ 내일 예보 데이터를 가져오지 못했어요.")
        return
    if home is None:
        send_telegram(tg_token, tg_chat, "⚠️ 내일 예보 데이터를 가져오지 못했어요.")
        return

    today_feels_max = load_today_feels_max()
    save_tomorrow_feels_max(home["weather"]["feels_max"])

    if quiet_mode and is_routine_day(
        home["weather"], home["air"], home["pollen"], today_feels_max
    ):
        print("[info] 평범한 날이라 알림 생략")
        return

    msg = build_message(home, today_feels_max)
    send_telegram(tg_token, tg_chat, msg)
    print(msg)


if __name__ == "__main__":
    main()
