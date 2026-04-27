"""내일 날씨, 미세먼지, 강수 정보를 텔레그램으로 보내는 스크립트.

GitHub Actions cron으로 매일 한 번 실행되어 PC가 꺼져 있어도 알림이 도착한다.
필요한 환경변수:
  OWM_API_KEY       OpenWeatherMap API 키
  TELEGRAM_TOKEN    텔레그램 봇 토큰
  TELEGRAM_CHAT_ID  메시지를 받을 채팅 ID
  LAT, LON          위도/경도 (예: 37.5665, 126.9780  서울시청)
"""
from __future__ import annotations

import os
import sys
import urllib.parse
import urllib.request
import json
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

# OpenWeatherMap Air Pollution API 의 PM2.5 / PM10 µg/m³ 한국 환경부 기준 등급
# 참고: https://www.airkorea.or.kr (좋음/보통/나쁨/매우나쁨)
PM25_BREAKS = [(15, "좋음"), (35, "보통"), (75, "나쁨"), (float("inf"), "매우나쁨")]
PM10_BREAKS = [(30, "좋음"), (80, "보통"), (150, "나쁨"), (float("inf"), "매우나쁨")]


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


def summarize_weather(slots: list[dict]) -> dict:
    """OpenWeatherMap 3시간 단위 forecast 슬롯들을 요약."""
    temps = [s["main"]["temp"] for s in slots]
    feels = [s["main"]["feels_like"] for s in slots]
    descriptions: dict[str, int] = {}
    for s in slots:
        desc = s["weather"][0]["description"]
        descriptions[desc] = descriptions.get(desc, 0) + 1
    main_desc = max(descriptions, key=descriptions.get) if descriptions else "정보없음"

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
        "t_min": min(temps) if temps else None,
        "t_max": max(temps) if temps else None,
        "feels_min": min(feels) if feels else None,
        "feels_max": max(feels) if feels else None,
        "main_desc": main_desc,
        "rain_slots": rain_slots,
        "max_pop": max((s.get("pop", 0) for s in slots), default=0),
    }


def summarize_air(items: list[dict]) -> dict:
    if not items:
        return {}
    pm25 = [it["components"]["pm2_5"] for it in items]
    pm10 = [it["components"]["pm10"] for it in items]
    pm25_max = max(pm25)
    pm10_max = max(pm10)
    return {
        "pm25_max": pm25_max,
        "pm10_max": pm10_max,
        "pm25_grade": grade(pm25_max, PM25_BREAKS),
        "pm10_grade": grade(pm10_max, PM10_BREAKS),
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
        parts.append(f"비 약 {total_rain:.1f}mm")
    if total_snow:
        parts.append(f"눈 약 {total_snow:.1f}mm")
    parts.append(f"({when})")
    return "  ".join(parts)


def build_message(weather: dict, air: dict, location_label: str) -> str:
    start, _ = tomorrow_window()
    date_str = start.strftime("%m월 %d일 (%a)")

    lines = [f"🗓 *내일 날씨* — {date_str}  _{location_label}_", ""]
    lines.append(f"☁️ 하늘: {weather['main_desc']}")
    if weather["t_min"] is not None:
        lines.append(
            f"🌡 기온: {weather['t_min']:.0f}°C ~ {weather['t_max']:.0f}°C"
            f"  (체감 {weather['feels_min']:.0f}°C ~ {weather['feels_max']:.0f}°C)"
        )

    lines.append(umbrella_advice(weather))

    if air:
        lines.append(
            f"😷 미세먼지 PM10: {air['pm10_max']:.0f} µg/m³  ({air['pm10_grade']})"
        )
        lines.append(
            f"😷 초미세먼지 PM2.5: {air['pm25_max']:.0f} µg/m³  ({air['pm25_grade']})"
        )

    return "\n".join(lines)


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
    lat = os.environ.get("LAT", "37.5665")
    lon = os.environ.get("LON", "126.9780")
    label = os.environ.get("LOCATION_LABEL", "서울")

    forecast = fetch_forecast(lat, lon, owm_key)
    pollution = fetch_air_pollution(lat, lon, owm_key)

    weather_slots = filter_tomorrow(forecast.get("list", []))
    if not weather_slots:
        send_telegram(
            tg_token, tg_chat, "⚠️ 내일 예보 데이터를 가져오지 못했어요."
        )
        return

    air_slots = filter_tomorrow(pollution.get("list", []))

    msg = build_message(
        summarize_weather(weather_slots),
        summarize_air(air_slots),
        label,
    )
    send_telegram(tg_token, tg_chat, msg)
    print(msg)


if __name__ == "__main__":
    main()
