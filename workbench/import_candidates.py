"""Import a local agent's cited job candidates into one private workspace."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import stat
import urllib.parse
from datetime import datetime
from pathlib import Path

from .jobs import AGENT_BOARD, AGENT_SOURCE, JobStore, utc_now

ROOT = Path(__file__).resolve().parents[1]
ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
HOST_RE = re.compile(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\Z")
JOB_QUERY_KEYS = {"gh_jid", "job_id", "posting_id"}
QUERY_VALUE_RE = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")
MAX_FILE = 1_000_000
MAX_CANDIDATES = 100


def _text(value, field, limit, required=True):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f"{field} 必须是有长度限制的文字")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError(f"{field} 含控制字符")
    return value.strip()


def _time(value, field):
    value = _text(value, field, 60)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} 时间无效") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} 必须带时区")
    return parsed.isoformat()


def public_url(value, field):
    value = _text(value, field, 2048)
    if any(c.isspace() for c in value) or any(c in value for c in ('<', '>', '"', "'", "\\")):
        raise ValueError(f"{field} 含不安全字符")
    try:
        parts = urllib.parse.urlsplit(value)
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise ValueError(f"{field} 不是安全 URL") from exc
    if (parts.scheme != "https" or not host or parts.username or parts.password or
            port is not None or parts.fragment or not HOST_RE.fullmatch(host) or
            parts.path in {"", "/"}):
        raise ValueError(f"{field} 必须是无凭据的公开 HTTPS 具体页面")
    lowered = host.lower()
    if lowered.endswith((".local", ".internal", ".localhost", ".lan", ".home", ".invalid", ".test")):
        raise ValueError(f"{field} 主机不公开")
    try:
        ipaddress.ip_address(lowered)
    except ValueError:
        pass
    else:
        raise ValueError(f"{field} 不能使用 IP 地址")
    if not lowered.rsplit(".", 1)[1].isalpha() or len(lowered.rsplit(".", 1)[1]) < 2:
        raise ValueError(f"{field} 主机后缀无效")
    path = parts.path.rstrip("/")
    if any(segment in {".", ".."} for segment in urllib.parse.unquote(path).split("/")):
        raise ValueError(f"{field} 路径无效")
    query = ""
    if parts.query:
        try:
            pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
        except ValueError as exc:
            raise ValueError(f"{field} 查询参数无效") from exc
        if (not pairs or len(pairs) > len(JOB_QUERY_KEYS) or len({key for key, _ in pairs}) != len(pairs) or
                any(key not in JOB_QUERY_KEYS or not QUERY_VALUE_RE.fullmatch(value) for key, value in pairs)):
            raise ValueError(f"{field} 只接受明确的职位 ID 参数")
        query = urllib.parse.urlencode(sorted(pairs))
    return urllib.parse.urlunsplit(("https", lowered, path, query, ""))


def _unique_json_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("JSON 含重复字段")
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError("JSON 含非标准数值")


def parse_batch(data):
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("需要 schema_version=1")
    agent_id = data.get("agent_id")
    batch_id = data.get("batch_id")
    if not isinstance(agent_id, str) or not ID_RE.fullmatch(agent_id) or not isinstance(batch_id, str) or not ID_RE.fullmatch(batch_id):
        raise ValueError("agent_id 和 batch_id 无效")
    generated_at = _time(data.get("generated_at"), "generated_at")
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= MAX_CANDIDATES:
        raise ValueError("candidates 需要 1–100 条")
    normalized = []
    seen = set()
    for index, item in enumerate(candidates):
        prefix = f"candidates[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{prefix} 必须是对象")
        title = _text(item.get("title"), f"{prefix}.title", 300)
        job_url = public_url(item.get("job_url"), f"{prefix}.job_url")
        if job_url in seen:
            raise ValueError("同批次职位 URL 重复")
        seen.add(job_url)
        apply_url = public_url(item["apply_url"], f"{prefix}.apply_url") if item.get("apply_url") not in (None, "") else None
        source = item.get("source")
        if not isinstance(source, dict):
            raise ValueError(f"{prefix}.source 缺失")
        source_name = _text(source.get("name"), f"{prefix}.source.name", 120)
        source_url = public_url(source.get("url"), f"{prefix}.source.url")
        source_observed_at = _time(source.get("observed_at"), f"{prefix}.source.observed_at")
        reason = _text(item.get("reason"), f"{prefix}.reason", 1200)
        references = item.get("evidence_refs")
        if not isinstance(references, list) or not 1 <= len(references) <= 8:
            raise ValueError(f"{prefix}.evidence_refs 需要 1–8 条")
        evidence_refs = []
        for ref in references:
            if not isinstance(ref, dict):
                raise ValueError(f"{prefix}.evidence_refs 项无效")
            evidence_refs.append({"url": public_url(ref.get("url"), "evidence_refs.url"), "locator": _text(ref.get("locator"), "evidence_refs.locator", 200)})
        unknowns = item.get("unknowns")
        if not isinstance(unknowns, list) or len(unknowns) > 10:
            raise ValueError(f"{prefix}.unknowns 必须是列表且不超过 10 条")
        unknowns = [_text(value, "unknowns", 200) for value in unknowns]
        optional = {}
        for key, limit in (("location", 300), ("department", 200), ("team", 200), ("description", 10000), ("employment_type", 100), ("published_at", 80)):
            value = item.get(key)
            optional[key] = "" if value is None else _text(value, f"{prefix}.{key}", limit, required=False)
        normalized.append({"id": hashlib.sha256(job_url.encode("utf-8")).hexdigest(), "title": title,
                           "job_url": job_url, "apply_url": apply_url,
                           "origin_name": source_name, "origin_url": source_url,
                           "origin_observed_at": source_observed_at, "reason": reason,
                           "evidence_refs": evidence_refs, "unknowns": unknowns,
                           "secondary_locations": [], "raw_fields": {}, **optional})
    return {"schema_version": 1, "agent_id": agent_id, "batch_id": batch_id,
            "generated_at": generated_at, "candidates": normalized}


def read_batch_file(store, file_path):
    supplied = Path(file_path)
    if supplied.suffix.lower() != ".json" or supplied.is_symlink():
        raise ValueError("只能导入当前 workspace 内的普通 JSON 文件")
    try:
        path = supplied.resolve(strict=True)
    except OSError as exc:
        raise ValueError("JSON 文件不存在") from exc
    if not path.is_relative_to(store.workspace) or path.suffix.lower() != ".json":
        raise ValueError("JSON 文件必须在当前 workspace 内")
    relative = path.relative_to(store.workspace)
    handles = []
    try:
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        handles.append(os.open(store.workspace, directory_flags))
        for part in relative.parts[:-1]:
            handles.append(os.open(part, directory_flags, dir_fd=handles[-1]))
        handles.append(os.open(relative.parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=handles[-1]))
        metadata = os.fstat(handles[-1])
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_FILE:
            raise ValueError("JSON 文件必须是普通文件且不超过 1 MiB")
        raw = os.read(handles[-1], MAX_FILE + 1)
        if len(raw) > MAX_FILE:
            raise ValueError("JSON 文件超过 1 MiB")
    except OSError as exc:
        raise ValueError("无法安全读取当前 workspace 内的 JSON 文件") from exc
    finally:
        for handle in reversed(handles):
            os.close(handle)
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json_pairs, parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("JSON 内容无效") from exc
    return parse_batch(data)


def import_file(store, file_path, at=None):
    batch = read_batch_file(store, file_path)
    digest = hashlib.sha256(json.dumps(batch, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    at = _time(at or utc_now(), "imported_at")
    with store._connect() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute("SELECT digest,candidate_count FROM discovery_agent_batches WHERE agent_id=? AND batch_id=?", (batch["agent_id"], batch["batch_id"])).fetchone()
        if previous:
            if previous["digest"] != digest:
                raise ValueError("同一 agent/batch_id 的内容已不同，拒绝覆盖")
            return {"status": "already_imported", "total": previous["candidate_count"], "new": 0}
        db.execute("INSERT INTO discovery_agent_batches(agent_id,batch_id,digest,generated_at,imported_at,candidate_count) VALUES(?,?,?,?,?,?)", (batch["agent_id"], batch["batch_id"], digest, batch["generated_at"], at, len(batch["candidates"])))
        db.execute("INSERT INTO discovery_sources(source,board,source_url,last_attempt_at,last_success_at,last_error,failures,next_allowed_at) VALUES(?,?,?,?,?,?,0,NULL) ON CONFLICT(source,board) DO UPDATE SET last_attempt_at=excluded.last_attempt_at,last_success_at=excluded.last_success_at", (AGENT_SOURCE, AGENT_BOARD, "", at, at, None))
        new_count = 0
        for job in batch["candidates"]:
            existing = db.execute("SELECT 1 FROM discovery_jobs WHERE source=? AND board=? AND source_job_id=?", (AGENT_SOURCE, AGENT_BOARD, job["id"])).fetchone()
            db.execute("INSERT INTO discovery_jobs(source,board,source_job_id,payload,first_seen_at,last_seen_at,present_latest) VALUES(?,?,?,?,?,?,1) ON CONFLICT(source,board,source_job_id) DO UPDATE SET payload=excluded.payload,last_seen_at=excluded.last_seen_at,present_latest=1", (AGENT_SOURCE, AGENT_BOARD, job["id"], json.dumps(job, ensure_ascii=False), at, at))
            report = {"agent_id": batch["agent_id"], "batch_id": batch["batch_id"], "generated_at": batch["generated_at"], "reason": job["reason"], "evidence_refs": job["evidence_refs"], "unknowns": job["unknowns"], "origin_name": job["origin_name"], "origin_url": job["origin_url"], "origin_observed_at": job["origin_observed_at"]}
            db.execute("INSERT INTO discovery_agent_reports(agent_id,batch_id,source_job_id,payload,imported_at) VALUES(?,?,?,?,?)", (batch["agent_id"], batch["batch_id"], job["id"], json.dumps(report, ensure_ascii=False), at))
            new_count += not bool(existing)
    return {"status": "imported", "total": len(batch["candidates"]), "new": int(new_count)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="当前用户的 private workspace")
    parser.add_argument("--file", required=True, help="同一 workspace 内的 agent JSON 输出")
    args = parser.parse_args()
    workspace = (ROOT / args.workspace).resolve()
    private_root = (ROOT / "private").resolve()
    if workspace == private_root or not workspace.is_relative_to(private_root):
        parser.error("workspace 必须是仓库 private/ 下当前用户的目录")
    try:
        print(json.dumps(import_file(JobStore(workspace), args.file), ensure_ascii=False))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"未导入：{exc}\n")


if __name__ == "__main__":
    main()
