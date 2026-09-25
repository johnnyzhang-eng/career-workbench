import copy
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from career import Workflow
from workbench.interview_evidence import InterviewEvidenceStore


NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


class InterviewEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name) / "private" / "fictional-interviews"
        self.workspace.mkdir(parents=True)
        self.evidence = self.workspace / "mock-note.txt"
        self.evidence.write_text("虚构面试笔记；不含真人信息。", encoding="utf-8")
        self.store = InterviewEvidenceStore(self.workspace, clock=lambda: NOW)
        self.note = {
            "interview_date": "2026-09-24", "company": "虚构甲公司", "role": "虚构分析实习",
            "input_kind": "question", "interviewer_input": "请解释一条 SQL 查询如何筛选数据？",
            "input_fidelity": "paraphrase",
            "self_observed_answer_or_problem": "本人记得回答了 WHERE，但没有说清空值处理。",
            "evidence_source": {"kind": "local_path", "value": "mock-note.txt"},
            "observation_confidence": "medium", "status": "unverified",
            "inference": "可能需要练习 SQL 三值逻辑", "inference_confidence": "low",
            "linked_skill_target": "sql-foundations",
            "next_practice_step": "独立写三个 NULL 条件查询，解释每条结果。",
        }

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def add(self, op="fictional-first", note=None):
        return self.store.add({"operation_id": op, "note": note or self.note})

    def test_create_separates_observation_inference_and_never_claims_mastery(self):
        saved = self.add()
        self.assertEqual(saved["record_id"], "INT-fictional-first")
        self.assertEqual(saved["version"], 1)
        self.assertEqual(saved["note"]["observation"]["input_fidelity"], "paraphrase")
        self.assertEqual(saved["note"]["observation"]["evidence_source"]["value"], "mock-note.txt")
        self.assertEqual(saved["note"]["inference"]["basis"], "user_hypothesis")
        self.assertEqual(saved["note"]["inference"]["confidence"], "low")
        self.assertEqual(saved["note"]["mastery_status"], "not_assessed")
        self.assertEqual(saved["note"]["resume_claim_status"], "not_created")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM interview_events").fetchone()[0], 1)
        self.assertEqual(os.stat(self.workspace).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(self.store.db_path).st_mode & 0o777, 0o600)

    def test_correction_keeps_original_and_requires_current_version(self):
        original = self.add()
        corrected = copy.deepcopy(self.note)
        corrected["interviewer_input"] = "我后来核对笔记：面试官问的是 LEFT JOIN 与 NULL。"
        corrected["input_fidelity"] = "verbatim"
        corrected["status"] = "user_checked"
        corrected["inference"] = None
        corrected["inference_confidence"] = None
        latest = self.store.correct({"operation_id": "fix-question", "record_id": original["record_id"],
            "expected_version": 1, "reason": "重新核对虚构笔记后纠正问题内容", "note": corrected})
        self.assertEqual(latest["version"], 2)
        self.assertIsNone(latest["note"]["inference"])
        history = self.store.get(original["record_id"], include_history=True)["history"]
        self.assertEqual([item["kind"] for item in history], ["created", "corrected"])
        self.assertEqual(history[0]["note"]["observation"]["interviewer_input"], self.note["interviewer_input"])
        self.assertEqual(history[1]["previous_event_id"], history[0]["event_id"])
        self.assertEqual(history[1]["correction_reason"], "重新核对虚构笔记后纠正问题内容")
        with self.assertRaisesRegex(ValueError, "读取最新版本"):
            self.store.correct({"operation_id": "stale-fix", "record_id": original["record_id"],
                "expected_version": 1, "reason": "陈旧页面更正", "note": corrected})
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM interview_events").fetchone()[0], 2)

    def test_duplicate_retry_does_not_duplicate_events(self):
        first = self.add()
        replay = self.add()
        self.assertEqual(first["record_id"], replay["record_id"])
        changed = copy.deepcopy(self.note)
        changed["role"] = "另一虚构职位"
        with self.assertRaisesRegex(ValueError, "不同操作"):
            self.add(note=changed)
        corrected = {"operation_id": "fix-once", "record_id": first["record_id"],
                     "expected_version": 1, "reason": "补全本人观察", "note": changed}
        self.store.correct(corrected)
        self.store.correct(corrected)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM interview_events").fetchone()[0], 2)
        with self.assertRaisesRegex(ValueError, "不同操作"):
            self.store.correct({**corrected, "reason": "不同原因"})

    def test_list_filter_and_restart_persist(self):
        first_note = copy.deepcopy(self.note)
        first_note["linked_goal_id"] = "GOAL-A"
        first = self.add(note=first_note)
        second_note = copy.deepcopy(self.note)
        second_note.update(company="虚构乙公司", role="虚构工程岗", input_kind="feedback",
                           interviewer_input="请更清楚说明项目取舍。")
        second_note["linked_goal_id"] = "GOAL-B"
        second = self.add("fictional-second", second_note)
        self.assertEqual({item["record_id"] for item in self.store.list()},
                         {first["record_id"], second["record_id"]})
        self.assertEqual([item["record_id"] for item in self.store.list(company="虚构乙公司")],
                         [second["record_id"]])
        self.assertEqual(self.store.list(role="不存在"), [])
        self.assertEqual([item["record_id"] for item in self.store.list(goal_id="GOAL-A")],
                         [first["record_id"]])
        self.store.close()
        self.store = InterviewEvidenceStore(self.workspace, clock=lambda: NOW)
        self.assertEqual(self.store.get(first["record_id"])["note"]["company"], "虚构甲公司")
        self.assertEqual(len(self.store.list()), 2)

    def test_validation_prevents_future_empty_and_unattributed_inference(self):
        cases = [
            {"interview_date": "2026-09-26"}, {"interview_date": "2026-02-30"},
            {"company": ""}, {"role": ""},
            {"interviewer_input": " "}, {"self_observed_answer_or_problem": ""},
            {"evidence_source": {"kind": "local_path", "value": "missing.txt"}},
            {"next_practice_step": ""}, {"linked_skill_target": "bad skill"},
            {"observation_confidence": "certain"}, {"status": "mastered"},
            {"inference": "猜测", "inference_confidence": None},
            {"inference": None, "inference_confidence": "high"},
            {"linked_goal_id": "bad goal"},
        ]
        for index, changes in enumerate(cases):
            with self.subTest(changes=changes):
                note = {**self.note, **changes}
                with self.assertRaises(ValueError):
                    self.add(f"invalid-{index}", note)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM interview_events").fetchone()[0], 0)

    def test_evidence_path_cannot_escape_private_workspace(self):
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("虚构外部文件", encoding="utf-8")
        for value in (str(outside), "../../outside.txt"):
            note = copy.deepcopy(self.note)
            note["evidence_source"]["value"] = value
            with self.assertRaisesRegex(ValueError, "当前 private"):
                self.add("outside-attempt", note)
        link = self.workspace / "escaped-link.txt"
        link.symlink_to(outside)
        note = copy.deepcopy(self.note)
        note["evidence_source"]["value"] = link.name
        with self.assertRaisesRegex(ValueError, "当前 private"):
            self.add("symlink-attempt", note)

    def test_url_evidence_is_local_metadata_without_network_or_token(self):
        note = copy.deepcopy(self.note)
        note["evidence_source"] = {"kind": "url", "value": "https://example.org/fictional-interview-note"}
        saved = self.add(note=note)
        self.assertEqual(saved["note"]["observation"]["evidence_source"]["kind"], "url")
        for url in ("http://example.org/note", "https://user:pass@example.org/note",
                    "https://example.org/note?q=secret", "https://example.org/note#private"):
            bad = copy.deepcopy(note)
            bad["evidence_source"]["value"] = url
            with self.assertRaises(ValueError):
                self.add("bad-url", bad)

    def test_legacy_application_records_are_unchanged(self):
        flow = Workflow(self.workspace)
        try:
            flow.add({"id": "FAKE-JOB", "company": "虚构甲公司", "role": "虚构分析实习",
                      "family": "analysis", "url": "https://example.org/fake-job"})
            flow.db.commit()
            before = flow.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            self.add()
            self.assertEqual(flow.get("FAKE-JOB")["state"], "discovered")
            self.assertEqual(flow.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], before)
            self.assertEqual(flow.db.execute("SELECT COUNT(*) FROM learning").fetchone()[0], 0)
        finally:
            flow.db.close()

    def test_private_workspace_required(self):
        with self.assertRaisesRegex(ValueError, "private"):
            InterviewEvidenceStore(Path(self.temp.name) / "public", clock=lambda: NOW)

    def test_database_symlink_cannot_escape_workspace(self):
        other = Path(self.temp.name) / "private" / "other"
        other.mkdir(parents=True)
        target = other / "elsewhere.sqlite3"
        target.write_bytes(b"not a database")
        self.store.close()
        self.store.db_path.unlink()
        self.store.db_path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "符号链接"):
            InterviewEvidenceStore(self.workspace, clock=lambda: NOW)
        self.store.db_path.unlink()
        self.store = InterviewEvidenceStore(self.workspace, clock=lambda: NOW)


if __name__ == "__main__":
    unittest.main()
