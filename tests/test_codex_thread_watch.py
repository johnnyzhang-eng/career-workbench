import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("thread_watch", Path(__file__).parents[1] / "scripts/codex_thread_watch.py")
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


def event(kind, **fields):
    return {"timestamp": "2026-01-01T00:00:00Z", "type": "event_msg", "payload": {"type": kind, **fields}}


def usage(tokens, cumulative=90000000):
    return event("token_count", info={"last_token_usage": {"input_tokens": tokens},
                                     "total_token_usage": {"input_tokens": cumulative},
                                     "model_context_window": 1000})


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "fictional.jsonl"
        self.config = self.root / "config.json"
        self.workspace = self.root / "private"
        self.config.write_text(json.dumps({"tasks": [{"task_id": "T01", "thread_id": "fictional-thread",
                                                       "rollout_path": str(self.source)}]}))
        self.reset()

    def reset(self):
        self.source.write_text(json.dumps({"type": "session_meta", "payload": {"id": "fictional-thread"}}) + "\n")

    def append(self, *events):
        with self.source.open("a") as stream:
            for value in events:
                stream.write(json.dumps(value) + "\n")

    def scan(self):
        report, changed = watch.scan(self.config, self.workspace)
        return report["items"][0], changed

    def test_cumulative_usage_never_triggers_pressure(self):
        self.append(usage(100))
        row, _ = self.scan()
        self.assertEqual(row["last_input_ratio"], .1)
        self.assertEqual(row["advisory"], "none")

    def test_active_turn_waits_then_handoff_is_only_advisory(self):
        self.append(event("task_started", turn_id="turn-a"), usage(850))
        self.assertEqual(self.scan()[0]["advisory"], "checkpoint_after_turn")
        self.append(event("task_complete", turn_id="turn-a", last_agent_message="Everything done"))
        row, _ = self.scan()
        self.assertEqual(row["advisory"], "review_handoff")
        self.assertEqual(row["task_completion"], "not_inferred")

    def test_compaction_invalidates_previous_pressure(self):
        self.append(usage(950), {"type": "compacted", "payload": {"message": "private words"}})
        row, _ = self.scan()
        self.assertIsNone(row["last_input_ratio"])
        self.assertEqual(row["advisory"], "none")
        self.append(usage(100))
        self.assertEqual(self.scan()[0]["last_input_ratio"], .1)

    def test_unrelated_completed_turn_does_not_end_new_active_turn(self):
        self.append(event("task_started", turn_id="turn-new"), event("task_complete", turn_id="turn-old"))
        self.assertEqual(self.scan()[0]["turn_state"], "active")

    def test_partial_record_is_retried_without_advancing(self):
        data = json.dumps(usage(500))
        with self.source.open("a") as stream:
            stream.write(data[:30])
        self.assertIsNone(self.scan()[0]["input_tokens"])
        with self.source.open("a") as stream:
            stream.write(data[30:] + "\n")
        self.assertEqual(self.scan()[0]["input_tokens"], 500)

    def test_no_change_is_idempotent_after_restart(self):
        self.append(usage(500))
        self.scan()
        original = json.loads((self.workspace / "state.json").read_text())
        _, changed = self.scan()
        self.assertFalse(changed)
        self.assertEqual(original, json.loads((self.workspace / "state.json").read_text()))

    def test_truncation_replays_instead_of_reusing_old_metric(self):
        self.append(usage(850))
        self.scan()
        self.reset()
        self.assertIsNone(self.scan()[0]["input_tokens"])

    def test_replacement_file_same_header_is_replayed(self):
        self.append(usage(850))
        self.scan()
        replacement = self.root / "replacement.jsonl"
        replacement.write_text(self.source.read_text().splitlines()[0] + "\n" + json.dumps(usage(100)) + "\n")
        replacement.replace(self.source)
        self.assertEqual(self.scan()[0]["input_tokens"], 100)

    def test_same_size_in_place_rewrite_is_replayed(self):
        self.append(usage(850))
        self.scan()
        self.reset()
        self.append(usage(100))
        self.assertEqual(self.scan()[0]["input_tokens"], 100)

    def test_missing_source_is_unknown_and_recovers(self):
        self.append(usage(850))
        self.scan()
        self.source.unlink()
        row, _ = self.scan()
        self.assertEqual(row["advisory"], "check_source")
        self.assertIsNone(row["input_tokens"])
        self.reset()
        self.append(usage(100))
        self.assertEqual(self.scan()[0]["source_health"], "ok")

    def test_wrong_thread_identity_is_rejected(self):
        self.source.write_text(json.dumps({"type": "session_meta", "payload": {"id": "other-thread"}}) + "\n")
        self.append(usage(850))
        self.assertEqual(self.scan()[0]["source_health"], "source_unavailable_or_invalid")

    def test_malformed_metrics_are_unknown(self):
        for value in [True, -1, "850", None]:
            with self.subTest(value=value):
                self.append(usage(value))
                self.assertIsNone(self.scan()[0]["input_tokens"])

    def test_private_content_and_unregistered_sources_never_persist(self):
        secret = "PRIVATE-FIXTURE-CONTENT"
        self.append({"type": "response_item", "payload": {"content": secret}},
                    event("task_complete", turn_id="turn-a", last_agent_message=secret),
                    event("token_count", info={"last_token_usage": {"input_tokens": 100},
                                               "model_context_window": 1000, "secret": secret}))
        (self.root / "unregistered.jsonl").write_text(secret)
        self.scan()
        for name in ["state.json", "report.json"]:
            stored = (self.workspace / name).read_text()
            self.assertNotIn(secret, stored)
            self.assertNotIn(str(self.source), stored)

    def test_lock_does_not_overwrite_and_recovers_when_released(self):
        self.scan()
        lock = self.workspace / "scan.lock"
        lock.write_text("fictional-owner")
        original = (self.workspace / "state.json").read_bytes()
        with self.assertRaises(FileExistsError):
            self.scan()
        self.assertEqual(original, (self.workspace / "state.json").read_bytes())
        lock.unlink()
        self.assertEqual(self.scan()[0]["source_health"], "ok")

    def test_malformed_line_clears_old_metric(self):
        self.append(usage(850))
        self.scan()
        with self.source.open("a") as stream:
            stream.write("bad-json\n")
        self.assertIsNone(self.scan()[0]["input_tokens"])

    def test_large_compaction_invalidates_metric_without_persisting_body(self):
        self.append(usage(850), {"type": "compacted", "payload": {"message": "x" * 2_100_000}})
        row, _ = self.scan()
        self.assertEqual(row["source_health"], "ok")
        self.assertIsNone(row["input_tokens"])
        self.assertLess((self.workspace / "state.json").stat().st_size, 2000)

    def test_oversized_record_is_unknown_not_healthy_old_metric(self):
        self.append(usage(850))
        self.scan()
        self.append({"type": "response_item", "payload": {"content": "x" * 2000}})
        with patch.object(watch, "MAX_LINE", 1000):
            self.assertEqual(self.scan()[0]["source_health"], "source_unavailable_or_invalid")

    def test_token_sample_without_valid_time_is_unknown(self):
        value = usage(850)
        value["timestamp"] = "invalid"
        self.append(value)
        self.assertIsNone(self.scan()[0]["input_tokens"])


if __name__ == "__main__":
    unittest.main()
