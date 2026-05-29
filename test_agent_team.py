"""agent_team 프로토타입 단위 테스트 (표준 라이브러리 + MockLLM, 네트워크 없음).

실행:  python -m unittest discover -v
"""
import tempfile
import unittest
from pathlib import Path

from agent_team.agents import Planner, Reviewer, Worker, build_user_message
from agent_team.journal import Journal, JournalEntry, derive_tags, now_iso
from agent_team.llm import DriftingMockLLM, MockLLM, Message, get_llm
from agent_team.team import Team
from agent_team.drift import diagnose
from agent_team.dashboard import build_demo_data, render_html, render_svg, write_dashboard


def entry(task="주간 뉴스레터 작성", lesson="교훈", tags=None, agent="기획자"):
    return JournalEntry(
        ts=now_iso(),
        agent=agent,
        task=task,
        did="d",
        worked="w",
        stuck="s",
        lesson=lesson,
        tags=tags if tags is not None else derive_tags(task),
    )


class DeriveTagsTest(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(derive_tags("주간 뉴스레터 작성"), ["주간", "뉴스레터", "작성"])

    def test_drops_short_and_dupes(self):
        self.assertEqual(derive_tags("팀 팀 보고서"), ["보고서"])  # '팀'은 1글자라 제외


class JournalTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.j = Journal(Path(self._tmp.name) / "j.jsonl")

    def tearDown(self):
        self._tmp.cleanup()

    def test_record_roundtrip(self):
        e = entry()
        self.j.record(e)
        got = self.j.all_entries()
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].lesson, e.lesson)
        self.assertEqual(got[0].tags, e.tags)

    def test_recall_by_tag_overlap(self):
        self.j.record(entry(task="주간 뉴스레터 작성", lesson="A"))
        self.j.record(entry(task="월간 매출 보고서", lesson="B"))
        hits = self.j.recall(derive_tags("주간 뉴스레터 작성"))
        self.assertEqual([h.lesson for h in hits], ["A"])

    def test_recall_before_filter(self):
        self.j.record(entry(lesson="과거"))
        cutoff = now_iso()
        self.j.record(entry(lesson="현재"))
        hits = self.j.recall(derive_tags("주간 뉴스레터 작성"), before=cutoff)
        self.assertEqual([h.lesson for h in hits], ["과거"])

    def test_wisdom_dedup_latest_first(self):
        self.j.record(entry(lesson="A"))
        self.j.record(entry(lesson="B"))
        self.j.record(entry(lesson="A"))
        self.assertEqual(self.j.wisdom(), ["A", "B"])


class MockLLMTest(unittest.TestCase):
    def setUp(self):
        self.llm = MockLLM()

    def _ask(self, role, lessons=()):
        msg = build_user_message("주간 뉴스레터 작성", list(lessons), prior="")
        return self.llm.complete(f"[ROLE:{role}] 테스트", [Message("user", msg)])

    def test_planner_three_steps(self):
        out = self._ask("planner")
        self.assertIn("3단계", out)
        self.assertIn("참고할 과거 교훈 없음", out)

    def test_reviewer_flags_human(self):
        self.assertIn("🧑 사람 결정 필요", self._ask("reviewer"))

    def test_reflects_recalled_lessons(self):
        out = self._ask("worker", lessons=["요지를 앞에"])
        self.assertIn("과거 교훈 1건 반영", out)


class AgentTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.j = Journal(Path(self._tmp.name) / "j.jsonl")

    def tearDown(self):
        self._tmp.cleanup()

    def test_run_writes_one_entry(self):
        res = Planner(get_llm(), self.j).run("주간 뉴스레터 작성")
        self.assertEqual(len(self.j.all_entries()), 1)
        self.assertEqual(res.entry.tags, ["주간", "뉴스레터", "작성"])
        self.assertEqual(res.lessons_used, [])  # 빈 일지라 회상 없음


class TeamTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.j = Journal(Path(self._tmp.name) / "j.jsonl")
        self.team = Team(get_llm(), self.j)

    def tearDown(self):
        self._tmp.cleanup()

    def test_single_run_outputs_and_human_gate(self):
        r = self.team.run("주간 뉴스레터 작성")
        self.assertIn("3단계", r.plan.output)
        self.assertIn("초안", r.draft.output)
        self.assertTrue(r.human_decisions)
        self.assertEqual(len(self.j.all_entries()), 3)
        self.assertEqual(r.lessons_applied, 0)  # 1차엔 과거 일기 없음

    def test_learning_across_runs(self):
        r1 = self.team.run("주간 뉴스레터 작성")
        r2 = self.team.run("주간 뉴스레터 작성")
        self.assertEqual(r1.lessons_applied, 0)
        self.assertGreater(r2.lessons_applied, 0)  # 1차 일기를 회상해 적용
        self.assertIn("과거 교훈", r2.plan.output)
        self.assertEqual(len(self.j.all_entries()), 6)

    def test_render_has_sections(self):
        out = self.team.run("주간 뉴스레터 작성").render()
        self.assertIn("📋 작업", out)
        self.assertIn("[기획자]", out)
        self.assertIn("[검토자]", out)
        self.assertIn("🧑 사람이 결정할 것", out)


class DriftTest(unittest.TestCase):
    TASK = "주간 뉴스레터 작성"

    def test_healthy_is_stable(self):
        out = "[실행] '주간 뉴스레터 작성' 초안 작성. (과거 교훈 1건 반영)"
        rep = diagnose("실행가", self.TASK, out, lessons_available=1, expect_markers=("초안",))
        self.assertEqual(rep.verdict, "안정")
        self.assertLess(rep.score, 25)

    def test_total_breakdown_is_flagged(self):
        out = "음... 무엇을 하던 중인지 모르겠습니다."
        rep = diagnose("실행가", self.TASK, out, lessons_available=1, expect_markers=("초안",))
        self.assertEqual(rep.verdict, "이탈")
        self.assertGreaterEqual(rep.score, 55)

    def test_lesson_neglect_signal(self):
        out = "[실행] '주간 뉴스레터 작성' 초안 작성."  # 교훈 언급 없음
        rep = diagnose("실행가", self.TASK, out, lessons_available=2, expect_markers=("초안",))
        self.assertGreater(rep.signals.lesson_neglect, 0)

    def test_no_lessons_means_no_neglect(self):
        out = "[실행] '주간 뉴스레터 작성' 초안 작성."
        rep = diagnose("실행가", self.TASK, out, lessons_available=0, expect_markers=("초안",))
        self.assertEqual(rep.signals.lesson_neglect, 0.0)


class DriftingModelTest(unittest.TestCase):
    def test_scores_climb_to_breakdown(self):
        llm = DriftingMockLLM()
        task = "주간 뉴스레터 작성"
        msg = build_user_message(task, ["A", "B"], prior="")
        scores = []
        for _ in range(4):
            out = llm.complete("[ROLE:worker]", [Message("user", msg)])
            scores.append(
                diagnose("실행가", task, out, lessons_available=2, expect_markers=("초안",)).score
            )
        self.assertEqual(scores[0], 0)
        self.assertEqual(scores, sorted(scores))  # 단조 증가
        self.assertGreaterEqual(scores[-1], 55)   # 끝엔 이탈


class DashboardTest(unittest.TestCase):
    def test_render_has_sections(self):
        page = render_html(build_demo_data())
        for token in ("<!DOCTYPE html>", "드리프트", "지혜", "파이프라인", "사람 결정"):
            self.assertIn(token, page)

    def test_write_dashboard(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_dashboard(Path(d) / "dash.html")
            self.assertTrue(p.exists())
            self.assertGreater(p.stat().st_size, 500)

    def test_render_svg(self):
        svg = render_svg(build_demo_data())
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("드리프트", svg)
        self.assertIn("</svg>", svg)


if __name__ == "__main__":
    unittest.main()
