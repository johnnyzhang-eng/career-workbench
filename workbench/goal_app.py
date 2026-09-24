"""Local goal workbench commands and a truthful, persisted read model."""

import hashlib
import json
import re
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .daily import DailyStore
from .goal_daily_bridge import GoalDailyBridge
from .goal_result_bridge import GoalResultBridge
from .goals import GoalStore
from .plan_templates import build_first_plan
from .scene_state import scene_state
from .scene_actions import SceneActionStore


OPERATION_ID = re.compile(r"[A-Za-z0-9_-]{1,48}\Z")
PATHS = {"cet6": "learning", "recruiting": "recruiting"}


def _required_text(value, field, maximum=500):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{field} 需要 1–{maximum} 个字符")
    return value.strip()


def _operation(payload):
    value = payload.get("operation_id")
    if not isinstance(value, str) or not OPERATION_ID.fullmatch(value):
        raise ValueError("operation_id 无效")
    return value


def _stable_id(prefix, *parts):
    material = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return prefix + hashlib.sha256(material.encode("utf-8")).hexdigest()[:40].upper()


def _result_fields(payload):
    minutes = payload.get("actual_minutes")
    if type(minutes) is not int or not 0 <= minutes <= 10080:
        raise ValueError("实际分钟需要本人填写 0–10080 的整数")
    metric = payload.get("metric")
    if metric is not None:
        if not isinstance(metric, dict) or not metric or set(metric) - {"correct", "total", "expected"}:
            raise ValueError("成绩只接受 correct、total、expected 数字")
        if not {"correct", "total"} <= set(metric):
            raise ValueError("成绩需要正确数与总题数")
        if any(type(value) is not int or not 0 <= value <= 10000 for value in metric.values()):
            raise ValueError("成绩数字无效")
        if metric["total"] == 0 or metric["correct"] > metric["total"] or metric.get("expected", 0) > metric["total"]:
            raise ValueError("成绩总题数或正确数无效")
    evidence_ref = payload.get("evidence_ref")
    if evidence_ref is not None and (not isinstance(evidence_ref, str) or len(evidence_ref) > 1000):
        raise ValueError("结果依据位置过长")
    note = payload.get("note")
    if not isinstance(note, str) or len(note) > 1000:
        raise ValueError("本人结果说明需要文字且不超过 1000 字")
    return minutes, metric, evidence_ref, note


