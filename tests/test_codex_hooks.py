import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from workbench.activity import ActivityInbox
from workbench.codex_hooks import ingest_codex_hook, observation_from_hook


NOW = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)


class CodexHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = lambda: NOW
        self.inbox = ActivityInbox(self.temp.name, clock=self.clock)
        self.inbox.connect("codex-hooks", "codex.hooks", [
            "turn_prompted", "turn_stop_observed", "turn_interrupted", "tool_used"])
        self.inbox.close()

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def payload(name, **changes):
        result = {"hook_event_name": name, "session_id": "session-001",
                  "turn_id": "turn-001", "tool_use_id": "tool-call-001",
                  "tool_name": "apply_patch",
                  "prompt": "SECRET_PROMPT", "tool_input": {"command": "SECRET_INPUT"},
                  "tool_response": "SECRET_OUTPUT",
                  "transcript_path": "/SECRET_TRANSCRIPT", "cwd": "/SECRET_CWD"}
        result.update(changes)
        return result

    def test_four_hooks_create_distinct_accurate_observations_without_content(self):
        for name, expected in (("UserPromptSubmit", "turn_prompted"),
                               ("Stop", "turn_stop_observed"),
                               ("Interrupt", "turn_interrupted"),
                               ("PostToolUse", "tool_used")):
            observed = ingest_codex_hook(self.temp.name, "codex-hooks",
                                         self.payload(name), self.clock)
            self.assertEqual(observed["kind"], expected)
            self.assertNotIn("SECRET", json.dumps(observed))
            self.assertEqual(observed["tool_name"],
                             "apply_patch" if name == "PostToolUse" else None)
        db_bytes = (Path(self.temp.name) / "activity.sqlite3").read_bytes()
        for secret in (b"SECRET_PROMPT", b"SECRET_INPUT", b"SECRET_OUTPUT",
                       b"SECRET_TRANSCRIPT", b"SECRET_CWD", b"session-001", b"turn-001"):
            self.assertNotIn(secret, db_bytes)

    def test_duplicate_delivery_is_idempotent_across_clock_change(self):
        first = ingest_codex_hook(self.temp.name, "codex-hooks",
                                  self.payload("PostToolUse"), self.clock)
        retry = ingest_codex_hook(self.temp.name, "codex-hooks",
                                  self.payload("PostToolUse"),
                                  lambda: NOW + timedelta(minutes=2))
        self.assertEqual(first, retry)
        inbox = ActivityInbox(self.temp.name, clock=self.clock)
        try:
            self.assertEqual(len(inbox.list_observations()), 1)
        finally:
            inbox.close()

    def test_pause_and_disconnect_reject_new_events(self):
        inbox = ActivityInbox(self.temp.name, clock=self.clock)
        inbox.pause("codex-hooks")
        inbox.close()
        with self.assertRaises(ValueError):
            ingest_codex_hook(self.temp.name, "codex-hooks",
                              self.payload("UserPromptSubmit"), self.clock)
        inbox = ActivityInbox(self.temp.name, clock=self.clock)
        inbox.disconnect("codex-hooks")
        inbox.close()
        with self.assertRaises(ValueError):
            ingest_codex_hook(self.temp.name, "codex-hooks",
                              self.payload("Stop"), self.clock)

    def test_unsupported_and_missing_identity_never_create_records(self):
        invalid = [self.payload("SessionEnd"),
                   self.payload("Stop", turn_id=None),
                   self.payload("PostToolUse", tool_use_id=None),
                   self.payload("PostToolUse", tool_name="/private/file")]
        for payload in invalid:
            with self.assertRaises(ValueError):
                observation_from_hook(payload, NOW)
        inbox = ActivityInbox(self.temp.name, clock=self.clock)
        try:
            self.assertEqual(inbox.list_observations(), [])
        finally:
            inbox.close()

    def test_command_hook_never_echoes_secret_or_blocks_codex(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "codex_hook_activity.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--workspace", self.temp.name,
             "--connection", "codex-hooks"],
            input=json.dumps(self.payload("Stop")), text=True,
            capture_output=True, check=False)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout), {})
        self.assertNotIn("SECRET", proc.stdout + proc.stderr)
        bad = subprocess.run(
            [sys.executable, str(script), "--workspace", self.temp.name,
             "--connection", "missing-connection"],
            input=json.dumps(self.payload("Stop")), text=True,
            capture_output=True, check=False)
        self.assertEqual(bad.returncode, 0)
        self.assertNotIn("SECRET", bad.stdout + bad.stderr)

    def test_existing_inbox_database_receives_metadata_columns(self):
        old_path = Path(self.temp.name) / "activity.sqlite3"
        old = sqlite3.connect(old_path)
        try:
            old.execute("DROP TABLE activity_observations")
            old.execute("""CREATE TABLE activity_observations (
                connection_id TEXT NOT NULL, event_id TEXT NOT NULL,
                source TEXT NOT NULL, kind TEXT NOT NULL,
                occurred_at TEXT NOT NULL, observed_at TEXT NOT NULL,
                task_hint TEXT, PRIMARY KEY(connection_id,event_id))""")
            old.commit()
        finally:
            old.close()
        result = ingest_codex_hook(self.temp.name, "codex-hooks",
                                   self.payload("PostToolUse"), self.clock)
        self.assertEqual(result["tool_name"], "apply_patch")


if __name__ == "__main__":
    unittest.main()
