"""Replay accepted goal plans into the local daily checklist.

An accepted PlanVersion is the durable source for scheduling. The two stores
write separate SQLite files, so this projection exposes pending/conflict state
and can be retried after a crash. It does not change an existing daily task.
"""

import hashlib
import json
import sqlite3


TERMINAL = {"completed", "cancelled"}


def schedule_event_id(goal_id, version, task_id):
    """Stable, DailyStore-compatible ID for one plan item's first schedule."""
    material = json.dumps([goal_id, version, task_id], separators=(",", ":"))
    return "GD-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:40].upper()


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
    }


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

    def status(self, goal_id):
        """Report what is durably present, without writing either store."""
        snapshot = self.goals.snapshot(goal_id)
        plans = snapshot["plans"]
        version = snapshot["goal"]["active_version"]
        if version == 0:
            return {"goal_id": goal_id, "plan_version": 0, "state": "no_plan", "items": []}

        active = plans[-1]
        prior_by_version = {plan["version"]: plan for plan in plans}
        rows = self._schedule_rows()
        daily_states = self.daily._tasks()
        items = []
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
            elif old_item != item:
                items.append({"task_id": task_id, "state": "conflict", "reason": "新版计划改动了已有任务，尚无安全改期命令",
                              "source_ref": item.get("source_ref")})
            else:
                items.append({"task_id": task_id, "state": "applied",
                              "daily_state": daily_states[task_id]["state"],
                              "scheduled_from_version": recorded_version,
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
        return {"goal_id": goal_id, "plan_version": version, "state": state, "items": items}

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
        status = self.status(goal_id)
        if status["state"] in {"no_plan", "conflict", "applied"}:
            return status
        plan = self.goals.snapshot(goal_id)["plans"][-1]
        pending = {item["task_id"] for item in status["items"] if item["state"] == "sync_pending"}
        for item in plan["items"]:
            if item["task_id"] not in pending:
                continue
            task = daily_task(plan, item, goal_id)
            try:
                self.daily.command("schedule", schedule_event_id(goal_id, plan["version"], item["task_id"]),
                                   item["task_id"], {"task": task})
            except (ValueError, sqlite3.Error) as exc:
                result = self.status(goal_id)
                result["last_error"] = str(exc)
                if isinstance(exc, ValueError):
                    result["state"] = "conflict"
                return result
        return self.status(goal_id)
