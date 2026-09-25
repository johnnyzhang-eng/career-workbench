"""A discovery lead can inform a plan without becoming an application record."""

import hashlib
import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from workbench.discovery_candidates import get_candidate, list_candidates
from workbench.plan_templates import build_first_plan


class CandidateContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.url = "https://careers.example.org/jobs/fictional-17"
        self.candidate_id = hashlib.sha256(self.url.encode()).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def seed(self, *, payload=None, present=1):
        with sqlite3.connect(self.workspace / "discovery.sqlite3") as db:
            db.execute("""CREATE TABLE discovery_jobs(source TEXT, board TEXT, source_job_id TEXT,
                          payload TEXT, first_seen_at TEXT, last_seen_at TEXT, present_latest INTEGER)""")
            data = payload if payload is not None else {
                "id": self.candidate_id, "title": "虚构数据岗位",
                "job_url": self.url, "origin_observed_at": "2026-10-01T10:00:00+08:00",
                "unknowns": ["毕业届别尚未核实", "是否需要 SQL 测试未知"]}
            db.execute("INSERT INTO discovery_jobs VALUES (?,?,?,?,?,?,?)",
                       ("agent", "local", self.candidate_id, json.dumps(data, ensure_ascii=False),
                        "2026-10-01T10:00:00+08:00", "2026-10-01T10:00:00+08:00", present))

    def test_missing_and_invalid_records_do_not_create_or_promote(self):
        self.assertEqual(list_candidates(self.workspace), {"state": "missing", "candidates": []})
        self.assertFalse((self.workspace / "discovery.sqlite3").exists())
        with self.assertRaisesRegex(ValueError, "候选 ID 无效"):
            get_candidate(self.workspace, "../../private")
        self.seed(payload={"id": self.candidate_id, "title": "坏链接",
                           "job_url": "javascript:alert(1)", "origin_observed_at": "x", "unknowns": []})
        self.assertEqual(list_candidates(self.workspace)["candidates"], [])
        with self.assertRaisesRegex(ValueError, "记录无效"):
            get_candidate(self.workspace, self.candidate_id)

    def test_selected_lead_stays_goal_custom_tasks_with_unknowns(self):
        self.seed()
        candidate = get_candidate(self.workspace, self.candidate_id)
        self.assertEqual(candidate["verification_state"], "待核查")
        self.assertEqual(len(list_candidates(self.workspace)["candidates"]), 1)
        goal = {"id": "G-FICTIONAL", "domain": "recruiting", "active_version": 0,
                "revision": 1, "weekly_minutes": 420, "timezone": "Asia/Shanghai",
                "target_at": None, "target_confidence": "unknown", "baseline": "虚构起点"}
        bundle = build_first_plan(goal, "recruiting", date(2026, 10, 5), "P-FICTIONAL",
                                  candidate=candidate, study_focus=["sql", "python", "algorithms"])
        items = bundle["proposal"]["items"]
        self.assertEqual(len(items), 14)
        self.assertTrue(all(item["source_kind"] == "goal" for item in items))
        self.assertFalse(any(item["task_kind"] == "apply_job" for item in items))
        self.assertIn(self.url, items[0]["source_ref"])
        self.assertTrue(any(item["field"] == "candidate_unknown" for item in bundle["unknowns"]))
        self.assertIn("待核查候选", bundle["proposal"]["reason"])

    def test_disappeared_candidate_must_be_reselected(self):
        self.seed(present=0)
        with self.assertRaisesRegex(ValueError, "已不存在"):
            get_candidate(self.workspace, self.candidate_id)


if __name__ == "__main__":
    unittest.main()
