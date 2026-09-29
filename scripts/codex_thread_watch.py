#!/usr/bin/env python3
"""Experimental, read-only adapter for explicitly registered local Codex rollouts.

No model, network, transcript persistence, or chat/task mutations. Rollout JSONL
is an observed local format, not a stable public Codex interface.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
from datetime import datetime, timezone

MAX_LINE = 16_000_000  # Compaction records can carry a large replacement history.
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(value):
    return isinstance(value, str) and bool(IDENTIFIER.fullmatch(value))


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.isoformat() if parsed.tzinfo else None
    except ValueError:
        return None


def blank():
    return {"turn_state": "unknown", "turn_id": None, "completed_turn_id": None,
            "input_tokens": None, "context_window": None, "sample_at": None,
            "compactions": 0, "compacted_at": None, "event_at": None}


def apply_event(signal, event):
    if not isinstance(event, dict):
        return
    stamp = timestamp(event.get("timestamp"))
    payload = event.get("payload")
    if event.get("type") == "compacted":
        signal.update(input_tokens=None, context_window=None, sample_at=None,
                      compactions=signal["compactions"] + 1, compacted_at=stamp,
                      event_at=stamp)
        return
    if event.get("type") != "event_msg" or not isinstance(payload, dict):
        return
    kind = payload.get("type")
    turn_id = payload.get("turn_id")
    if kind == "task_started" and identifier(turn_id):
        signal.update(turn_state="active", turn_id=turn_id, event_at=stamp)
    elif kind in {"task_complete", "turn_aborted"} and identifier(turn_id):
        # This event ends a MODEL TURN. It never completes a person's task.
        if signal["turn_id"] in {None, turn_id}:
            signal.update(turn_state="idle" if kind == "task_complete" else "interrupted",
                          turn_id=turn_id, event_at=stamp)
        if kind == "task_complete" and signal["turn_id"] == turn_id:
            signal["completed_turn_id"] = turn_id
    elif kind == "token_count":
        info = payload.get("info")
        info = info if isinstance(info, dict) else {}
        usage = info.get("last_token_usage")
        usage = usage if isinstance(usage, dict) else {}
        tokens, window = usage.get("input_tokens"), info.get("model_context_window")
        valid = type(tokens) is int and tokens >= 0 and type(window) is int and window > 0 and stamp is not None
        signal.update(input_tokens=tokens if valid else None,
                      context_window=window if valid else None,
                      sample_at=stamp if valid else None, event_at=stamp)


def read_source(task, previous):
    path = Path(task["rollout_path"])
    signal = blank()
    cursor = 0
    identity = None
    anchor = None
    try:
        with path.open("rb") as stream:
            stat = os.fstat(stream.fileno())
            header = stream.readline(MAX_LINE + 1)
            if not header.endswith(b"\n") or len(header) > MAX_LINE:
                raise ValueError("invalid_header")
            first = json.loads(header)
            if not isinstance(first, dict) or first.get("type") != "session_meta":
                raise ValueError("invalid_header")
            payload = first.get("payload")
            if not isinstance(payload, dict) or payload.get("id") != task["thread_id"]:
                raise ValueError("identity_mismatch")
            identity = [stat.st_dev, stat.st_ino, hashlib.sha256(header).hexdigest()]
            old_offset = previous.get("offset", 0)
            stream.seek(max(0, old_offset - 256))
            old_anchor = hashlib.sha256(stream.read(min(256, old_offset))).hexdigest()
            if (previous.get("identity") == identity and stat.st_size >= old_offset
                    and previous.get("anchor") == old_anchor):
                signal = dict(previous["signal"])
                cursor = previous["offset"]
            else:
                cursor = len(header)
            stream.seek(cursor)
            while True:
                line = stream.readline(MAX_LINE + 1)
                if not line:
                    break
                if len(line) > MAX_LINE:
                    raise ValueError("oversized_record")
                if not line.endswith(b"\n"):
                    break  # A writer may still be appending: retry from the same offset.
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("invalid_record")
                apply_event(signal, event)
                cursor = stream.tell()
            stream.seek(max(0, cursor - 256))
            anchor = hashlib.sha256(stream.read(min(256, cursor))).hexdigest()
        health = "ok"
    except (OSError, ValueError, KeyError, TypeError):
        # Do not retain a healthy-looking old metric when the measuring source fails.
        health, signal, cursor, identity, anchor = "source_unavailable_or_invalid", blank(), 0, None, None
    return {"identity": identity, "offset": cursor, "anchor": anchor, "signal": signal, "health": health}


def public_row(task, source, threshold):
    signal = source["signal"]
    ratio = None
    if signal["input_tokens"] is not None and signal["context_window"]:
        ratio = signal["input_tokens"] / signal["context_window"]
    advisory = "none"
    if source["health"] != "ok":
        advisory = "check_source"
    elif ratio is not None and ratio >= threshold:
        advisory = "checkpoint_after_turn" if signal["turn_state"] == "active" else "review_handoff"
    return {"task_id": task["task_id"], "thread_id": task["thread_id"],
            **signal, "source_health": source["health"],
            "last_input_ratio": round(ratio, 4) if ratio is not None else None,
            "advisory": advisory, "task_completion": "not_inferred"}


def atomic_json(path, value):
    temp = path.with_name(path.name + ".new")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def scan(config_path, workspace):
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    tasks, threshold = config["tasks"], config.get("input_ratio_threshold", 0.8)
    if not isinstance(tasks, list) or not 0 < threshold <= 1:
        raise ValueError("invalid configuration")
    seen = set()
    for task in tasks:
        if not identifier(task.get("task_id")) or not identifier(task.get("thread_id")):
            raise ValueError("invalid identifier")
        if task["task_id"] in seen or not Path(task["rollout_path"]).is_absolute():
            raise ValueError("duplicate task or non-absolute source")
        seen.add(task["task_id"])
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    lock = workspace / "scan.lock"
    # Never race another scanner into overwriting newer cursors.
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(fd, str(os.getpid()).encode())
        state_path, report_path = workspace / "state.json", workspace / "report.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        old_report = json.loads(report_path.read_text()) if report_path.exists() else {}
        sources, rows = {}, []
        for task in tasks:
            key = hashlib.sha256((task["thread_id"] + task["rollout_path"]).encode()).hexdigest()
            source = read_source(task, state.get("sources", {}).get(key, {}))
            sources[key] = source
            rows.append(public_row(task, source, threshold))
        changed = rows != old_report.get("items") or threshold != old_report.get("input_ratio_threshold")
        report = {"schema_version": 1, "revision": old_report.get("revision", 0) + int(changed),
                  "as_of": now(), "input_ratio_threshold": threshold, "mode": "observe_only",
                  "metric": "last_request_input_not_exact_live_context", "items": rows}
        # State first; both are reconstructable. No transcript fields are persisted.
        atomic_json(state_path, {"schema_version": 1, "sources": sources})
        atomic_json(report_path, report)
        return report, changed
    finally:
        os.close(fd)
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=15)
    args = parser.parse_args()
    if args.interval < 1:
        parser.error("interval must be at least one second")
    while True:
        try:
            report, changed = scan(args.config, args.workspace)
            if not args.watch:
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return
            if changed:
                print(json.dumps({"revision": report["revision"], "as_of": report["as_of"],
                                  "task_count": len(report["items"])}), flush=True)
        except FileExistsError:
            if not args.watch:
                parser.exit(2, "scanner already locked; check the local owner's PID\n")
        except (OSError, ValueError, KeyError, TypeError):
            parser.exit(2, "invalid configuration/state; inspect private files locally\n")
        if not args.watch:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
