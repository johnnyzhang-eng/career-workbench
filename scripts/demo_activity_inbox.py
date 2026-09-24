#!/usr/bin/env python3
"""Fictional, offline example of the opt-in activity inbox contract."""

import json
import tempfile
from datetime import datetime, timezone

from workbench.activity import ActivityInbox


class FictionalToolAdapter:
    """Receives only the event sink, never the host's connection controls."""

    def __init__(self, send_event):
        self.send_event = send_event

    def report_session_end(self, occurred_at, event_id, task_hint):
        return self.send_event("demo-connector", {
            "event_id": event_id, "source": "fictional.tool",
            "kind": "work_session_ended", "occurred_at": occurred_at,
            "task_hint": task_hint,
        })


def main():
    moment = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as workspace:
        inbox = ActivityInbox(workspace, clock=lambda: moment)
        try:
            connection = inbox.connect("demo-connector", "fictional.tool",
                                       ["work_session_ended"])
            adapter = FictionalToolAdapter(inbox.ingest)
            observed = adapter.report_session_end(moment.isoformat(), "demo-opaque-001",
                                                  "DEMO-TASK-001")
            inbox.pause("demo-connector")
            try:
                adapter.report_session_end(moment.isoformat(), "demo-opaque-002",
                                           "DEMO-TASK-001")
            except ValueError:
                paused_rejected = True
            else:
                paused_rejected = False
            inbox.delete_observation("demo-connector", observed["event_id"])
            inbox.disconnect("demo-connector")
            print(json.dumps({"connection_before_pause": connection,
                              "observation": observed,
                              "paused_new_event_rejected": paused_rejected,
                              "observations_after_delete": inbox.list_observations(),
                              "connection_after_disconnect": inbox.get_connection("demo-connector")},
                             ensure_ascii=False, indent=2))
        finally:
            inbox.close()


if __name__ == "__main__":
    main()
