"""Translate local goal activity into a truthful room scene read model.

The room is a visualization of *reported* activity. A scheduled task only
provides a preview; it never makes the avatar act as if work has begun, and
no scene state marks a task complete. Connected observations are optional and
must already have explicit permission and a task link when supplied.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


MODES = {"idle", "desk", "study", "interview", "rest"}
OBSERVATION_WINDOW = timedelta(minutes=10)


def _mode_for_task(task):
    kind = task.get("task_kind")
    if kind == "prepare_interview":
        return "interview"
    if kind == "practice":
        return "study"
    # A rest scene is a user's explicit choice, not a guess from a vague title.
    return "desk"


def _observed_at(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None or result.utcoffset() is None:
        return None
    return result


def scene_state(selected, now, *, observations=(), explicit_mode=None, action=None):
    """Return one JSON-compatible visual state for the chosen goal.

    ``selected`` uses GoalApp's selected read model. ``observations`` is an
    optional normalized, opt-in activity stream: each item needs
    ``authorized=True``, ``state='active'``, a matching ``task_id`` and a
    timezone-aware ``observed_at`` no older than ten minutes. An observation
    is a visual clue, never task completion evidence.
    """
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("场景时钟必须是带时区的时间")
    if explicit_mode is not None and explicit_mode not in MODES:
        raise ValueError("未知房间场景")
    goal = selected.get("goal") if selected else None
    zone = ZoneInfo(goal["timezone"]) if goal else now.astimezone().tzinfo
    local_now = now.astimezone(zone)
    phase = "day" if 6 <= local_now.hour < 18 else "evening"
    scene = {"mode": "idle", "phase": phase, "activity_state": "unknown",
             "source": "none", "task_id": None, "task_title": None,
             "suggested_mode": None, "as_of": now.isoformat(),
             "action": {"state": "none", "task_id": None, "at": None, "can_resume": False}}
    if explicit_mode is not None:
        scene.update(mode=explicit_mode, activity_state="self_selected", source="user_selected")
        return scene
    if not selected:
        return scene

    tasks = [task for task in selected.get("today_tasks", ())
             if task.get("sync_state") == "applied"
             and task.get("daily_state") not in {"completed", "cancelled", "not_scheduled"}]
    by_id = {task["task_id"]: task for task in tasks}
    if action and action.get("state") != "none":
        action = dict(action)
        stamp = _observed_at(action.get("at"))
        same_day = bool(stamp and stamp.astimezone(zone).date() == local_now.date())
        finished = next((task for task in selected.get("today_tasks", ())
                         if task.get("task_id") == action.get("task_id")
                         and task.get("daily_state") == "completed"), None)
        if finished is not None:
            # Completion is a DailyStore fact. A lingering action event should
            # not be called a cross-day session or keep the avatar working.
            result_recorded = any(result.get("task_id") == finished["task_id"]
                                  and result.get("outcome") == "completed"
                                  and result.get("basis") == "self_report"
                                  for result in selected.get("results", ()))
            action.update(state="result_recorded" if result_recorded else "completed",
                          can_resume=False)
            scene.update(activity_state="result_recorded" if result_recorded else "completion_recorded",
                         source="daily_task",
                         task_id=finished["task_id"], task_title=finished["title"])
            scene["action"] = action
            return scene
        if (action.get("state") == "active" and
                (not same_day or action.get("task_id") not in by_id)):
            action["state"] = "stale"
        if action.get("state") == "paused" and not same_day:
            action["state"] = "stale"
        if action.get("state") == "stopped" and not same_day:
            action["state"] = "none"
        action["can_resume"] = (action["state"] in {"paused", "stale"}
                                and action.get("task_id") in by_id)
        scene["action"] = action
        if action["state"] == "active":
            task = by_id[action["task_id"]]
            scene.update(mode=_mode_for_task(task), activity_state="declared_active",
                         source="scene_action", task_id=task["task_id"],
                         task_title=task["title"])
            return scene
        # A paused or stopped session overrides an old DailyStore in_progress
        # flag, so the avatar never appears to keep working after a pause.
        if action["state"] in {"paused", "stopped", "stale"}:
            planned = by_id.get(action["task_id"])
            if planned is not None and action["state"] != "stopped":
                scene.update(activity_state="planned", source="plan",
                             task_id=planned["task_id"], task_title=planned["title"],
                             suggested_mode=_mode_for_task(planned))
            return scene
    active = next((task for task in tasks if task.get("daily_state") == "in_progress"), None)
    if active is not None:
        scene.update(mode=_mode_for_task(active), activity_state="declared_active",
                     source="daily_task", task_id=active["task_id"],
                     task_title=active["title"])
        return scene

    latest = None
    for observation in observations:
        if not isinstance(observation, dict) or observation.get("authorized") is not True:
            continue
        if observation.get("state") != "active" or observation.get("task_id") not in by_id:
            continue
        observed = _observed_at(observation.get("observed_at"))
        if observed is None or not timedelta(0) <= now - observed <= OBSERVATION_WINDOW:
            continue
        if latest is None or observed > latest[0]:
            latest = (observed, by_id[observation["task_id"]])
    if latest is not None:
        task = latest[1]
        scene.update(mode=_mode_for_task(task), activity_state="observed",
                     source="activity_observation", task_id=task["task_id"],
                     task_title=task["title"])
        return scene

    planned = next((task for task in tasks if task.get("daily_state") in {"scheduled", "deferred"}), None)
    if planned is not None:
        scene.update(activity_state="planned", source="plan", task_id=planned["task_id"],
                     task_title=planned["title"], suggested_mode=_mode_for_task(planned))
    return scene
