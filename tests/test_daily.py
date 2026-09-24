import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from career import CHECKS, Workflow
from workbench.daily import DailyStore


class Clock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


class DailyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = datetime.now(timezone.utc).replace(hour=1, minute=0, second=0, microsecond=0)
        self.clock = Clock(self.base)
        self.daily = DailyStore(self.temp.name, self.clock)

    def tearDown(self):
        self.daily.close()
        self.temp.cleanup()

    def task(self, task_id="DEMO-TASK-001", kind="custom", source_kind="self", source_id="DEMO-SELF"):
        return {"id": task_id, "title": "整理虚构学生的今日计划", "kind": kind,
                "source_kind": source_kind, "source_id": source_id,
                "reason": "从前一天延续的准备事项", "scheduled_at": (self.base + timedelta(hours=1)).isoformat(),
                "due_at": None, "due_verified": False}

    def schedule(self, task=None, event_id="E-SCHEDULE"):
        task = task or self.task()
        return self.daily.command("schedule", event_id, task["id"], {"task": task})

    def command(self, name, event_id, payload=None, task_id="DEMO-TASK-001"):
        return self.daily.command(name, event_id, task_id, payload)

    def test_midnight_sleep_restart_and_defer_keep_original_reason(self):
        self.schedule()
        self.clock.value = self.base + timedelta(days=1, hours=2)
        snapshot = self.daily.snapshot()
        self.assertEqual(len(snapshot["tasks"]), 1)
        self.assertEqual(snapshot["tasks"][0]["state"], "scheduled")
        self.assertEqual(snapshot["tasks"][0]["reason"], "从前一天延续的准备事项")
        self.assertIn("尚未完成", snapshot["tasks"][0]["carryover_reason"])
        self.command("defer", "E-DEFER", {"scheduled_at": (self.clock.value + timedelta(days=2)).isoformat(),
                                            "reason": "等待虚构材料"})
        self.assertEqual(self.daily.snapshot()["tasks"][0]["carryover_reason"], "等待虚构材料")
        self.assertEqual(self.daily.snapshot()["tasks"][0]["origin_scheduled_at"], self.task()["scheduled_at"])
        self.daily.db.commit()
        reopened = DailyStore(self.temp.name, self.clock)
        try:
            self.assertEqual(reopened.snapshot(), self.daily.snapshot())
        finally:
            reopened.close()

    def test_timezone_recomputes_today_without_changing_event_time(self):
        self.schedule()
        self.clock.value = self.base + timedelta(hours=15)
        shanghai = self.daily.snapshot("Asia/Shanghai")
        los_angeles = self.daily.snapshot("America/Los_Angeles")
        self.assertNotEqual(shanghai["today"], los_angeles["today"])
        self.assertEqual(shanghai["tasks"][0]["scheduled_at"], los_angeles["tasks"][0]["scheduled_at"])
        self.assertEqual(shanghai["tasks"][0]["id"], los_angeles["tasks"][0]["id"])

    def test_idempotency_conflict_and_terminal_history(self):
        task = self.task()
        self.schedule(task)
        self.schedule(task)
        self.assertEqual(self.daily.db.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0], 1)
        with self.assertRaises(ValueError):
            self.command("start", "E-SCHEDULE")
        self.command("start", "E-START")
        self.command("complete", "E-DONE", {"evidence": {"result_ref": "private/fictional-plan.md"}})
        self.assertEqual(self.daily.snapshot()["tasks"][0]["evidence_state"], "recorded")
        with self.assertRaises(ValueError):
            self.command("cancel", "E-CANCEL", {"reason": "too late"})
        self.clock.value += timedelta(days=1)
        self.assertEqual(self.daily.snapshot()["tasks"], [])

    def test_block_cancel_and_no_auto_failure(self):
        self.schedule()
        self.command("block", "E-BLOCK", {"reason": "等待活动主办方确认"})
        self.clock.value += timedelta(days=2)
        self.assertEqual(self.daily.snapshot()["tasks"][0]["state"], "blocked")
        self.assertEqual(self.daily.snapshot()["tasks"][0]["carryover_reason"], "等待活动主办方确认")
        self.command("cancel", "E-CANCEL", {"reason": "本人不再参加"})
        self.assertEqual(self.daily.snapshot()["tasks"][0]["state"], "cancelled")

    def test_due_unknown_never_becomes_verified_or_precise_countdown(self):
        task = self.task()
        task["due_at"] = (self.base + timedelta(days=4)).isoformat()
        self.schedule(task)
        first = self.daily.snapshot()["tasks"][0]
        self.assertFalse(first["due_verified"])
        self.assertIsNone(first["due_verified_at"])
        with self.assertRaises(ValueError):
            self.schedule({**self.task("OTHER"), "due_verified": True}, "E-OTHER")
        self.assertEqual(self.daily.db.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0], 1)

    def test_per_kind_completion_checks(self):
        cases = [
            ("attend_event", "event", {"attendance_ref": "event-note", "observed_at": self.base.isoformat()}),
            ("prepare_interview", "event", {"notes_ref": "private/interview-notes"}),
            ("follow_up", "job", {"contact_ref": "private/follow-up-note"}),
            ("custom", "self", {"result_ref": "private/plan"}),
        ]
        for number, (kind, source_kind, evidence) in enumerate(cases):
            task_id = f"DEMO-TASK-{number}"
            self.schedule(self.task(task_id, kind, source_kind), f"E-S-{number}")
            with self.assertRaises(ValueError):
                self.command("complete", f"E-BAD-{number}", {"evidence": {}}, task_id)
            self.command("complete", f"E-OK-{number}", {"evidence": evidence}, task_id)

    def test_reminder_dedup_across_restart_and_timezone(self):
        self.schedule()
        self.assertEqual(self.daily.claim_reminders(), [])
        self.clock.value += timedelta(hours=2)
        first = self.daily.claim_reminders()
        self.assertEqual(len(first), 1)
        self.assertEqual(self.daily.claim_reminders(), [])
        reopened = DailyStore(self.temp.name, self.clock)
        try:
            self.assertEqual(reopened.claim_reminders(), [])
        finally:
            reopened.close()
        self.command("defer", "E-DEFER", {"reason": "本人改期", "scheduled_at": (self.clock.value + timedelta(days=1)).isoformat()})
        self.assertEqual(self.daily.claim_reminders(), [])
        self.clock.value += timedelta(days=1, minutes=1)
        self.assertEqual(len(self.daily.claim_reminders()), 1)

    def test_legacy_application_receipt_gate(self):
        self.base = datetime.now(timezone.utc) - timedelta(minutes=2)
        self.clock.value = self.base
        workflow = Workflow(self.temp.name)
        try:
            job = {"id": "DEMO-JOB-001", "company": "虚构甲公司", "role": "虚构岗位",
                   "family": "solutions", "url": "https://example.com/jobs/demo-1"}
            with workflow.db:
                workflow.add(job)
            verify = self.task("DEMO-VERIFY", "verify_job", "job", job["id"])
            apply = self.task("DEMO-APPLY", "apply_job", "job", job["id"])
            self.schedule(verify, "E-S-VERIFY")
            self.schedule(apply, "E-S-APPLY")
            with self.assertRaises(ValueError):
                self.command("complete", "E-OPENED", {"evidence": {"opened_url": job["url"]}}, apply["id"])
            assessment = {"checked_at": datetime.now(timezone.utc).isoformat(), "source": job["url"],
                          "checks": {key: {"result": "pass", "evidence": "虚构资格条件"} for key in CHECKS}}
            with workflow.db:
                workflow.assess(job["id"], assessment)
            verify_seq = workflow.db.execute("SELECT seq FROM events WHERE kind='assessed'").fetchone()[0]
            self.clock.value = max(self.clock.value, datetime.now(timezone.utc)) + timedelta(minutes=1)
            self.command("complete", "E-VERIFY", {"evidence": {"job_event_seq": verify_seq}}, verify["id"])
            with self.assertRaises(ValueError):
                self.command("complete", "E-NO-RECEIPT", {"evidence": {"job_event_seq": verify_seq}}, apply["id"])
            resume = Path(self.temp.name) / "fictional-resume.md"
            resume.write_text("虚构材料", encoding="utf-8")
            with workflow.db:
                workflow.prepare(job["id"], {"resume_path": str(resume), "claims_evidence": ["虚构事实"]})
                workflow.approve(job["id"], True)
            with self.assertRaises(ValueError):
                self.command("complete", "E-APPROVED-ONLY", {"evidence": {"job_event_seq": verify_seq}}, apply["id"])
            with workflow.db:
                workflow.record(job["id"], "submitted", "虚构回执位置；测试未发送申请")
            submitted_seq = workflow.db.execute("SELECT seq FROM events WHERE kind='submitted'").fetchone()[0]
            self.clock.value = datetime.now(timezone.utc) + timedelta(minutes=2)
            self.command("complete", "E-SUBMITTED", {"evidence": {"job_event_seq": submitted_seq}}, apply["id"])
            self.assertEqual(workflow.get(job["id"])["state"], "submitted")
            self.assertEqual(self.daily.snapshot()["tasks"][1]["state"], "completed")
            self.clock.value += timedelta(days=8)
            follow_up = self.daily.snapshot()["tasks"][0]
            self.assertEqual(follow_up["kind"], "follow_up")
            self.assertEqual(workflow.get(job["id"])["state"], "submitted")
            old_receipt_task = self.task("DEMO-APPLY-AGAIN", "apply_job", "job", job["id"])
            self.schedule(old_receipt_task, "E-S-AGAIN")
            with self.assertRaises(ValueError):
                self.command("complete", "E-REUSE-RECEIPT",
                             {"evidence": {"job_event_seq": submitted_seq}}, old_receipt_task["id"])
        finally:
            workflow.db.close()

    def test_legacy_job_suggestion_is_explainable_and_user_schedules_it(self):
        workflow = Workflow(self.temp.name)
        try:
            with workflow.db:
                workflow.add({"id": "DEMO-JOB-002", "company": "虚构乙公司", "role": "虚构运营岗位",
                              "family": "operations", "url": "https://example.com/jobs/demo-2"})
            suggestion = self.daily.snapshot()["tasks"][0]
            self.assertEqual(suggestion["state"], "suggested")
            self.assertEqual(suggestion["kind"], "verify_job")
            self.assertEqual(suggestion["source_id"], "DEMO-JOB-002")
            self.assertFalse(suggestion["due_verified"])
            chosen = {key: suggestion[key] for key in
                      ("id", "title", "kind", "source_kind", "source_id", "reason", "scheduled_at",
                       "due_at", "due_verified")}
            self.schedule(chosen)
            self.assertEqual(self.daily.snapshot()["tasks"][0]["state"], "scheduled")
            self.assertEqual(len(self.daily.snapshot()["tasks"]), 1)
        finally:
            workflow.db.close()

    def test_reject_bad_clock_zone_and_naive_times(self):
        with self.assertRaises(ValueError):
            self.daily.snapshot("Imaginary/Zone")
        task = self.task()
        task["scheduled_at"] = "2026-09-24T09:00:00"
        with self.assertRaises(ValueError):
            self.schedule(task)
        self.assertEqual(self.daily.snapshot()["tasks"], [])


if __name__ == "__main__":
    unittest.main()
