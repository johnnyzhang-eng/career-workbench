"""Project explicit daily outcomes into goal results and gentle reviews.

The daily completion is durable before a goal result is written. Both stores
retain their own event log; deterministic goal event IDs make a retry safe.
"""

import hashlib
import json

from workbench.daily import ID as DAILY_ID, stamp
from workbench.goal_daily_bridge import schedule_event_id


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _id(value, label):
    _need(isinstance(value, str) and DAILY_ID.fullmatch(value), f"{label} 无效")


def _stable(prefix, *parts):
    digest = hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return prefix + digest[:40].upper()


def _user_fields(actual_minutes, metric, evidence_ref, note, actor):
    _need(actor == "user", "结果必须由本人确认；工具观察不能代替")
    _need(type(actual_minutes) is int and actual_minutes >= 0, "actual_minutes 必须由本人填写非负整数")
    _need(metric is None or isinstance(metric, dict), "metric 必须由本人填写对象或 null")
    _need(evidence_ref is None or isinstance(evidence_ref, str),
          "evidence_ref 必须由本人填写文字或 null")
    _need(isinstance(note, str), "note 必须由本人填写文字，可为空")


class GoalResultBridge:
    """A local API; the host UI is responsible for authenticating the user."""

    def __init__(self, goals, daily):
        _need(goals.workspace == daily.workspace, "GoalStore 与 DailyStore 必须在同一私有 workspace")
        self.goals = goals
        self.daily = daily

    def _linked_task(self, goal_id, task_id):
        _id(goal_id, "goal_id")
        _id(task_id, "task_id")
        task = self.daily._tasks().get(task_id)
        _need(task is not None and task.get("goal_id") == goal_id, "每日任务未关联此目标")
        version = task.get("plan_version")
        _need(type(version) is int and version > 0, "每日任务没有有效计划版本")
        snapshot = self.goals.snapshot(goal_id)
        plan = next((p for p in snapshot["plans"] if p["version"] == version), None)
        _need(plan is not None and any(item["task_id"] == task_id for item in plan["items"]),
              "每日任务版本与已生效目标计划不匹配")

        # The initial schedule is immutable. A later safe reschedule may
        # update the daily projection's plan_version, so check provenance
        # against the original version and result linkage against the current.
        row = self.daily.db.execute(
            "SELECT event_id,payload FROM daily_events WHERE task_id=? AND command='schedule'",
            (task_id,)).fetchone()
        _need(row is not None, "每日任务缺少安排事件")
        initial = json.loads(row["payload"])["task"]
        initial_version = initial.get("plan_version")
        _need(type(initial_version) is int and initial_version > 0
              and initial.get("goal_id") == goal_id
              and row["event_id"] == schedule_event_id(goal_id, initial_version, task_id),
              "任务并非由该目标计划安排")
        original_plan = next((p for p in snapshot["plans"] if p["version"] == initial_version), None)
        _need(original_plan is not None
              and any(item["task_id"] == task_id for item in original_plan["items"]),
              "初次安排版本与目标计划不匹配")
        return task, version

    def _completion(self, task, complete_event_id):
        _id(complete_event_id, "complete_event_id")
        row = self.daily.db.execute(
            "SELECT task_id,at,command,payload FROM daily_events WHERE event_id=?",
            (complete_event_id,)).fetchone()
        _need(row is not None and row["task_id"] == task["id"] and row["command"] == "complete"
              and task["state"] == "completed" and task["terminal_at"] == row["at"],
              "需要此任务已保存的每日完成事件")
        evidence = json.loads(row["payload"])["evidence"]
        # Recheck the domain gate at projection time. For apply_job this still
        # requires a matching submitted event with receipt in the job store.
        self.daily._validate_completion(task, evidence, stamp(row["at"], "完成时间"))
        return row

    def status(self, goal_id):
        """Show completed daily tasks awaiting explicit user result input."""
        snapshot = self.goals.snapshot(goal_id)
        results = snapshot["results"]
        tasks = []
        for task in self.daily._tasks().values():
            if task.get("goal_id") != goal_id or task["state"] != "completed":
                continue
            task_id = task["id"]
            try:
                _, version = self._linked_task(goal_id, task_id)
                event = self.daily.db.execute(
                    "SELECT event_id,at FROM daily_events WHERE task_id=? AND command='complete' "
                    "ORDER BY seq DESC LIMIT 1", (task_id,)).fetchone()
                _need(event is not None, "已完成任务缺少完成事件")
                state = "recorded" if any(r["task_id"] == task_id
                                          and r["plan_version"] == version
                                          and r["basis"] == "self_report" for r in results) else "awaiting_user_confirmation"
                tasks.append({"task_id": task_id, "task_title": task["title"],
                              "completed_at": event["at"], "plan_version": version, "state": state})
            except ValueError as exc:
                tasks.append({"task_id": task_id, "plan_version": task.get("plan_version"),
                              "state": "conflict", "reason": str(exc)})
        return {"goal_id": goal_id, "tasks": tasks}

    def completion_event_id(self, goal_id, task_id):
        """Resolve the durable completion server-side after a browser restart."""
        task, _version = self._linked_task(goal_id, task_id)
        row = self.daily.db.execute(
            "SELECT event_id FROM daily_events WHERE task_id=? AND command='complete' "
            "ORDER BY seq DESC LIMIT 1", (task_id,)).fetchone()
        _need(row is not None, "任务尚未保存完成事件")
        self._completion(task, row["event_id"])
        return row["event_id"]

    def record_completed(self, goal_id, task_id, complete_event_id, *, actual_minutes,
                         metric, evidence_ref, note, actor, correction_id=None):
        """Record one user-confirmed result; correction appends a new result."""
        _user_fields(actual_minutes, metric, evidence_ref, note, actor)
        task, version = self._linked_task(goal_id, task_id)
        self._completion(task, complete_event_id)
        if correction_id is not None:
            _id(correction_id, "correction_id")
        first_id = _stable("GR-", goal_id, version, task_id, complete_event_id, "first")
        result_id = (first_id if correction_id is None else
                     _stable("GR-", goal_id, version, task_id, complete_event_id, correction_id))
        if correction_id is not None:
            _need(first_id in self.goals.snapshot()["results"], "先记录首次结果，再追加更正")
        result = {"id": result_id, "goal_id": goal_id, "plan_version": version,
                  "task_id": task_id, "outcome": "completed", "basis": "self_report",
                  "actual_minutes": actual_minutes, "metric": metric,
                  "evidence_ref": evidence_ref, "note": note}
        self.goals.command("record_result", _stable("GE-", result_id), {"result": result})
        return self.goals.snapshot()["results"][result_id]

    def record_unfinished(self, goal_id, task_id, report_id, outcome, *, actual_minutes,
                          metric, evidence_ref, note, actor):
        """Preserve a user's missed/partial/blocked report without completing a task."""
        _user_fields(actual_minutes, metric, evidence_ref, note, actor)
        _id(report_id, "report_id")
        _need(outcome in {"missed", "partial", "blocked"}, "此处只记录未完成或部分完成")
        task, version = self._linked_task(goal_id, task_id)
        _need(task["state"] != "cancelled", "已取消任务不可报未完成")
        _need(outcome != "missed" or task["state"] != "completed", "已完成任务不可报未做")
        result_id = _stable("GR-", goal_id, version, task_id, report_id)
        result = {"id": result_id, "goal_id": goal_id, "plan_version": version,
                  "task_id": task_id, "outcome": outcome, "basis": "self_report",
                  "actual_minutes": actual_minutes, "metric": metric,
                  "evidence_ref": evidence_ref, "note": note}
        self.goals.command("record_result", _stable("GE-", result_id), {"result": result})
        return self.goals.snapshot()["results"][result_id]

    def review_with_proposal(self, goal_id, result_id, review_id, proposal_id, *,
                             proposed_items, finding, proposal_reason, source_ref, actor):
        """Append a gentle review and a pending *manual* proposal, never activate it."""
        _need(actor == "user", "复盘及计划提案需要本人确认")
        for name, value in (("result_id", result_id), ("review_id", review_id),
                            ("proposal_id", proposal_id)):
            _id(value, name)
        _need(isinstance(finding, str) and finding.strip(), "finding 必须是温和的具体复盘文字")
        _need(isinstance(proposal_reason, str) and proposal_reason.strip(), "proposal_reason 必须说明调整原因")
        _need(isinstance(source_ref, str) and source_ref.strip(), "source_ref 必须指向本人结果或来源")
        snapshot = self.goals.snapshot(goal_id)
        result = next((r for r in snapshot["results"] if r["id"] == result_id), None)
        _need(result is not None and result["basis"] == "self_report"
              and result["outcome"] in {"missed", "partial", "blocked"},
              "只用本人确认的未完成或部分完成结果形成此类复盘")
        existing_review = next((r for r in snapshot["reviews"] if r["id"] == review_id), None)
        existing_proposal = next((p for p in snapshot["proposals"] if p["id"] == proposal_id), None)
        if existing_proposal is not None:
            _need(existing_review is not None and existing_review["result_ids"] == [result_id]
                  and existing_review["finding"] == finding
                  and existing_review["source_ref"] == source_ref
                  and existing_proposal["review_id"] == review_id
                  and existing_proposal["reason"] == proposal_reason
                  and existing_proposal["items"] == proposed_items
                  and existing_proposal["source_ref"] == source_ref
                  and existing_proposal["method"] == "manual", "复盘或提案 ID 已用于不同内容")
            return {"review": existing_review, "proposal": existing_proposal}
        goal = snapshot["goal"]
        _need(goal["active_version"] > 0, "没有生效计划")
        _need(existing_review is None or existing_review["plan_version"] == goal["active_version"],
              "复盘写入后计划已变化，请重新审阅提案")
        trigger = "missed_day" if result["outcome"] == "missed" else "weekly"
        review = {"id": review_id, "goal_id": goal_id, "plan_version": goal["active_version"],
                  "trigger": trigger, "result_ids": [result_id], "finding": finding,
                  "source_ref": source_ref}
        self.goals.command("record_review", _stable("GE-", review_id), {"review": review})
        # The review write may have committed before interruption. On retry,
        # the same deterministic event ID returns it; the proposal follows.
        proposal = {"id": proposal_id, "goal_id": goal_id,
                    "goal_revision": goal["revision"], "base_version": goal["active_version"],
                    "review_id": review_id, "reason": proposal_reason,
                    "items": proposed_items, "method": "manual", "source_ref": source_ref}
        self.goals.command("propose_plan", _stable("GE-", proposal_id), {"proposal": proposal})
        return {"review": next(r for r in self.goals.snapshot(goal_id)["reviews"] if r["id"] == review_id),
                "proposal": next(p for p in self.goals.snapshot(goal_id)["proposals"] if p["id"] == proposal_id)}
