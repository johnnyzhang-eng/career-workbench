import copy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from career import Workflow, CHECKS, now, demo
from scripts.check_privacy import findings


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.flow = Workflow(self.temp.name)
        self.job = {"id": "TEST-001", "company": "虚构公司", "role": "虚构岗位", "family": "solutions", "url": "https://example.com/job/1"}
        self.flow.add(self.job)
        self.assessment = {"checked_at": now(), "source": self.job["url"], "checks": {k: {"result": "pass", "evidence": "测试条件"} for k in CHECKS}}
        self.resume = Path(self.temp.name) / "resume.md"
        self.resume.write_text("虚构材料", encoding="utf-8")
        self.packet = {"resume_path": str(self.resume), "claims_evidence": ["虚构事实依据"]}

    def tearDown(self):
        self.flow.db.close()
        self.temp.cleanup()

    def ready(self):
        self.flow.assess(self.job["id"], self.assessment)
        self.flow.prepare(self.job["id"], self.packet)
        self.flow.approve(self.job["id"], True)

    def submitted(self):
        self.ready()
        self.flow.record(self.job["id"], "submitted", "虚构回执")

    def test_full_lifecycle_and_learning(self):
        self.submitted()
        self.flow.record(self.job["id"], "interview", "虚构邀请")
        self.flow.review(self.job["id"], {"summary": "循环缺口", "evidence": "虚构复盘", "gaps": [{"topic": "循环", "exercise": "计数", "acceptance": "边界测试"}]})
        result = self.flow.practice(1, "虚构独立代码", True)
        self.assertEqual(result["state"], "practiced")
        self.assertNotEqual(result["state"], "mastered")
        self.assertEqual(self.flow.get(self.job["id"])["state"], "interview")
        self.assertEqual(self.flow.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 8)

    def test_missing_check_holds(self):
        del self.assessment["checks"]["cohort"]
        self.assertEqual(self.flow.assess(self.job["id"], self.assessment)["state"], "hold")

    def test_exclusion_can_be_reassessed(self):
        bad = copy.deepcopy(self.assessment)
        bad["checks"]["degree"]["result"] = "fail"
        self.assertEqual(self.flow.assess(self.job["id"], bad)["state"], "excluded")
        self.assertEqual(self.flow.assess(self.job["id"], self.assessment)["state"], "eligible")

    def test_evidence_required_for_pass(self):
        self.assessment["checks"]["degree"]["evidence"] = " "
        with self.assertRaises(ValueError):
            self.flow.assess(self.job["id"], self.assessment)

    def test_stale_and_future_rejected(self):
        for delta in (timedelta(days=-4), timedelta(days=1)):
            self.assessment["checked_at"] = (datetime.now(timezone.utc) + delta).isoformat()
            with self.assertRaises(ValueError):
                self.flow.assess(self.job["id"], self.assessment)

    def test_timezone_required(self):
        self.assessment["checked_at"] = datetime.now().isoformat()
        with self.assertRaises(ValueError):
            self.flow.assess(self.job["id"], self.assessment)

    def test_cannot_skip_approval_or_submission(self):
        for state in ("submitted", "interview", "offer"):
            with self.assertRaises(ValueError):
                self.flow.record(self.job["id"], state, "虚构证据")

    def test_no_approval_without_confirmation(self):
        self.flow.assess(self.job["id"], self.assessment)
        self.flow.prepare(self.job["id"], self.packet)
        with self.assertRaises(ValueError):
            self.flow.approve(self.job["id"])

    def test_resume_change_invalidates_approval(self):
        self.ready()
        self.resume.write_text("变更后的材料", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.flow.record(self.job["id"], "submitted", "虚构回执")
        self.assertIn("文件已改变", self.flow.today()["jobs"][0]["next"])

    def test_new_packet_revokes_approval(self):
        self.ready()
        self.flow.prepare(self.job["id"], {**self.packet, "note": "修改"})
        self.assertNotIn("approval", self.flow.get(self.job["id"]))

    def test_reassessment_revokes_packet(self):
        self.ready()
        self.flow.assess(self.job["id"], self.assessment)
        self.assertNotIn("materials", self.flow.get(self.job["id"]))

    def test_duplicate_never_overwrites(self):
        with self.assertRaises(ValueError):
            self.flow.add(self.job)
        with self.assertRaises(ValueError):
            self.flow.add({**self.job, "id": "OTHER"})

    def test_repeated_interview_and_terminal(self):
        self.submitted()
        self.flow.record(self.job["id"], "interview", "一轮邀请")
        self.flow.record(self.job["id"], "interview", "二轮邀请")
        self.flow.record(self.job["id"], "rejected", "明确拒信")
        with self.assertRaises(ValueError):
            self.flow.record(self.job["id"], "interview", "不应重开")

    def test_review_atomic_validation(self):
        self.submitted()
        with self.assertRaises(ValueError):
            self.flow.review(self.job["id"], {"summary": "复盘", "evidence": "证据", "gaps": [{"topic": "a", "exercise": "b", "acceptance": "c"}, {}]})
        self.assertEqual(self.flow.db.execute("SELECT COUNT(*) FROM learning").fetchone()[0], 0)

    def test_reply_cannot_regress_interview_stage(self):
        self.submitted()
        self.flow.record(self.job["id"], "interview", "虚构邀请")
        with self.assertRaises(ValueError):
            self.flow.record(self.job["id"], "responded", "后续回信")
        self.assertEqual(self.flow.get(self.job["id"])["state"], "interview")

    def test_practice_requires_independent_evidence(self):
        with self.assertRaises(ValueError):
            self.flow.practice(1, "AI 答案", False)

    def test_materials_cannot_read_outside_workspace(self):
        with self.assertRaises(ValueError):
            self.flow.material_snapshot({"resume_path": __file__, "claims_evidence": ["test"]})

    def test_reopen_preserves_history(self):
        self.flow.db.commit()
        another = Workflow(self.temp.name)
        try:
            self.assertEqual(another.get(self.job["id"])["state"], "discovered")
        finally:
            another.db.close()


class DemoTests(unittest.TestCase):
    def test_idempotent_offline_demo(self):
        with tempfile.TemporaryDirectory() as directory:
            first = demo(directory)
            self.assertEqual(first, demo(directory))
            self.assertEqual(first["jobs"][0]["state"], "interview")
            self.assertEqual(len(first["learning"]), 1)


class PrivacyTests(unittest.TestCase):
    def test_synthetic_credentials_flagged_without_outputting_them(self):
        token = "gh" + "p_" + "A" * 32
        self.assertIn("credential", findings(token))

    def test_safe_example_and_private_term(self):
        self.assertEqual(findings("student@example.com"), [])
        self.assertEqual(findings("SYNTHETIC_PERSON", ["synthetic_person"]), ["private_term"])

    def test_phone_and_local_identity_path(self):
        self.assertIn("mobile", findings("138" + "0" * 8))
        self.assertIn("personal_path", findings("/" + "Users/fictional/file"))


if __name__ == "__main__":
    unittest.main()
