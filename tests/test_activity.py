import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from career import Workflow
from workbench.activity import ActivityInbox
from workbench.daily import DailyStore


class Clock:
    def __init__(self):
        self.value = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


class ActivityInboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.inbox = ActivityInbox(self.temp.name, self.clock)
        self.inbox.connect("demo-connection", "fictional.tool",
                           ["work_session_ended", "artifact_updated"])

    def tearDown(self):
        self.inbox.close()
        self.temp.cleanup()

    def event(self, event_id="demo-event-1", **changes):
        event = {"event_id": event_id, "source": "fictional.tool",
                 "kind": "work_session_ended", "occurred_at": self.clock.value.isoformat(),
                 "task_hint": "DEMO-TASK-001"}
        event.update(changes)
        return event

    def test_opt_in_pause_resume_disconnect_and_inspection(self):
        self.assertEqual(self.inbox.list_observations(), [])
        self.assertEqual(self.inbox.get_connection("demo-connection")["state"], "enabled")
        observed = self.inbox.ingest("demo-connection", self.event())
        self.assertEqual(observed["event_id"], "demo-event-1")
        self.assertEqual(observed["task_hint"], "DEMO-TASK-001")
        self.inbox.pause("demo-connection")
        with self.assertRaises(ValueError):
            self.inbox.ingest("demo-connection", self.event("demo-event-2"))
        self.assertEqual(len(self.inbox.list_observations("demo-connection")), 1)
        self.inbox.resume("demo-connection")
        self.inbox.ingest("demo-connection", self.event("demo-event-2"))
        self.inbox.disconnect("demo-connection")
        with self.assertRaises(ValueError):
            self.inbox.ingest("demo-connection", self.event("demo-event-3"))
        self.assertEqual(len(self.inbox.list_observations("demo-connection")), 2)
        with self.assertRaises(ValueError):
            self.inbox.resume("demo-connection")

    def test_unapproved_source_and_event_payload_are_rejected(self):
        with self.assertRaises(ValueError):
            self.inbox.ingest("unconnected-tool", self.event())
        with self.assertRaises(ValueError):
            self.inbox.ingest("demo-connection", self.event(source="another.tool"))
        with self.assertRaises(ValueError):
            self.inbox.ingest("demo-connection", self.event(kind="work_session_started"))
        with self.assertRaises(ValueError):
            self.inbox.ingest("demo-connection", self.event(screen_text="private content"))
        with self.assertRaises(ValueError):
            self.inbox.connect("unsafe", "fictional.tool", ["screen_capture"])
        self.assertEqual(self.inbox.list_observations(), [])

    def test_duplicate_id_is_idempotent_and_conflicts_are_rejected(self):
        first = self.inbox.ingest("demo-connection", self.event())
        self.clock.value += timedelta(minutes=1)
        self.assertEqual(self.inbox.ingest("demo-connection", self.event(
            occurred_at=first["occurred_at"])), first)
        with self.assertRaises(ValueError):
            self.inbox.ingest("demo-connection", self.event(kind="artifact_updated",
                                                            occurred_at=first["occurred_at"]))
        self.assertEqual(len(self.inbox.list_observations()), 1)

    def test_restart_preserves_observation_and_connection_state(self):
        self.inbox.ingest("demo-connection", self.event())
        self.inbox.pause("demo-connection")
        reopened = ActivityInbox(self.temp.name, self.clock)
        try:
            self.assertEqual(reopened.get_connection("demo-connection")["state"], "paused")
            self.assertEqual(len(reopened.list_observations()), 1)
            with self.assertRaises(ValueError):
                reopened.ingest("demo-connection", self.event("demo-event-new"))
        finally:
            reopened.close()

    def test_delete_blocks_replay_and_forget_removes_all_local_records(self):
        event = self.event()
        self.inbox.ingest("demo-connection", event)
        self.inbox.delete_observation("demo-connection", event["event_id"])
        self.assertEqual(self.inbox.list_observations(), [])
        reopened = ActivityInbox(self.temp.name, self.clock)
        try:
            with self.assertRaises(ValueError):
                reopened.ingest("demo-connection", event)
        finally:
            reopened.close()
        self.assertEqual(self.inbox.db.execute(
            "SELECT COUNT(*) FROM activity_deleted_ids").fetchone()[0], 1)
        self.inbox.forget_connection("demo-connection")
        self.assertEqual(self.inbox.list_connections(), [])
        self.assertEqual(self.inbox.db.execute(
            "SELECT COUNT(*) FROM activity_deleted_ids").fetchone()[0], 0)
        with self.assertRaises(ValueError):
            self.inbox.ingest("demo-connection", event)

    def test_retention_and_time_validation(self):
        with self.assertRaises(ValueError):
            self.inbox.ingest("demo-connection", self.event(
                occurred_at=(self.clock.value - timedelta(days=31)).isoformat()))
        with self.assertRaises(ValueError):
            self.inbox.ingest("demo-connection", self.event(occurred_at="2026-09-24T09:00:00"))
        with self.assertRaises(ValueError):
            self.inbox.ingest("demo-connection", self.event(
                occurred_at=(self.clock.value + timedelta(minutes=6)).isoformat()))
        self.inbox.ingest("demo-connection", self.event())
        self.clock.value += timedelta(days=31)
        self.inbox.prune_expired()
        self.assertEqual(self.inbox.list_observations(), [])

    def test_observation_does_not_complete_daily_task(self):
        daily = DailyStore(self.temp.name, self.clock)
        workflow = Workflow(self.temp.name)
        try:
            with workflow.db:
                workflow.add({"id": "DEMO-JOB-001", "company": "虚构公司", "role": "虚构岗位",
                              "family": "operations", "url": "https://example.com/jobs/demo"})
            job_events_before = workflow.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            task = {"id": "DEMO-TASK-001", "title": "整理虚构练习结果", "kind": "custom",
                    "source_kind": "self", "source_id": "DEMO-SELF", "reason": "今日练习",
                    "scheduled_at": self.clock.value.isoformat(), "due_at": None,
                    "due_verified": False}
            daily.command("schedule", "DEMO-SCHEDULE", task["id"], {"task": task})
            before = daily.db.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0]
            self.inbox.ingest("demo-connection", self.event())
            after = daily.db.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0]
            self.assertEqual(before, after)
            self.assertEqual(daily.snapshot("UTC")["tasks"][0]["state"], "scheduled")
            self.assertEqual(daily.snapshot("UTC")["tasks"][0]["evidence_state"], "missing")
            self.assertEqual(workflow.get("DEMO-JOB-001")["state"], "discovered")
            self.assertEqual(workflow.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                             job_events_before)
        finally:
            daily.close()
            workflow.db.close()


if __name__ == "__main__":
    unittest.main()
