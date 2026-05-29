"""weather_notify.py 의 순수 함수 단위 테스트 (표준 라이브러리만 사용).

네트워크 없이 돌아간다.  실행:  python -m unittest -v
"""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import weather_notify as wn

KST = wn.KST


def slot(hour, *, feels=20.0, desc="맑음", rain=0.0, snow=0.0, pop=0.0, day=30):
    """filter_tomorrow 를 통과한 예보 슬롯 한 칸을 흉내 낸다."""
    item = {
        "_kst": datetime(2026, 5, day, hour, tzinfo=KST),
        "main": {"feels_like": feels},
        "weather": [{"description": desc}],
        "pop": pop,
    }
    if rain:
        item["rain"] = {"3h": rain}
    if snow:
        item["snow"] = {"3h": snow}
    return item


class GradeTest(unittest.TestCase):
    def test_pm25_breakpoints(self):
        self.assertEqual(wn.grade(10, wn.PM25_BREAKS), "좋음")
        self.assertEqual(wn.grade(15, wn.PM25_BREAKS), "좋음")
        self.assertEqual(wn.grade(30, wn.PM25_BREAKS), "보통")
        self.assertEqual(wn.grade(50, wn.PM25_BREAKS), "나쁨")
        self.assertEqual(wn.grade(200, wn.PM25_BREAKS), "매우나쁨")


