"""내일 날씨, 미세먼지, 꽃가루, 강수 정보를 텔레그램으로 보내는 스크립트.

GitHub Actions cron으로 매일 한 번 실행되어 PC가 꺼져 있어도 알림이 도착한다.
필요한 환경변수:
  OWM_API_KEY        OpenWeatherMap API 키
  TELEGRAM_TOKEN     텔레그램 봇 토큰
  TELEGRAM_CHAT_ID   메시지를 받을 채팅 ID
  LAT, LON           위도/경도 (예: 37.5665, 126.9780  서울시청)
선택 환경변수:
  TOMORROW_API_KEY   Tomorrow.io 키 (있으면 꽃가루/알레르기 지수 포함)
  QUIET_MODE         "false" 로 두면 평범한 날에도 알림 발송 (기본: true=무음)
"""
from __future__ import annotations

import os
import sys
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


def http_get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_forecast(lat: str, lon: str, key: str) -> dict:
    qs = urllib.parse.urlencode(
        {"lat": lat, "lon": lon, "appid": key, "units": "metric", "lang": "kr"}
    )
    return http_get_json(f"https://api.openweathermap.org/data/2.5/forecast?{qs}")


def fetch_air_pollution(lat: str, lon: str, key: str) -> dict:
    qs = urllib.parse.urlencode({"lat": lat, "lon": lon, "appid": key})
    # forecast 엔드포인트는 시간별 대기질 예보(약 4일치)
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


# 강수량(3h 슬롯 합계, mm) → 사람이 이해하기 쉬운 텍스트
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


# 시간대 버킷: 새벽(0~6), 오전(6~12), 오후(12~18), 저녁(18~24)
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

    # 각 버킷의 가장 흔한 묘사
    sequence = [(n, max(buckets[n], key=buckets[n].get)) for n in order]

    # 인접 버킷이 같은 묘사면 합쳐서 "오전·오후 흐림"
    merged: list[tuple[list[str], str]] = []
    for name, desc in sequence:
        if merged and merged[-1][1] == desc:
            merged[-1][0].append(name)
        else:
            merged.append(([name], desc))

    if len(merged) == 1:
        names, desc = merged[0]
        if len(names) == len(order):
            return f"하루 종일 {desc}"
        return f"{'·'.join(names)} {desc}"
    return " → ".join(f"{'·'.join(ns)} {d}" for ns, d in merged)


def summarize_weather(slots: list[dict]) -> dict:
    """OpenWeatherMap 3시간 단위 forecast 슬롯들을 요약."""
    feels = [s["main"]["feels_like"] for s in slots]

    rain_slots = []
    for s in slots:
        rain_mm = s.get("rain", {}).get("3h", 0) or 0
        snow_mm = s.get("snow", {}).get("3h", 0) or 0
        pop = s.get("pop", 0)  # 강수확률 0~1
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
    """Tomorrow.io 응답에서 내일 날짜의 tree/grass/weed 지수를 뽑아낸다."""
    if not payload:
        return {}
    intervals = (
        payload.get("data", {}).get("timelines", [{}])[0].get("intervals", [])
    )
    start, end = tomorrow_window()
    for iv in intervals:
        # startTime 예: "2026-04-28T00:00:00+09:00"
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


def umbrella_advice(weather: dict) -> str:
    rain_slots = weather["rain_slots"]
    if not rain_slots:
        if weather["max_pop"] >= 0.3:
            return f"☂️ 강수확률 {int(weather['max_pop']*100)}%  접이식 우산 챙기면 안심"
        return "🌂 우산 필요 없을 듯"

    first = rain_slots[0]["time"]
    last = rain_slots[-1]["time"] + timedelta(hours=3)
    total_rain = sum(s["rain_mm"] for s in rain_slots)
    total_snow = sum(s["snow_mm"] for s in rain_slots)

    when = f"{first.strftime('%H시')}~{last.strftime('%H시')}"
    parts = ["☔ 우산 필수"]
    if total_rain:
        parts.append(rain_text(total_rain, len(rain_slots)))
    if total_snow:
        parts.append("눈 옴")
    parts.append(f"({when})")
    return "  ".join(parts)


def pollen_line(pollen: dict) -> str | None:
    if not pollen:
        return None
    items = [("나무", pollen["tree"]), ("잔디", pollen["grass"]), ("잡초", pollen["weed"])]
    peak_name, peak_val = max(items, key=lambda x: x[1])
    if peak_val == 0:
        return "🌳 꽃가루: 없음"
    parts = [f"{n} {POLLEN_LABELS.get(v, '?')}" for n, v in items if v > 0]
    headline = "🌳 꽃가루: " + " / ".join(parts)
    if peak_val >= 4:
        headline += f"  ⚠️ {peak_name} 알레르기 주의"
    return headline


