"""Explicit, local-only action sessions for the room avatar.

These events describe a user's declared activity, not task completion. They
do not modify DailyStore or any job/application state.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


STATES = {"start": "active", "resume": "active", "pause": "paused", "stop": "stopped"}


class SceneActionStore:
    def __init__(self, workspace, clock=None):
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.db = sqlite3.connect(Path(workspace) / "scene_actions.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS scene_action_events (
            seq INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
            goal_id TEXT NOT NULL, task_id TEXT NOT NULL,
            action TEXT NOT NULL, at TEXT NOT NULL)""")
        self.db.commit()

    def close(self):
        self.db.close()

    def snapshot(self, goal_id):
        row = self.db.execute("""SELECT goal_id,task_id,action,at FROM scene_action_events
                                 WHERE goal_id=? ORDER BY seq DESC LIMIT 1""", (goal_id,)).fetchone()
        if row is None:
            return {"state": "none", "task_id": None, "at": None}
        return {"state": STATES[row["action"]], "task_id": row["task_id"], "at": row["at"]}

    def command(self, action, event_id, goal_id, task_id, *, timezone_name):
        if action not in STATES:
            raise ValueError("房间行动命令无效")
        if not all(isinstance(value, str) and value for value in (event_id, goal_id, task_id)):
            raise ValueError("房间行动缺少事件或任务 ID")
        now = self.clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("房间行动时钟必须带时区")
        from zoneinfo import ZoneInfo
        zone = ZoneInfo(timezone_name)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            previous = self.db.execute("SELECT * FROM scene_action_events WHERE event_id=?", (event_id,)).fetchone()
            if previous is not None:
                if (previous["action"], previous["goal_id"], previous["task_id"]) != (action, goal_id, task_id):
                    raise ValueError("房间行动事件 ID 已被其他操作使用")
                self.db.commit()
                return self.snapshot(goal_id)
            current = self.snapshot(goal_id)
            current_at = datetime.fromisoformat(current["at"]) if current["at"] else None
            same_day = bool(current_at and current_at.astimezone(zone).date() == now.astimezone(zone).date())
            if action == "start":
                if current["state"] in {"active", "paused"} and same_day:
                    raise ValueError("请先结束当前行动，再开始另一项")
            elif current["task_id"] != task_id:
                raise ValueError("当前房间行动不是这项任务")
            elif action == "pause":
                if current["state"] != "active" or not same_day:
                    raise ValueError("当前没有可暂停的行动")
            elif action == "resume":
                if current["state"] not in {"paused", "active"} or (current["state"] == "active" and same_day):
                    raise ValueError("当前行动不能继续")
            elif action == "stop" and current["state"] not in {"active", "paused"}:
                raise ValueError("当前没有可结束的行动")
            self.db.execute("INSERT INTO scene_action_events(event_id,goal_id,task_id,action,at) VALUES(?,?,?,?,?)",
                            (event_id, goal_id, task_id, action, now.isoformat()))
            self.db.commit()
            return self.snapshot(goal_id)
        except Exception:
            self.db.rollback()
            raise
