"""Fictional, local result/review flow for Issue #32."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from career import CHECKS, Workflow
from workbench.daily import DailyStore
from workbench.goal_daily_bridge import GoalDailyBridge
from workbench.goal_result_bridge import GoalResultBridge
from workbench.goals import GoalStore


class GoalResultBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.clock = lambda: self.now
        self.goals = GoalStore(self.temp.name, self.clock)
        self.daily = DailyStore(self.temp.name, self.clock)
        self.schedule = GoalDailyBridge(self.goals, self.daily)
        self.bridge = GoalResultBridge(self.goals, self.daily)

    def tearDown(self):
        self.goals.close()
        self.daily.close()
        self.temp.cleanup()

    def goal(self, goal_id):
        return {"id": goal_id, "title": "虚构目标", "domain": "learning",
                "timezone": "Asia/Shanghai", "weekly_minutes": 300,
                "success_criterion": "本人记录练习，不代表通过考试或投递成功",
                "baseline": "虚构基线", "target_at": None,
                "target_confidence": "unknown", "target_source_ref": None,
                "target_checked_at": None}

    def item(self, goal_id, task_id, kind="practice", source_kind="goal", source_id=None):
        return {"task_id": task_id, "title": "虚构练习" if kind == "practice" else "虚构申请",
                "reason": "根据虚构目标安排", "source_ref": "fictional-plan-source-v1",
                "task_kind": kind, "source_kind": source_kind, "source_id": source_id or goal_id,
                "scheduled_at": (self.now + timedelta(hours=1)).isoformat(),
                "estimated_minutes": 25, "completion_rule": "保留本人依据",
                "due_at": None, "due_confidence": "unknown", "due_source_ref": None,
                "due_checked_at": None, "flexible": True}

    def accept(self, goal_id, task_id, *, kind="practice", source_kind="goal", source_id=None):
        item = self.item(goal_id, task_id, kind, source_kind, source_id)
        self.goals.command("create_goal", f"CREATE-{goal_id}", {"goal": self.goal(goal_id)})
        self.goals.command("propose_plan", f"PROPOSE-{goal_id}", {"proposal": {
            "id": f"PLAN-{goal_id}", "goal_id": goal_id, "goal_revision": 1,
            "base_version": 0, "review_id": None, "reason": "虚构有来源初始计划",
            "items": [item], "method": "rule_template", "source_ref": "fictional-plan-source-v1"}})
        self.goals.command("decide_plan", f"ACCEPT-{goal_id}", {
            "proposal_id": f"PLAN-{goal_id}", "decision": "accept", "actor": "user",
            "reason": "本人接受虚构计划", "edited_items": None, "policy_ref": None})
        self.assertEqual(self.schedule.sync(goal_id)["state"], "applied")
        return item

    def confirm(self, goal_id, task_id, complete_event_id, *, correction_id=None,
                actual_minutes=25, metric=None, evidence_ref="fictional-evidence", note="虚构本人记录"):
        return self.bridge.record_completed(
            goal_id, task_id, complete_event_id, actual_minutes=actual_minutes,
            metric=metric, evidence_ref=evidence_ref, note=note,
            actor="user", correction_id=correction_id)

    def test_cet6_first_attempt_completion_and_correction_keep_first_result(self):
        self.accept("G-CET6", "T-CET6")
        self.daily.command("start", "START-CET6", "T-CET6")
        self.daily.command("complete", "DONE-CET6", "T-CET6", {"evidence": {
            "material_ref": "fictional-material", "first_attempt_ref": "fictional-first-attempt",
            "reflection_ref": "fictional-reflection"}})
        self.assertEqual(self.bridge.status("G-CET6")["tasks"][0]["state"],
                         "awaiting_user_confirmation")
        first = self.confirm("G-CET6", "T-CET6", "DONE-CET6",
                             metric={"correct": 11, "total": 20, "expected": 14})
        self.assertEqual(first["basis"], "self_report")
        self.assertEqual(first["plan_version"], 1)
        self.assertEqual(first["metric"]["correct"], 11)
        self.assertEqual(self.confirm("G-CET6", "T-CET6", "DONE-CET6",
                                      metric={"correct": 11, "total": 20, "expected": 14})["id"], first["id"])
        self.assertEqual(self.bridge.status("G-CET6")["tasks"][0]["state"], "recorded")
        with self.assertRaises(ValueError):
            self.confirm("G-CET6", "T-CET6", "DONE-CET6", actual_minutes=26,
                         metric={"correct": 11, "total": 20, "expected": 14})
        corrected = self.confirm("G-CET6", "T-CET6", "DONE-CET6",
                                 correction_id="CORRECT-1", actual_minutes=27,
                                 metric={"correct": 12, "total": 20, "expected": 14},
                                 note="本人更正虚构分数")
        self.assertNotEqual(first["id"], corrected["id"])
        results = self.goals.snapshot("G-CET6")["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["metric"]["correct"], 11)
        self.assertEqual(results[1]["metric"]["correct"], 12)
        self.assertFalse((Path(self.temp.name) / "state.sqlite3").exists())

    def test_daily_write_then_goal_write_failure_is_visible_and_retryable(self):
        self.accept("G-CET6", "T-CET6")
        self.daily.command("complete", "DONE-CET6", "T-CET6", {"evidence": {
            "material_ref": "fictional-material", "first_attempt_ref": "fictional-first-attempt",
            "reflection_ref": "fictional-reflection"}})
        original = self.goals.command

        def interrupted(kind, *args, **kwargs):
            if kind == "record_result":
                raise OSError("fictional interruption before goal write")
            return original(kind, *args, **kwargs)

        self.goals.command = interrupted
        with self.assertRaises(OSError):
            self.confirm("G-CET6", "T-CET6", "DONE-CET6")
        self.goals.close()
        self.daily.close()
        self.goals = GoalStore(self.temp.name, self.clock)
        self.daily = DailyStore(self.temp.name, self.clock)
        self.bridge = GoalResultBridge(self.goals, self.daily)
        self.assertEqual(self.bridge.status("G-CET6")["tasks"][0]["state"],
                         "awaiting_user_confirmation")
        self.confirm("G-CET6", "T-CET6", "DONE-CET6")
        self.confirm("G-CET6", "T-CET6", "DONE-CET6")
        self.assertEqual(len(self.goals.snapshot("G-CET6")["results"]), 1)
        self.assertEqual(self.daily.db.execute("SELECT COUNT(*) FROM daily_events WHERE command='complete'").fetchone()[0], 1)

    def test_activity_or_opened_page_cannot_be_submitted_result(self):
        self.accept("G-RECRUIT", "T-APPLY", kind="apply_job", source_kind="job", source_id="J-DEMO")
        with self.assertRaises(ValueError):
            self.confirm("G-RECRUIT", "T-APPLY", "OBSERVED-CODEX")
        with self.assertRaises(ValueError):
            self.daily.command("complete", "OPENED-PAGE", "T-APPLY", {"evidence": {
                "opened_url": "https://example.com/fictional-job"}})
        self.assertEqual(self.goals.snapshot("G-RECRUIT")["results"], [])

        flow = Workflow(self.temp.name)
        try:
            job_url = "https://example.com/fictional-job"
            resume = Path(self.temp.name) / "fictional-resume.md"
            resume.write_text("虚构材料", encoding="utf-8")
            with flow.db:
                flow.add({"id": "J-DEMO", "company": "虚构单位", "role": "虚构岗位",
                          "family": "operations", "url": job_url})
                flow.assess("J-DEMO", {"checked_at": datetime.now(timezone.utc).isoformat(),
                                      "source": job_url, "checks": {
                                          key: {"result": "pass", "evidence": "虚构资格"} for key in CHECKS}})
                flow.prepare("J-DEMO", {"resume_path": str(resume), "claims_evidence": ["虚构事实"]})
                flow.approve("J-DEMO", True)
                flow.record("J-DEMO", "submitted", "虚构回执；未发送申请")
            receipt_seq = flow.db.execute("SELECT seq FROM events WHERE kind='submitted'").fetchone()[0]
            self.now = datetime.now(timezone.utc) + timedelta(minutes=1)
            self.daily.command("complete", "DONE-APPLY", "T-APPLY", {"evidence": {
                "job_event_seq": receipt_seq}})
            result = self.confirm("G-RECRUIT", "T-APPLY", "DONE-APPLY",
                                  metric=None, evidence_ref="fictional-receipt-location")
            self.assertEqual(result["outcome"], "completed")
            self.assertEqual(flow.get("J-DEMO")["state"], "submitted")
        finally:
            flow.db.close()

    def test_missed_and_partial_review_propose_without_activating_or_penalty(self):
        item = self.accept("G-CET6", "T-CET6")
        missed = self.bridge.record_unfinished("G-CET6", "T-CET6", "REPORT-MISSED", "missed",
                                               actual_minutes=0, metric=None, evidence_ref=None,
                                               note="虚构课程冲突", actor="user")
        adjusted = {**item, "scheduled_at": (self.now + timedelta(days=1, hours=1)).isoformat(),
                    "reason": "本人根据冲突建议调整至次日", "source_ref": "self:REPORT-MISSED"}
        response = self.bridge.review_with_proposal(
            "G-CET6", missed["id"], "REVIEW-MISSED", "PROPOSAL-MISSED",
            proposed_items=[adjusted], finding="这次没有完成；可根据课程安排重新选择时段，不扣分。",
            proposal_reason="建议把虚构练习改到可用时段，等本人确认", source_ref="self:REPORT-MISSED",
            actor="user")
        self.assertEqual(response["review"]["trigger"], "missed_day")
        self.assertEqual(response["proposal"]["status"], "pending")
        self.assertEqual(self.goals.snapshot("G-CET6")["goal"]["active_version"], 1)
        self.assertEqual(self.daily._tasks()["T-CET6"]["state"], "scheduled")
        self.assertEqual(self.bridge.review_with_proposal(
            "G-CET6", missed["id"], "REVIEW-MISSED", "PROPOSAL-MISSED",
            proposed_items=[adjusted], finding="这次没有完成；可根据课程安排重新选择时段，不扣分。",
            proposal_reason="建议把虚构练习改到可用时段，等本人确认", source_ref="self:REPORT-MISSED",
            actor="user")["proposal"]["id"], "PROPOSAL-MISSED")
        partial = self.bridge.record_unfinished("G-CET6", "T-CET6", "REPORT-PARTIAL", "partial",
                                                actual_minutes=10, metric={"correct": 2, "total": 5},
                                                evidence_ref="fictional-first-attempt",
                                                note="本人只完成一部分", actor="user")
        self.assertEqual(partial["outcome"], "partial")
        self.assertEqual(len(self.goals.snapshot("G-CET6")["results"]), 2)
        self.assertNotIn("points", self.goals.snapshot("G-CET6"))

    def test_two_goals_and_current_projection_version_are_isolated(self):
        self.accept("G-ONE", "T-ONE")
        self.accept("G-TWO", "T-TWO")
        self.daily.command("complete", "DONE-ONE", "T-ONE", {"evidence": {
            "material_ref": "fictional-material", "first_attempt_ref": "fictional-first-attempt",
            "reflection_ref": "fictional-reflection"}})
        self.assertEqual(self.bridge.status("G-TWO")["tasks"], [])
        with self.assertRaises(ValueError):
            self.confirm("G-TWO", "T-ONE", "DONE-ONE")
        first = self.confirm("G-ONE", "T-ONE", "DONE-ONE")
        self.assertEqual(len(self.goals.snapshot("G-TWO")["results"]), 0)
        self.assertEqual(first["goal_id"], "G-ONE")
        with self.assertRaises(ValueError):
            self.bridge.record_unfinished("G-ONE", "T-ONE", "AUTOMATED", "missed",
                                          actual_minutes=0, metric=None, evidence_ref=None,
                                          note="tool observed", actor="tool")

    def test_result_uses_current_daily_projection_version_after_new_plan(self):
        item = self.accept("G-CET6", "T-CET6")
        self.goals.command("record_review", "REVIEW-FOR-V2", {"review": {
            "id": "R-FOR-V2", "goal_id": "G-CET6", "plan_version": 1,
            "trigger": "external_event", "result_ids": [], "finding": "虚构计划调时段",
            "source_ref": "fictional-note"}})
        changed = {**item, "scheduled_at": (self.now + timedelta(hours=2)).isoformat()}
        self.goals.command("propose_plan", "PROPOSE-V2", {"proposal": {
            "id": "P-V2", "goal_id": "G-CET6", "goal_revision": 1,
            "base_version": 1, "review_id": "R-FOR-V2", "reason": "虚构调整时段",
            "items": [changed], "method": "manual", "source_ref": "fictional-note"}})
        self.goals.command("decide_plan", "ACCEPT-V2", {
            "proposal_id": "P-V2", "decision": "accept", "actor": "user",
            "reason": "本人接受新时段", "edited_items": None, "policy_ref": None})
        self.daily.command("complete", "DONE-CET6", "T-CET6", {"evidence": {
            "material_ref": "fictional-material", "first_attempt_ref": "fictional-first-attempt",
            "reflection_ref": "fictional-reflection"}})

        # Simulate #33's event projection in this stacked branch: the initial
        # schedule row remains v1 while current DailyStore state is v2.
        original_tasks = self.daily._tasks

        def current_projection():
            tasks = original_tasks()
            tasks["T-CET6"]["plan_version"] = 2
            return tasks

        self.daily._tasks = current_projection
        result = self.confirm("G-CET6", "T-CET6", "DONE-CET6")
        self.assertEqual(result["plan_version"], 2)
        self.assertEqual(self.goals.snapshot("G-CET6")["plans"][0]["version"], 1)

    def test_confirmed_result_stays_recorded_after_projection_version_changes(self):
        item = self.accept("G-CET6", "T-CET6")
        self.daily.command("complete", "DONE-CET6", "T-CET6", {"evidence": {
            "material_ref": "fictional-material", "first_attempt_ref": "fictional-first-attempt",
            "reflection_ref": "fictional-reflection"}})
        first = self.confirm("G-CET6", "T-CET6", "DONE-CET6")
        self.goals.command("record_review", "REVIEW-FOR-V2", {"review": {
            "id": "R-FOR-V2", "goal_id": "G-CET6", "plan_version": 1,
            "trigger": "external_event", "result_ids": [], "finding": "虚构版本更新",
            "source_ref": "fictional-note"}})
        self.goals.command("propose_plan", "PROPOSE-V2", {"proposal": {
            "id": "P-V2", "goal_id": "G-CET6", "goal_revision": 1,
            "base_version": 1, "review_id": "R-FOR-V2", "reason": "虚构版本更新",
            "items": [item], "method": "manual", "source_ref": "fictional-note"}})
        self.goals.command("decide_plan", "ACCEPT-V2", {
            "proposal_id": "P-V2", "decision": "accept", "actor": "user",
            "reason": "本人接受虚构新版本", "edited_items": None, "policy_ref": None})
        original_tasks = self.daily._tasks

        def current_projection():
            tasks = original_tasks()
            tasks["T-CET6"]["plan_version"] = 2
            return tasks

        self.daily._tasks = current_projection
        self.assertEqual(self.bridge.status("G-CET6")["tasks"][0]["state"], "recorded")
        self.assertEqual(self.confirm("G-CET6", "T-CET6", "DONE-CET6")["id"], first["id"])
        corrected = self.confirm("G-CET6", "T-CET6", "DONE-CET6", correction_id="CORRECT-V2",
                                 actual_minutes=27, note="虚构更正")
        self.assertEqual(corrected["plan_version"], 1)
        self.assertEqual(len(self.goals.snapshot("G-CET6")["results"]), 2)

    def test_unfinished_report_id_retry_survives_projection_version_change(self):
        item = self.accept("G-CET6", "T-CET6")
        first = self.bridge.record_unfinished("G-CET6", "T-CET6", "REPORT-SAME-DAY", "partial",
                                              actual_minutes=10, metric=None, evidence_ref=None,
                                              note="虚构只做了一部分", actor="user")
        self.goals.command("record_review", "REVIEW-FOR-V2", {"review": {
            "id": "R-FOR-V2", "goal_id": "G-CET6", "plan_version": 1,
            "trigger": "external_event", "result_ids": [], "finding": "虚构版本更新",
            "source_ref": "fictional-note"}})
        self.goals.command("propose_plan", "PROPOSE-V2", {"proposal": {
            "id": "P-V2", "goal_id": "G-CET6", "goal_revision": 1,
            "base_version": 1, "review_id": "R-FOR-V2", "reason": "虚构版本更新",
            "items": [item], "method": "manual", "source_ref": "fictional-note"}})
        self.goals.command("decide_plan", "ACCEPT-V2", {
            "proposal_id": "P-V2", "decision": "accept", "actor": "user",
            "reason": "本人接受虚构新版本", "edited_items": None, "policy_ref": None})
        original_tasks = self.daily._tasks

        def current_projection():
            tasks = original_tasks()
            tasks["T-CET6"]["plan_version"] = 2
            return tasks

        self.daily._tasks = current_projection
        retried = self.bridge.record_unfinished("G-CET6", "T-CET6", "REPORT-SAME-DAY", "partial",
                                                actual_minutes=10, metric=None, evidence_ref=None,
                                                note="虚构只做了一部分", actor="user")
        self.assertEqual(retried["id"], first["id"])
        self.assertEqual(len(self.goals.snapshot("G-CET6")["results"]), 1)

    def test_review_write_then_proposal_interruption_retries_without_duplicate(self):
        item = self.accept("G-CET6", "T-CET6")
        missed = self.bridge.record_unfinished("G-CET6", "T-CET6", "REPORT-MISSED", "missed",
                                               actual_minutes=0, metric=None, evidence_ref=None,
                                               note="本人虚构漏做", actor="user")
        proposed = [{**item, "scheduled_at": (self.now + timedelta(days=1, hours=1)).isoformat()}]
        arguments = {"proposed_items": proposed, "finding": "漏做已记录；建议另选可用时段。",
                     "proposal_reason": "本人审阅延期建议", "source_ref": "self:REPORT-MISSED",
                     "actor": "user"}
        actual_command = self.goals.command

        def interrupted(kind, *args, **kwargs):
            if kind == "propose_plan":
                raise OSError("fictional interruption before proposal")
            return actual_command(kind, *args, **kwargs)

        self.goals.command = interrupted
        with self.assertRaises(OSError):
            self.bridge.review_with_proposal("G-CET6", missed["id"], "RV-1", "P-2", **arguments)
        self.assertEqual(len(self.goals.snapshot("G-CET6")["reviews"]), 1)
        self.assertEqual(len(self.goals.snapshot("G-CET6")["proposals"]), 1)  # initial plan proposal only
        self.goals.close()
        self.daily.close()
        self.goals = GoalStore(self.temp.name, self.clock)
        self.daily = DailyStore(self.temp.name, self.clock)
        self.bridge = GoalResultBridge(self.goals, self.daily)
        retry = self.bridge.review_with_proposal("G-CET6", missed["id"], "RV-1", "P-2", **arguments)
        self.assertEqual(retry["proposal"]["status"], "pending")
        self.assertEqual(len(self.goals.snapshot("G-CET6")["reviews"]), 1)
        self.assertEqual(len(self.goals.snapshot("G-CET6")["proposals"]), 2)


if __name__ == "__main__":
    unittest.main()
