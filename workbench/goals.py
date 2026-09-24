"""Draft generic goal and immutable plan history for Issue #21.

This store records planning decisions and self-reported results. It never runs a
daily task, verifies an external fact, or changes the recruiting state machine.
"""

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
OUTCOMES = {"completed", "partial", "missed", "blocked", "observed"}
TRIGGERS = {"weekly", "missed_day", "lower_result", "external_event", "goal_change"}
CONFIDENCE = {"unknown", "self_set", "estimated", "verified"}
KINDS = {"custom", "verify_job", "prepare_materials", "approve_materials",
         "apply_job", "practice", "attend_event", "prepare_interview", "follow_up"}
JOB_KINDS = {"verify_job", "prepare_materials", "approve_materials", "apply_job"}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value, name):
    _need(isinstance(value, str) and bool(value.strip()), f"{name} 必须是非空文本")


def _id(value, name):
    _need(isinstance(value, str) and ID.fullmatch(value), f"{name} 无效")


def _stamp(value, name):
    _text(value, name)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} 时间格式无效") from exc
    _need(parsed.tzinfo is not None and parsed.utcoffset() is not None,
          f"{name} 必须带时区")
    return parsed


def _deadline(item, prefix):
    confidence = item.get(f"{prefix}_confidence")
    value = item.get(f"{prefix}_at")
    source = item.get(f"{prefix}_source_ref")
    checked = item.get(f"{prefix}_checked_at")
    _need(confidence in CONFIDENCE, f"{prefix}_confidence 无效")
    _need(source is None or isinstance(source, str), f"{prefix}_source_ref 必须是文字或 null")
    if confidence == "unknown":
        _need(value is None and checked is None, f"未知的 {prefix} 不能有精确时间或核验时间")
    else:
        _stamp(value, f"{prefix}_at")
    if confidence == "verified":
        _text(source, f"{prefix}_source_ref")
        _stamp(checked, f"{prefix}_checked_at")
    else:
        _need(checked is None, f"未核验的 {prefix} 不应填写核验时间")


def _goal(value):
    _need(isinstance(value, dict), "goal 必须是对象")
    _need(set(value) == {"id", "title", "domain", "timezone", "weekly_minutes",
                         "success_criterion", "baseline", "target_at",
                         "target_confidence", "target_source_ref", "target_checked_at"},
          "goal 字段不符合契约")
    _id(value["id"], "goal.id")
    for key in ("title", "domain", "success_criterion"):
        _text(value[key], f"goal.{key}")
    _need(type(value["weekly_minutes"]) is int and value["weekly_minutes"] >= 0,
          "weekly_minutes 必须是非负整数")
    _need(isinstance(value["baseline"], str), "baseline 必须是文字，可为空")
    try:
        ZoneInfo(value["timezone"])
    except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
        raise ValueError("goal.timezone 必须是 IANA 时区") from exc
    _deadline(value, "target")


def _items(items, goal_id):
    _need(isinstance(items, list) and bool(items), "计划必须包含至少一项任务")
    seen = set()
    for item in items:
        _need(isinstance(item, dict), "计划任务必须是对象")
        _need(set(item) == {"task_id", "title", "reason", "source_ref",
                             "task_kind", "source_kind", "source_id",
                             "scheduled_at", "estimated_minutes", "completion_rule",
                             "due_at", "due_confidence", "due_source_ref", "due_checked_at",
                             "flexible"},
              "计划任务字段不符合契约")
        _id(item["task_id"], "task_id")
        _need(item["task_id"] not in seen, "同一计划版本中 task_id 不能重复")
        seen.add(item["task_id"])
        for key in ("title", "reason", "source_ref", "completion_rule"):
            _text(item[key], key)
        _need(item["task_kind"] in KINDS, "task_kind 无效")
        _need(item["source_kind"] in {"goal", "job", "event", "learning"}, "source_kind 无效")
        _id(item["source_id"], "source_id")
        if item["source_kind"] == "goal":
            _need(item["source_id"] == goal_id and item["task_kind"] in {"custom", "practice"},
                  "通用目标任务应关联当前 goal，使用 custom 或 practice 类型")
        if item["source_kind"] == "learning":
            _need(item["task_kind"] in {"custom", "practice"},
                  "学习来源只支持 custom 或 practice 类型")
        if item["task_kind"] in JOB_KINDS:
            _need(item["source_kind"] == "job", "该任务需要岗位来源")
        _stamp(item["scheduled_at"], "scheduled_at")
        _need(type(item["estimated_minutes"]) is int and item["estimated_minutes"] >= 0,
              "estimated_minutes 必须是非负整数")
        _need(type(item["flexible"]) is bool, "flexible 必须是布尔值")
        _deadline(item, "due")


