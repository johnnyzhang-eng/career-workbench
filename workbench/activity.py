"""Local, opt-in tool activity observations. No task or job state is changed here."""

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


EVENT_KINDS = frozenset({"work_session_started", "work_session_ended", "artifact_updated"})
IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
STATES = frozenset({"enabled", "paused", "disconnected"})


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _identifier(value, label):
    _require(isinstance(value, str) and IDENTIFIER.fullmatch(value), f"{label} 无效")
    return value


def _timestamp(value, label):
    _require(isinstance(value, str), f"{label} 必须是带时区的 ISO 时间")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} 时间格式无效") from exc
    _require(result.tzinfo is not None and result.utcoffset() is not None,
             f"{label} 必须带时区")
    return result.astimezone(timezone.utc)


class ActivityInbox:
    """Private workspace inbox; only a trusted host UI should call connection controls.

    Adapters call ingest after the host has enabled a named connection. This class
    is a persistence and validation boundary, not a process authentication layer.
    """

    def __init__(self, workspace, clock=None, retention_days=30):
        _require(type(retention_days) is int and 1 <= retention_days <= 365,
                 "retention_days 必须为 1 到 365 天")
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.retention_days = retention_days
        path = self.workspace / "activity.sqlite3"
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS activity_connections (
            id TEXT PRIMARY KEY, source TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('enabled','paused','disconnected')),
            allowed_types TEXT NOT NULL, created_at TEXT NOT NULL, changed_at TEXT NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS activity_observations (
            connection_id TEXT NOT NULL REFERENCES activity_connections(id) ON DELETE CASCADE,
            event_id TEXT NOT NULL, source TEXT NOT NULL, kind TEXT NOT NULL,
            occurred_at TEXT NOT NULL, observed_at TEXT NOT NULL,
            task_hint TEXT, PRIMARY KEY(connection_id,event_id))""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS activity_deleted_ids (
            connection_id TEXT NOT NULL REFERENCES activity_connections(id) ON DELETE CASCADE,
            event_hash TEXT NOT NULL, deleted_at TEXT NOT NULL,
            PRIMARY KEY(connection_id,event_hash))""")
        self._prune(self._now())
        self.db.commit()
        # Local records can contain personal timing and task IDs. Ignore chmod on
        # platforms without Unix permission bits; the host still owns workspace ACLs.
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def close(self):
        self.db.close()

    def _now(self):
        value = self.clock()
        _require(isinstance(value, datetime) and value.tzinfo is not None
                 and value.utcoffset() is not None, "时钟必须返回带时区的时间")
        return value.astimezone(timezone.utc)

    def _connection(self, connection_id):
        _identifier(connection_id, "连接 ID")
        row = self.db.execute("SELECT * FROM activity_connections WHERE id=?",
                              (connection_id,)).fetchone()
        _require(row is not None, "连接未获授权或不存在")
        return row

    @staticmethod
    def _connection_dict(row):
        return {"id": row["id"], "source": row["source"], "state": row["state"],
                "allowed_types": json.loads(row["allowed_types"]),
                "created_at": row["created_at"], "changed_at": row["changed_at"]}

    @staticmethod
    def _observation_dict(row):
        return {key: row[key] for key in ("connection_id", "event_id", "source", "kind",
                                          "occurred_at", "observed_at", "task_hint")}

    def connect(self, connection_id, source, allowed_types):
        """Trusted host action after explicit user opt-in; no adapter calls this."""
        _identifier(connection_id, "连接 ID")
        _identifier(source, "来源")
        _require(isinstance(allowed_types, (list, tuple, set, frozenset))
                 and bool(allowed_types) and all(isinstance(kind, str) for kind in allowed_types)
                 and set(allowed_types) <= EVENT_KINDS,
                 "必须选择允许的事件类型")
        types = sorted(set(allowed_types))
        now = self._now().isoformat()
        with self.db:
            _require(self.db.execute("SELECT 1 FROM activity_connections WHERE id=?",
                                     (connection_id,)).fetchone() is None,
                     "连接 ID 已存在；请检查现有授权或另建连接")
            self.db.execute("""INSERT INTO activity_connections
                (id,source,state,allowed_types,created_at,changed_at)
                VALUES(?,?,'enabled',?,?,?)""",
                (connection_id, source, json.dumps(types), now, now))
        return self.get_connection(connection_id)

    def get_connection(self, connection_id):
        return self._connection_dict(self._connection(connection_id))

    def list_connections(self):
        return [self._connection_dict(row) for row in
                self.db.execute("SELECT * FROM activity_connections ORDER BY created_at,id")]

    def _change_state(self, connection_id, target, from_states):
        _require(target in STATES, "连接状态无效")
        with self.db:
            row = self._connection(connection_id)
            _require(row["state"] in from_states, "当前连接状态不能执行此操作")
            self.db.execute("UPDATE activity_connections SET state=?,changed_at=? WHERE id=?",
                            (target, self._now().isoformat(), connection_id))
        return self.get_connection(connection_id)

    def pause(self, connection_id):
        return self._change_state(connection_id, "paused", {"enabled"})

    def resume(self, connection_id):
        return self._change_state(connection_id, "enabled", {"paused"})

    def disconnect(self, connection_id):
        """Stop new events; prior observations remain inspectable until deleted."""
        return self._change_state(connection_id, "disconnected", {"enabled", "paused"})

    def _prune(self, now):
        cutoff = (now - timedelta(days=self.retention_days)).isoformat()
        self.db.execute("DELETE FROM activity_observations WHERE observed_at<?", (cutoff,))
        self.db.execute("DELETE FROM activity_deleted_ids WHERE deleted_at<?", (cutoff,))

    @staticmethod
    def _event_hash(connection_id, event_id):
        return hashlib.sha256(f"{connection_id}\0{event_id}".encode("utf-8")).hexdigest()

    def prune_expired(self):
        """Host housekeeping hook; ingest also calls this before writing."""
        with self.db:
            self._prune(self._now())

    def ingest(self, connection_id, event):
        """Accept only a minimal allowlisted observation; never writes DailyStore."""
        _require(isinstance(event, dict), "事件必须是对象")
        required = {"event_id", "source", "kind", "occurred_at"}
        _require(required <= set(event) <= required | {"task_hint"},
                 "事件字段无效；只允许 ID、来源、类型、时间和可选任务提示")
        event_id = _identifier(event["event_id"], "事件 ID")
        source = _identifier(event["source"], "来源")
        kind = event["kind"]
        _require(isinstance(kind, str) and kind in EVENT_KINDS,
                 "事件类型不在允许清单")
        occurred = _timestamp(event["occurred_at"], "occurred_at")
        task_hint = event.get("task_hint")
        if task_hint is not None:
            _identifier(task_hint, "任务提示")
        with self.db:
            connection = self._connection(connection_id)
            _require(source == connection["source"], "来源与获授权连接不匹配")
            _require(kind in json.loads(connection["allowed_types"]), "此连接未获准接收该事件类型")
            prior = self.db.execute("""SELECT * FROM activity_observations
                WHERE connection_id=? AND event_id=?""", (connection_id, event_id)).fetchone()
            if prior is not None:
                _require(prior["source"] == source and prior["kind"] == kind
                         and prior["occurred_at"] == occurred.isoformat()
                         and prior["task_hint"] == task_hint,
                         "事件 ID 已用于不同内容")
                return self._observation_dict(prior)
            _require(connection["state"] == "enabled", "连接已暂停或断开，不能接收新事件")
            now = self._now()
            self._prune(now)
            _require(now - timedelta(days=self.retention_days) <= occurred
                     <= now + timedelta(minutes=5), "事件时间超出允许范围")
            deleted = self.db.execute("""SELECT 1 FROM activity_deleted_ids
                WHERE connection_id=? AND event_hash=?""",
                (connection_id, self._event_hash(connection_id, event_id))).fetchone()
            _require(deleted is None, "该观察记录已删除，不能由重放重新加入")
            self.db.execute("""INSERT INTO activity_observations
                (connection_id,event_id,source,kind,occurred_at,observed_at,task_hint)
                VALUES(?,?,?,?,?,?,?)""",
                (connection_id, event_id, source, kind, occurred.isoformat(),
                 now.isoformat(), task_hint))
            row = self.db.execute("""SELECT * FROM activity_observations
                WHERE connection_id=? AND event_id=?""", (connection_id, event_id)).fetchone()
            return self._observation_dict(row)

    def list_observations(self, connection_id=None):
        if connection_id is None:
            rows = self.db.execute("""SELECT * FROM activity_observations
                ORDER BY observed_at DESC,connection_id,event_id""")
        else:
            self._connection(connection_id)
            rows = self.db.execute("""SELECT * FROM activity_observations
                WHERE connection_id=? ORDER BY observed_at DESC,event_id""",
                (connection_id,))
        return [self._observation_dict(row) for row in rows]

    def delete_observation(self, connection_id, event_id):
        """Remove a record; retain its ID for the retention window to block replay."""
        _identifier(event_id, "事件 ID")
        with self.db:
            self._connection(connection_id)
            row = self.db.execute("""SELECT 1 FROM activity_observations
                WHERE connection_id=? AND event_id=?""", (connection_id, event_id)).fetchone()
            _require(row is not None, "观察记录不存在")
            self.db.execute("""INSERT INTO activity_deleted_ids
                (connection_id,event_hash,deleted_at) VALUES(?,?,?)""",
                (connection_id, self._event_hash(connection_id, event_id),
                 self._now().isoformat()))
            self.db.execute("""DELETE FROM activity_observations
                WHERE connection_id=? AND event_id=?""", (connection_id, event_id))

    def forget_connection(self, connection_id):
        """Delete authorization, observations and replay IDs for this connection."""
        with self.db:
            self._connection(connection_id)
            self.db.execute("DELETE FROM activity_connections WHERE id=?", (connection_id,))
