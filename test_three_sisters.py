"""인공지능의 세자매 단위 테스트 (MockLLM 기반, 네트워크/API 키 없음).

실행:  python -m unittest discover -v
"""
import tempfile
import unittest
from pathlib import Path

from three_sisters import cli
from three_sisters.chronicle import Chronicle, Decision, derive_tags, now_iso
from three_sisters.council import Council
from three_sisters.llm import Message, MockLLM, get_llm
from three_sisters.scene import _sample_result, render_scene, write_scene
from three_sisters.scene_html import (
    find_art,
    render_council_html,
    render_interactive_html,
    write_council_html,
    write_interactive_html,
)

# 웹 서버 테스트는 fastapi/httpx 가 있을 때만 (코어 스위트는 표준 라이브러리만으로 통과).
try:
    from fastapi.testclient import TestClient

    from three_sisters.server import create_app

    _HAS_WEB = True
except Exception:  # noqa: BLE001
    _HAS_WEB = False


class DeriveTagsTest(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(derive_tags("이직 할까 고민"), ["이직", "할까", "고민"])

    def test_drops_one_char(self):
        self.assertEqual(derive_tags("집 살까 말까"), ["살까", "말까"])  # '집'은 1글자


class ChronicleTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.c = Chronicle(Path(self._tmp.name) / "c.jsonl")

    def tearDown(self):
        self._tmp.cleanup()

    def test_record_and_all(self):
        self.c.record(Decision(now_iso(), "이직할까", "남는다", "안정", derive_tags("이직할까")))
        got = self.c.all()
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].choice, "남는다")

    def test_recall_by_tag(self):
        self.c.record(Decision(now_iso(), "이직 고민", "남는다", "", derive_tags("이직 고민")))
        self.c.record(Decision(now_iso(), "이사 갈까", "간다", "", derive_tags("이사 갈까")))
        hits = self.c.recall(derive_tags("이직 다시 고민"))
        self.assertEqual([h.dilemma for h in hits], ["이직 고민"])

    def test_recall_empty_when_no_overlap(self):
        self.c.record(Decision(now_iso(), "이사 갈까", "간다", "", derive_tags("이사 갈까")))
        self.assertEqual(self.c.recall(derive_tags("주식 살까")), [])


class MockLLMTest(unittest.TestCase):
    def _counsel(self, role):
        system = ["서문", f"[ROLE:{role}]\n페르소나"]
        return MockLLM().complete(system, [Message("user", "고민: 이직할까\n지난 기록:\n- (없음)")])

    def test_roles_differ_and_echo_dilemma(self):
        opt, pes, pra = self._counsel("optimist"), self._counsel("pessimist"), self._counsel("pragmatist")
        self.assertIn("기회", opt)
        self.assertIn("최악", pes)
        self.assertIn("비용", pra)
        for text in (opt, pes, pra):
            self.assertIn("이직할까", text)

    def test_synth_default_role(self):
        out = MockLLM().complete("[ROLE:synth] 종합하라", [Message("user", "고민: 이직할까")])
        self.assertIn("트레이드오프", out)


class CouncilTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.council = Council(get_llm(), Chronicle(Path(self._tmp.name) / "c.jsonl"))

    def tearDown(self):
        self._tmp.cleanup()

    def test_deliberate_three_plus_synthesis(self):
        r = self.council.deliberate("새 노트북 살까")
        self.assertEqual(set(r.counsels), {"여명", "황혼", "잿불"})
        self.assertTrue(all(r.counsels.values()))
        self.assertTrue(r.synthesis)
        self.assertEqual(r.recalled, [])  # 첫 결정엔 회상 없음

    def test_seal_then_recall_next_time(self):
        r1 = self.council.deliberate("이직 고민")
        self.council.seal(r1, "남는다", "안정이 좋다")
        r2 = self.council.deliberate("이직 다시 고민")
        self.assertEqual(len(r2.recalled), 1)
        self.assertEqual(r2.recalled[0].choice, "남는다")


class CliSmokeTest(unittest.TestCase):
    def test_one_round_with_fake_io(self):
        inputs = iter(["주말에 여행 갈까", "간다", "오래 못 쉬었다", ""])
        out_lines: list[str] = []
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "c.jsonl")
            scene = str(Path(d) / "council.html")
            cli.run(
                llm=MockLLM(),
                chronicle_path=path,
                input_fn=lambda _prompt="": next(inputs),
                output_fn=out_lines.append,
                scene_path=scene,
            )
            text = "\n".join(out_lines)
            self.assertIn("인공지능의 세자매", text)
            self.assertIn("여명", text)
            self.assertIn("서기의 종합", text)
            self.assertEqual(len(Chronicle(path).all()), 1)  # 결정이 연대기에 기록됨
            self.assertTrue(Path(scene).exists())  # 장면 HTML 이 생성됨