class GoalApp:
    """Open fresh SQLite connections per call; safe for request/restart use."""

    def __init__(self, workspace, clock=None):
        self.workspace = Path(workspace).expanduser().resolve()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @contextmanager
    def _stores(self):
        goals = GoalStore(self.workspace, self.clock)
        try:
            daily = DailyStore(self.workspace, self.clock)
            try:
                yield goals, daily, GoalDailyBridge(goals, daily)
            finally:
                daily.close()
        finally:
            goals.close()

    def state(self, goal_id=None):
        with self._stores() as (goals, daily, bridge):
            all_state = goals.snapshot()
            goal_list = sorted(all_state["goals"].values(), key=lambda goal: goal["created_at"], reverse=True)
            if goal_id is None and goal_list:
                goal_id = goal_list[0]["id"]
            if goal_id is not None and goal_id not in all_state["goals"]:
                raise ValueError("目标不存在")
            now = self.clock()
            result = {"as_of": now.isoformat(), "goals": goal_list, "selected_goal_id": goal_id,
                      "selected": None, "storage": "local", "result_bridge": "available"}
            if goal_id is None:
                result["scene"] = scene_state(None, now)
                return result
            snapshot = goals.snapshot(goal_id)
            goal = snapshot["goal"]
            local_now = now.astimezone(ZoneInfo(goal["timezone"]))
            active = snapshot["plans"][-1] if snapshot["plans"] else None
            daily_tasks = daily._tasks()
            sync = bridge.status(goal_id)
            sync_by_id = {item["task_id"]: item for item in sync["items"]}
            plan_items = []
            if active:
                for item in active["items"]:
                    task_id = item["task_id"]
                    task = daily_tasks.get(task_id)
                    plan_items.append({**item, "daily_state": task["state"] if task else "not_scheduled",
                                       "current_scheduled_at": task["scheduled_at"] if task else None,
                                       "carryover_reason": task["latest_reason"] if task else None,
                                       "sync_state": sync_by_id.get(task_id, {}).get("state", "sync_pending")})
            today = local_now.date().isoformat()
            def local_day(stamp):
                return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(
                    ZoneInfo(goal["timezone"])).date().isoformat()

            today_tasks = []
            for item in plan_items:
                task = daily_tasks.get(item["task_id"])
                planned_day = local_day(item["current_scheduled_at"] or item["scheduled_at"])
                finished_today = bool(task and task["terminal_at"]
                                      and local_day(task["terminal_at"]) == today)
                if (planned_day <= today and item["daily_state"] not in {"completed", "cancelled"}) or finished_today:
                    today_tasks.append(item)
            today_tasks.sort(key=lambda item: (item["daily_state"] == "completed",
                                               item["current_scheduled_at"] or item["scheduled_at"]))
            overdue = [item for item in today_tasks if item["daily_state"] not in {"completed", "not_scheduled"}
                       and local_day(item["current_scheduled_at"] or item["scheduled_at"]) < today]
            feedback = ("有未完成的行动。可以保留实际进度，查看原因后再调整；不会扣分。" if overdue else
                        "按自己的节奏记录今天的行动。实际结果会成为之后调整计划的依据。")
            pending = [proposal for proposal in snapshot["proposals"] if proposal["status"] == "pending"]
            result["selected"] = {"goal": goal, "today": today, "local_time": local_now.isoformat(),
                                  "active_plan": {**active, "items": plan_items} if active else None,
                                  "pending_proposals": pending, "sync": sync,
                                  "today_tasks": today_tasks, "feedback": feedback,
                                  "results": snapshot["results"], "reviews": snapshot["reviews"],
                                  "result_status": GoalResultBridge(goals, daily).status(goal_id)}
            actions = SceneActionStore(self.workspace, self.clock)
            try:
                action = actions.snapshot(goal_id)
            finally:
                actions.close()
            result["scene"] = scene_state(result["selected"], now, action=action)
            return result

    def _change_action(self, payload, action):
        operation = _operation(payload)
        goal_id = _required_text(payload.get("goal_id"), "目标 ID", 80)
        task_id = _required_text(payload.get("task_id"), "任务 ID", 80)
        current = self.state(goal_id)["selected"]
        plan = current["active_plan"]
        if not plan or current["sync"]["state"] != "applied":
            raise ValueError("计划尚未写入每日清单")
        task = next((item for item in current["today_tasks"] if item["task_id"] == task_id), None)
        if task is None or task["sync_state"] != "applied":
            raise ValueError("行动不属于今日或待处理清单")
        if action != "stop" and task["daily_state"] in {"completed", "cancelled", "not_scheduled"}:
            raise ValueError("已结束的任务不能开始或继续")
        actions = SceneActionStore(self.workspace, self.clock)
        try:
            actions.command(action, "E-A-" + operation, goal_id, task_id,
                            timezone_name=current["goal"]["timezone"])
        finally:
            actions.close()
        return self.state(goal_id)

    def start_action(self, payload):
        return self._change_action(payload, "start")

    def pause_action(self, payload):
        return self._change_action(payload, "pause")

    def resume_action(self, payload):
        return self._change_action(payload, "resume")

    def stop_action(self, payload):
        return self._change_action(payload, "stop")

    def create_goal(self, payload):
        operation = _operation(payload)
        path = payload.get("path")
        if path not in PATHS:
            raise ValueError("首版路径只能是 CET6 或秋招")
        minutes = payload.get("weekly_minutes")
        if type(minutes) is not int or not 105 <= minutes <= 10080:
            raise ValueError("七日模板需要每周至少 105 分钟，且不超过一周总时长")
        zone = payload.get("timezone", "Asia/Shanghai")
        try:
            ZoneInfo(zone)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError("时区无效") from exc
        target = payload.get("target_at") or None
        if target is not None:
            _required_text(target, "本人目标日期", 80)
            parsed = datetime.fromisoformat(target.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("本人目标日期需要时区")
        goal_id = "G-" + operation
        goal = {"id": goal_id, "title": _required_text(payload.get("title"), "目标名称", 100),
                "domain": PATHS[path], "timezone": zone, "weekly_minutes": minutes,
                "success_criterion": _required_text(payload.get("success_criterion"), "成功标准", 500),
                "baseline": payload.get("baseline", ""), "target_at": target,
                "target_confidence": "self_set" if target else "unknown",
                "target_source_ref": None, "target_checked_at": None}
        if not isinstance(goal["baseline"], str) or len(goal["baseline"]) > 1000:
            raise ValueError("起点说明过长")
        with self._stores() as (goals, _daily, _bridge):
            goals.command("create_goal", "E-G-" + operation, {"goal": goal})
        return self.state(goal_id)

    def propose_plan(self, payload):
        operation = _operation(payload)
        goal_id = _required_text(payload.get("goal_id"), "目标 ID", 80)
        try:
            start_on = date.fromisoformat(_required_text(payload.get("start_on"), "开始日期", 20))
        except ValueError as exc:
            raise ValueError("开始日期需要 YYYY-MM-DD") from exc
        with self._stores() as (goals, _daily, _bridge):
            goal = goals.snapshot(goal_id)["goal"]
            path = "cet6" if goal["domain"] == "learning" else "recruiting"
            proposal = build_first_plan(goal, path, start_on, "P-" + operation)["proposal"]
            goals.command("propose_plan", "E-P-" + operation, {"proposal": proposal})
        return self.state(goal_id)

    def decide_plan(self, payload):
        operation = _operation(payload)
        proposal_id = _required_text(payload.get("proposal_id"), "提案 ID", 80)
        decision = payload.get("decision")
        if decision not in {"accept", "decline"}:
            raise ValueError("仅支持本人接受或拒绝计划")
        with self._stores() as (goals, _daily, _bridge):
            all_state = goals.snapshot()
            proposal = all_state["proposals"].get(proposal_id)
            if proposal is None:
                raise ValueError("提案不存在")
            subject = "首版计划" if proposal["base_version"] == 0 else "复盘提案"
            goals.command("decide_plan", "E-D-" + operation,
                          {"proposal_id": proposal_id, "decision": decision, "actor": "user",
                           "reason": "本人在本地工作台" + ("接受" if decision == "accept" else "拒绝") + subject,
                           "edited_items": None, "policy_ref": None})
            goal_id = proposal["goal_id"]
        return self.state(goal_id)

    def sync_plan(self, payload):
        _operation(payload)
        goal_id = _required_text(payload.get("goal_id"), "目标 ID", 80)
        with self._stores() as (_goals, _daily, bridge):
            bridge.sync(goal_id)
        return self.state(goal_id)

    def complete_task(self, payload):
        operation = _operation(payload)
        goal_id = _required_text(payload.get("goal_id"), "目标 ID", 80)
        task_id = _required_text(payload.get("task_id"), "任务 ID", 80)
        evidence = payload.get("evidence")
        if not isinstance(evidence, dict):
            raise ValueError("请填写完成依据")
        if any(not isinstance(value, str) or not value.strip() or len(value) > 1000
               for value in evidence.values()):
            raise ValueError("完成依据需要非空文字，每项不超过 1000 字")
        with self._stores() as (goals, daily, bridge):
            snapshot = goals.snapshot(goal_id)
            active = snapshot["plans"][-1] if snapshot["plans"] else None
            if active is None or task_id not in {item["task_id"] for item in active["items"]}:
                raise ValueError("任务不属于当前计划")
            if bridge.status(goal_id)["state"] != "applied":
                raise ValueError("计划尚未完成同步，请先处理待同步或冲突")
            task = daily._tasks().get(task_id)
            if task is None or task["kind"] not in {"practice", "custom"}:
                raise ValueError("此任务需要对应的求职原流程，不支持在此直接完成")
            daily.command("complete", "E-C-" + operation, task_id, {"evidence": evidence})
        return self.state(goal_id)

    def confirm_result(self, payload):
        """Only an explicit same-origin UI command can project a completed task."""
        _operation(payload)
        goal_id = _required_text(payload.get("goal_id"), "目标 ID", 80)
        task_id = _required_text(payload.get("task_id"), "任务 ID", 80)
        minutes, metric, evidence_ref, note = _result_fields(payload)
        correct = payload.get("correct", False)
        if type(correct) is not bool:
            raise ValueError("更正标记无效")
        with self._stores() as (goals, daily, _bridge):
            results = GoalResultBridge(goals, daily)
            complete_event_id = results.completion_event_id(goal_id, task_id)
            correction_id = (_stable_id("CR-", goal_id, task_id, complete_event_id,
                                        minutes, metric, evidence_ref, note) if correct else None)
            results.record_completed(goal_id, task_id, complete_event_id,
                                     actual_minutes=minutes, metric=metric,
                                     evidence_ref=evidence_ref, note=note,
                                     actor="user", correction_id=correction_id)
        return self.state(goal_id)

    def report_unfinished(self, payload):
        """A user's report changes GoalStore history, never DailyStore completion."""
        _operation(payload)
        goal_id = _required_text(payload.get("goal_id"), "目标 ID", 80)
        task_id = _required_text(payload.get("task_id"), "任务 ID", 80)
        outcome = payload.get("outcome")
        if outcome not in {"missed", "partial", "blocked"}:
            raise ValueError("仅支持未做、部分完成或受阻的本人记录")
        minutes, metric, evidence_ref, note = _result_fields(payload)
        if not note.strip():
            raise ValueError("请写下实际情况，才能形成温和复盘")
        with self._stores() as (goals, daily, _bridge):
            goal = goals.snapshot(goal_id)["goal"]
            task = daily._tasks().get(task_id)
            if task is None or task["state"] in {"completed", "cancelled"}:
                raise ValueError("只能报告尚未完成的每日任务")
            local_now = self.clock().astimezone(ZoneInfo(goal["timezone"]))
            scheduled = datetime.fromisoformat(task["scheduled_at"].replace("Z", "+00:00"))
            if scheduled.astimezone(ZoneInfo(goal["timezone"])).date() > local_now.date():
                raise ValueError("未来任务还不能报告未完成")
            # One identical report per local day is a retry; an identical
            # report tomorrow is a separate observation of ongoing work.
            report_id = _stable_id("RU-", goal_id, task_id, local_now.date().isoformat(), outcome,
                                   minutes, metric, evidence_ref, note)
            GoalResultBridge(goals, daily).record_unfinished(
                goal_id, task_id, report_id, outcome, actual_minutes=minutes,
                metric=metric, evidence_ref=evidence_ref, note=note, actor="user")
        return self.state(goal_id)

    def review_result(self, payload):
        """Propose keeping the current plan after a gentle, user-triggered review."""
        _operation(payload)
        goal_id = _required_text(payload.get("goal_id"), "目标 ID", 80)
        result_id = _required_text(payload.get("result_id"), "结果 ID", 80)
        with self._stores() as (goals, daily, _bridge):
            snapshot = goals.snapshot(goal_id)
            active = snapshot["plans"][-1] if snapshot["plans"] else None
            if active is None:
                raise ValueError("没有可审阅的生效计划")
            result = next((r for r in snapshot["results"] if r["id"] == result_id), None)
            if result is None or result["outcome"] not in {"missed", "partial", "blocked"}:
                raise ValueError("此结果不能形成未完成复盘")
            reviewed_ids = {review["id"] for review in snapshot["reviews"]
                            if result_id in review["result_ids"]}
            if any(proposal["review_id"] in reviewed_ids for proposal in snapshot["proposals"]):
                # A retry after accept/decline must not propose the same result
                # against a newer plan version. An interrupted review without a
                # proposal is still retried by the deterministic IDs below.
                return self.state(goal_id)
            finding = {
                "missed": "这次没有完成；先回顾可用时间，再决定是否调整。不会扣分。",
                "partial": "这次只完成一部分；下次可从剩余内容继续。不会扣分。",
                "blocked": "这次遇到阻碍；先确认阻碍是否仍在，再决定下一步。不会扣分。",
            }[result["outcome"]]
            reason = "建议暂保留现有七日任务与时段；若要改期，请另行审阅具体安排。"
            source_ref = "self:" + result_id
            review_id = _stable_id("RV-", goal_id, active["version"], result_id)
            proposal_id = _stable_id("PR-", goal_id, active["version"], result_id)
            GoalResultBridge(goals, daily).review_with_proposal(
                goal_id, result_id, review_id, proposal_id,
                proposed_items=active["items"], finding=finding,
                proposal_reason=reason, source_ref=source_ref, actor="user")
        return self.state(goal_id)
