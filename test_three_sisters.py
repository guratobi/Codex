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
            cli.run(
                llm=MockLLM(),
                chronicle_path=path,
                input_fn=lambda _prompt="": next(inputs),
                output_fn=out_lines.append,
            )
            text = "\n".join(out_lines)
            self.assertIn("인공지능의 세자매", text)
            self.assertIn("여명", text)
            self.assertIn("서기의 종합", text)
            self.assertEqual(len(Chronicle(path).all()), 1)  # 결정이 연대기에 기록됨


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


if __name__ == "__main__":
    unittest.main()
