import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from career import Workflow
from workbench.learning import LearningStore
from workbench.learning_web import LearningHTTPServer
from workbench.learning_resources import RESOURCE_BY_ID


NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


class LearningResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.flow = Workflow(self.workspace)
        self.jobs = [
            {"id": "FAKE-ANALYST", "company": "虚构甲公司", "role": "虚构分析岗",
             "family": "analytics", "url": "https://example.com/fake-analyst"},
            {"id": "FAKE-ENGINEER", "company": "虚构乙公司", "role": "虚构工程岗",
             "family": "engineering", "url": "https://example.com/fake-engineer"},
        ]
        for job in self.jobs:
            self.flow.add(job)
        self.flow.db.commit()
        self.store = LearningStore(self.workspace, clock=lambda: NOW)

    def tearDown(self):
        self.store.close()
        self.flow.db.close()
        self.temp.cleanup()

    def add_requirement(self, job_index=0, skill="sql-foundations", op="req-one",
                        status="confirmed"):
        job = self.jobs[job_index]
        state = self.store.add_requirement({"operation_id": op, "job_id": job["id"],
            "skill_id": skill, "excerpt": "虚构 JD：需要 SQL 查询。",
            "source_url": job["url"], "source_checked_at": NOW.isoformat(),
            "confirmation_status": status})
        return next(req for req in state["requirements"] if req["id"] == "REQ-" + op)

    def event(self, requirement, resource, kind, op, evidence=None):
        payload = {"operation_id": op, "requirement_id": requirement["id"],
                   "resource_id": resource, "kind": kind}
        if evidence is not None:
            payload["evidence_ref"] = evidence
        return self.store.record_event(payload)

    def test_two_jds_share_skill_but_keep_distinct_sources(self):
        first = self.add_requirement()
        second = self.add_requirement(1, op="req-two")
        self.assertNotEqual(first["source_ref"]["content_revision"], second["source_ref"]["content_revision"])
        self.assertEqual(first["recommendation"]["status"], "ready")
        self.assertEqual(second["recommendation"]["status"], "ready")
        self.assertEqual(first["recommendation"]["items"][0]["id"], "postgres-select")
        self.assertEqual(first["recommendation"]["items"][1]["id"], "sqlite-select")
        self.assertIn("postgresql.org/docs/current/tutorial-select.html",
                      first["recommendation"]["items"][0]["url"])
        self.assertEqual(self.flow.get(self.jobs[0]["id"])["state"], "discovered")
        self.assertEqual(self.flow.db.execute("SELECT COUNT(*) FROM events WHERE kind='submitted'").fetchone()[0], 0)

    def test_review_no_match_and_prerequisites_are_explicit(self):
        pending = self.add_requirement(skill="stream-processing", status="needs_review")
        self.assertEqual(pending["recommendation"]["status"], "needs_review")
        self.assertEqual(pending["recommendation"]["items"], [])
        confirmed = self.add_requirement(skill="stream-processing", op="req-stream")
        self.assertEqual(confirmed["recommendation"]["status"], "no_match")
        algorithms = self.add_requirement(skill="algorithms-foundations", op="req-algo")
        mit = next(item for item in algorithms["recommendation"]["items"] if item["id"] == "mit-algorithm-lecture")
        self.assertEqual(mit["missing_prerequisites"], ["python-basics", "discrete-math"])
        self.assertEqual(algorithms["recommendation"]["status"], "needs_review")
        self.store.set_profile({"operation_id": "profile-zh", "language": "zh", "known_skills": []})
        sql = self.add_requirement(op="req-zh")
        self.assertEqual(sql["recommendation"]["status"], "needs_review")
        self.assertTrue(all(item["language_mismatch"] for item in sql["recommendation"]["items"]))

    def test_learning_events_are_ordered_idempotent_and_unverified(self):
        requirement = self.add_requirement()
        with self.assertRaisesRegex(ValueError, "先明确打开"):
            self.event(requirement, "postgres-select", "in_progress", "skip-open")
        opened = self.event(requirement, "postgres-select", "opened", "open-one")
        self.assertEqual(opened["requirements"][0]["activities"]["postgres-select"]["state"], "opened")
        self.event(requirement, "postgres-select", "opened", "open-one")
        self.event(requirement, "postgres-select", "opened", "open-again")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM learning_events").fetchone()[0], 1)
        self.event(requirement, "postgres-select", "in_progress", "progress-one")
        with self.assertRaisesRegex(ValueError, "依据"):
            self.event(requirement, "postgres-select", "completed_self_reported", "no-evidence")
        finished = self.event(requirement, "postgres-select", "completed_self_reported", "done-one",
                              "虚构练习笔记：本机路径，由本人待核验")
        activity = finished["requirements"][0]["activities"]["postgres-select"]
        self.assertEqual(activity["state"], "completed_self_reported")
        self.assertEqual(activity["evidence_status"], "unverified")
        self.assertEqual(activity["skill_status"], "needs_validation")
        self.assertNotIn("mastered", json.dumps(finished))
        self.assertEqual(self.flow.get(self.jobs[0]["id"])["state"], "discovered")
        self.assertEqual(self.flow.db.execute("SELECT COUNT(*) FROM events WHERE kind='submitted'").fetchone()[0], 0)
        self.event(requirement, "postgres-select", "completed_self_reported", "done-again",
                   "虚构练习笔记：本机路径，由本人待核验")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM learning_events").fetchone()[0], 3)
        with self.assertRaisesRegex(ValueError, "不同操作"):
            self.event(requirement, "sqlite-select", "opened", "open-one")

    def test_source_change_invalidates_old_mapping_and_persists(self):
        requirement = self.add_requirement()
        self.store.close()
        self.store = LearningStore(self.workspace, clock=lambda: NOW)
        self.assertEqual(self.store.state()["requirements"][0]["id"], requirement["id"])
        job = self.flow.get(self.jobs[0]["id"])
        job["url"] = "https://example.com/changed-job"
        with self.flow.db:
            self.flow.save(job, "source-updated", {"reason": "fictional test"})
        current = self.store.state()["requirements"][0]
        self.assertTrue(current["source_stale"])
        self.assertEqual(current["recommendation"]["status"], "needs_review")
        with self.assertRaisesRegex(ValueError, "重新核对"):
            self.event(requirement, "postgres-select", "opened", "stale-open")

    def test_choice_reject_access_issue_and_input_validation(self):
        requirement = self.add_requirement()
        self.store.choose({"operation_id": "reject-one", "requirement_id": requirement["id"],
                           "decision": "reject", "reason": "本人更偏好别的资源"})
        result = self.store.choose({"operation_id": "choose-one", "requirement_id": requirement["id"],
                                    "resource_id": "postgres-select", "decision": "choose",
                                    "reason": "先看官方教程"})
        self.assertEqual(result["requirements"][0]["choice"]["resource_id"], "postgres-select")
        result = self.store.report_access_issue({"operation_id": "access-one", "resource_id": "postgres-select",
                                                 "reason": "虚构访问问题"})
        resource = next(item for item in result["requirements"][0]["recommendation"]["items"]
                        if item["id"] == "postgres-select")
        self.assertEqual(resource["access_status"], "access_needs_recheck")
        with self.assertRaises(ValueError):
            self.store.choose({"operation_id": "bad-choice", "requirement_id": requirement["id"],
                               "resource_id": "python-control", "decision": "choose", "reason": "错误技能"})
        with self.assertRaises(ValueError):
            self.store.add_requirement({"operation_id": "bad-source", "job_id": self.jobs[0]["id"],
                                        "skill_id": "sql-foundations", "excerpt": "虚构 JD",
                                        "source_url": "http://example.com/plain", "source_checked_at": NOW.isoformat(),
                                        "confirmation_status": "confirmed"})

    def test_chapter_revision_change_keeps_old_events_historical(self):
        requirement = self.add_requirement()
        self.store.choose({"operation_id": "choose-original", "requirement_id": requirement["id"],
                           "resource_id": "postgres-select", "decision": "choose", "reason": "原章节"})
        self.event(requirement, "postgres-select", "opened", "open-original")
        original = RESOURCE_BY_ID["postgres-select"]
        try:
            RESOURCE_BY_ID["postgres-select"] = {**original, "url": "https://example.org/revised-chapter"}
            changed = self.store.state()["requirements"][0]
            self.assertTrue(changed["choice"]["source_stale"])
            self.assertTrue(changed["historical_activities"])
            self.assertNotIn("postgres-select", changed["activities"])
            with self.assertRaisesRegex(ValueError, "先明确打开"):
                self.event(requirement, "postgres-select", "in_progress", "skip-new-open")
            updated = self.event(requirement, "postgres-select", "opened", "open-revised")
            self.assertEqual(updated["requirements"][0]["activities"]["postgres-select"]["state"], "opened")
            self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM learning_events").fetchone()[0], 2)
        finally:
            RESOURCE_BY_ID["postgres-select"] = original