def _safe_auto_change(goal, old_items, new_items, task_state):
    """Only reorder or move an unstarted flexible task within its local day."""
    if not old_items or {item["task_id"] for item in old_items} != {item["task_id"] for item in new_items}:
        return False
    old_by_id = {item["task_id"]: item for item in old_items}
    old_position = {item["task_id"]: index for index, item in enumerate(old_items)}
    viewing_zone = ZoneInfo(goal["timezone"])
    any_change = False
    for position, changed in enumerate(new_items):
        prior = old_by_id[changed["task_id"]]
        if {key: value for key, value in changed.items() if key != "scheduled_at"} != {
                key: value for key, value in prior.items() if key != "scheduled_at"}:
            return False
        if changed["scheduled_at"] != prior["scheduled_at"]:
            any_change = True
            if (not prior["flexible"] or prior["due_at"] is not None
                    or not callable(task_state) or task_state(prior["task_id"]) != "scheduled"):
                return False
            before = _stamp(prior["scheduled_at"], "scheduled_at").astimezone(viewing_zone)
            after = _stamp(changed["scheduled_at"], "scheduled_at").astimezone(viewing_zone)
            if before.date() != after.date():
                return False
        if position != old_position[changed["task_id"]]:
            any_change = True
            if (not prior["flexible"] or prior["due_at"] is not None
                    or not callable(task_state) or task_state(prior["task_id"]) != "scheduled"):
                return False
    return any_change


