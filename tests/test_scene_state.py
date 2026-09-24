"""Scene evidence boundaries with fictional task records only."""

import unittest
from datetime import datetime, timedelta, timezone

from workbench.scene_state import scene_state


NOW = datetime(2026, 10, 5, 2, 0, tzinfo=timezone.utc)  # 10:00 in Shanghai


def task(task_id="READ", *, kind="practice", state="scheduled", sync="applied"):
    return {"task_id": task_id, "title": "虚构英语阅读练习", "task_kind": kind,
            "daily_state": state, "sync_state": sync}


def selected(*tasks):
    return {"goal": {"timezone": "Asia/Shanghai"}, "today_tasks": list(tasks)}


class SceneStateTests(unittest.TestCase):
    def test_scheduled_action_only_previews_scene_and_never_claims_work(self):
        scene = scene_state(selected(task()), NOW)
        self.assertEqual((scene["mode"], scene["suggested_mode"]), ("idle", "study"))
        self.assertEqual((scene["activity_state"], scene["source"]), ("planned", "plan"))
        self.assertEqual(scene["task_id"], "READ")

    def test_explicitly_started_task_changes_room_but_not_completion(self):
        scene = scene_state(selected(task(kind="prepare_interview", state="in_progress")), NOW)
        self.assertEqual(scene["mode"], "interview")
        self.assertEqual(scene["activity_state"], "declared_active")
        self.assertNotIn("completed", scene.values())

    def test_untrusted_stale_or_unlinked_observations_do_not_activate_avatar(self):
        base = {"state": "active", "task_id": "READ", "observed_at": NOW.isoformat()}
        bad = [base, {**base, "authorized": True, "task_id": "OTHER"},
               {**base, "authorized": True,
                "observed_at": (NOW - timedelta(minutes=11)).isoformat()}]
        scene = scene_state(selected(task()), NOW, observations=bad)
        self.assertEqual(scene["mode"], "idle")
        self.assertEqual(scene["activity_state"], "planned")

    def test_recent_opt_in_observation_is_visual_clue_only(self):
        observation = {"authorized": True, "state": "active", "task_id": "READ",
                       "observed_at": (NOW - timedelta(minutes=2)).isoformat()}
        scene = scene_state(selected(task()), NOW, observations=[observation])
        self.assertEqual(scene["mode"], "study")
        self.assertEqual(scene["activity_state"], "observed")
        self.assertEqual(scene["source"], "activity_observation")

    def test_unsynced_or_completed_tasks_do_not_drive_room(self):
        scene = scene_state(selected(task(state="completed"), task("PENDING", sync="sync_pending")), NOW)
        self.assertEqual(scene["mode"], "idle")
        self.assertEqual(scene["activity_state"], "unknown")

    def test_completed_task_overrides_lingering_active_visual_event(self):
        scene = scene_state(selected(task(state="completed")), NOW,
                            action={"state": "active", "task_id": "READ", "at": NOW.isoformat()})
        self.assertEqual((scene["mode"], scene["action"]["state"]), ("idle", "completed"))
        self.assertEqual(scene["activity_state"], "completion_recorded")

    def test_confirmed_result_advances_room_caption_state_without_claiming_mastery(self):
        current = selected(task(state="completed"))
        current["results"] = [{"task_id": "READ", "outcome": "completed", "basis": "self_report"}]
        scene = scene_state(current, NOW,
                            action={"state": "stopped", "task_id": "READ", "at": NOW.isoformat()})
        self.assertEqual((scene["mode"], scene["action"]["state"]), ("idle", "result_recorded"))
        self.assertEqual(scene["activity_state"], "result_recorded")

    def test_local_clock_drives_phase_and_user_choice_can_show_rest(self):
        evening = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
        scene = scene_state(selected(), evening, explicit_mode="rest")
        self.assertEqual((scene["mode"], scene["phase"]), ("rest", "evening"))
        self.assertEqual(scene["activity_state"], "self_selected")
        with self.assertRaises(ValueError):
            scene_state(selected(), NOW, explicit_mode="gaming")


if __name__ == "__main__":
    unittest.main()
