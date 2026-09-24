"""Event-sourced daily checklist. It never changes a job or submits an application."""

import json
import re
import sqlite3
import hashlib
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


KINDS = {
    "verify_job": "在求职记录中保存原岗位来源、核验结论和核验时间",
    "prepare_materials": "在求职记录中保存已核对的材料包",
    "approve_materials": "本人核对当前材料，并在求职记录中明确确认",
    "apply_job": "本人实际投递，完成材料确认，并在求职记录中保存投递回执",
    "practice": "在求职记录中保存本人独立练习与作品证据；不代表掌握",
    "attend_event": "记录参加情况、时间和可回看的依据",
    "prepare_interview": "保存面试准备笔记的位置",
    "follow_up": "保存本人跟进结果或发出信息的依据",
    "custom": "保存可回看的任务产物或结果位置",
}
JOB_EVENT_KINDS = {
    "verify_job": "assessed",
    "prepare_materials": "prepared",
    "approve_materials": "approved",
    "apply_job": "submitted",
    "practice": "practice",
}
TERMINAL = {"completed", "cancelled"}
ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def stamp(value, label):
    require(isinstance(value, str), f"{label} 必须是带时区的 ISO 时间")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} 时间格式无效") from exc
    require(result.tzinfo is not None and result.utcoffset() is not None, f"{label} 必须带时区")
    return result


def zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
        raise ValueError("未知时区，请使用 IANA 名称") from exc


