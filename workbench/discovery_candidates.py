"""Read unverified agent candidates from this workspace without changing discovery state."""

import json
import hashlib
import ipaddress
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit


CANDIDATE_ID = re.compile(r"[0-9a-f]{64}\Z")
PUBLIC_HOST = re.compile(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\Z")


def _public_url(value):
    if (not isinstance(value, str) or len(value) > 2048 or
            any(char.isspace() or char in '<>"\'\\' for char in value)):
        return False
    try:
        parsed = urlsplit(value)
        host, port = parsed.hostname, parsed.port
    except ValueError:
        return False
    if (parsed.scheme != "https" or not host or port is not None or
            parsed.username or parsed.password or not PUBLIC_HOST.fullmatch(host)
            or parsed.path in {"", "/"}):
        return False
    lowered = host.lower()
    if lowered.endswith((".local", ".internal", ".localhost", ".lan", ".home", ".invalid", ".test")):
        return False
    try:
        ipaddress.ip_address(lowered)
    except ValueError:
        return lowered.rsplit(".", 1)[1].isalpha()
    return False


def _candidate(row):
    try:
        data = json.loads(row["payload"])
    except (TypeError, ValueError):
        return None
    if (not isinstance(data, dict) or data.get("id") != row["source_job_id"]
            or not isinstance(data.get("id"), str)
            or not CANDIDATE_ID.fullmatch(data["id"])):
        return None
    title, url, observed, unknowns = (data.get("title"), data.get("job_url"),
                                      data.get("origin_observed_at"), data.get("unknowns"))
    if not (isinstance(title, str) and 0 < len(title.strip()) <= 300
            and _public_url(url) and isinstance(observed, str) and 0 < len(observed) <= 80
            and isinstance(unknowns, list) and len(unknowns) <= 10
            and all(isinstance(item, str) and 0 < len(item) <= 200 for item in unknowns)):
        return None
    if hashlib.sha256(url.encode("utf-8")).hexdigest() != data["id"]:
        return None
    try:
        stamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return None
    return {"id": data["id"], "title": title.strip(), "job_url": url,
            "origin_observed_at": observed, "unknowns": unknowns,
            "verification_state": "待核查"}


def list_candidates(workspace):
    """Return bounded, sanitized candidates; a missing or incompatible DB stays visible."""
    db_path = Path(workspace).expanduser().resolve() / "discovery.sqlite3"
    if not db_path.is_file():
        return {"state": "missing", "candidates": []}
    try:
        with sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=2) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("""SELECT source_job_id, payload FROM discovery_jobs
                                  WHERE source='agent' AND board='local' AND present_latest=1
                                  ORDER BY last_seen_at DESC LIMIT 100""").fetchall()
    except sqlite3.Error:
        return {"state": "unavailable", "candidates": []}
    candidates = [candidate for row in rows if (candidate := _candidate(row)) is not None]
    return {"state": "ready", "candidates": candidates}


def get_candidate(workspace, candidate_id):
    """Re-read the selected record server side; never trust a client-supplied URL."""
    if not isinstance(candidate_id, str) or not CANDIDATE_ID.fullmatch(candidate_id):
        raise ValueError("候选 ID 无效")
    db_path = Path(workspace).expanduser().resolve() / "discovery.sqlite3"
    if not db_path.is_file():
        raise ValueError("当前工作区还没有岗位候选库")
    try:
        with sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=2) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("""SELECT source_job_id, payload FROM discovery_jobs
                                WHERE source='agent' AND board='local' AND present_latest=1
                                  AND source_job_id=?""", (candidate_id,)).fetchone()
    except sqlite3.Error as exc:
        raise ValueError("候选库暂不可读，请先检查本机发现数据") from exc
    candidate = _candidate(row) if row else None
    if candidate is None:
        raise ValueError("候选已不存在或记录无效，请重新选择")
    return candidate
