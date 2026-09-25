"""Private, append-only interview observations and user hypotheses.

This module does not inspect external accounts, infer mastery, or write to the
legacy application workflow. Callers provide their own private workspace.
"""

import hashlib
import json
import os
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,48}\Z")
RECORD_IDENTIFIER = re.compile(r"INT-[A-Za-z0-9_-]{1,48}\Z")
SKILL_TARGET = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
INPUT_KINDS = {"question", "feedback"}
INPUT_FIDELITY = {"verbatim", "paraphrase", "uncertain"}
CONFIDENCE = {"low", "medium", "high"}
STATUSES = {"unverified", "user_checked", "needs_review"}
NOTE_FIELDS = (
    "interview_date", "company", "role", "input_kind", "interviewer_input",
    "input_fidelity", "self_observed_answer_or_problem", "evidence_source",
    "observation_confidence", "status", "inference", "inference_confidence",
    "linked_skill_target", "next_practice_step",
)
OPTIONAL_NOTE_FIELDS = {"linked_goal_id"}


def _required(value, name, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} 需要 1–{limit} 个字符")
    return value.strip()


def _optional(value, name, limit):
    if value is None or value == "":
        return None
    return _required(value, name, limit)


def _identifier(value, name):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} 只允许 1–48 位字母、数字、下划线或连字符")
    return value


def _record_id(value):
    if not isinstance(value, str) or not RECORD_IDENTIFIER.fullmatch(value):
        raise ValueError("记录 ID 无效")
    return value


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