class RainTextTest(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(wn.rain_text(0.5, 1), "약한 비")
        self.assertEqual(wn.rain_text(4.0, 1), "소나기")  # 단일 슬롯 집중호우
        self.assertEqual(wn.rain_text(3.0, 2), "약한 비")
        self.assertEqual(wn.rain_text(10.0, 3), "보통 비")
        self.assertEqual(wn.rain_text(20.0, 3), "강한 비")
        self.assertEqual(wn.rain_text(40.0, 3), "매우 강한 비")


class BucketTest(unittest.TestCase):
    def test_bucket_for(self):
        self.assertEqual(wn.bucket_for(3), "새벽")
        self.assertEqual(wn.bucket_for(9), "오전")
        self.assertEqual(wn.bucket_for(15), "오후")
        self.assertEqual(wn.bucket_for(21), "저녁")


class FlowTest(unittest.TestCase):
    def test_single_bucket_returns_desc_only(self):
        slots = [slot(9, desc="흐림"), slot(10, desc="흐림")]
        self.assertEqual(wn.time_of_day_flow(slots), "흐림")

    def test_two_buckets(self):
        slots = [slot(9, desc="맑음"), slot(15, desc="비")]
        self.assertEqual(wn.time_of_day_flow(slots), "오전 맑음 → 오후 비")

    def test_consecutive_same_desc_merged(self):
        slots = [slot(9, desc="비"), slot(15, desc="비"), slot(21, desc="맑음")]
        self.assertEqual(wn.time_of_day_flow(slots), "오전·오후 비 → 저녁 맑음")


class SummarizeWeatherTest(unittest.TestCase):
    def test_summary_fields(self):
        slots = [
            slot(9, feels=15.0, desc="맑음", pop=0.1),
            slot(15, feels=22.0, desc="비", rain=5.0, pop=0.8),
        ]
        s = wn.summarize_weather(slots)
        self.assertEqual(s["feels_min"], 15.0)
        self.assertEqual(s["feels_max"], 22.0)
        self.assertEqual(s["max_pop"], 0.8)
        self.assertEqual(len(s["rain_slots"]), 1)
        self.assertEqual(s["flow"], "오전 맑음 → 오후 비")

    def test_empty(self):
        s = wn.summarize_weather([])
        self.assertIsNone(s["feels_min"])
        self.assertEqual(s["rain_slots"], [])
        self.assertEqual(s["flow"], "정보없음")


class UmbrellaLineTest(unittest.TestCase):
    def test_none_when_dry(self):
        weather = wn.summarize_weather([slot(9, desc="맑음")])
        self.assertIsNone(wn.umbrella_line(weather))

    def test_rain(self):
        weather = wn.summarize_weather([slot(15, desc="비", rain=10.0, pop=0.8)])
        line = wn.umbrella_line(weather)
        self.assertIsNotNone(line)
        self.assertTrue(line.startswith("☔"))
        self.assertIn("15~18시", line)

    def test_snow(self):
        weather = wn.summarize_weather([slot(6, desc="눈", snow=2.0, pop=0.9)])
        self.assertIn("눈", wn.umbrella_line(weather))


class PollenLineTest(unittest.TestCase):
    def test_below_threshold(self):
        self.assertIsNone(wn.pollen_line({"tree": 2, "grass": 1, "weed": 3}))

    def test_high(self):
        self.assertEqual(wn.pollen_line({"tree": 4, "grass": 1, "weed": 0}), "🌳 나무 꽃가루 높음")

    def test_empty(self):
        self.assertIsNone(wn.pollen_line({}))


class AirLineTest(unittest.TestCase):
    def test_good_or_normal_is_silent(self):
        self.assertIsNone(wn.air_line({"pm25_max": 30, "pm25_grade": "보통"}))
        self.assertIsNone(wn.air_line({}))

    def test_bad(self):
        self.assertEqual(wn.air_line({"pm25_max": 76.0, "pm25_grade": "나쁨"}), "😷 미세먼지 나쁨 (76)")


class SummarizeAirTest(unittest.TestCase):
    def test_max_and_grade(self):
        items = [
            {"components": {"pm2_5": 40}},
            {"components": {"pm2_5": 80}},
        ]
        s = wn.summarize_air(items)
        self.assertEqual(s["pm25_max"], 80)
        self.assertEqual(s["pm25_grade"], "매우나쁨")

    def test_empty(self):
        self.assertEqual(wn.summarize_air([]), {})


class DiffLineTest(unittest.TestCase):
    def test_none_when_no_baseline(self):
        self.assertIsNone(wn.diff_line(None, 25.0))

    def test_none_when_small_delta(self):
        self.assertIsNone(wn.diff_line(20.0, 22.0))

    def test_warmer(self):
        self.assertEqual(wn.diff_line(20.0, 26.0), "📈 오늘보다 6°C 따뜻")

    def test_colder(self):
        self.assertEqual(wn.diff_line(26.0, 19.0), "📉 오늘보다 7°C 추움")


class RoutineDayTest(unittest.TestCase):
    def _weather(self, **kw):
        base = {"rain_slots": [], "max_pop": 0.1, "feels_max": 20.0}
        base.update(kw)
        return base

    def test_routine(self):
        self.assertTrue(
            wn.is_routine_day(
                self._weather(),
                {"pm25_max": 30, "pm25_grade": "보통"},
                {"tree": 1, "grass": 0, "weed": 2},
                18.0,
            )
        )

    def test_rain_breaks_routine(self):
        self.assertFalse(wn.is_routine_day(self._weather(rain_slots=[{"x": 1}]), {}, {}, None))

    def test_high_pop_breaks_routine(self):
        self.assertFalse(wn.is_routine_day(self._weather(max_pop=0.5), {}, {}, None))

    def test_bad_air_breaks_routine(self):
        self.assertFalse(
            wn.is_routine_day(self._weather(), {"pm25_max": 90, "pm25_grade": "나쁨"}, {}, None)
        )

    def test_high_pollen_breaks_routine(self):
        self.assertFalse(
            wn.is_routine_day(self._weather(), {}, {"tree": 4, "grass": 0, "weed": 0}, None)
        )

    def test_big_temp_swing_breaks_routine(self):
        self.assertFalse(wn.is_routine_day(self._weather(feels_max=20.0), {}, {}, 10.0))


class SummarizePollenTest(unittest.TestCase):
    def test_picks_tomorrow_interval(self):
        start, _ = wn.tomorrow_window()
        payload = {
            "data": {
                "timelines": [
                    {
                        "intervals": [
                            {
                                "startTime": start.isoformat(),
                                "values": {
                                    "treeIndex": 3,
                                    "grassIndex": 1,
                                    "weedIndex": 2,
                                },
                            }
                        ]
                    }
                ]
            }
        }
        self.assertEqual(wn.summarize_pollen(payload), {"tree": 3, "grass": 1, "weed": 2})

    def test_none_payload(self):
        self.assertEqual(wn.summarize_pollen(None), {})


class CacheTest(unittest.TestCase):
    def setUp(self):
        self._orig = wn.CACHE_PATH
        self._tmp = tempfile.TemporaryDirectory()
        wn.CACHE_PATH = Path(self._tmp.name) / "last_forecast.json"

    def tearDown(self):
        wn.CACHE_PATH = self._orig
        self._tmp.cleanup()

    def test_load_missing_returns_none(self):
        self.assertIsNone(wn.load_today_feels_max())

    def test_save_writes_tomorrow_date(self):
        wn.save_tomorrow_feels_max(22.5)
        data = json.loads(wn.CACHE_PATH.read_text())
        start, _ = wn.tomorrow_window()
        self.assertEqual(data["for_date"], start.strftime("%Y-%m-%d"))
        self.assertEqual(data["feels_max"], 22.5)

    def test_save_none_is_noop(self):
        wn.save_tomorrow_feels_max(None)
        self.assertFalse(wn.CACHE_PATH.exists())

    def test_load_matches_today(self):
        today = datetime.now(KST).strftime("%Y-%m-%d")
        wn.CACHE_PATH.write_text(json.dumps({"for_date": today, "feels_max": 19.0}))
        self.assertEqual(wn.load_today_feels_max(), 19.0)

    def test_load_ignores_stale_date(self):
        wn.CACHE_PATH.write_text(json.dumps({"for_date": "2000-01-01", "feels_max": 19.0}))
        self.assertIsNone(wn.load_today_feels_max())


class BuildMessageTest(unittest.TestCase):
    def test_contains_core_lines(self):
        weather = wn.summarize_weather(
            [
                slot(9, feels=15.0, desc="맑음", pop=0.1),
                slot(15, feels=22.0, desc="비", rain=10.0, pop=0.8),
            ]
        )
        home = {
            "label": "테스트동",
            "weather": weather,
            "air": {"pm25_max": 80.0, "pm25_grade": "나쁨"},
            "pollen": {"tree": 4, "grass": 0, "weed": 0},
        }
        msg = wn.build_message(home, today_feels_max=15.0)
        self.assertTrue(msg.startswith("🗓"))
        self.assertIn("테스트동", msg)
        self.assertIn("체감 15~22°C", msg)
        self.assertIn("😷", msg)  # 미세먼지 나쁨
        self.assertIn("🌳", msg)  # 꽃가루 높음
        self.assertIn("☔", msg)  # 비


if __name__ == "__main__":
    unittest.main()