class GoalStore:
    """Append-only local planning log. Auto decisions require an explicit policy hook."""

    def __init__(self, workspace, clock=None, auto_policy=None, task_state=None):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.auto_policy = auto_policy
        self.task_state = task_state
        self.db = sqlite3.connect(self.workspace / "goals.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS goal_events (
            seq INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
            at TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL)""")
        self.db.commit()

    def close(self):
        self.db.close()

    def _now(self):
        now = self.clock()
        _need(isinstance(now, datetime) and now.tzinfo is not None
              and now.utcoffset() is not None, "时钟必须返回带时区的时间")
        return now

    def _state(self):
        state = {"goals": {}, "goal_revisions": {}, "plans": {},
                 "proposals": {}, "results": {}, "reviews": {}}
        for row in self.db.execute("SELECT at,kind,payload FROM goal_events ORDER BY seq"):
            payload = json.loads(row["payload"])
            kind = row["kind"]
            if kind == "create_goal":
                goal = {**payload["goal"], "active_version": 0, "revision": 1,
                        "created_at": row["at"], "updated_at": row["at"]}
                state["goals"][goal["id"]] = goal
                state["goal_revisions"][goal["id"]] = [
                    {"revision": 1, "at": row["at"], "actor": "user",
                     "reason": "创建目标", "goal": payload["goal"]}]
                state["plans"][goal["id"]] = []
            elif kind == "update_goal":
                new_goal = payload["goal"]
                old_goal = state["goals"][new_goal["id"]]
                revision = old_goal["revision"] + 1
                state["goals"][new_goal["id"]] = {
                    **new_goal, "active_version": old_goal["active_version"],
                    "revision": revision, "created_at": old_goal["created_at"],
                    "updated_at": row["at"]}
                state["goal_revisions"][new_goal["id"]].append(
                    {"revision": revision, "at": row["at"], "actor": payload["actor"],
                     "reason": payload["reason"], "goal": new_goal})
            elif kind == "propose_plan":
                proposal = {**payload["proposal"], "status": "pending", "proposed_at": row["at"],
                            "decision_at": None, "decision": None, "decision_reason": None,
                            "policy_ref": None, "version": None}
                state["proposals"][proposal["id"]] = proposal
            elif kind == "decide_plan":
                proposal = state["proposals"][payload["proposal_id"]]
                proposal.update(status="declined" if payload["decision"] == "decline" else "accepted",
                                decision_at=row["at"], decision=payload["decision"],
                                decision_reason=payload["reason"],
                                policy_ref=payload.get("policy_ref"))
                if payload["decision"] != "decline":
                    goal_id = proposal["goal_id"]
                    version = state["goals"][goal_id]["active_version"] + 1
                    state["goals"][goal_id]["active_version"] = version
                    proposal["version"] = version
                    state["plans"][goal_id].append({"version": version, "from_proposal": proposal["id"],
                                                    "at": row["at"], "decision": payload["decision"],
                                                    "actor": payload["actor"],
                                                    "reason": payload["reason"],
                                                    "policy_ref": payload.get("policy_ref"),
                                                    "items": payload.get("edited_items") or proposal["items"],
                                                    "goal_revision": proposal["goal_revision"],
                                                    "undid_version": None})
            elif kind == "undo_auto":
                goal_id = payload["goal_id"]
                current = state["plans"][goal_id][-1]
                target_index = next(index for index, plan in enumerate(state["plans"][goal_id])
                                    if plan["version"] == payload["version"])
                previous = state["plans"][goal_id][target_index - 1]
                version = current["version"] + 1
                state["goals"][goal_id]["active_version"] = version
                state["plans"][goal_id].append({"version": version, "from_proposal": None,
                                                "at": row["at"], "decision": "undo_auto",
                                                "actor": payload["actor"],
                                                "reason": payload["reason"], "policy_ref": None,
                                                "items": previous["items"],
                                                "goal_revision": previous["goal_revision"],
                                                "undid_version": payload["version"]})
            elif kind == "record_result":
                result = {**payload["result"], "recorded_at": row["at"]}
                state["results"][result["id"]] = result
            elif kind == "record_review":
                review = {**payload["review"], "recorded_at": row["at"]}
                state["reviews"][review["id"]] = review
        for proposal in state["proposals"].values():
            if (proposal["status"] == "pending"
                    and (proposal["base_version"] < state["goals"][proposal["goal_id"]]["active_version"]
                         or proposal["goal_revision"] < state["goals"][proposal["goal_id"]]["revision"])):
                proposal["status"] = "superseded"
        for goal_id, goal in state["goals"].items():
            goal["needs_replan"] = bool(state["plans"][goal_id]
                                         and state["plans"][goal_id][-1]["goal_revision"] != goal["revision"])
        return state

    def snapshot(self, goal_id=None):
        state = self._state()
        if goal_id is None:
            return state
        _need(goal_id in state["goals"], "目标不存在")
        return {"goal": state["goals"][goal_id],
                "goal_revisions": state["goal_revisions"][goal_id],
                "plans": state["plans"][goal_id],
                "proposals": [p for p in state["proposals"].values() if p["goal_id"] == goal_id],
                "results": [r for r in state["results"].values() if r["goal_id"] == goal_id],
                "reviews": [r for r in state["reviews"].values() if r["goal_id"] == goal_id]}

    def command(self, kind, event_id, payload, at=None):
        """Validate and append one command; exact event-ID retries are idempotent."""
        _need(kind in {"create_goal", "update_goal", "propose_plan", "decide_plan", "undo_auto",
                       "record_result", "record_review"}, "命令无效")
        _id(event_id, "event_id")
        _need(isinstance(payload, dict), "payload 必须是对象")
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            previous = self.db.execute("SELECT * FROM goal_events WHERE event_id=?", (event_id,)).fetchone()
            if previous is not None:
                _need(previous["kind"] == kind and previous["payload"] == encoded
                      and (at is None or previous["at"] == at), "event_id 已用于不同命令")
                self.db.commit()
                return self._state()
            now = self._now()
            occurred = _stamp(at, "at") if at is not None else now
            _need(occurred <= now + timedelta(minutes=5), "事件时间不能来自未来")
            last = self.db.execute("SELECT at FROM goal_events ORDER BY seq DESC LIMIT 1").fetchone()
            if last:
                _need(occurred >= _stamp(last["at"], "last_at"), "事件时间不能早于上个事件")
            state = self._state()
            self._validate(kind, payload, state)
            self.db.execute("INSERT INTO goal_events(event_id,at,kind,payload) VALUES(?,?,?,?)",
                            (event_id, occurred.isoformat(), kind, encoded))
            result = self._state()
            self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            raise

    def _validate(self, kind, payload, state):
        if kind == "create_goal":
            _need(set(payload) == {"goal"}, "create_goal 需要 goal")
            _goal(payload["goal"])
            _need(payload["goal"]["id"] not in state["goals"], "目标 ID 已存在")
        elif kind == "update_goal":
            _need(set(payload) == {"goal", "actor", "reason"}, "update_goal 字段不符合契约")
            _need(payload["actor"] == "user", "目标修改需要用户操作")
            _text(payload["reason"], "update_goal.reason")
            _goal(payload["goal"])
            old = state["goals"].get(payload["goal"]["id"])
            _need(old is not None, "目标不存在")
            _need(any(payload["goal"][key] != old[key] for key in payload["goal"]),
                  "目标内容没有变化")
        elif kind == "propose_plan":
            _need(set(payload) == {"proposal"}, "propose_plan 需要 proposal")
            proposal = payload["proposal"]
            _need(isinstance(proposal, dict) and set(proposal) ==
                  {"id", "goal_id", "goal_revision", "base_version", "review_id", "reason",
                   "items", "method", "source_ref"},
                  "proposal 字段不符合契约")
            _id(proposal["id"], "proposal.id")
            _id(proposal["goal_id"], "goal_id")
            _need(proposal["id"] not in state["proposals"], "计划提案 ID 已存在")
            goal = state["goals"].get(proposal["goal_id"])
            _need(goal is not None, "目标不存在")
            _need(type(proposal["base_version"]) is int
                  and proposal["base_version"] == goal["active_version"], "提案基于过期计划")
            _need(type(proposal["goal_revision"]) is int
                  and proposal["goal_revision"] == goal["revision"], "提案基于过期目标")
            if proposal["base_version"] == 0:
                _need(proposal["review_id"] is None, "初始计划不需要复盘")
            else:
                review = state["reviews"].get(proposal["review_id"])
                _need(review is not None and review["goal_id"] == proposal["goal_id"],
                      "修订计划需要同目标复盘")
            _text(proposal["reason"], "proposal.reason")
            _need(proposal["method"] in {"rule_template", "ai_suggestion", "manual"},
                  "proposal.method 无效")
            if proposal["base_version"] == 0:
                _need(proposal["method"] != "ai_suggestion",
                      "初始计划从有来源的规则模板或手动任务起步")
            if proposal["method"] in {"rule_template", "ai_suggestion"}:
                _text(proposal["source_ref"], "proposal.source_ref")
            _need(proposal["source_ref"] is None or isinstance(proposal["source_ref"], str),
                  "source_ref 必须是文字或 null")
            _items(proposal["items"], proposal["goal_id"])
        elif kind == "decide_plan":
            allowed = {"proposal_id", "decision", "actor", "reason", "edited_items", "policy_ref"}
            _need(set(payload) == allowed, "decide_plan 字段不符合契约")
            proposal = state["proposals"].get(payload["proposal_id"])
            _need(proposal is not None and proposal["status"] == "pending", "提案不存在或已决策")
            goal = state["goals"][proposal["goal_id"]]
            _need(proposal["base_version"] == goal["active_version"], "不能接受基于旧版的提案")
            _need(proposal["goal_revision"] == goal["revision"], "不能接受基于旧目标的提案")
            decision = payload["decision"]
            _need(decision in {"accept", "edit", "decline", "auto_apply"}, "计划决策无效")
            _text(payload["reason"], "decision.reason")
            if decision == "auto_apply":
                _need(payload["actor"] == "system", "自动调整必须由系统策略执行")
                _text(payload["policy_ref"], "policy_ref")
                _need(payload["edited_items"] is None, "自动决策不能暗中编辑提案")
                current = state["plans"][proposal["goal_id"]][-1]["items"] if goal["active_version"] else []
                _need(_safe_auto_change(goal, current, proposal["items"], self.task_state)
                      and callable(self.auto_policy)
                      and self.auto_policy(goal, current, proposal["items"], payload["policy_ref"]),
                      "没有授权的自动调整策略")
            else:
                _need(payload["actor"] == "user" and payload["policy_ref"] is None,
                      "实质计划决策需要用户；不得附自动策略")
                if decision == "edit":
                    _items(payload["edited_items"], proposal["goal_id"])
                else:
                    _need(payload["edited_items"] is None, "此决策不应包含 edited_items")
        elif kind == "undo_auto":
            _need(set(payload) == {"goal_id", "version", "actor", "reason"},
                  "undo_auto 字段不符合契约")
            _need(payload["actor"] == "user", "撤销自动调整需要用户操作")
            _text(payload["reason"], "undo_auto.reason")
            plans = state["plans"].get(payload["goal_id"], [])
            target = next((index for index, plan in enumerate(plans)
                           if plan["version"] == payload["version"]), None)
            _need(target is not None and target > 0 and plans[target]["decision"] == "auto_apply",
                  "只能撤销自动调整版本")
            _need(plans[target]["goal_revision"] == state["goals"][payload["goal_id"]]["revision"],
                  "目标已修改，需要新提案确认")
            later = plans[target + 1:]
            _need(all(plan["decision"] == "auto_apply" for plan in later),
                  "之后已有本人决策或撤销，需要新提案确认")
            _need(_safe_auto_change(state["goals"][payload["goal_id"]],
                                    plans[-1]["items"], plans[target - 1]["items"],
                                    self.task_state),
                  "受影响任务已开始或无法安全撤销，请由本人确认新提案")
        elif kind == "record_result":
            _need(set(payload) == {"result"}, "record_result 需要 result")
            result = payload["result"]
            _need(isinstance(result, dict) and set(result) ==
                  {"id", "goal_id", "plan_version", "task_id", "outcome", "basis",
                   "actual_minutes", "metric", "evidence_ref", "note"},
                  "result 字段不符合契约")
            _id(result["id"], "result.id")
            _need(result["id"] not in state["results"], "结果 ID 已存在")
            _id(result["goal_id"], "goal_id")
            _id(result["task_id"], "task_id")
            plans = state["plans"].get(result["goal_id"], [])
            _need(type(result["plan_version"]) is int and result["plan_version"] > 0,
                  "plan_version 必须是正整数")
            plan = next((p for p in plans if p["version"] == result["plan_version"]), None)
            _need(plan is not None and any(i["task_id"] == result["task_id"] for i in plan["items"]),
                  "结果必须关联已生效计划中的任务")
            _need(result["basis"] in {"self_report", "tool_observation"}, "basis 无效")
            _need(result["outcome"] in OUTCOMES, "outcome 无效")
            if result["basis"] == "tool_observation":
                _need(result["outcome"] == "observed" and result["metric"] is None,
                      "工具活动只能是线索，不能证明完成或能力")
            else:
                _need(result["outcome"] != "observed", "用户结果应记录具体状态")
            _need(type(result["actual_minutes"]) is int and result["actual_minutes"] >= 0,
                  "actual_minutes 必须是非负整数")
            _need(result["metric"] is None or isinstance(result["metric"], dict),
                  "metric 必须是对象或 null")
            _need(result["evidence_ref"] is None or isinstance(result["evidence_ref"], str),
                  "evidence_ref 必须是文字或 null")
            _need(isinstance(result["note"], str), "note 必须是文字")
        else:  # record_review
            _need(set(payload) == {"review"}, "record_review 需要 review")
            review = payload["review"]
            _need(isinstance(review, dict) and set(review) ==
                  {"id", "goal_id", "plan_version", "trigger", "result_ids", "finding", "source_ref"},
                  "review 字段不符合契约")
            _id(review["id"], "review.id")
            _need(review["id"] not in state["reviews"], "复盘 ID 已存在")
            _need(review["goal_id"] in state["goals"], "目标不存在")
            _need(type(review["plan_version"]) is int
                  and review["plan_version"] == state["goals"][review["goal_id"]]["active_version"]
                  and review["plan_version"] > 0, "复盘需要当前生效计划")
            _need(review["trigger"] in TRIGGERS, "trigger 无效")
            _need(isinstance(review["result_ids"], list), "result_ids 必须是列表")
            for result_id in review["result_ids"]:
                result = state["results"].get(result_id)
                _need(result is not None and result["goal_id"] == review["goal_id"],
                      "复盘结果必须属于当前目标")
            if review["trigger"] == "external_event":
                _text(review["source_ref"], "review.source_ref")
            elif review["trigger"] != "goal_change":
                _need(bool(review["result_ids"]), "此类复盘需要实际结果或观察记录")
            _text(review["finding"], "review.finding")
