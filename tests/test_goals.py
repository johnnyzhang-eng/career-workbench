"""Fictional contract examples. No real job, study record, or external action."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from workbench.daily import DailyStore
from workbench.goals import GoalStore


BASE = datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc)


def goal(goal_id="DEMO-CET6"):
    return {"id": goal_id, "title": "虚构 CET6 七日练习", "domain": "learning",
            "timezone": "Asia/Shanghai", "weekly_minutes": 300,
            "success_criterion": "本人完成设定的练习与阶段测验；不代表通过考试",
            "baseline": "虚构起点：听力 12/25、阅读 16/30",
            "target_at": "2026-11-30T20:00:00+08:00", "target_confidence": "self_set",
            "target_source_ref": None, "target_checked_at": None}


def item(task_id="DEMO-READ-1", scheduled_at="2026-09-24T20:00:00+08:00"):
    return {"task_id": task_id, "title": "阅读一组虚构练习",
            "reason": "根据虚构基线安排阅读练习",
            "source_ref": "fictional-template-v1;self:baseline",
            "task_kind": "practice",
            "source_kind": "goal", "source_id": "DEMO-CET6",
            "scheduled_at": scheduled_at, "estimated_minutes": 35,
            "completion_rule": "本人记录完成页数、正确数和错题位置",
            "due_at": None, "due_confidence": "unknown", "due_source_ref": None,
            "due_checked_at": None, "flexible": True}


def proposal(proposal_id, base, review_id, items, reason="根据实际结果调整"):
    return {"id": proposal_id, "goal_id": "DEMO-CET6", "goal_revision": 1,
            "base_version": base,
            "review_id": review_id, "reason": reason, "items": items,
            "method": "rule_template" if base == 0 else "ai_suggestion",
            "source_ref": "fictional-template-v1" if base == 0 else f"fictional-template-v1;review:{review_id}"}


def result(result_id, task_id="DEMO-READ-1", outcome="completed", basis="self_report",
           metric=None):
    return {"id": result_id, "goal_id": "DEMO-CET6", "plan_version": 1,
            "task_id": task_id, "outcome": outcome, "basis": basis, "actual_minutes": 30,
            "metric": metric, "evidence_ref": "private/fictional-practice-note",
            "note": "仅为虚构自述"}


def review(review_id, trigger, result_ids, source_ref=None):
    return {"id": review_id, "goal_id": "DEMO-CET6", "plan_version": 1,
            "trigger": trigger, "result_ids": result_ids, "finding": "需要改动下一周的安排",
            "source_ref": source_ref}


class GoalContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = lambda: BASE
        self.store = GoalStore(self.temp.name, self.clock)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def command(self, kind, event_id, payload):
        return self.store.command(kind, event_id, payload)

    def initial_plan(self):
        self.command("create_goal", "E-GOAL", {"goal": goal()})
        self.command("propose_plan", "E-PROPOSE-1",
                     {"proposal": proposal("P-1", 0, None, [item()])})
        self.command("decide_plan", "E-ACCEPT-1",
                     {"proposal_id": "P-1", "decision": "accept", "actor": "user",
                      "reason": "本人同意此虚构计划", "edited_items": None, "policy_ref": None})

    def test_cet6_manual_goal_without_job_record_and_immutable_versions(self):
        self.initial_plan()
        self.assertFalse((self.store.workspace / "state.sqlite3").exists())
        self.assertEqual(self.store.snapshot("DEMO-CET6")["goal"]["active_version"], 1)
        original = self.store.snapshot("DEMO-CET6")["plans"][0]["items"]
        self.assertEqual(original[0]["reason"], "根据虚构基线安排阅读练习")
        self.assertEqual(original[0]["source_ref"], "fictional-template-v1;self:baseline")
        self.command("record_result", "E-RESULT-1", {"result": result("R-1", metric={"correct": 11, "total": 20, "expected": 14})})
        self.command("record_review", "E-REVIEW-1",
                     {"review": review("RV-1", "lower_result", ["R-1"])})
        revised = [item("DEMO-READ-2", "2026-09-25T20:00:00+08:00")]
        self.command("propose_plan", "E-PROPOSE-2",
                     {"proposal": proposal("P-2", 1, "RV-1", revised)})
        self.assertEqual(self.store.snapshot("DEMO-CET6")["goal"]["active_version"], 1)
        self.command("decide_plan", "E-EDIT-2",
                     {"proposal_id": "P-2", "decision": "edit", "actor": "user",
                      "reason": "改为周末", "edited_items": [item("DEMO-READ-2", "2026-09-26T10:00:00+08:00")],
                      "policy_ref": None})
        snap = self.store.snapshot("DEMO-CET6")
        self.assertEqual(snap["goal"]["active_version"], 2)
        self.assertEqual(snap["plans"][0]["items"], original)
        self.assertNotEqual(snap["plans"][1]["items"], revised)
        self.assertEqual(snap["results"][0]["plan_version"], 1)
        self.assertEqual(snap["proposals"][1]["decision"], "edit")
        reopened = GoalStore(self.temp.name, self.clock)
        try:
            self.assertEqual(reopened.snapshot("DEMO-CET6"), snap)
        finally:
            reopened.close()

    def test_each_plan_item_requires_reason_and_source_reference(self):
        self.command("create_goal", "E-GOAL", {"goal": goal()})
        for field in ("reason", "source_ref"):
            bad = item()
            bad[field] = "  "
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, f"{field} 必须是非空文本"):
                self.command("propose_plan", f"E-BAD-{field}",
                             {"proposal": proposal(f"P-BAD-{field}", 0, None, [bad])})
        good = item()
        self.command("propose_plan", "E-GOOD",
                     {"proposal": proposal("P-GOOD", 0, None, [good])})
        self.command("decide_plan", "E-GOOD-ACCEPT",
                     {"proposal_id": "P-GOOD", "decision": "accept", "actor": "user",
                      "reason": "本人确认", "edited_items": None, "policy_ref": None})
        saved = self.store.snapshot("DEMO-CET6")["plans"][0]["items"][0]
        self.assertEqual((saved["reason"], saved["source_ref"]),
                         (good["reason"], good["source_ref"]))

    def test_missed_day_and_external_event_can_propose_but_decline_preserves_plan(self):
        self.initial_plan()
        self.command("record_result", "E-MISSED", {"result": result("R-MISSED", outcome="missed")})
        self.command("record_review", "E-MISSED-REVIEW",
                     {"review": review("RV-MISSED", "missed_day", ["R-MISSED"])})
        self.command("propose_plan", "E-P-MISSED",
                     {"proposal": proposal("P-MISSED", 1, "RV-MISSED", [item("DEMO-RETRY")])})
        self.command("decide_plan", "E-DECLINE",
                     {"proposal_id": "P-MISSED", "decision": "decline", "actor": "user",
                      "reason": "本人暂不调整", "edited_items": None, "policy_ref": None})
        self.command("record_review", "E-EXTERNAL",
                     {"review": review("RV-EXTERNAL", "external_event", [], "private/fictional-event-note")})
        self.command("propose_plan", "E-P-EXTERNAL",
                     {"proposal": proposal("P-EXTERNAL", 1, "RV-EXTERNAL", [item("DEMO-NEW")])})
        snap = self.store.snapshot("DEMO-CET6")
        self.assertEqual(snap["goal"]["active_version"], 1)
        self.assertEqual([p["status"] for p in snap["proposals"]],
                         ["accepted", "declined", "pending"])

    def test_tool_activity_is_observation_and_auto_policy_is_explicit(self):
        self.initial_plan()
        seen = result("R-OBSERVED", outcome="observed", basis="tool_observation")
        seen["metric"] = None
        self.command("record_result", "E-OBSERVED", {"result": seen})
        falsely_done = result("R-FALSE", outcome="completed", basis="tool_observation")
        with self.assertRaisesRegex(ValueError, "工具活动只能是线索"):
            self.command("record_result", "E-FALSE", {"result": falsely_done})
        self.command("record_review", "E-RV", {"review": review("RV-OBS", "weekly", ["R-OBSERVED"])})
        self.command("propose_plan", "E-P2",
                     {"proposal": proposal("P-2", 1, "RV-OBS", [item("DEMO-NEXT")])})
        auto = {"proposal_id": "P-2", "decision": "auto_apply", "actor": "system",
                "reason": "虚构策略允许的调整", "edited_items": None, "policy_ref": "POLICY-DEMO-1"}
        with self.assertRaisesRegex(ValueError, "没有授权的自动调整策略"):
            self.command("decide_plan", "E-AUTO-NO-POLICY", auto)
        self.store.auto_policy = lambda goal_record, old, new, policy_ref: False
        with self.assertRaisesRegex(ValueError, "没有授权的自动调整策略"):
            self.command("decide_plan", "E-AUTO-DENIED", auto)
        self.store.task_state = lambda task_id: "scheduled"
        self.store.auto_policy = lambda goal_record, old, new, policy_ref: policy_ref == "POLICY-DEMO-1"
        unsafe = [item("DEMO-NEXT", "2026-09-26T10:00:00+08:00")]
        self.command("record_review", "E-RV-EXTERNAL",
                     {"review": review("RV-EXT", "external_event", [], "private/fictional-event")})
        self.command("propose_plan", "E-P-UNSAFE",
                     {"proposal": proposal("P-UNSAFE", 1, "RV-EXT", unsafe)})
        with self.assertRaisesRegex(ValueError, "没有授权的自动调整策略"):
            self.command("decide_plan", "E-AUTO-UNSAFE",
                         {**auto, "proposal_id": "P-UNSAFE"})
        # Same task, same local day, only the scheduled time moves.
        moved = [item("DEMO-READ-1", "2026-09-24T21:00:00+08:00")]
        self.command("propose_plan", "E-P-SAFE",
                     {"proposal": proposal("P-SAFE", 1, "RV-OBS", moved)})
        auto["proposal_id"] = "P-SAFE"
        self.command("decide_plan", "E-AUTO-OK", auto)
        snap = self.store.snapshot("DEMO-CET6")
        self.assertEqual(snap["goal"]["active_version"], 2)
        self.assertEqual(snap["proposals"][-1]["policy_ref"], "POLICY-DEMO-1")
        self.assertEqual(snap["plans"][1]["decision"], "auto_apply")
        self.store.task_state = lambda task_id: "in_progress"
        with self.assertRaisesRegex(ValueError, "受影响任务已开始"):
            self.command("undo_auto", "E-UNDO-TOO-LATE",
                         {"goal_id": "DEMO-CET6", "version": 2,
                          "actor": "user", "reason": "开始后尝试撤销"})
        self.store.task_state = lambda task_id: "scheduled"
        self.command("undo_auto", "E-UNDO", {"goal_id": "DEMO-CET6", "version": 2,
                                               "actor": "user", "reason": "恢复原时段"})
        undone = self.store.snapshot("DEMO-CET6")
        self.assertEqual(undone["goal"]["active_version"], 3)
        self.assertEqual(undone["plans"][2]["items"], undone["plans"][0]["items"])
        self.assertEqual(undone["plans"][2]["undid_version"], 2)

    def test_validation_idempotency_and_job_gate_stays_with_daily_store(self):
        self.initial_plan()
        self.command("create_goal", "E-GOAL", {"goal": goal()})
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM goal_events").fetchone()[0], 3)
        with self.assertRaisesRegex(ValueError, "event_id 已用于不同命令"):
            self.command("create_goal", "E-GOAL", {"goal": goal("OTHER")})
        stale = proposal("P-STALE", 0, None, [item()])
        with self.assertRaisesRegex(ValueError, "过期计划"):
            self.command("propose_plan", "E-STALE", {"proposal": stale})
        bad_goal = goal("DEMO-BAD")
        bad_goal.update(target_at="2026-11-30T20:00:00+08:00", target_confidence="unknown")
        with self.assertRaisesRegex(ValueError, "未知的 target"):
            self.command("create_goal", "E-BAD-GOAL", {"goal": bad_goal})
        daily = DailyStore(self.temp.name, self.clock)
        try:
            job_task = {"id": "DEMO-APPLY", "title": "虚构投递", "kind": "apply_job",
                        "source_kind": "job", "source_id": "DEMO-JOB", "reason": "模拟门槛",
                        "scheduled_at": BASE.isoformat(), "due_at": None, "due_verified": False}
            daily.command("schedule", "DAILY-SCHEDULE", "DEMO-APPLY", {"task": job_task})
            with self.assertRaises(ValueError):
                daily.command("complete", "DAILY-OPENED", "DEMO-APPLY",
                              {"evidence": {"opened_url": "https://example.com/jobs/fictional"}})
            self.assertEqual(daily.snapshot()["tasks"][0]["state"], "scheduled")
        finally:
            daily.close()

    def test_public_fixture_and_manual_generic_goal(self):
        fixture_path = Path(__file__).resolve().parents[1] / "templates/goal_contract_fixture.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assertTrue(fixture["fictional"])
        self.store.clock = lambda: datetime(2026, 10, 8, 13, 0, tzinfo=timezone.utc)
        for command in fixture["commands"]:
            self.store.command(command["kind"], command["event_id"], command["payload"],
                               at=command["at"])
        snap = self.store.snapshot("FIXTURE-CET6")
        self.assertEqual(snap["goal"]["active_version"], 1)
        self.assertEqual(snap["reviews"][0]["trigger"], "lower_result")

        custom = goal("DEMO-OTHER")
        custom.update(domain="custom", title="虚构通用目标", target_at=None,
                      target_confidence="unknown")
        self.command("create_goal", "E-OTHER", {"goal": custom})
        manual_item = item("OTHER-TASK")
        manual_item["source_id"] = "DEMO-OTHER"
        manual_item["task_kind"] = "custom"
        manual = {"id": "OTHER-P-1", "goal_id": "DEMO-OTHER", "base_version": 0,
                  "goal_revision": 1, "review_id": None, "reason": "本人手动列任务", "items": [manual_item],
                  "method": "manual", "source_ref": None}
        self.command("propose_plan", "E-OTHER-P", {"proposal": manual})
        self.command("decide_plan", "E-OTHER-ACCEPT",
                     {"proposal_id": "OTHER-P-1", "decision": "accept", "actor": "user",
                      "reason": "本人确认手动任务", "edited_items": None, "policy_ref": None})
        self.assertEqual(self.store.snapshot("DEMO-OTHER")["plans"][0]["items"][0]["source_kind"],
                         "goal")

    def test_auto_reorder_only_unstarted_flexible_tasks(self):
        self.command("create_goal", "E-GOAL", {"goal": goal()})
        first = item("A")
        second = item("B", "2026-09-24T21:00:00+08:00")
        self.command("propose_plan", "E-P1",
                     {"proposal": proposal("P-1", 0, None, [first, second])})
        self.command("decide_plan", "E-D1", {"proposal_id": "P-1", "decision": "accept",
                                               "actor": "user", "reason": "本人确认", "edited_items": None,
                                               "policy_ref": None})
        observed = result("OBS", task_id="A", outcome="observed", basis="tool_observation")
        observed["metric"] = None
        self.command("record_result", "E-OBS", {"result": observed})
        self.command("record_review", "E-RV", {"review": review("RV-1", "weekly", ["OBS"])})
        self.store.auto_policy = lambda goal_record, old, new, policy_ref: True
        self.store.task_state = lambda task_id: "scheduled" if task_id == "A" else "in_progress"
        self.command("propose_plan", "E-P2",
                     {"proposal": proposal("P-2", 1, "RV-1", [second, first])})
        auto = {"proposal_id": "P-2", "decision": "auto_apply", "actor": "system",
                "reason": "显示排序", "edited_items": None, "policy_ref": "POLICY-DEMO"}
        with self.assertRaisesRegex(ValueError, "没有授权的自动调整策略"):
            self.command("decide_plan", "E-DENIED", auto)
        self.store.task_state = lambda task_id: "scheduled"
        self.command("decide_plan", "E-ALLOWED", auto)
        self.assertEqual([i["task_id"] for i in self.store.snapshot("DEMO-CET6")["plans"][1]["items"]],
                         ["B", "A"])

    def test_practice_source_and_user_goal_revision_invalidate_old_proposal(self):
        self.command("create_goal", "E-GOAL", {"goal": goal()})
        initial = item()
        self.assertEqual(initial["task_kind"], "practice")
        self.command("propose_plan", "E-OLD",
                     {"proposal": proposal("P-OLD", 0, None, [initial])})
        changed_goal = goal()
        changed_goal["weekly_minutes"] = 280
        with self.assertRaisesRegex(ValueError, "目标修改需要用户"):
            self.command("update_goal", "E-SYSTEM-UPDATE",
                         {"goal": changed_goal, "actor": "system", "reason": "未经本人确认"})
        self.command("update_goal", "E-USER-UPDATE",
                     {"goal": changed_goal, "actor": "user", "reason": "本人调整每周可用时间"})
        snap = self.store.snapshot("DEMO-CET6")
        self.assertEqual(snap["goal"]["revision"], 2)
        self.assertEqual(len(snap["goal_revisions"]), 2)
        self.assertEqual(snap["proposals"][0]["status"], "superseded")
        with self.assertRaisesRegex(ValueError, "提案不存在或已决策"):
            self.command("decide_plan", "E-STALE-DECISION",
                         {"proposal_id": "P-OLD", "decision": "accept", "actor": "user",
                          "reason": "旧提案", "edited_items": None, "policy_ref": None})
        updated = proposal("P-NEW", 0, None, [initial])
        updated["goal_revision"] = 2
        self.command("propose_plan", "E-NEW", {"proposal": updated})
        self.command("decide_plan", "E-NEW-ACCEPT",
                     {"proposal_id": "P-NEW", "decision": "accept", "actor": "user",
                      "reason": "本人确认新版计划", "edited_items": None, "policy_ref": None})
        self.assertEqual(self.store.snapshot("DEMO-CET6")["plans"][0]["goal_revision"], 2)

        job_practice = item("JOB-PRACTICE")
        job_practice.update(source_kind="job", source_id="DEMO-JOB")
        self.command("record_review", "E-RV-EXTERNAL",
                     {"review": review("RV-EXTERNAL", "external_event", [], "private/fictional-job-note")})
        self.command("propose_plan", "E-JOB-PRACTICE",
                     {"proposal": proposal("P-JOB-PRACTICE", 1, "RV-EXTERNAL", [job_practice]) | {"goal_revision": 2}})
        bad_apply = item("BAD-APPLY")
        bad_apply["task_kind"] = "apply_job"
        with self.assertRaisesRegex(ValueError, "通用目标任务应关联当前 goal"):
            self.command("propose_plan", "E-BAD-APPLY",
                         {"proposal": proposal("P-BAD-APPLY", 1, "RV-EXTERNAL", [bad_apply]) | {"goal_revision": 2}})
        next_goal = goal()
        next_goal["weekly_minutes"] = 240
        self.command("update_goal", "E-USER-UPDATE-2",
                     {"goal": next_goal, "actor": "user", "reason": "虚构周可用时间再次变化"})
        latest = self.store.snapshot("DEMO-CET6")
        self.assertEqual(latest["goal"]["active_version"], 1)
        self.assertTrue(latest["goal"]["needs_replan"])
        self.assertEqual(latest["plans"][0]["goal_revision"], 2)
        self.assertEqual(latest["proposals"][-1]["status"], "superseded")
        self.command("record_review", "E-GOAL-RV",
                     {"review": review("RV-GOAL-CHANGE", "goal_change", [])})
        fresh = proposal("P-GOAL-CHANGE", 1, "RV-GOAL-CHANGE", [item("NEXT-PRACTICE")])
        fresh["goal_revision"] = 3
        self.command("propose_plan", "E-GOAL-P", {"proposal": fresh})
        self.command("decide_plan", "E-GOAL-D",
                     {"proposal_id": "P-GOAL-CHANGE", "decision": "accept", "actor": "user",
                      "reason": "本人确认可用时间变更后的计划", "edited_items": None, "policy_ref": None})
        latest = self.store.snapshot("DEMO-CET6")
        self.assertEqual(latest["goal"]["active_version"], 2)
        self.assertFalse(latest["goal"]["needs_replan"])

    def test_ai_plan_proposal_requires_source(self):
        self.initial_plan()
        self.command("record_result", "E-RESULT", {"result": result("R-AI")})
        self.command("record_review", "E-REVIEW",
                     {"review": review("RV-AI", "weekly", ["R-AI"])})
        unsourced = proposal("P-AI-UNSOURCED", 1, "RV-AI", [item("AI-NEXT")])
        unsourced["source_ref"] = None
        with self.assertRaisesRegex(ValueError, "proposal.source_ref 必须是非空文本"):
            self.command("propose_plan", "E-AI-UNSOURCED", {"proposal": unsourced})
        sourced = proposal("P-AI-SOURCED", 1, "RV-AI", [item("AI-NEXT")])
        self.command("propose_plan", "E-AI-SOURCED", {"proposal": sourced})
        self.assertEqual(self.store.snapshot("DEMO-CET6")["proposals"][-1]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