class DailyStore:
    """One private workspace, one event log; clock and viewing zone are injectable."""

    def __init__(self, workspace, clock=None):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.db = sqlite3.connect(self.workspace / "daily.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS daily_events (
            seq INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
            task_id TEXT NOT NULL, at TEXT NOT NULL,
            command TEXT NOT NULL, payload TEXT NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS daily_reminders (
            task_id TEXT NOT NULL, scheduled_at TEXT NOT NULL,
            claimed_at TEXT NOT NULL, PRIMARY KEY(task_id, scheduled_at))""")
        self.db.commit()

    def close(self):
        self.db.close()

    def _now(self):
        result = self.clock()
        require(isinstance(result, datetime) and result.tzinfo is not None
                and result.utcoffset() is not None, "时钟必须返回带时区的时间")
        return result

    def _tasks(self):
        tasks = {}
        for row in self.db.execute("SELECT * FROM daily_events ORDER BY seq"):
            payload = json.loads(row["payload"])
            task_id = row["task_id"]
            if row["command"] == "schedule":
                task = dict(payload["task"])
                task.update(state="scheduled", origin_scheduled_at=task["scheduled_at"],
                            evidence_state="missing", created_at=row["at"], last_at=row["at"], latest_reason=None,
                            terminal_at=None)
                tasks[task_id] = task
                continue
            task = tasks[task_id]
            command = row["command"]
            if command == "start":
                task["state"] = "in_progress"
            elif command == "defer":
                task["state"] = "deferred"
                task["scheduled_at"] = payload["scheduled_at"]
                task["latest_reason"] = payload["reason"]
            elif command == "block":
                task["state"] = "blocked"
                task["latest_reason"] = payload["reason"]
            elif command == "complete":
                task["state"] = "completed"
                task["evidence_state"] = "recorded"
                task["terminal_at"] = row["at"]
            elif command == "cancel":
                task["state"] = "cancelled"
                task["latest_reason"] = payload["reason"]
                task["terminal_at"] = row["at"]
            task["last_at"] = row["at"]
        return tasks

    def _validate_task(self, task, occurred):
        require(isinstance(task, dict), "task 必须是对象")
        for key in ("id", "title", "kind", "source_kind", "source_id", "reason", "scheduled_at"):
            require(nonempty(task.get(key)), f"缺少 {key}")
        require(ID.fullmatch(task["id"]), "任务 ID 只允许字母、数字、下划线和连字符")
        require(task["kind"] in KINDS, "任务类型无效")
        require(task["source_kind"] in {"job", "event", "learning", "self"}, "来源类型无效")
        if task["kind"] in JOB_EVENT_KINDS:
            require(task["source_kind"] == "job", "该任务需要岗位来源")
        stamp(task["scheduled_at"], "scheduled_at")
        due = task.get("due_at")
        if due is not None:
            stamp(due, "due_at")
        require(type(task.get("due_verified")) is bool, "due_verified 必须是布尔值")
        checked = task.get("due_verified_at")
        if task["due_verified"]:
            require(due is not None and checked is not None, "核实截止需要 due_at 与 due_verified_at")
            require(stamp(checked, "due_verified_at") <= occurred + timedelta(minutes=5),
                    "截止核验时间不能来自未来")
        else:
            require(checked is None, "未核实截止不能设置 due_verified_at")
        require(set(task) <= {"id", "title", "kind", "source_kind", "source_id", "reason",
                             "scheduled_at", "due_at", "due_verified", "due_verified_at"}, "task 含未知字段")

    def _job_event(self, task, evidence, occurred):
        require(isinstance(evidence, dict) and type(evidence.get("job_event_seq")) is int,
                "完成该任务需要求职记录事件序号 job_event_seq")
        path = self.workspace / "state.sqlite3"
        require(path.is_file(), "求职记录不存在；先在原工作流登记")
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as jobs:
            row = jobs.execute("SELECT job,at,kind,payload FROM events WHERE seq=?",
                               (evidence["job_event_seq"],)).fetchone()
        require(row is not None and row[0] == task["source_id"]
                and row[2] == JOB_EVENT_KINDS[task["kind"]], "岗位事件不匹配任务类型或来源")
        require(stamp(row[1], "岗位事件时间") <= occurred + timedelta(minutes=5),
                "求职记录事件不能晚于任务完成时间")
        require(stamp(row[1], "岗位事件时间") >= stamp(task["created_at"], "任务创建时间"),
                "求职记录事件早于任务创建，不能复用旧结果完成新任务")
        details = json.loads(row[3])
        if task["kind"] == "verify_job":
            require(nonempty(details.get("source")) and nonempty(details.get("checked_at"))
                    and isinstance(details.get("checks"), dict), "核验事件缺少来源、时间或结论")
            stamp(details["checked_at"], "checked_at")
        elif task["kind"] == "apply_job":
            require(nonempty(details.get("evidence")), "投递事件缺少回执依据")
        elif task["kind"] == "practice":
            require(details.get("independent_self_report") is True
                    and nonempty(details.get("evidence")), "独立练习事件缺少作品依据")

    def _validate_completion(self, task, evidence, occurred):
        if task["kind"] in JOB_EVENT_KINDS:
            self._job_event(task, evidence, occurred)
            return
        require(isinstance(evidence, dict), "完成依据必须是对象")
        fields = {"attend_event": ("attendance_ref", "observed_at"),
                  "prepare_interview": ("notes_ref",),
                  "follow_up": ("contact_ref",), "custom": ("result_ref",)}[task["kind"]]
        require(all(nonempty(evidence.get(key)) for key in fields),
                "缺少该类型的完成依据：" + ", ".join(fields))
        if "observed_at" in fields:
            require(stamp(evidence["observed_at"], "observed_at") <= occurred + timedelta(minutes=5),
                    "参加时间不能来自未来")

    def _suggestions(self, now, existing):
        """Read current legacy job state as proposals; never writes or auto-schedules."""
        path = self.workspace / "state.sqlite3"
        if not path.is_file():
            return []
        mapping = {
            "discovered": ("verify_job", "岗位资格尚未核验"),
            "hold": ("verify_job", "仍有资格条件未知，补查原岗位页"),
            "eligible": ("prepare_materials", "资格已核验，下一步准备材料"),
            "prepared": ("approve_materials", "材料已准备，等待本人核对确认"),
            "approved": ("apply_job", "材料已确认；本人可去原站投递并保存回执"),
            "assessment": ("prepare_interview", "笔试阶段，准备后续沟通与复盘"),
            "interview": ("prepare_interview", "面试阶段，准备问题与案例"),
        }
        proposals = []
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as jobs:
            for (raw,) in jobs.execute("SELECT payload FROM jobs ORDER BY id"):
                job = json.loads(raw)
                latest = jobs.execute("SELECT seq,at FROM events WHERE job=? ORDER BY seq DESC LIMIT 1",
                                      (job["id"],)).fetchone()
                state = job["state"]
                if state in {"submitted", "responded"}:
                    last = job.get("last_event_at")
                    if not last or now - stamp(last, "last_event_at") < timedelta(days=7):
                        continue
                    kind, reason = "follow_up", "七天未记录新进展，可人工核对是否需要跟进；沉默不代表拒绝"
                else:
                    if state not in mapping:
                        continue
                    kind, reason = mapping[state]
                if any(task["source_kind"] == "job" and task["source_id"] == job["id"]
                       and task["kind"] == kind
                       and (task["state"] not in TERMINAL
                            or (task["terminal_at"] and latest
                                and stamp(task["terminal_at"], "terminal_at") >= stamp(latest[1], "last job event")))
                       for task in existing.values()):
                    continue
                digest = hashlib.sha256(f"{job['id']}:{kind}:{latest[0] if latest else 0}".encode()).hexdigest()[:16].upper()
                proposed_id = f"SUG-{digest}"
                proposed_time = now.isoformat()
                proposals.append({
                    "id": proposed_id, "title": f"{job['role']}：{KINDS[kind]}",
                    "kind": kind, "state": "suggested", "source_kind": "job",
                    "source_id": job["id"], "reason": reason,
                    "scheduled_at": proposed_time, "due_at": None, "due_verified": False,
                    "completion_rule": KINDS[kind], "evidence_state": "missing",
                    "origin_scheduled_at": proposed_time, "carryover_reason": None,
                    "due_verified_at": None,
                })
        return proposals

    def command(self, command, event_id, task_id, payload=None, at=None):
        """Apply an explicit command; duplicate event IDs return the original task."""
        require(command in {"schedule", "start", "complete", "defer", "block", "cancel"}, "命令无效")
        require(nonempty(event_id) and ID.fullmatch(event_id), "事件 ID 无效")
        require(nonempty(task_id) and ID.fullmatch(task_id), "任务 ID 无效")
        payload = {} if payload is None else payload
        require(isinstance(payload, dict), "命令参数必须是对象")
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            previous = self.db.execute("SELECT * FROM daily_events WHERE event_id=?", (event_id,)).fetchone()
            if previous is not None:
                require(previous["command"] == command and previous["task_id"] == task_id
                        and previous["payload"] == encoded and (at is None or previous["at"] == at),
                        "事件 ID 已用于不同命令")
                result = self._tasks()[task_id]
                self.db.commit()
                return result
            now = self._now()
            occurred = stamp(at, "at") if at is not None else now
            require(occurred <= now + timedelta(minutes=5), "事件时间不能来自未来")
            tasks = self._tasks()
            if command == "schedule":
                require(task_id not in tasks, "任务 ID 已存在")
                require(set(payload) == {"task"}, "schedule 需要 task")
                self._validate_task(payload["task"], occurred)
                require(payload["task"]["id"] == task_id, "任务 ID 不匹配")
            else:
                require(task_id in tasks, "任务不存在")
                task = tasks[task_id]
                require(task["state"] not in TERMINAL, "终态任务不可更改")
                require(occurred >= stamp(task["last_at"], "last_at"), "事件时间不能早于上个事件")
                if command == "start":
                    require(task["state"] in {"scheduled", "deferred", "blocked"}, "当前状态不能开始")
                    require(not payload, "start 不接受额外参数")
                elif command == "defer":
                    require(nonempty(payload.get("reason")), "延期需要原因")
                    require(stamp(payload.get("scheduled_at"), "scheduled_at") > occurred,
                            "延期时间必须晚于事件时间")
                    require(set(payload) == {"reason", "scheduled_at"}, "defer 参数无效")
                elif command in {"block", "cancel"}:
                    require(nonempty(payload.get("reason")) and set(payload) == {"reason"},
                            "该命令需要原因")
                elif command == "complete":
                    require(set(payload) == {"evidence"}, "complete 需要 evidence")
                    self._validate_completion(task, payload["evidence"], occurred)
            self.db.execute("INSERT INTO daily_events(event_id,task_id,at,command,payload) VALUES(?,?,?,?,?)",
                            (event_id, task_id, occurred.isoformat(), command, encoded))
            result = self._tasks()[task_id]
            self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            raise

    def snapshot(self, timezone_name="Asia/Shanghai"):
        viewing_zone = zone(timezone_name)
        now = self._now().astimezone(viewing_zone)
        today = now.date()
        tasks = self._tasks()
        visible = []
        for task in tasks.values():
            planned = stamp(task["scheduled_at"], "scheduled_at").astimezone(viewing_zone)
            ended = (stamp(task["terminal_at"], "terminal_at").astimezone(viewing_zone).date()
                     if task["terminal_at"] else None)
            original = stamp(task["origin_scheduled_at"], "origin_scheduled_at")
            if planned.date() > today and original.date() >= today and ended != today:
                continue
            if task["state"] in TERMINAL and ended != today:
                continue
            first_date = original.date()
            carryover = None
            if task["state"] not in TERMINAL and first_date < today:
                carryover = task["latest_reason"] or "原定日期已过，任务尚未完成"
            visible.append({
                "id": task["id"], "title": task["title"], "kind": task["kind"],
                "state": task["state"], "source_kind": task["source_kind"],
                "source_id": task["source_id"], "reason": task["reason"],
                "scheduled_at": task["scheduled_at"], "due_at": task.get("due_at"),
                "due_verified": task["due_verified"], "completion_rule": KINDS[task["kind"]],
                "evidence_state": task["evidence_state"],
                "origin_scheduled_at": task["origin_scheduled_at"],
                "carryover_reason": carryover, "due_verified_at": task.get("due_verified_at"),
            })
        visible.extend(self._suggestions(now, tasks))
        visible.sort(key=lambda item: (item["state"] in TERMINAL,
                                       stamp(item["scheduled_at"], "scheduled_at").timestamp(),
                                       item["id"]))
        return {"schema_version": 0, "as_of": now.isoformat(), "timezone": timezone_name,
                "today": today.isoformat(), "tasks": visible}

    def claim_reminders(self):
        """Return newly due planned-time reminders once per task/time, across restarts."""
        now = self._now()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            claimed = []
            for task in self._tasks().values():
                if task["state"] in TERMINAL or task["state"] == "blocked":
                    continue
                planned = task["scheduled_at"]
                if stamp(planned, "scheduled_at") > now:
                    continue
                cursor = self.db.execute("""INSERT OR IGNORE INTO daily_reminders
                    (task_id,scheduled_at,claimed_at) VALUES(?,?,?)""",
                    (task["id"], planned, now.isoformat()))
                if cursor.rowcount:
                    claimed.append({"task_id": task["id"], "scheduled_at": planned})
            self.db.commit()
            return claimed
        except Exception:
            self.db.rollback()
            raise
