"""Read-only public job discovery with per-workspace SQLite snapshots."""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .directions import empty_direction_profile, validate_direction_form

SOURCE = "ashby"
AGENT_SOURCE = "agent"
AGENT_BOARD = "local"
API_HOST = "api.ashbyhq.com"
JOBS_HOST = "jobs.ashbyhq.com"
BOARD_RE = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
JOB_ID_RE = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\Z")
AGENT_JOB_ID_RE = re.compile(r"[0-9a-f]{64}\Z")
MAX_RESPONSE = 15_000_000
MIN_REFRESH_SECONDS = 60
CITY_ALIASES = {
    "上海": ("上海", "shanghai"),
    "shanghai": ("上海", "shanghai"),
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_board(board):
    if not isinstance(board, str) or not BOARD_RE.fullmatch(board):
        raise ValueError("board 名称只允许字母、数字、下划线和连字符")
    return board


def source_url(board):
    return f"https://{API_HOST}/posting-api/job-board/{validate_board(board)}"


def validated_job_url(value, board, job_id=None, application=False):
    if not isinstance(value, str):
        raise ValueError("原站职位链接缺失")
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != "https" or parsed.netloc != JOBS_HOST or
            parsed.query or parsed.fragment or parsed.username or parsed.password):
        raise ValueError("原站链接主机或协议无效")
    parts = parsed.path.strip("/").split("/")
    expected = 3 if application else 2
    if (len(parts) != expected or parts[0] != board or
            not JOB_ID_RE.fullmatch(parts[1]) or
            (application and parts[2] != "application") or
            (job_id is not None and parts[1].lower() != job_id.lower())):
        raise ValueError("原站链接与 board 或职位 ID 不符")
    canonical = f"https://{JOBS_HOST}/{board}/{parts[1].lower()}"
    return canonical + ("/application" if application else ""), parts[1].lower()


def _short(value, limit=200):
    return value[:limit] if isinstance(value, str) else ""


def parse_ashby(board, payload):
    validate_board(board)
    if not isinstance(payload, dict) or payload.get("apiVersion") != "1" or not isinstance(payload.get("jobs"), list):
        raise ValueError("Ashby 返回结构无效")
    result = []
    seen = set()
    for raw in payload["jobs"]:
        if not isinstance(raw, dict):
            raise ValueError("职位记录无效")
        if raw.get("isListed") is not True:
            continue
        title = _short(raw.get("title"), 300).strip()
        if not title:
            raise ValueError("职位标题缺失")
        job_url, job_id = validated_job_url(raw.get("jobUrl"), board)
        if job_id in seen:
            raise ValueError("来源响应存在重复职位 ID")
        seen.add(job_id)
        apply_url = None
        if raw.get("applyUrl"):
            try:
                apply_url, _ = validated_job_url(raw["applyUrl"], board, job_id, True)
            except ValueError:
                pass  # Preserve the job and mark its application route unknown.
        description = _short(raw.get("descriptionPlain"), 20000)
        secondary = raw.get("secondaryLocations")
        other_locations = []
        if isinstance(secondary, list):
            other_locations = [_short(x.get("location"), 200) for x in secondary if isinstance(x, dict)]
        original = {key: raw.get(key) for key in ("title", "location", "secondaryLocations", "department", "team", "isRemote", "workplaceType", "publishedAt", "employmentType", "jobUrl", "applyUrl")}
        result.append({
            "id": job_id, "title": title, "location": _short(raw.get("location"), 300),
            "secondary_locations": other_locations, "department": _short(raw.get("department")),
            "team": _short(raw.get("team")), "employment_type": _short(raw.get("employmentType")),
            "published_at": _short(raw.get("publishedAt"), 60), "description": description,
            "job_url": job_url, "apply_url": apply_url,
            "raw_fields": original,
        })
    return result


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("来源重定向已拒绝")


