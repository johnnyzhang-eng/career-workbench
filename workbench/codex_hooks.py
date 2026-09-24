"""Lossy, consent-gated Codex Hook adapter. Hook content never reaches storage."""

import hashlib
from datetime import datetime, timezone

from workbench.activity import ActivityInbox, IDENTIFIER


SOURCE = "codex.hooks"
KINDS = {
    "UserPromptSubmit": "turn_prompted",
    "Stop": "turn_stop_observed",
    "Interrupt": "turn_interrupted",
    "PostToolUse": "tool_used",
}


def _token(value, name):
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError(f"缺少或无效的 {name}")
    return value


def _digest(*parts):
    payload = "\0".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def observation_from_hook(payload, now=None):
    """Take only documented identity fields; ignore every content-bearing field."""
    if not isinstance(payload, dict):
        raise ValueError("Hook 输入必须是对象")
    event = payload.get("hook_event_name")
    if event not in KINDS:
        raise ValueError("不支持的 Hook 事件")
    session = _token(payload.get("session_id"), "session_id")
    turn = _token(payload.get("turn_id"), "turn_id")
    event_parts = [session, turn, event]
    tool_name = None
    if event == "PostToolUse":
        tool_use = _token(payload.get("tool_use_id"), "tool_use_id")
        tool_name = _token(payload.get("tool_name"), "tool_name")
        if not IDENTIFIER.fullmatch(tool_name):
            raise ValueError("工具名不符合最小元数据规则")
        event_parts.append(tool_use)
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("时间必须带时区")
    return {
        "event_id": _digest(*event_parts),
        "source": SOURCE,
        "kind": KINDS[event],
        "occurred_at": timestamp.astimezone(timezone.utc).isoformat(),
        "session_ref": _digest("session", session),
        "turn_ref": _digest("turn", session, turn),
        **({"tool_name": tool_name} if tool_name else {}),
    }


def ingest_codex_hook(workspace, connection_id, payload, clock=None):
    """An installed hook may submit only after the Workbench enabled its connection."""
    event = observation_from_hook(payload, clock() if clock else None)
    inbox = ActivityInbox(workspace, clock=clock)
    try:
        prior = inbox.get_observation(connection_id, event["event_id"])
        if prior is not None:
            stable = ("source", "kind", "session_ref", "turn_ref", "tool_name")
            if any(prior[key] != event.get(key) for key in stable):
                raise ValueError("重复 Hook ID 的内容冲突")
            event["occurred_at"] = prior["occurred_at"]
        return inbox.ingest(connection_id, event)
    finally:
        inbox.close()
