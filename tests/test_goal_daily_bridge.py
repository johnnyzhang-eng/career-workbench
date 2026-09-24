"""Fictional cross-store scheduling and recovery checks for Issue #17."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from workbench.daily import DailyStore
from workbench.goal_daily_bridge import GoalDailyBridge, daily_task, schedule_event_id
from workbench.goals import GoalStore


class GoalDailyBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.clock = lambda: self.now
        self.goals = GoalStore(self.temp.name, self.clock)
        self.daily = DailyStore(self.temp.name, self.clock)
        self.bridge = GoalDailyBridge(self.goals, self.daily)

    def tearDown(self):
        self.goals.close()
        self.daily.close()
        self.temp.cleanup()

    def goal(self, goal_id):
        return {"id": goal_id, "title": "虚构执行目标", "domain": "learning",
                "timezone": "Asia/Shanghai", "weekly_minutes": 300,
                "success_criterion": "本人记录完成与复盘，不代表考试通过或投递成功",
                "baseline": "虚构基线", "target_at": None, "target_confidence": "unknown",
                "target_source_ref": None, "target_checked_at": None}

    def item(self, task_id, goal_id, *, kind="practice", source_kind="goal", source_id=None,
             scheduled_at=None):
        return {"task_id": task_id, "title": "虚构练习" if kind == "practice" else "虚构岗位申请",
                "task_kind": kind, "source_kind": source_kind, "source_id": source_id or goal_id,
                "reason": "根据虚构目标安排此项任务", "source_ref": "fictional-task-source-v1",
                "scheduled_at": scheduled_at or (self.now + timedelta(hours=1)).isoformat(),
                "estimated_minutes": 30, "completion_rule": "记录实际依据",
                "due_at": None, "due_confidence": "unknown", "due_source_ref": None,
                "due_checked_at": None, "flexible": True}

    def accept(self, goal_id, items, *, version=1, review_id=None):
        if version == 1:
            self.goals.command("create_goal", f"G-{goal_id}", {"goal": self.goal(goal_id)})
        proposal_id = f"P-{goal_id}-{version}"
        self.goals.command("propose_plan", f"EP-{goal_id}-{version}", {"proposal": {
            "id": proposal_id, "goal_id": goal_id, "goal_revision": 1,
            "base_version": version - 1, "review_id": review_id,
            "reason": "虚构有来源的每日安排", "items": items, "method": "rule_template",
            "source_ref": "fictional-template-v1"}})
        self.goals.command("decide_plan", f"ED-{goal_id}-{version}", {
            "proposal_id": proposal_id, "decision": "accept", "actor": "user",
            "reason": "本人接受虚构方案", "edited_items": None, "policy_ref": None})

    def test_cet6_acceptance_is_pending_until_replayed_and_idempotent(self):
        goal_id, task_id = "DEMO-CET6", "DEMO-READ"
        self.accept(goal_id, [self.item(task_id, goal_id)])
        self.assertEqual(self.bridge.status(goal_id)["state"], "sync_pending")
        self.assertEqual(self.daily.snapshot()["tasks"], [])
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        self.assertEqual(self.bridge.status(goal_id)["items"][0]["source_ref"], "fictional-task-source-v1")
        self.assertEqual(self.daily._tasks()[task_id]["reason"], "根据虚构目标安排此项任务")
        self.assertEqual(self.daily.db.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0], 1)
        event_id = self.daily.db.execute("SELECT event_id FROM daily_events").fetchone()[0]
        self.assertEqual(event_id, schedule_event_id(goal_id, 1, task_id))
        self.daily.command("start", "DEMO-START", task_id)
        with self.assertRaises(ValueError):
            self.daily.command("complete", "DEMO-BAD", task_id, {"evidence": {"result_ref": "score"}})
        self.daily.command("complete", "DEMO-DONE", task_id, {"evidence": {
            "material_ref": "fictional-material", "first_attempt_ref": "fictional-first-attempt",
            "reflection_ref": "fictional-reflection"}})
        self.assertEqual(self.bridge.status(goal_id)["items"][0]["daily_state"], "completed")
        self.assertFalse((self.goals.workspace / "state.sqlite3").exists())

    def test_partial_sync_recovers_after_transient_failure(self):
        goal_id = "DEMO-CET6"
        self.accept(goal_id, [self.item("DEMO-READ", goal_id), self.item("DEMO-LISTEN", goal_id)])
        actual_command = self.daily.command
        calls = [0]

        def interrupted(*args, **kwargs):
            calls[0] += 1
            if calls[0] == 2:
                raise sqlite3.OperationalError("fictional interrupted write")
            return actual_command(*args, **kwargs)

        self.daily.command = interrupted
        first = self.bridge.sync(goal_id)
        self.assertEqual(first["state"], "sync_pending")
        self.assertEqual([x["state"] for x in first["items"]], ["applied", "sync_pending"])
        self.assertIn("fictional interrupted", first["last_error"])
        self.daily.close()
        self.goals.close()
        self.daily = DailyStore(self.temp.name, self.clock)
        self.goals = GoalStore(self.temp.name, self.clock)
        self.bridge = GoalDailyBridge(self.goals, self.daily)
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        self.assertEqual(self.daily.db.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0], 2)

    def test_recruiting_plan_keeps_legacy_receipt_gate(self):
        goal_id, task_id = "DEMO-RECRUIT", "DEMO-APPLY"
        self.accept(goal_id, [self.item(task_id, goal_id, kind="apply_job",
                                        source_kind="job", source_id="DEMO-JOB")])
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        with self.assertRaises(ValueError):
            self.daily.command("complete", "DEMO-OPENED", task_id,
                               {"evidence": {"opened_url": "https://example.com/fictional"}})
        with self.assertRaises(ValueError):
            self.daily.command("complete", "DEMO-FAKE-RECEIPT", task_id,
                               {"evidence": {"job_event_seq": 1}})
        self.assertEqual(self.daily._tasks()[task_id]["state"], "scheduled")

    def test_existing_task_id_and_changed_plan_report_conflict(self):
        goal_id, task_id = "DEMO-CET6", "DEMO-READ"
        first_item = self.item(task_id, goal_id)
        self.accept(goal_id, [first_item])
        unrelated = daily_task(self.goals.snapshot(goal_id)["plans"][-1], first_item, goal_id)
        self.daily.command("schedule", "MANUAL-SCHEDULE", task_id, {"task": unrelated})
        self.assertEqual(self.bridge.status(goal_id)["state"], "conflict")
        self.assertEqual(self.bridge.sync(goal_id)["state"], "conflict")
        self.assertEqual(self.daily.db.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0], 1)

    def test_new_plan_can_add_task_but_changed_existing_task_needs_resolution(self):
        goal_id, task_id = "DEMO-CET6", "DEMO-READ"
        first_item = self.item(task_id, goal_id)
        self.accept(goal_id, [first_item])
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        self.goals.command("record_review", "DEMO-REVIEW-E", {"review": {
            "id": "DEMO-REVIEW", "goal_id": goal_id, "plan_version": 1,
            "trigger": "external_event", "result_ids": [], "finding": "虚构安排需调整",
            "source_ref": "fictional-event-note"}})
        second = self.item("DEMO-LISTEN", goal_id)
        self.accept(goal_id, [first_item, second], version=2, review_id="DEMO-REVIEW")
        self.assertEqual(self.bridge.status(goal_id)["state"], "sync_pending")
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        self.assertEqual(self.bridge.status(goal_id)["items"][0]["scheduled_from_version"], 1)
        self.goals.command("record_review", "DEMO-REVIEW-E3", {"review": {
            "id": "DEMO-REVIEW-3", "goal_id": goal_id, "plan_version": 2,
            "trigger": "external_event", "result_ids": [], "finding": "虚构时段需调整",
            "source_ref": "fictional-event-note"}})
        changed = {**first_item, "scheduled_at": (self.now + timedelta(hours=2)).isoformat()}
        self.accept(goal_id, [changed, second], version=3, review_id="DEMO-REVIEW-3")
        self.assertEqual(self.bridge.status(goal_id)["state"], "conflict")
        self.assertEqual(self.bridge.sync(goal_id)["state"], "conflict")

    def test_no_plan_and_workspace_guard(self):
        goal_id = "DEMO-CET6"
        self.goals.command("create_goal", "DEMO-GOAL", {"goal": self.goal(goal_id)})
        self.assertEqual(self.bridge.status(goal_id)["state"], "no_plan")
        self.goals.command("propose_plan", "DEMO-PROPOSE", {"proposal": {
            "id": "DEMO-PENDING", "goal_id": goal_id, "goal_revision": 1,
            "base_version": 0, "review_id": None, "reason": "仅提议",
            "items": [self.item("DEMO-UNACCEPTED", goal_id)],
            "method": "rule_template", "source_ref": "fictional-template-v1"}})
        self.assertEqual(self.bridge.sync(goal_id)["state"], "no_plan")
        self.assertEqual(self.daily.db.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0], 0)
        with tempfile.TemporaryDirectory() as other:
            other_daily = DailyStore(other, self.clock)
            try:
                with self.assertRaises(ValueError):
                    GoalDailyBridge(self.goals, other_daily)
            finally:
                other_daily.close()

    def test_removed_unfinished_task_is_visible_conflict(self):
        goal_id = "DEMO-CET6"
        self.accept(goal_id, [self.item("DEMO-OLD", goal_id)])
        self.bridge.sync(goal_id)
        self.goals.command("record_review", "DEMO-REMOVE-REVIEW-E", {"review": {
            "id": "DEMO-REMOVE-REVIEW", "goal_id": goal_id, "plan_version": 1,
            "trigger": "external_event", "result_ids": [], "finding": "虚构任务替换",
            "source_ref": "fictional-event-note"}})
        self.accept(goal_id, [self.item("DEMO-NEW", goal_id)],
                    version=2, review_id="DEMO-REMOVE-REVIEW")
        status = self.bridge.status(goal_id)
        self.assertEqual(status["state"], "conflict")
        self.assertIn("DEMO-OLD", [entry["task_id"] for entry in status["items"]
                                   if entry["state"] == "conflict"])
        self.assertEqual(self.bridge.sync(goal_id)["state"], "conflict")
        self.assertEqual(self.daily.db.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
