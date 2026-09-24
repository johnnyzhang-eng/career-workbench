"""Fictional goal-to-room action lifecycle and restart boundary."""

import tempfile
import unittest
from datetime import datetime, timezone

from workbench.goal_app import GoalApp


class SceneActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = datetime(2026, 10, 5, 2, 0, tzinfo=timezone.utc)
        self.clock = lambda: self.now
        self.app = GoalApp(self.temp.name, self.clock)
        created = self.app.create_goal({
            "operation_id": "G" * 24, "path": "cet6", "title": "虚构英语目标",
            "weekly_minutes": 300, "baseline": "虚构起点",
            "success_criterion": "记录首次作答", "timezone": "Asia/Shanghai"})
        self.goal_id = created["selected_goal_id"]

    def tearDown(self):
        self.temp.cleanup()

    def action(self, name, operation, task_id=None):
        payload = {"operation_id": operation * 24, "goal_id": self.goal_id,
                   "task_id": task_id or self.task_id}
        return getattr(self.app, name + "_action")(payload)["scene"]

    def test_action_requires_an_accepted_and_synced_daily_task(self):
        with self.assertRaises(ValueError):
            self.app.start_action({"operation_id": "X" * 24, "goal_id": self.goal_id,
                                   "task_id": "UNKNOWN"})

    def test_start_pause_resume_stop_and_next_day_require_explicit_resume(self):
        proposal = self.app.propose_plan({"operation_id": "P" * 24,
                                          "goal_id": self.goal_id, "start_on": "2026-10-05"})
        pending = proposal["selected"]["pending_proposals"][0]
        self.app.decide_plan({"operation_id": "D" * 24,
                              "proposal_id": pending["id"], "decision": "accept"})
        self.app.sync_plan({"operation_id": "S" * 24, "goal_id": self.goal_id})
        self.task_id = self.app.state(self.goal_id)["selected"]["today_tasks"][0]["task_id"]
        self.assertEqual(self.app.state(self.goal_id)["scene"]["mode"], "idle")
        started = self.action("start", "A")
        self.assertEqual((started["mode"], started["action"]["state"]), ("study", "active"))
        self.assertEqual(self.action("start", "A")["action"]["at"], started["action"]["at"])
        self.assertEqual(started["activity_state"], "declared_active")
        self.assertEqual(self.app.state(self.goal_id)["selected"]["today_tasks"][0]["daily_state"],
                         "scheduled")  # Visual declaration never completes or changes a checklist task.
        with self.assertRaises(ValueError):
            self.action("start", "B")
        paused = self.action("pause", "C")
        self.assertEqual((paused["mode"], paused["action"]["state"]), ("idle", "paused"))
        self.assertTrue(paused["action"]["can_resume"])
        resumed = self.action("resume", "D")
        self.assertEqual((resumed["mode"], resumed["action"]["state"]), ("study", "active"))

        self.now = datetime(2026, 10, 6, 2, 0, tzinfo=timezone.utc)
        restarted = GoalApp(self.temp.name, self.clock).state(self.goal_id)["scene"]
        self.assertEqual((restarted["mode"], restarted["action"]["state"]), ("idle", "stale"))
        self.assertTrue(restarted["action"]["can_resume"])
        continued = self.action("resume", "E")
        self.assertEqual((continued["mode"], continued["action"]["state"]), ("study", "active"))
        stopped = self.action("stop", "F")
        self.assertEqual((stopped["mode"], stopped["action"]["state"]), ("idle", "stopped"))
        self.assertFalse(stopped["action"]["can_resume"])
        with self.assertRaises(ValueError):
            self.action("resume", "H")


if __name__ == "__main__":
    unittest.main()