class SceneTest(unittest.TestCase):
    def test_render_has_elements(self):
        svg = render_scene(_sample_result())
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.rstrip().endswith("</svg>"))
        for token in ("인공지능의 세자매", "여명", "황혼", "잿불", "운명이 말하다"):
            self.assertIn(token, svg)

    def test_write_scene(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_scene(path=str(Path(d) / "scene.svg"))
            self.assertTrue(p.exists())
            self.assertGreater(p.stat().st_size, 800)

    def test_html_fallback_inlines_svg_with_live_text(self):
        # 아트 없음(art=False) → SVG 폴백, 실시간 텍스트 포함
        page = render_council_html(_sample_result(), art=False)
        self.assertIn("<!doctype html>", page)
        self.assertIn("<svg", page)
        self.assertIn("되돌릴 수 있는가", page)

    def test_html_uses_art_when_present(self):
        # 가짜 이미지 파일을 주면 base64 임베드 + 본문 오버레이(헤더는 아트에 베이크됨)
        with tempfile.TemporaryDirectory() as d:
            art = Path(d) / "council.png"
            art.write_bytes(b"\x89PNG\r\n\x1a\n fake png bytes")
            page = render_council_html(_sample_result(), art=art)
            self.assertIn("data:image/png;base64,", page)
            self.assertIn('class="fate"', page)             # 오버레이 박스 존재
            self.assertIn("되돌릴 수 있는가", page)            # 실제 종합이 박스에
            self.assertIn("지금 다니는 회사", page)            # 고민도 함께

    def test_find_art_prefers_council(self):
        with tempfile.TemporaryDirectory() as d:
            assets = Path(d)
            (assets / "zzz.png").write_bytes(b"x")
            (assets / "council.png").write_bytes(b"y")
            self.assertEqual(find_art(assets).name, "council.png")

    def test_find_art_falls_back_to_any_image(self):
        with tempfile.TemporaryDirectory() as d:
            assets = Path(d)
            (assets / "scene.webp").write_bytes(b"x")
            self.assertEqual(find_art(assets).name, "scene.webp")

    def test_find_art_none_when_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(find_art(Path(d)))

    def test_write_council_html(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_council_html(path=str(Path(d) / "c.html"), art=False)
            self.assertTrue(p.exists())
            self.assertGreater(p.stat().st_size, 400)

    def test_interactive_html_has_input_and_js(self):
        with tempfile.TemporaryDirectory() as d:
            art = Path(d) / "council.png"
            art.write_bytes(b"\x89PNG\r\n\x1a\n fake")
            page = render_interactive_html(_sample_result(), art=art)
            self.assertIn('id="q"', page)            # 입력창
            self.assertIn("평의회에 묻다", page)        # 버튼
            self.assertIn("function council", page)   # 클라이언트 목 두뇌
            self.assertIn("data:image/png;base64,", page)
            for sid in ('id="dawn"', 'id="dusk"', 'id="ember"', 'id="synth"'):
                self.assertIn(sid, page)

    def test_write_interactive_html(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_interactive_html(path=str(Path(d) / "sub" / "index.html"), art=False)
            self.assertTrue(p.exists())  # 부모 폴더 자동 생성
            self.assertIn("function council", p.read_text(encoding="utf-8"))


@unittest.skipUnless(_HAS_WEB, "fastapi/httpx 미설치 — 웹 서버 테스트 건너뜀")
class ServerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        chron = str(Path(self._tmp.name) / "chronicle.jsonl")
        self.client = TestClient(create_app(MockLLM(), chronicle_path=chron))

    def tearDown(self):
        self._tmp.cleanup()

    def test_index_serves_interactive_page(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("평의회에 묻다", r.text)
        self.assertIn("api/ask", r.text)  # 페이지가 백엔드를 부른다

    def test_health_reports_mock_brain(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["brain"], "mock")

    def test_ask_returns_three_sisters_and_synthesis(self):
        r = self.client.post("/api/ask", json={"dilemma": "이직할까"})
        self.assertEqual(r.status_code, 200)
        j = r.json()
        for key in ("dawn", "dusk", "ember", "synth"):
            self.assertTrue(j[key], f"{key} 비어있음")
        self.assertIn("이직할까", j["dawn"])     # 목이 고민을 반영
        self.assertEqual(j["brain"], "mock")

    def test_ask_empty_is_400(self):
        r = self.client.post("/api/ask", json={"dilemma": "   "})
        self.assertEqual(r.status_code, 400)

    def test_seal_then_recall(self):
        sealed = self.client.post(
            "/api/seal",
            json={"dilemma": "이직 고민", "choice": "이직한다", "rationale": "성장"},
        )
        self.assertEqual(sealed.status_code, 200)
        # 태그('이직')가 겹치는 새 고민 → 과거 결정을 회상해야 한다
        r = self.client.post("/api/ask", json={"dilemma": "이직 다시 고민"})
        recalled = r.json()["recalled"]
        self.assertTrue(any(x["choice"] == "이직한다" for x in recalled))


if __name__ == "__main__":
    unittest.main()
