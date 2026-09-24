"""Replay accepted goal plans into the local daily checklist.

An accepted PlanVersion is the durable source for scheduling. The two stores
write separate SQLite files, so this projection exposes pending/conflict state
and can be retried after a crash. Only audited automatic micro-adjustments
can change an already scheduled task.
"""

import hashlib
import json
import sqlite3

from workbench.daily import stamp, zone


TERMINAL = {"completed", "cancelled"}


def schedule_event_id(goal_id, version, task_id):
    """Stable, DailyStore-compatible ID for one plan item's first schedule."""
    material = json.dumps([goal_id, version, task_id], separators=(",", ":"))
    return "GD-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:40].upper()


def adjust_event_id(goal_id, version, task_id):
    """Stable ID for one accepted auto/undo transition and task."""
    material = json.dumps(["adjust", goal_id, version, task_id], separators=(",", ":"))
    return "GA-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:40].upper()


def item_position(plan, task_id):
    return next(index for index, item in enumerate(plan["items"]) if item["task_id"] == task_id)


def daily_task(plan, item, goal_id):
    """Project only fields DailyStore understands; GoalStore keeps provenance."""
    verified = item["due_confidence"] == "verified"
    return {
        "id": item["task_id"],
        "title": item["title"],
        "kind": item["task_kind"],
        "source_kind": item["source_kind"],
        "source_id": item["source_id"],
        "reason": item.get("reason") or f"目标计划 v{plan['version']}：{plan['reason']}",
        "scheduled_at": item["scheduled_at"],
        "due_at": item["due_at"],
        "due_verified": verified,
        "due_verified_at": item["due_checked_at"] if verified else None,
        "goal_id": goal_id,
        "plan_version": plan["version"],
        "flexible": item["flexible"],
        "display_order": item_position(plan, item["task_id"]),
    }


def _same_content(before, after):
    return {key: value for key, value in before.items() if key != "scheduled_at"} == {
        key: value for key, value in after.items() if key != "scheduled_at"}


def _safe_transition(goal, prior, changed, old_position, new_position):
    """Recheck the immutable plan diff; runtime task state is checked separately."""
    if not _same_content(prior, changed):
        return False
    moved = prior["scheduled_at"] != changed["scheduled_at"]
    reordered = old_position != new_position
    if not (moved or reordered):
        return True
    if not prior["flexible"] or prior["due_at"] is not None:
        return False
    viewing_zone = zone(goal["timezone"])
    before = stamp(prior["scheduled_at"], "scheduled_at").astimezone(viewing_zone)
    after = stamp(changed["scheduled_at"], "scheduled_at").astimezone(viewing_zone)
    return before.date() == after.date()