class InterviewEvidenceStore:
    """Event-sourced store; a correction appends a complete new snapshot."""

    def __init__(self, workspace, clock=None):
        self.workspace = Path(workspace).expanduser().resolve()
        # macOS resolves /var to /private/var; that system prefix is not a
        # user-selected private workspace.
        if "private" not in self.workspace.parts[2:]:
            raise ValueError("面试记录工作区必须位于 private/ 目录之下")
        self.workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.workspace, 0o700)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.db_path = self.workspace / "interview_evidence.sqlite3"
        if self.db_path.is_symlink():
            raise ValueError("面试记录数据库不能是符号链接")
        self.db = sqlite3.connect(self.db_path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS interview_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                record_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('created','corrected')),
                previous_event_id TEXT,
                at TEXT NOT NULL,
                correction_reason TEXT,
                payload TEXT NOT NULL,
                UNIQUE(record_id, version)
            );
            CREATE INDEX IF NOT EXISTS interview_events_record
                ON interview_events(record_id, version);
            CREATE TABLE IF NOT EXISTS interview_operations (
                operation_id TEXT PRIMARY KEY,
                digest TEXT NOT NULL,
                record_id TEXT NOT NULL,
                event_id TEXT NOT NULL
            );
        """)
        self.db.commit()
        os.chmod(self.db_path, 0o600)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _now(self):
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("时钟必须包含时区")
        return value.isoformat()

    def _evidence_source(self, raw):
        if not isinstance(raw, dict) or set(raw) != {"kind", "value"}:
            raise ValueError("evidence_source 需要 kind 和 value")
        kind = raw["kind"]
        value = _required(raw["value"], "证据来源", 1000)
        if kind == "local_path":
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = self.workspace / path
            path = path.resolve()
            if not path.is_relative_to(self.workspace) or not path.is_file():
                raise ValueError("证据路径需要指向当前 private 工作区内的已有文件")
            relative = path.relative_to(self.workspace)
            return {"kind": kind, "value": relative.as_posix(),
                    "checked_at": self._now(), "file_size_bytes": path.stat().st_size}
        if kind == "url":
            parsed = urlsplit(value)
            if (parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password
                    or parsed.query or parsed.fragment):
                raise ValueError("证据 URL 需要无凭证、查询参数及片段的 HTTPS 地址")
            return {"kind": kind, "value": value, "checked_at": self._now()}
        raise ValueError("证据来源只能是 local_path 或 url")

    def _note(self, raw):
        if (not isinstance(raw, dict) or not set(NOTE_FIELDS) <= set(raw)
                or set(raw) - set(NOTE_FIELDS) - OPTIONAL_NOTE_FIELDS):
            raise ValueError("面试记录字段不完整或包含未知字段")
        interview_date = _required(raw["interview_date"], "面试日期", 10)
        try:
            parsed_date = date.fromisoformat(interview_date)
        except ValueError as exc:
            raise ValueError("面试日期需要 YYYY-MM-DD") from exc
        if parsed_date.isoformat() != interview_date or parsed_date > self.clock().date():
            raise ValueError("面试观察日期需要有效且不能来自未来")
        if raw["input_kind"] not in INPUT_KINDS:
            raise ValueError("面试官输入只能标为问题或反馈")
        if raw["input_fidelity"] not in INPUT_FIDELITY:
            raise ValueError("请说明面试官输入是原话、转述还是不确定")
        if raw["observation_confidence"] not in CONFIDENCE:
            raise ValueError("观察信心只能为 low、medium 或 high")
        if raw["status"] not in STATUSES:
            raise ValueError("记录状态无效")
        target = raw["linked_skill_target"]
        if not isinstance(target, str) or not SKILL_TARGET.fullmatch(target):
            raise ValueError("关联技能目标需要稳定 ID")
        goal_id = raw.get("linked_goal_id")
        if goal_id is not None and (not isinstance(goal_id, str) or not SKILL_TARGET.fullmatch(goal_id)):
            raise ValueError("关联目标 ID 无效")
        inference = _optional(raw["inference"], "本人推断", 1000)
        inference_confidence = raw["inference_confidence"]
        if inference is None and inference_confidence is not None:
            raise ValueError("没有推断时不能填写推断信心")
        if inference is not None and inference_confidence not in CONFIDENCE:
            raise ValueError("推断需要独立标注 low、medium 或 high 信心")
        return {
            "interview_date": interview_date,
            "company": _required(raw["company"], "公司", 120),
            "role": _required(raw["role"], "职位", 120),
            "observation": {
                "input_kind": raw["input_kind"],
                "interviewer_input": _required(raw["interviewer_input"], "面试官问题或反馈", 2000),
                "input_fidelity": raw["input_fidelity"],
                "self_observed_answer_or_problem": _required(
                    raw["self_observed_answer_or_problem"], "本人观察到的作答或问题", 2000),
                "confidence": raw["observation_confidence"],
                "status": raw["status"],
                "evidence_source": self._evidence_source(raw["evidence_source"]),
            },
            "inference": ({"hypothesis": inference, "confidence": inference_confidence,
                           "basis": "user_hypothesis"} if inference is not None else None),
            "linked_skill_target": target,
            "linked_goal_id": goal_id,
            "next_practice_step": _required(raw["next_practice_step"], "下一步练习", 1000),
            "mastery_status": "not_assessed",
            "resume_claim_status": "not_created",
        }

    def _latest(self, record_id):
        row = self.db.execute("SELECT * FROM interview_events WHERE record_id=? "
                              "ORDER BY version DESC LIMIT 1", (_record_id(record_id),)).fetchone()
        if row is None:
            raise ValueError("面试记录不存在")
        return row

    def _mutate(self, kind, payload, action):
        operation_id = _identifier(payload.get("operation_id"), "operation_id")
        fingerprint = _digest({"kind": kind, "payload": {k: v for k, v in payload.items()
                                                   if k != "operation_id"}})
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            existing = self.db.execute("SELECT * FROM interview_operations WHERE operation_id=?",
                                       (operation_id,)).fetchone()
            if existing:
                if existing["digest"] != fingerprint:
                    raise ValueError("operation_id 已用于不同操作")
                return self.get(existing["record_id"])
            record_id, event_id = action(operation_id)
            self.db.execute("INSERT INTO interview_operations VALUES(?,?,?,?)",
                            (operation_id, fingerprint, record_id, event_id))
        return self.get(record_id)

    def add(self, payload):
        """Create one user-entered interview note; operation_id makes retries safe."""
        if not isinstance(payload, dict) or set(payload) != {"operation_id", "note"}:
            raise ValueError("新增需要 operation_id 和 note")
        note = self._note(payload["note"])

        def save(operation_id):
            record_id = "INT-" + operation_id
            at = self._now()
            self.db.execute("INSERT INTO interview_events(event_id,record_id,version,kind,previous_event_id,"
                            "at,correction_reason,payload) VALUES(?,?,1,'created',NULL,?,NULL,?)",
                            (operation_id, record_id, at, json.dumps(note, ensure_ascii=False)))
            return record_id, operation_id

        return self._mutate("add", payload, save)

    def correct(self, payload):
        """Append a full replacement snapshot after an explicit version check."""
        if not isinstance(payload, dict) or set(payload) != {
                "operation_id", "record_id", "expected_version", "reason", "note"}:
            raise ValueError("更正需要 operation_id、record_id、expected_version、reason 和 note")
        record_id = _record_id(payload["record_id"])
        expected = payload["expected_version"]
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 1:
            raise ValueError("expected_version 需要正整数")
        reason = _required(payload["reason"], "更正原因", 500)
        note = self._note(payload["note"])

        def save(operation_id):
            previous = self._latest(record_id)
            if previous["version"] != expected:
                raise ValueError("记录已更新，请先读取最新版本再更正")
            at = self._now()
            self.db.execute("INSERT INTO interview_events(event_id,record_id,version,kind,previous_event_id,"
                            "at,correction_reason,payload) VALUES(?,?,?,'corrected',?,?,?,?)",
                            (operation_id, record_id, expected + 1, previous["event_id"], at,
                             reason, json.dumps(note, ensure_ascii=False)))
            return record_id, operation_id

        return self._mutate("correct", payload, save)

    def get(self, record_id, include_history=False):
        latest = self._latest(record_id)
        result = {"record_id": record_id, "version": latest["version"],
                  "last_event_id": latest["event_id"], "updated_at": latest["at"],
                  "note": json.loads(latest["payload"])}
        if include_history:
            result["history"] = [
                {"event_id": row["event_id"], "version": row["version"], "kind": row["kind"],
                 "previous_event_id": row["previous_event_id"], "at": row["at"],
                 "correction_reason": row["correction_reason"], "note": json.loads(row["payload"])}
                for row in self.db.execute("SELECT * FROM interview_events WHERE record_id=? ORDER BY version",
                                           (record_id,))]
        return result

    def list(self, company=None, role=None, goal_id=None):
        """Return latest snapshots only; optional exact context filters."""
        if company is not None:
            company = _required(company, "公司筛选", 120)
        if role is not None:
            role = _required(role, "职位筛选", 120)
        if goal_id is not None and (not isinstance(goal_id, str) or not SKILL_TARGET.fullmatch(goal_id)):
            raise ValueError("关联目标 ID 无效")
        records = []
        for row in self.db.execute("SELECT record_id, MAX(version) FROM interview_events "
                                   "GROUP BY record_id ORDER BY MAX(seq) DESC"):
            item = self.get(row["record_id"])
            if ((company is None or item["note"]["company"] == company) and
                    (role is None or item["note"]["role"] == role) and
                    (goal_id is None or item["note"]["linked_goal_id"] == goal_id)):
                records.append(item)
        return records
