"""Guard the two measurement errors caught during the actual macOS run."""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sample_runtime import cpu_seconds, summarise


class RuntimeSamplerTest(unittest.TestCase):
    def test_accumulated_cpu_time_parser(self):
        self.assertEqual(cpu_seconds("1:02.50"), 62.5)
        self.assertEqual(cpu_seconds("1:01:02.50"), 3662.5)
        self.assertEqual(cpu_seconds("1-01:01:02.50"), 90062.5)

    def test_late_unrelated_webkit_process_is_excluded(self):
        events = [{"kind": kind, "time": timestamp} for kind, timestamp in
                  (("launched", 100), ("ready", 100), ("hidden", 130),
                   ("restored", 155), ("completed", 175))]
        samples = []
        for time in range(100, 176):
            companion = {"pid": 1, "cpu_seconds_total": time / 100, "rss_kib": 10}
            owned = {"pid": 2, "cpu_seconds_total": time - 100, "rss_kib": 100}
            webkit = [owned]
            if time >= 140:
                # A second app starts WebKit halfway through the hidden phase.
                webkit.append({"pid": 3, "cpu_seconds_total": (time - 140) * 2,
                               "rss_kib": 500})
            samples.append({"time": time, "host": companion, "webkit": webkit})
        report = summarise(samples, events, set(), {"parser_detected": True})
        self.assertEqual(report["launch_cohort_candidate_pids"], [2])
        self.assertEqual(report["new_webkit_candidate_pids"], [2, 3])
        self.assertEqual(report["phase_summary"]["hidden"]["launch_cohort_webkit_cpu_core_percent_from_cputime"], 100)


if __name__ == "__main__":
    unittest.main()