class AshbySource:
    """Second public ATS source can implement fetch(board) and parse(board, payload)."""
    name = SOURCE

    def fetch(self, board):
        request = urllib.request.Request(source_url(board), headers={"Accept": "application/json", "User-Agent": "CareerWorkbench/0.1"})
        opener = urllib.request.build_opener(_NoRedirect)
        with opener.open(request, timeout=8) as response:
            if response.status != 200 or response.headers.get_content_type() != "application/json":
                raise ValueError("来源未返回 JSON 成功响应")
            data = response.read(MAX_RESPONSE + 1)
            if len(data) > MAX_RESPONSE:
                raise ValueError("来源响应超过大小限制")
        return json.loads(data.decode("utf-8"))

    def parse(self, board, payload):
        return parse_ashby(board, payload)


class JobStore:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db_path = self.workspace / "discovery.sqlite3"
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS discovery_sources(
                    source TEXT NOT NULL, board TEXT NOT NULL, source_url TEXT NOT NULL,
                    last_attempt_at TEXT, last_success_at TEXT, last_error TEXT,
                    failures INTEGER NOT NULL DEFAULT 0, next_allowed_at TEXT,
                    PRIMARY KEY(source, board));
                CREATE TABLE IF NOT EXISTS discovery_jobs(
                    source TEXT NOT NULL, board TEXT NOT NULL, source_job_id TEXT NOT NULL,
                    payload TEXT NOT NULL, first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL, present_latest INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY(source, board, source_job_id));
                CREATE TABLE IF NOT EXISTS discovery_profile(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS direction_profile(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS discovery_flags(
                    source TEXT NOT NULL, board TEXT NOT NULL, source_job_id TEXT NOT NULL,
                    viewed INTEGER NOT NULL DEFAULT 0, bookmarked INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(source, board, source_job_id));
                CREATE TABLE IF NOT EXISTS discovery_agent_batches(
                    agent_id TEXT NOT NULL, batch_id TEXT NOT NULL, digest TEXT NOT NULL,
                    generated_at TEXT NOT NULL, imported_at TEXT NOT NULL,
                    candidate_count INTEGER NOT NULL, PRIMARY KEY(agent_id, batch_id));
                CREATE TABLE IF NOT EXISTS discovery_agent_reports(
                    agent_id TEXT NOT NULL, batch_id TEXT NOT NULL, source_job_id TEXT NOT NULL,
                    payload TEXT NOT NULL, imported_at TEXT NOT NULL,
                    PRIMARY KEY(agent_id, batch_id, source_job_id));
            """)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def source_state(self, board):
        with self._connect() as db:
            row = db.execute("SELECT * FROM discovery_sources WHERE source=? AND board=?", (SOURCE, validate_board(board))).fetchone()
            return dict(row) if row else {"source": SOURCE, "board": board, "source_url": source_url(board), "last_success_at": None, "last_error": None, "next_allowed_at": None}

    def agent_state(self):
        with self._connect() as db:
            row = db.execute("SELECT last_success_at FROM discovery_sources WHERE source=? AND board=?", (AGENT_SOURCE, AGENT_BOARD)).fetchone()
            count = db.execute("SELECT COUNT(*) FROM discovery_jobs WHERE source=? AND board=?", (AGENT_SOURCE, AGENT_BOARD)).fetchone()[0]
            batches = db.execute("SELECT COUNT(*) FROM discovery_agent_batches").fetchone()[0]
        return {"last_imported_at": row[0] if row else None, "candidates": count, "batches": batches}

    def refresh(self, board, adapter=None, at=None):
        board = validate_board(board)
        adapter = adapter or AshbySource()
        if adapter.name != SOURCE:
            raise ValueError("未接入的来源")
        at = at or utc_now()
        stamp = datetime.fromisoformat(at)
        if stamp.tzinfo is None:
            raise ValueError("刷新时间必须带时区")
        state = self.source_state(board)
        if state["next_allowed_at"] and stamp < datetime.fromisoformat(state["next_allowed_at"]):
            return {"status": "cooldown", "next_allowed_at": state["next_allowed_at"]}
        try:
            jobs = adapter.parse(board, adapter.fetch(board))
        except (ValueError, OSError, urllib.error.URLError, json.JSONDecodeError, UnicodeError) as exc:
            failures = min(int(state.get("failures", 0)) + 1, 7)
            wait_seconds = min(3600, MIN_REFRESH_SECONDS * 2 ** (failures - 1))
            next_at = (stamp + timedelta(seconds=wait_seconds)).isoformat()
            with self._connect() as db:
                db.execute("INSERT INTO discovery_sources(source,board,source_url,last_attempt_at,last_error,failures,next_allowed_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(source,board) DO UPDATE SET last_attempt_at=excluded.last_attempt_at,last_error=excluded.last_error,failures=excluded.failures,next_allowed_at=excluded.next_allowed_at", (SOURCE, board, source_url(board), at, type(exc).__name__, failures, next_at))
            return {"status": "error", "next_allowed_at": next_at}
        next_at = (stamp + timedelta(seconds=MIN_REFRESH_SECONDS)).isoformat()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO discovery_sources(source,board,source_url,last_attempt_at,last_success_at,last_error,failures,next_allowed_at) VALUES(?,?,?,?,?,?,0,?) ON CONFLICT(source,board) DO UPDATE SET last_attempt_at=excluded.last_attempt_at,last_success_at=excluded.last_success_at,last_error=NULL,failures=0,next_allowed_at=excluded.next_allowed_at", (SOURCE, board, source_url(board), at, at, None, next_at))
            db.execute("UPDATE discovery_jobs SET present_latest=0 WHERE source=? AND board=?", (SOURCE, board))
            new_count = 0
            for job in jobs:
                payload = json.dumps(job, ensure_ascii=False, separators=(",", ":"))
                existed = db.execute("SELECT 1 FROM discovery_jobs WHERE source=? AND board=? AND source_job_id=?", (SOURCE, board, job["id"])).fetchone()
                db.execute("INSERT INTO discovery_jobs(source,board,source_job_id,payload,first_seen_at,last_seen_at,present_latest) VALUES(?,?,?,?,?,?,1) ON CONFLICT(source,board,source_job_id) DO UPDATE SET payload=excluded.payload,last_seen_at=excluded.last_seen_at,present_latest=1", (SOURCE, board, job["id"], payload, at, at))
                new_count += not bool(existed)
        return {"status": "success", "total": len(jobs), "new": int(new_count), "last_success_at": at}

    def profile(self):
        with self._connect() as db:
            row = db.execute("SELECT payload FROM discovery_profile WHERE singleton=1").fetchone()
        return json.loads(row[0]) if row else {"city": "", "direction": "", "keywords": "", "cohort": "", "exclude": "", "include_unknown_cohort": True}

    def save_profile(self, profile):
        keys = ("city", "direction", "keywords", "cohort", "exclude")
        safe = {key: _short(profile.get(key), 120).strip() for key in keys}
        safe["include_unknown_cohort"] = bool(profile.get("include_unknown_cohort"))
        with self._connect() as db:
            db.execute("INSERT INTO discovery_profile(singleton,payload) VALUES(1,?) ON CONFLICT(singleton) DO UPDATE SET payload=excluded.payload", (json.dumps(safe, ensure_ascii=False),))
        return safe

    def direction_profile(self):
        with self._connect() as db:
            row = db.execute("SELECT payload FROM direction_profile WHERE singleton=1").fetchone()
        return json.loads(row[0]) if row else empty_direction_profile()

    def save_direction_form(self, values):
        profile = validate_direction_form(values)
        profile["updated_at"] = utc_now()
        with self._connect() as db:
            db.execute(
                "INSERT INTO direction_profile(singleton,payload) VALUES(1,?) "
                "ON CONFLICT(singleton) DO UPDATE SET payload=excluded.payload",
                (json.dumps(profile, ensure_ascii=False),),
            )
        return profile

    def save_direction_seed(self, main="", secondary="", watch=""):
        """Save a proxy-entered hypothesis without pretending the user confirmed it."""
        profile = empty_direction_profile()
        profile["priorities"] = {
            "main": _short(main, 240).strip(),
            "secondary": _short(secondary, 240).strip(),
            "watch": _short(watch, 240).strip(),
        }
        profile.update(source="proxy", updated_at=utc_now())
        with self._connect() as db:
            db.execute(
                "INSERT INTO direction_profile(singleton,payload) VALUES(1,?) "
                "ON CONFLICT(singleton) DO UPDATE SET payload=excluded.payload",
                (json.dumps(profile, ensure_ascii=False),),
            )
        return profile

    def set_flag(self, board, job_id, flag, value=True, source=SOURCE):
        if source == SOURCE:
            board = validate_board(board)
            valid_id = isinstance(job_id, str) and JOB_ID_RE.fullmatch(job_id)
        elif source == AGENT_SOURCE:
            valid_id = board == AGENT_BOARD and isinstance(job_id, str) and AGENT_JOB_ID_RE.fullmatch(job_id)
        else:
            valid_id = False
        if flag not in {"viewed", "bookmarked"} or not valid_id:
            raise ValueError("收藏或查看参数无效")
        with self._connect() as db:
            exists = db.execute("SELECT 1 FROM discovery_jobs WHERE source=? AND board=? AND source_job_id=?", (source, board, job_id)).fetchone()
            if not exists:
                raise ValueError("职位不存在")
            db.execute(f"INSERT INTO discovery_flags(source,board,source_job_id,{flag}) VALUES(?,?,?,?) ON CONFLICT(source,board,source_job_id) DO UPDATE SET {flag}=excluded.{flag}", (source, board, job_id, int(bool(value))))

    def jobs(self, boards, profile=None):
        profile = profile or self.profile()
        boards = [validate_board(board) for board in boards]
        board_filter = ""
        params = [AGENT_SOURCE, AGENT_BOARD]
        if boards:
            placeholders = ",".join("?" for _ in boards)
            board_filter = f" OR (j.source=? AND j.board IN ({placeholders}))"
            params.extend([SOURCE, *boards])
        with self._connect() as db:
            rows = db.execute(f"SELECT j.*,s.last_success_at,f.viewed,f.bookmarked FROM discovery_jobs j JOIN discovery_sources s ON s.source=j.source AND s.board=j.board LEFT JOIN discovery_flags f ON f.source=j.source AND f.board=j.board AND f.source_job_id=j.source_job_id WHERE (j.source=? AND j.board=?){board_filter} ORDER BY j.first_seen_at DESC,j.source_job_id", params).fetchall()
            agent_reports = {}
            for report in db.execute("SELECT source_job_id,payload FROM discovery_agent_reports ORDER BY imported_at DESC"):
                agent_reports.setdefault(report["source_job_id"], []).append(json.loads(report["payload"]))
        results = []
        for row in rows:
            job = json.loads(row["payload"])
            title_text = " ".join((job["title"], job["department"], job["team"])).casefold()
            full_text = " ".join((title_text, job["description"].casefold()))
            locations = " ".join((job["location"], *job["secondary_locations"])).casefold()
            city = profile.get("city", "").strip().casefold()
            if city and not any(alias in locations for alias in CITY_ALIASES.get(city, (city,))):
                continue
            if profile.get("direction") and profile["direction"].casefold() not in title_text:
                continue
            if profile.get("keywords") and profile["keywords"].casefold() not in full_text:
                continue
            exclude = [x.strip().casefold() for x in re.split(r"[,，\n]", profile.get("exclude", "")) if x.strip()]
            if any(x in full_text for x in exclude):
                continue
            cohort = profile.get("cohort", "")
            cohort_state = "未设置" if not cohort else "来源文字匹配" if cohort.casefold() in full_text else "未知"
            if cohort and cohort_state == "未知" and not profile.get("include_unknown_cohort", True):
                continue
            is_agent = row["source"] == AGENT_SOURCE
            job.update(board=row["board"], source=row["source"], source_url=job.get("origin_url") if is_agent else source_url(row["board"]),
                       first_seen_at=row["first_seen_at"], last_seen_at=row["last_seen_at"],
                       last_success_at=row["last_success_at"], present_latest=bool(row["present_latest"]),
                       viewed=bool(row["viewed"]), bookmarked=bool(row["bookmarked"]), cohort_state=cohort_state)
            job["agent_reports"] = agent_reports.get(job["id"], []) if is_agent else []
            job["list_state"] = "待核查" if is_agent or not row["present_latest"] else "已查看" if row["viewed"] else "新发现" if row["first_seen_at"] == row["last_success_at"] else "已发现"
            results.append(job)
        return results
