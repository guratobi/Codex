"""agent_team 프로토타입 단위 테스트 (표준 라이브러리 + MockLLM, 네트워크 없음).

실행:  python -m unittest discover -v
"""
import tempfile
import unittest
from pathlib import Path

from agent_team.agents import Planner, Reviewer, Worker, build_user_message
from agent_team.journal import Journal, JournalEntry, derive_tags, now_iso
from agent_team.llm import MockLLM, Message, get_llm
from agent_team.team import Team


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


if __name__ == "__main__":
    unittest.main()