class LearningHTTPTests(unittest.TestCase):
    def setUp(self):
        LearningResourceTests.setUp(self)
        self.server = LearningHTTPServer(("127.0.0.1", 0), self.workspace, clock=lambda: NOW)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        LearningResourceTests.tearDown(self)

    def request(self, method, path, body=None, host=None, origin=None, token=None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {"Host": host or f"127.0.0.1:{self.port}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if origin is not None:
            headers["Origin"] = origin
        if token is not None:
            headers["X-CSRF-Token"] = token
        conn.request(method, path, body=json.dumps(body).encode() if body is not None else None, headers=headers)
        response = conn.getresponse()
        data = response.read()
        result = (response.status, response.headers, data)
        conn.close()
        return result

    def test_http_loopback_origin_csrf_and_fixed_paths(self):
        code, headers, raw = self.request("GET", "/")
        self.assertEqual(code, 200)
        self.assertIn(b"Career Workbench", raw)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn(b"__CSP_NONCE__", raw)
        self.assertEqual(self.request("GET", "/?job_id=FAKE-ANALYST")[0], 200)
        self.assertEqual(self.request("GET", "/api/state", host="evil.example")[0], 403)
        self.assertEqual(self.request("GET", "/docs/learning-companion.html")[0], 404)
        self.assertEqual(self.request("POST", "/api/profile", {"operation_id": "a", "language": "any",
                                                                "known_skills": []})[0], 403)
        origin = f"http://127.0.0.1:{self.port}"
        self.assertEqual(self.request("POST", "/api/profile", {"operation_id": "a", "language": "any",
                                                                "known_skills": []}, origin=origin, token="bad")[0], 403)
        token = json.loads(self.request("GET", "/api/state")[2])["csrf_token"]
        code, _, raw = self.request("POST", "/api/profile", {"operation_id": "good-profile",
            "language": "en", "known_skills": ["python-basics"]}, origin=origin, token=token)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["profile"]["language"], "en")
        self.assertEqual(self.request("POST", "/api/profile", {"operation_id": "b", "language": "zh",
                        "known_skills": []}, origin="http://evil.example", token=token)[0], 403)

    def test_storage_error_is_explicit_not_false_success(self):
        with patch("workbench.learning_web.LearningStore", side_effect=sqlite3.OperationalError("disk unavailable")):
            code, _, raw = self.request("GET", "/api/state")
            self.assertEqual(code, 503)
            self.assertIn("暂不可用", json.loads(raw)["error"])
            origin = f"http://127.0.0.1:{self.port}"
            code, _, raw = self.request("POST", "/api/profile", {"operation_id": "storage-error",
                "language": "any", "known_skills": []}, origin=origin, token=self.server.csrf_token)
            self.assertEqual(code, 503)
            self.assertIn("操作未确认", json.loads(raw)["error"])


if __name__ == "__main__":
    unittest.main()
