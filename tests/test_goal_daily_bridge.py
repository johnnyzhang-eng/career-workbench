"""Fictional cross-store scheduling and recovery checks for Issue #17."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from workbench.daily import DailyStore
from workbench.goal_daily_bridge import GoalDailyBridge, adjust_event_id, daily_task, schedule_event_id
from workbench.goals import GoalStore


class GoalDailyBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc)
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

    def auto(self, goal_id, items, version=2):
        self.goals.auto_policy = lambda goal_record, old, new, policy_ref: policy_ref == "POLICY-DEMO"
        self.goals.task_state = lambda task_id: self.daily._tasks()[task_id]["state"]
        review_id = f"DEMO-AUTO-REVIEW-{version}"
        self.goals.command("record_review", f"DEMO-AUTO-REVIEW-E-{version}", {"review": {
            "id": review_id, "goal_id": goal_id, "plan_version": version - 1,
            "trigger": "external_event", "result_ids": [], "finding": "虚构微调",
            "source_ref": "fictional-local-note"}})
        proposal_id = f"DEMO-AUTO-P-{version}"
        self.goals.command("propose_plan", f"DEMO-AUTO-P-E-{version}", {"proposal": {
            "id": proposal_id, "goal_id": goal_id, "goal_revision": 1,
            "base_version": version - 1, "review_id": review_id,
            "reason": "仅移动弹性时段", "items": items, "method": "rule_template",
            "source_ref": "fictional-template-v1"}})
        self.goals.command("decide_plan", f"DEMO-AUTO-D-E-{version}", {
            "proposal_id": proposal_id, "decision": "auto_apply", "actor": "system",
            "reason": "同日本地弹性时段微调", "edited_items": None, "policy_ref": "POLICY-DEMO"})

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

    def test_pre_reschedule_daily_schedule_remains_readable_without_rewriting_provenance(self):
        goal_id, task_id = "DEMO-LEGACY", "DEMO-OLD-SCHEDULE"
        self.accept(goal_id, [self.item(task_id, goal_id)])
        plan = self.goals.snapshot(goal_id)["plans"][-1]
        legacy = daily_task(plan, plan["items"][0], goal_id)
        legacy.pop("flexible")
        legacy.pop("display_order")
        event_id = schedule_event_id(goal_id, 1, task_id)
        self.daily.command("schedule", event_id, task_id, {"task": legacy})
        row_before = dict(self.daily.db.execute("SELECT * FROM daily_events WHERE event_id=?", (event_id,)).fetchone())
        status = self.bridge.status(goal_id)
        self.assertEqual(status["state"], "applied")
        self.assertTrue(status["items"][0]["legacy_schedule"])
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        self.assertEqual(dict(self.daily.db.execute("SELECT * FROM daily_events WHERE event_id=?", (event_id,)).fetchone()),
                         row_before)

    def test_user_confirmed_edit_recovers_pending_daily_write_after_restart(self):
        goal_id, task_id = "DEMO-MANUAL", "DEMO-FUTURE"
        original = self.item(task_id, goal_id)
        self.accept(goal_id, [original])
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        self.goals.command("record_review", "REVIEW-MANUAL-E", {"review": {
            "id": "REVIEW-MANUAL", "goal_id": goal_id, "plan_version": 1,
            "trigger": "external_event", "result_ids": [], "finding": "虚构温和复盘",
            "source_ref": "fictional-note"}})
        proposal_id = "P-MANUAL"
        self.goals.command("propose_plan", "PROPOSE-MANUAL-E", {"proposal": {
            "id": proposal_id, "goal_id": goal_id, "goal_revision": 1, "base_version": 1,
            "review_id": "REVIEW-MANUAL", "reason": "本人考虑改时段", "items": [original],
            "method": "manual", "source_ref": "fictional-note"}})
        changed = {**original, "scheduled_at": (self.now + timedelta(hours=2)).isoformat()}
        self.goals.command("decide_plan", "DECIDE-MANUAL-E", {
            "proposal_id": proposal_id, "decision": "edit", "actor": "user",
            "reason": "本人查看前后时段并确认", "edited_items": [changed], "policy_ref": None})
        self.assertEqual(self.goals.snapshot(goal_id)["plans"][0]["items"][0]["scheduled_at"],
                         original["scheduled_at"])
        self.assertEqual(self.bridge.status(goal_id)["state"], "sync_pending")
        actual_command = self.daily.command
        def interrupted(*_args, **_kwargs):
            raise sqlite3.OperationalError("fictional daily write interruption")
        self.daily.command = interrupted
        self.assertEqual(self.bridge.sync(goal_id)["state"], "sync_pending")
        self.daily.command = actual_command
        self.daily.close()
        self.goals.close()
        self.daily = DailyStore(self.temp.name, self.clock)
        self.goals = GoalStore(self.temp.name, self.clock)
        self.bridge = GoalDailyBridge(self.goals, self.daily)
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        self.assertEqual(self.daily._tasks()[task_id]["scheduled_at"], changed["scheduled_at"])
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        self.assertEqual(self.daily.db.execute("SELECT COUNT(*) FROM daily_events WHERE command='reschedule'")
                         .fetchone()[0], 1)

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

    def test_same_day_move_and_undo_replay_with_history_and_restart(self):
        goal_id, task_id = "DEMO-CET6", "DEMO-READ"
        original = self.item(task_id, goal_id)
        self.accept(goal_id, [original])
        self.bridge.sync(goal_id)
        moved = {**original, "scheduled_at": (self.now + timedelta(hours=2)).isoformat()}
        self.auto(goal_id, [moved])
        self.assertEqual(self.bridge.status(goal_id)["state"], "sync_pending")
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        task = self.daily._tasks()[task_id]
        self.assertEqual((task["scheduled_at"], task["origin_scheduled_at"], task["plan_version"]),
                         (moved["scheduled_at"], original["scheduled_at"], 2))
        self.assertEqual(self.daily.db.execute("SELECT event_id FROM daily_events ORDER BY seq DESC LIMIT 1").fetchone()[0],
                         adjust_event_id(goal_id, 2, task_id))
        self.goals.command("undo_auto", "DEMO-UNDO-E", {
            "goal_id": goal_id, "version": 2, "actor": "user", "reason": "恢复原时段"})
        self.assertEqual(self.bridge.status(goal_id)["state"], "sync_pending")
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        task = self.daily._tasks()[task_id]
        self.assertEqual((task["scheduled_at"], task["origin_scheduled_at"], task["plan_version"]),
                         (original["scheduled_at"], original["scheduled_at"], 3))
        self.assertEqual(self.daily.db.execute("SELECT command FROM daily_events ORDER BY seq").fetchall()[-1][0],
                         "reschedule")
        self.assertEqual(self.daily.db.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0], 3)
        self.daily.close()
        self.goals.close()
        self.daily = DailyStore(self.temp.name, self.clock)
        self.goals = GoalStore(self.temp.name, self.clock)
        self.bridge = GoalDailyBridge(self.goals, self.daily)
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        self.assertEqual(self.daily.db.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0], 3)

    def test_auto_reorder_changes_snapshot_order_without_changing_evidence(self):
        goal_id = "DEMO-CET6"
        first = self.item("DEMO-FIRST", goal_id)
        second = self.item("DEMO-SECOND", goal_id,
                           scheduled_at=(self.now + timedelta(hours=1, minutes=30)).isoformat())
        self.accept(goal_id, [first, second])
        self.bridge.sync(goal_id)
        self.assertEqual([task["id"] for task in self.daily.snapshot()["tasks"]],
                         ["DEMO-FIRST", "DEMO-SECOND"])
        self.auto(goal_id, [second, first])
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        self.assertEqual([task["id"] for task in self.daily.snapshot()["tasks"]],
                         ["DEMO-SECOND", "DEMO-FIRST"])
        self.assertEqual(self.daily._tasks()["DEMO-FIRST"]["evidence_state"], "missing")
        self.assertEqual(self.daily._tasks()["DEMO-SECOND"]["state"], "scheduled")
        self.assertEqual(self.daily.db.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0], 4)

    def test_started_after_auto_acceptance_is_explicit_conflict(self):
        goal_id, task_id = "DEMO-CET6", "DEMO-READ"
        first = self.item(task_id, goal_id)
        self.accept(goal_id, [first])
        self.bridge.sync(goal_id)
        moved = {**first, "scheduled_at": (self.now + timedelta(hours=2)).isoformat()}
        self.auto(goal_id, [moved])
        self.daily.command("start", "DEMO-START-RACE", task_id)
        self.assertEqual(self.bridge.status(goal_id)["state"], "conflict")
        self.assertEqual(self.bridge.sync(goal_id)["state"], "conflict")
        self.assertEqual(self.daily._tasks()[task_id]["scheduled_at"], first["scheduled_at"])

    def test_partial_auto_replay_recovers_after_restart(self):
        goal_id = "DEMO-CET6"
        first = self.item("DEMO-FIRST", goal_id)
        second = self.item("DEMO-SECOND", goal_id)
        self.accept(goal_id, [first, second])
        self.bridge.sync(goal_id)
        moved = [{**first, "scheduled_at": (self.now + timedelta(hours=2)).isoformat()},
                 {**second, "scheduled_at": (self.now + timedelta(hours=3)).isoformat()}]
        self.auto(goal_id, moved)
        actual_command = self.daily.command
        calls = [0]

        def interrupted(*args, **kwargs):
            calls[0] += 1
            if calls[0] == 2:
                raise sqlite3.OperationalError("fictional interrupted adjustment")
            return actual_command(*args, **kwargs)

        self.daily.command = interrupted
        first_result = self.bridge.sync(goal_id)
        self.assertEqual(first_result["state"], "sync_pending")
        self.assertIn("fictional interrupted", first_result["last_error"])
        self.daily.close()
        self.goals.close()
        self.daily = DailyStore(self.temp.name, self.clock)
        self.goals = GoalStore(self.temp.name, self.clock)
        self.bridge = GoalDailyBridge(self.goals, self.daily)
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        self.assertEqual(self.daily.db.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0], 4)

    def test_multiple_accepted_moves_replay_each_version_before_current_view(self):
        goal_id, task_id = "DEMO-CET6", "DEMO-READ"
        first = self.item(task_id, goal_id)
        self.accept(goal_id, [first])
        self.bridge.sync(goal_id)
        second = {**first, "scheduled_at": (self.now + timedelta(hours=2)).isoformat()}
        third = {**first, "scheduled_at": (self.now + timedelta(hours=3)).isoformat()}
        self.auto(goal_id, [second], version=2)
        self.auto(goal_id, [third], version=3)
        self.assertEqual(self.bridge.status(goal_id)["state"], "sync_pending")
        self.assertEqual(self.bridge.sync(goal_id)["state"], "applied")
        self.assertEqual(self.daily._tasks()[task_id]["scheduled_at"], third["scheduled_at"])
        ids = [row[0] for row in self.daily.db.execute("SELECT event_id FROM daily_events ORDER BY seq")]
        self.assertEqual(ids, [schedule_event_id(goal_id, 1, task_id),
                               adjust_event_id(goal_id, 2, task_id),
                               adjust_event_id(goal_id, 3, task_id)])

    def test_cross_day_and_material_edit_are_not_auto_applied(self):
        goal_id = "DEMO-CET6"
        first = self.item("DEMO-READ", goal_id)
        self.accept(goal_id, [first])
        self.bridge.sync(goal_id)
        self.goals.auto_policy = lambda *args: True
        self.goals.task_state = lambda task_id: self.daily._tasks()[task_id]["state"]
        self.goals.command("record_review", "DEMO-BOUNDARY-R-E", {"review": {
            "id": "DEMO-BOUNDARY-R", "goal_id": goal_id, "plan_version": 1,
            "trigger": "external_event", "result_ids": [], "finding": "虚构边界",
            "source_ref": "fictional-local-note"}})
        unsafe_items = [
            {**first, "scheduled_at": (self.now + timedelta(days=1, hours=1)).isoformat()},
            {**first, "title": "擅自修改内容"},
            {**first, "flexible": False},
        ]
        for index, item in enumerate(unsafe_items):
            proposal_id = f"DEMO-BOUNDARY-{index}"
            self.goals.command("propose_plan", f"DEMO-BOUNDARY-P-{index}", {"proposal": {
                "id": proposal_id, "goal_id": goal_id, "goal_revision": 1,
                "base_version": 1, "review_id": "DEMO-BOUNDARY-R",
                "reason": "虚构提案", "items": [item], "method": "rule_template",
                "source_ref": "fictional-template-v1"}})
            with self.assertRaisesRegex(ValueError, "没有授权的自动调整策略"):
                self.goals.command("decide_plan", f"DEMO-BOUNDARY-D-{index}", {
                    "proposal_id": proposal_id, "decision": "auto_apply", "actor": "system",
                    "reason": "不得自动改", "edited_items": None, "policy_ref": "POLICY-DEMO"})
        self.assertEqual(self.bridge.status(goal_id)["state"], "applied")

    def test_fixed_and_verified_deadline_tasks_reject_auto_move(self):
        for goal_id, fixed in (("DEMO-FIXED", True), ("DEMO-DEADLINE", False)):
            item = self.item(f"{goal_id}-TASK", goal_id)
            if fixed:
                item["flexible"] = False
            else:
                item.update(due_at=(self.now + timedelta(hours=5)).isoformat(),
                            due_confidence="verified", due_source_ref="fictional-deadline-source",
                            due_checked_at=self.now.isoformat())
            self.accept(goal_id, [item])
            self.bridge.sync(goal_id)
            self.goals.task_state = lambda task_id: self.daily._tasks()[task_id]["state"]
            self.goals.auto_policy = lambda *args: True
            review_id = f"{goal_id}-REVIEW"
            self.goals.command("record_review", f"{goal_id}-REVIEW-E", {"review": {
                "id": review_id, "goal_id": goal_id, "plan_version": 1,
                "trigger": "external_event", "result_ids": [], "finding": "虚构改期",
                "source_ref": "fictional-local-note"}})
            proposal_id = f"{goal_id}-P2"
            self.goals.command("propose_plan", f"{goal_id}-P2-E", {"proposal": {
                "id": proposal_id, "goal_id": goal_id, "goal_revision": 1,
                "base_version": 1, "review_id": review_id, "reason": "虚构提案",
                "items": [{**item, "scheduled_at": (self.now + timedelta(hours=2)).isoformat()}],
                "method": "rule_template", "source_ref": "fictional-template-v1"}})
            with self.assertRaisesRegex(ValueError, "没有授权的自动调整策略"):
                self.goals.command("decide_plan", f"{goal_id}-P2-D", {
                    "proposal_id": proposal_id, "decision": "auto_apply", "actor": "system",
                    "reason": "拒绝不安全改期", "edited_items": None, "policy_ref": "POLICY-DEMO"})
            self.assertEqual(self.bridge.status(goal_id)["state"], "applied")


if __name__ == "__main__":
    unittest.main()
