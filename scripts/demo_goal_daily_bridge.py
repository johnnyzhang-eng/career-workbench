"""Fictional GoalStore -> DailyStore replay; no external actions or user data."""

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workbench.daily import DailyStore
from workbench.goal_daily_bridge import GoalDailyBridge
from workbench.goals import GoalStore


def goal(goal_id):
    return {"id": goal_id, "title": "虚构目标", "domain": "learning",
            "timezone": "Asia/Shanghai", "weekly_minutes": 300,
            "success_criterion": "本人保存实际依据", "baseline": "虚构起点",
            "target_at": None, "target_confidence": "unknown",
            "target_source_ref": None, "target_checked_at": None}


def item(task_id, goal_id, kind, source_kind, source_id, when):
    return {"task_id": task_id, "title": "虚构阅读练习" if kind == "practice" else "虚构岗位投递",
            "task_kind": kind, "source_kind": source_kind, "source_id": source_id,
            "reason": "根据虚构模板安排，尚需实际依据", "source_ref": "fictional-task-source-v1",
            "scheduled_at": when, "estimated_minutes": 30,
            "completion_rule": "按任务类型保存真实依据", "flexible": True,
            "due_at": None, "due_confidence": "unknown", "due_source_ref": None,
            "due_checked_at": None}


def accept(goals, goal_id, task):
    goals.command("create_goal", f"G-{goal_id}", {"goal": goal(goal_id)})
    goals.command("propose_plan", f"P-{goal_id}", {"proposal": {
        "id": f"PLAN-{goal_id}", "goal_id": goal_id, "goal_revision": 1,
        "base_version": 0, "review_id": None, "reason": "虚构模板安排",
        "items": [task], "method": "rule_template", "source_ref": "fictional-template-v1"}})
    goals.command("decide_plan", f"D-{goal_id}", {
        "proposal_id": f"PLAN-{goal_id}", "decision": "accept", "actor": "user",
        "reason": "虚构用户同意", "edited_items": None, "policy_ref": None})


def main():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    clock = lambda: now
    with tempfile.TemporaryDirectory() as workspace:
        goals = GoalStore(workspace, clock)
        daily = DailyStore(workspace, clock)
        try:
            bridge = GoalDailyBridge(goals, daily)
            when = (now + timedelta(minutes=10)).isoformat()
            accept(goals, "DEMO-CET6", item("DEMO-READ", "DEMO-CET6", "practice",
                                            "goal", "DEMO-CET6", when))
            accept(goals, "DEMO-RECRUIT", item("DEMO-APPLY", "DEMO-RECRUIT", "apply_job",
                                               "job", "DEMO-JOB", when))
            before = {key: bridge.status(key)["state"] for key in ("DEMO-CET6", "DEMO-RECRUIT")}
            after = {key: bridge.sync(key)["state"] for key in ("DEMO-CET6", "DEMO-RECRUIT")}
            bridge.sync("DEMO-CET6")  # duplicate replay produces no duplicate schedule
            daily.command("complete", "DEMO-READ-DONE", "DEMO-READ", {"evidence": {
                "material_ref": "fictional-reading-page",
                "first_attempt_ref": "fictional-first-attempt",
                "reflection_ref": "fictional-mistake-note"}})
            try:
                daily.command("complete", "DEMO-APPLY-NO-RECEIPT", "DEMO-APPLY",
                              {"evidence": {"job_event_seq": 1}})
            except ValueError:
                receipt_gate = "blocked: no legacy submitted event"
            else:
                raise AssertionError("application gate unexpectedly allowed completion")
            print(json.dumps({"fictional": True, "before": before, "after": after,
                              "schedule_events": daily.db.execute(
                                  "SELECT COUNT(*) FROM daily_events WHERE command='schedule'").fetchone()[0],
                              "cet6_daily_state": daily._tasks()["DEMO-READ"]["state"],
                              "recruiting_daily_state": daily._tasks()["DEMO-APPLY"]["state"],
                              "receipt_gate": receipt_gate}, ensure_ascii=False, indent=2))
        finally:
            daily.close()
            goals.close()


if __name__ == "__main__":
    main()