class GoalDailyBridge:
    """Read-only status plus explicit, idempotent scheduling replay."""

    def __init__(self, goals, daily):
        if goals.workspace != daily.workspace:
            raise ValueError("GoalStore 与 DailyStore 必须使用同一个本地 workspace")
        self.goals = goals
        self.daily = daily

    def _schedule_rows(self):
        rows = self.daily.db.execute(
            "SELECT event_id,task_id,payload FROM daily_events WHERE command='schedule'").fetchall()
        return {row["task_id"]: row for row in rows}

    def _inspect(self, goal_id):
        """Return public status and the next replay action for each pending task."""
        snapshot = self.goals.snapshot(goal_id)
        plans = snapshot["plans"]
        version = snapshot["goal"]["active_version"]
        if version == 0:
            return {"goal_id": goal_id, "plan_version": 0, "state": "no_plan", "items": []}, []

        active = plans[-1]
        prior_by_version = {plan["version"]: plan for plan in plans}
        rows = self._schedule_rows()
        daily_states = self.daily._tasks()
        items = []
        actions = []
        active_ids = {item["task_id"] for item in active["items"]}
        for item in active["items"]:
            task_id = item["task_id"]
            row = rows.get(task_id)
            if row is None:
                try:
                    self.daily._validate_task(daily_task(active, item, goal_id), self.daily._now())
                except ValueError as exc:
                    items.append({"task_id": task_id, "state": "conflict", "reason": str(exc),
                                  "source_ref": item.get("source_ref")})
                    continue
                items.append({"task_id": task_id, "state": "sync_pending", "reason": "尚未写入每日任务",
                              "source_ref": item.get("source_ref")})
                actions.append(("schedule", schedule_event_id(goal_id, version, task_id), task_id,
                                {"task": daily_task(active, item, goal_id)}))
                continue
            recorded = json.loads(row["payload"])["task"]
            recorded_version = recorded.get("plan_version")
            old_plan = prior_by_version.get(recorded_version)
            old_item = next((old for old in old_plan["items"] if old["task_id"] == task_id), None) if old_plan else None
            owned = (recorded.get("goal_id") == goal_id and old_item is not None
                     and row["event_id"] == schedule_event_id(goal_id, recorded_version, task_id)
                     and recorded == daily_task(old_plan, old_item, goal_id))
            if not owned:
                items.append({"task_id": task_id, "state": "conflict", "reason": "每日任务 ID 已被其他安排占用或内容不匹配",
                              "source_ref": item.get("source_ref")})
                continue

            actual_adjustments = self.daily.db.execute(
                "SELECT event_id,payload FROM daily_events WHERE task_id=? AND command='reschedule' ORDER BY seq",
                (task_id,)).fetchall()
            expected = []
            last_item, last_position = old_item, item_position(old_plan, task_id)
            current_version = recorded_version
            conflict = None
            for plan in plans[recorded_version:]:
                next_item = next((candidate for candidate in plan["items"]
                                  if candidate["task_id"] == task_id), None)
                if next_item is None:
                    conflict = "中间计划删除了任务，不能自动恢复原任务"
                    break
                next_position = item_position(plan, task_id)
                changed = (last_item["scheduled_at"] != next_item["scheduled_at"]
                           or last_position != next_position)
                if not _same_content(last_item, next_item):
                    conflict = "新版计划改变了任务内容，需要本人确认每日任务变更"
                    break
                if changed:
                    if plan["decision"] not in {"auto_apply", "undo_auto"} or not _safe_transition(
                            snapshot["goal"], last_item, next_item, last_position, next_position):
                        conflict = "计划变更超出同日弹性任务微调范围"
                        break
                    expected.append((adjust_event_id(goal_id, plan["version"], task_id), {
                        "reason": plan["reason"], "scheduled_at": next_item["scheduled_at"],
                        "display_order": next_position, "plan_version": plan["version"],
                        "prior_plan_version": current_version, "timezone": snapshot["goal"]["timezone"],
                        "prior_scheduled_at": last_item["scheduled_at"],
                        "prior_display_order": last_position,
                    }))
                    current_version = plan["version"]
                last_item, last_position = next_item, next_position
            if conflict is not None:
                items.append({"task_id": task_id, "state": "conflict", "reason": conflict,
                              "source_ref": item.get("source_ref")})
                continue
            if len(actual_adjustments) > len(expected) or any(
                    actual["event_id"] != wanted[0]
                    or json.loads(actual["payload"]) != wanted[1]
                    for actual, wanted in zip(actual_adjustments, expected)):
                items.append({"task_id": task_id, "state": "conflict",
                              "reason": "每日任务调整记录与已接受计划不一致",
                              "source_ref": item.get("source_ref")})
                continue
            pending_index = len(actual_adjustments)
            if pending_index < len(expected):
                event_id, payload = expected[pending_index]
                task = daily_states[task_id]
                if (task["state"] != "scheduled" or task.get("flexible") is not True
                        or task.get("due_at") is not None
                        or task["scheduled_at"] != payload["prior_scheduled_at"]
                        or task.get("display_order") != payload["prior_display_order"]
                        or task.get("plan_version") != payload["prior_plan_version"]):
                    items.append({"task_id": task_id, "state": "conflict",
                                  "reason": "任务已开始、非弹性、有截止时间或每日安排已另行更改",
                                  "source_ref": item.get("source_ref")})
                else:
                    items.append({"task_id": task_id, "state": "sync_pending",
                                  "reason": "已接受的安全微调尚未写入每日任务",
                                  "source_ref": item.get("source_ref")})
                    actions.append(("reschedule", event_id, task_id, payload))
                continue
            task = daily_states[task_id]
            if (task["plan_version"] != current_version
                    or task.get("display_order") != last_position
                    or (task["state"] == "scheduled" and task["scheduled_at"] != last_item["scheduled_at"])):
                items.append({"task_id": task_id, "state": "conflict",
                              "reason": "每日任务当前投影与已接受计划不一致",
                              "source_ref": item.get("source_ref")})
            else:
                items.append({"task_id": task_id, "state": "applied",
                              "daily_state": task["state"],
                              "scheduled_from_version": recorded_version,
                              "current_daily_version": current_version,
                              "source_ref": item.get("source_ref")})

        # A new complete plan may remove tasks. Never leave an unstarted task
        # silently visible in DailyStore while claiming both views agree.
        for task_id, row in rows.items():
            if task_id in active_ids:
                continue
            recorded = json.loads(row["payload"])["task"]
            recorded_version = recorded.get("plan_version")
            if recorded.get("goal_id") != goal_id or recorded_version not in prior_by_version:
                continue
            if row["event_id"] != schedule_event_id(goal_id, recorded_version, task_id):
                continue
            if daily_states[task_id]["state"] not in TERMINAL:
                items.append({"task_id": task_id, "state": "conflict",
                              "reason": "旧计划任务仍在每日清单，但不在当前计划"})

        states = {item["state"] for item in items}
        state = "conflict" if "conflict" in states else "sync_pending" if "sync_pending" in states else "applied"
        return {"goal_id": goal_id, "plan_version": version, "state": state, "items": items}, actions

    def status(self, goal_id):
        """Report what is durably present, without writing either store."""
        return self._inspect(goal_id)[0]

    def sync(self, goal_id):
        """Schedule missing active items; retrying after a partial write is safe."""
        # Serialize plan decisions while this replay chooses its source version.
        # A process crash still leaves the accepted plan for the next replay.
        self.goals.db.execute("BEGIN IMMEDIATE")
        try:
            result = self._sync_locked(goal_id)
            self.goals.db.commit()
            return result
        except Exception:
            self.goals.db.rollback()
            raise

    def _sync_locked(self, goal_id):
        # Each pass can write at most one transition per task. Recomputing after
        # each pass lets a restart resume a chain of accepted auto/undo versions.
        while True:
            status, actions = self._inspect(goal_id)
            if status["state"] in {"no_plan", "conflict", "applied"} or not actions:
                return status
            for command, event_id, task_id, payload in actions:
                try:
                    self.daily.command(command, event_id, task_id, payload)
                except (ValueError, sqlite3.Error) as exc:
                    result = self.status(goal_id)
                    result["last_error"] = str(exc)
                    if isinstance(exc, ValueError):
                        result["state"] = "conflict"
                    return result