def diff_line(today_feels_max: float | None, tomorrow_feels_max: float) -> str | None:
    """오늘(어제 시점에 캐시된 예보)과 내일을 비교한 한 줄."""
    if today_feels_max is None:
        return None
    delta = tomorrow_feels_max - today_feels_max
    if abs(delta) < 2:
        return "📊 오늘과 비슷한 날씨"
    if delta > 0:
        return f"📈 오늘보다 {delta:.0f}°C 더 따뜻해질 듯"
    return f"📉 오늘보다 {abs(delta):.0f}°C 더 추워질 듯"


def build_message(
    weather: dict,
    air: dict,
    pollen: dict,
    location_label: str,
    today_feels_max: float | None,
) -> str:
    start, _ = tomorrow_window()
    date_str = start.strftime("%m월 %d일 (%a)")

    lines = [f"🗓 *내일 날씨* — {date_str}  _{location_label}_", ""]
    lines.append(f"☁️ {weather['flow']}")
    if weather["feels_min"] is not None:
        lines.append(
            f"🌡 체감기온: {weather['feels_min']:.0f}°C ~ {weather['feels_max']:.0f}°C"
        )

    diff = diff_line(today_feels_max, weather["feels_max"]) if weather["feels_max"] is not None else None
    if diff:
        lines.append(diff)

    lines.append(umbrella_advice(weather))

    if air:
        lines.append(
            f"😷 미세먼지: {air['pm25_max']:.0f} µg/m³  ({air['pm25_grade']})"
        )

    pollen_text = pollen_line(pollen)
    if pollen_text:
        lines.append(pollen_text)

    return "\n".join(lines)


def is_routine_day(weather: dict, air: dict, pollen: dict, today_feels_max: float | None) -> bool:
    """평범한 날 = 비/눈 없음, 미세먼지 보통 이하, 꽃가루 보통 이하, 기온 변화 ±2°C."""
    if weather["rain_slots"] or weather["max_pop"] >= 0.3:
        return False
    if air and air["pm25_grade"] not in ("좋음", "보통"):
        return False
    if pollen:
        peak = max(pollen["tree"], pollen["grass"], pollen["weed"])
        if peak >= 4:  # 높음 이상
            return False
    if today_feels_max is not None and weather["feels_max"] is not None:
        if abs(weather["feels_max"] - today_feels_max) >= 5:
            return False
    return True


def load_today_feels_max() -> float | None:
    """어제 시점에 저장한 '내일=오늘' 예보의 체감 최고기온을 읽어온다."""
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    if data.get("for_date") != today_str:
        # 캐시가 오래됐거나 날짜 불일치 → 비교 생략
        return None
    return data.get("feels_max")


def save_tomorrow_feels_max(feels_max: float | None) -> None:
    if feels_max is None:
        return
    start, _ = tomorrow_window()
    payload = {
        "for_date": start.strftime("%Y-%m-%d"),
        "feels_max": feels_max,
    }
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


def main() -> None:
    owm_key = require_env("OWM_API_KEY")
    tg_token = require_env("TELEGRAM_TOKEN")
    tg_chat = require_env("TELEGRAM_CHAT_ID")
    pollen_key = os.environ.get("TOMORROW_API_KEY", "")
    lat = os.environ.get("LAT", "37.5665")
    lon = os.environ.get("LON", "126.9780")
    label = os.environ.get("LOCATION_LABEL", "서울")
    quiet_mode = os.environ.get("QUIET_MODE", "true").lower() != "false"

    forecast = fetch_forecast(lat, lon, owm_key)
    pollution = fetch_air_pollution(lat, lon, owm_key)
    pollen_raw = fetch_pollen(lat, lon, pollen_key)

    weather_slots = filter_tomorrow(forecast.get("list", []))
    if not weather_slots:
        send_telegram(
            tg_token, tg_chat, "⚠️ 내일 예보 데이터를 가져오지 못했어요."
        )
        return

    air_slots = filter_tomorrow(pollution.get("list", []))

    weather = summarize_weather(weather_slots)
    air = summarize_air(air_slots)
    pollen = summarize_pollen(pollen_raw)
    today_feels_max = load_today_feels_max()

    # 다음 실행 때 비교에 쓰도록 내일 예보 캐시
    save_tomorrow_feels_max(weather["feels_max"])

    if quiet_mode and is_routine_day(weather, air, pollen, today_feels_max):
        print("[info] 평범한 날이라 알림 생략")
        return

    msg = build_message(weather, air, pollen, label, today_feels_max)
    send_telegram(tg_token, tg_chat, msg)
    print(msg)


if __name__ == "__main__":
    main()
