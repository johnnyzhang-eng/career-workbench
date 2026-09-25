"""Local, user-confirmed job requirement → external chapter → learning events."""

import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

from .learning_resources import RESOURCE_BY_ID, SKILLS, recommend, resource_revision


ID = re.compile(r"[A-Za-z0-9_-]{1,120}\Z")


def _text(value, name, limit=1000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} 需要 1–{limit} 个字符")
    return value.strip()


def _id(value, name):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError(f"{name} 无效")
    return value


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _url(value, name):
    value = _text(value, name, 1000)
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"{name} 需要无凭证的 HTTPS 具体页面")
    return value


def _job_revision(job):
    # Application state changes do not mutate this job-source identity.
    return _digest({key: job.get(key) for key in ("id", "company", "role", "url")})


class LearningStore:
    def __init__(self, workspace, clock=None):
        self.workspace = Path(workspace).expanduser().resolve()
        self.workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.workspace, 0o700)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        database = self.workspace / "learning_resources.sqlite3"
        self.db = sqlite3.connect(database, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS profile (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS requirements (
                id TEXT PRIMARY KEY, job_id TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS choices (
                requirement_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS access_issues (
                resource_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS learning_events (
                seq INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
                requirement_id TEXT NOT NULL, resource_id TEXT NOT NULL,
                resource_revision TEXT,
                kind TEXT NOT NULL, at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS operations (
                operation_id TEXT PRIMARY KEY, kind TEXT NOT NULL, digest TEXT NOT NULL);
        """)
        if "resource_revision" not in {row[1] for row in self.db.execute("PRAGMA table_info(learning_events)")}:
            # Development snapshots without this binding remain historical.
            self.db.execute("ALTER TABLE learning_events ADD COLUMN resource_revision TEXT")
        self.db.commit()
        if not database.exists():
            raise RuntimeError("学习存储未创建")
        os.chmod(database, 0o600)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _jobs(self):
        database = self.workspace / "state.sqlite3"
        if not database.is_file():
            return []
        uri = "file:" + quote(str(database)) + "?mode=ro"
        try:
            with closing(sqlite3.connect(uri, uri=True, timeout=3)) as source:
                source.execute("PRAGMA query_only=ON")
                rows = source.execute("SELECT payload FROM jobs ORDER BY id").fetchall()
        except sqlite3.Error as exc:
            raise ValueError("岗位快照暂不可读取；学习记录没有变更") from exc
        return [json.loads(row[0]) for row in rows]

    def _requirement(self, requirement_id):
        row = self.db.execute("SELECT payload FROM requirements WHERE id=?",
                              (_id(requirement_id, "要求 ID"),)).fetchone()
        if row is None:
            raise ValueError("岗位技能要求不存在")
        return json.loads(row[0])

    def _usable_requirement(self, requirement_id):
        requirement = self._requirement(requirement_id)
        job = next((item for item in self._jobs() if item["id"] == requirement["job_id"]), None)
        if job is None or requirement["job_revision"] != _job_revision(job):
            raise ValueError("岗位来源快照已变化；旧映射保留，需重新核对")
        if requirement["confirmation_status"] != "confirmed":
            raise ValueError("先由本人确认这条岗位技能要求")
        return requirement

    def _mutate(self, kind, payload, action):
        operation = _id(payload.get("operation_id"), "operation_id")
        if len(operation) > 48:
            raise ValueError("operation_id 最长 48 个字符")
        fingerprint = _digest({key: value for key, value in payload.items() if key != "operation_id"})
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            existing = self.db.execute("SELECT kind,digest FROM operations WHERE operation_id=?",
                                       (operation,)).fetchone()
            if existing:
                if (existing["kind"], existing["digest"]) != (kind, fingerprint):
                    raise ValueError("operation_id 已用于不同操作")
                return
            action(operation)
            self.db.execute("INSERT INTO operations VALUES(?,?,?)", (operation, kind, fingerprint))

    def set_profile(self, payload):
        language = payload.get("language")
        known = payload.get("known_skills")
        if language not in {"en", "zh", "any"}:
            raise ValueError("语言偏好只能是英语、中文或不限")
        if not isinstance(known, list) or len(known) > 20 or any(
                not isinstance(skill, str) or not ID.fullmatch(skill) for skill in known):
            raise ValueError("已知前置技能列表无效")
        clean = {"language": language, "known_skills": sorted(set(known)),
                 "basis": "user_self_reported", "verified": False}
        self._mutate("profile", payload, lambda _op: self.db.execute(
            "INSERT OR REPLACE INTO profile VALUES('current',?)", (json.dumps(clean, ensure_ascii=False),)))
        return self.state()

    def add_requirement(self, payload):
        job_id = _id(payload.get("job_id"), "岗位 ID")
        job = next((job for job in self._jobs() if job["id"] == job_id), None)
        if job is None:
            raise ValueError("请先在旧岗位工作流中保存岗位，学习不会代建投递记录")
        skill_id = payload.get("skill_id")
        if skill_id not in SKILLS:
            raise ValueError("技能定义不存在，请人工补录后再映射")
        status = payload.get("confirmation_status")
        if status not in {"confirmed", "needs_review"}:
            raise ValueError("要求状态只能为本人确认或待核验")
        excerpt = _text(payload.get("excerpt"), "JD 原片段", 500)
        source_url = _url(payload.get("source_url"), "JD 来源")
        checked_at = _text(payload.get("source_checked_at"), "来源核对时间", 50)
        try:
            checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("来源核对时间需要 ISO 8601") from exc
        if checked.tzinfo is None or checked.astimezone(timezone.utc) > self.clock():
            raise ValueError("来源核对时间需要时区，不能来自未来")
        op = _id(payload.get("operation_id"), "operation_id")
        requirement = {"id": "REQ-" + op, "job_id": job_id, "job_revision": _job_revision(job),
                       "skill_id": skill_id, "skill_version": SKILLS[skill_id]["version"],
                       "source_ref": {"entity": "job_jd", "job_id": job_id, "source_url": source_url,
                                      "field": "requirement_excerpt", "excerpt": excerpt,
                                      "checked_at": checked_at,
                                      "content_revision": _digest([source_url, excerpt])},
                       "confirmation_status": status, "confirmed_by": "user" if status == "confirmed" else None,
                       "created_at": self.clock().isoformat()}

        def save(_operation):
            self.db.execute("INSERT INTO requirements VALUES(?,?,?)",
                            (requirement["id"], job_id, json.dumps(requirement, ensure_ascii=False)))

        self._mutate("requirement", payload, save)
        return self.state(job_id)

    def choose(self, payload):
        requirement = self._usable_requirement(payload.get("requirement_id"))
        resource_id = payload.get("resource_id")
        decision = payload.get("decision")
        if decision not in {"choose", "reject"}:
            raise ValueError("只能选择或拒绝推荐")
        if decision == "choose" and (resource_id not in RESOURCE_BY_ID or
                                      RESOURCE_BY_ID[resource_id]["skill_id"] != requirement["skill_id"]):
            raise ValueError("资源与岗位要求不匹配")
        reason = _text(payload.get("reason"), "选择原因", 500)
        choice = {"decision": decision, "resource_id": resource_id if decision == "choose" else None,
                  "resource_revision": resource_revision(RESOURCE_BY_ID[resource_id]) if decision == "choose" else None,
                  "reason": reason, "at": self.clock().isoformat(), "actor": "user"}
        self._mutate("choice", payload, lambda _op: self.db.execute(
            "INSERT OR REPLACE INTO choices VALUES(?,?)",
            (requirement["id"], json.dumps(choice, ensure_ascii=False))))
        return self.state(requirement["job_id"])

    def record_event(self, payload):
        requirement = self._usable_requirement(payload.get("requirement_id"))
        resource_id = payload.get("resource_id")
        resource = RESOURCE_BY_ID.get(resource_id)
        if resource is None or resource["skill_id"] != requirement["skill_id"]:
            raise ValueError("章节未绑定当前技能")
        revision = resource_revision(resource)
        kind = payload.get("kind")
        if kind not in {"opened", "in_progress", "completed_self_reported"}:
            raise ValueError("学习事件状态无效")
        evidence_ref = payload.get("evidence_ref")
        if kind == "completed_self_reported":
            evidence_ref = _text(evidence_ref, "本人作品或笔记依据", 1000)
        elif evidence_ref is not None:
            evidence_ref = _text(evidence_ref, "依据引用", 1000)

        def save(operation):
            rows = self.db.execute("SELECT kind FROM learning_events WHERE requirement_id=? AND resource_id=? "
                                   "AND resource_revision=? ORDER BY seq",
                                   (requirement["id"], resource_id, revision)).fetchall()
            history = {row["kind"] for row in rows}
            # The resource journey is monotone. Repeating a click or retrying a
            # request with a fresh operation ID must not create a second event.
            if kind in history:
                return
            if "completed_self_reported" in history:
                raise ValueError("该章节已有本人自报完成记录；不能倒退学习状态")
            if kind == "in_progress" and "opened" not in history:
                raise ValueError("请先明确打开原章节；不会把推荐视为已开始")
            if kind == "completed_self_reported" and "in_progress" not in history:
                raise ValueError("先记录进行中，再本人自报完成")
            event = {"evidence_ref": evidence_ref, "evidence_status": "unverified",
                     "skill_status": "needs_validation", "actor": "user"}
            self.db.execute("INSERT INTO learning_events(event_id,requirement_id,resource_id,resource_revision,kind,at,payload) "
                            "VALUES(?,?,?,?,?,?,?)", (operation, requirement["id"], resource_id, revision, kind,
                                                  self.clock().isoformat(), json.dumps(event, ensure_ascii=False)))

        self._mutate("event", payload, save)
        return self.state(requirement["job_id"])

    def report_access_issue(self, payload):
        resource_id = payload.get("resource_id")
        if resource_id not in RESOURCE_BY_ID:
            raise ValueError("章节不存在")
        reason = _text(payload.get("reason"), "访问问题", 500)
        issue = {"reason": reason, "at": self.clock().isoformat(), "status": "access_needs_recheck"}
        self._mutate("access_issue", payload, lambda _op: self.db.execute(
            "INSERT OR REPLACE INTO access_issues VALUES(?,?)",
            (resource_id, json.dumps(issue, ensure_ascii=False))))
        return self.state()

    def state(self, job_id=None):
        jobs = self._jobs()
        by_id = {job["id"]: job for job in jobs}
        if job_id is not None and job_id not in by_id:
            raise ValueError("岗位不存在")
        profile_row = self.db.execute("SELECT payload FROM profile WHERE key='current'").fetchone()
        profile = (json.loads(profile_row["payload"]) if profile_row else
                   {"language": "any", "known_skills": [], "basis": "not_set", "verified": False})
        issues = {row["resource_id"] for row in self.db.execute("SELECT resource_id FROM access_issues")}
        choices = {row["requirement_id"]: json.loads(row["payload"])
                   for row in self.db.execute("SELECT requirement_id,payload FROM choices")}
        activities = {}
        historical_activities = {}
        for row in self.db.execute("SELECT * FROM learning_events ORDER BY seq"):
            key = (row["requirement_id"], row["resource_id"])
            resource = RESOURCE_BY_ID.get(row["resource_id"])
            if resource is None or row["resource_revision"] != resource_revision(resource):
                historical_activities[row["requirement_id"]] = True
                continue
            activities[key] = {"state": row["kind"], "last_at": row["at"],
                               "evidence_ref": json.loads(row["payload"])["evidence_ref"],
                               "evidence_status": "unverified", "skill_status": "needs_validation"}
        requirements = []
        for row in self.db.execute("SELECT payload FROM requirements ORDER BY rowid"):
            requirement = json.loads(row["payload"])
            job = by_id.get(requirement["job_id"])
            stale = job is None or requirement["job_revision"] != _job_revision(job)
            effective = {**requirement, "confirmation_status": "needs_review" if stale else
                         requirement["confirmation_status"]}
            recommendation = recommend(effective, profile, issues, self.clock().date())
            choice = choices.get(requirement["id"])
            if choice and choice["decision"] == "choose":
                resource = RESOURCE_BY_ID.get(choice["resource_id"])
                choice = {**choice, "source_stale": resource is None or
                          choice.get("resource_revision") != resource_revision(resource)}
            requirements.append({**requirement, "source_stale": stale,
                                 "recommendation": recommendation,
                                 "choice": choice,
                                 "historical_activities": historical_activities.get(requirement["id"], False),
                                 "activities": {resource_id: value for (req_id, resource_id), value in activities.items()
                                                if req_id == requirement["id"]}})
        return {"jobs": jobs, "selected_job_id": job_id or (jobs[0]["id"] if jobs else None),
                "profile": profile, "skills": SKILLS, "requirements": requirements,
                "model_status": "not_configured", "storage": "local",
                "as_of": self.clock().isoformat()}
