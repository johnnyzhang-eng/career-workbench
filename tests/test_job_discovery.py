import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from http.server import ThreadingHTTPServer

from workbench.jobs import JobStore, _NoRedirect, parse_ashby, source_url
from workbench.directions import QUESTIONS
from workbench.web import make_handler

BOARD = "ExampleBoard"
J1 = "11111111-1111-4111-8111-111111111111"
J2 = "22222222-2222-4222-8222-222222222222"


def job(job_id=J1, title="Data Intern", location="Shanghai", apply=True, listed=True):
    return {
        "title": title, "location": location, "department": "Data", "team": "Analytics",
        "descriptionPlain": "2027 graduate SQL and Python", "publishedAt": "2026-09-18T00:00:00Z",
        "employmentType": "Intern", "isListed": listed,
        "jobUrl": f"https://jobs.ashbyhq.com/{BOARD}/{job_id}",
        "applyUrl": f"https://jobs.ashbyhq.com/{BOARD}/{job_id}/application" if apply else None,
    }


class FakeSource:
    name = "ashby"

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = 0

    def fetch(self, board):
        self.calls += 1
        if self.error:
            raise self.error
        return self.payload

    def parse(self, board, payload):
        return parse_ashby(board, payload)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(Path(self.tmp.name) / "one")
        self.t0 = datetime(2026, 9, 19, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def stamp(self, minutes):
        return (self.t0 + timedelta(minutes=minutes)).isoformat()

    def test_discovery_does_not_initialize_application_workflow(self):
        self.assertTrue(self.store.db_path.is_file())
        self.assertFalse((self.store.workspace / "state.sqlite3").exists())

    def test_refresh_deduplicates_updates_and_preserves_last_good_snapshot(self):
        first = FakeSource({"apiVersion": "1", "jobs": [job(), job(J2, "Solutions Engineer", "Beijing")]})
        self.assertEqual(self.store.refresh(BOARD, first, self.stamp(0))["new"], 2)
        self.assertEqual(self.store.refresh(BOARD, first, self.stamp(0))["status"], "cooldown")
        self.assertEqual(first.calls, 1)
        next_source = FakeSource({"apiVersion": "1", "jobs": [job(title="Senior Data Intern")]})
        result = self.store.refresh(BOARD, next_source, self.stamp(2))
        self.assertEqual(result["new"], 0)
        jobs = self.store.jobs([BOARD])
        self.assertEqual(len(jobs), 2)
        self.assertEqual(next(j for j in jobs if j["id"] == J1)["title"], "Senior Data Intern")
        self.assertEqual(next(j for j in jobs if j["id"] == J2)["list_state"], "待核查")
        self.assertEqual(next(j for j in jobs if j["id"] == J1)["first_seen_at"], self.stamp(0))
        self.assertEqual(self.store.refresh(BOARD, FakeSource(error=OSError("offline")), self.stamp(4))["status"], "error")
        self.assertEqual(self.store.source_state(BOARD)["last_success_at"], self.stamp(2))
        self.assertEqual(len(self.store.jobs([BOARD])), 2)

    def test_separate_users_have_separate_profiles_and_flags(self):
        payload = {"apiVersion": "1", "jobs": [job(), job(J2, "Solutions Engineer", "Beijing")]}
        other = JobStore(Path(self.tmp.name) / "two")
        self.store.refresh(BOARD, FakeSource(payload), self.stamp(0))
        other.refresh(BOARD, FakeSource(payload), self.stamp(0))
        self.store.save_profile({"city": "Shanghai", "direction": "Data", "cohort": "2027", "include_unknown_cohort": True})
        other.save_profile({"city": "Beijing", "direction": "Solutions", "cohort": "", "include_unknown_cohort": True})
        self.store.set_flag(BOARD, J1, "bookmarked")
        self.assertEqual([x["id"] for x in self.store.jobs([BOARD])], [J1])
        self.assertEqual([x["id"] for x in other.jobs([BOARD])], [J2])
        self.assertFalse(other.jobs([BOARD])[0]["bookmarked"])

    def test_unknown_cohort_and_empty_fields_are_honest(self):
        sample = job()
        sample["descriptionPlain"] = "SQL"
        sample["applyUrl"] = None
        sample["location"] = None
        self.store.refresh(BOARD, FakeSource({"apiVersion": "1", "jobs": [sample]}), self.stamp(0))
        self.store.save_profile({"cohort": "2027", "include_unknown_cohort": True})
        result = self.store.jobs([BOARD])[0]
        self.assertEqual(result["cohort_state"], "未知")
        self.assertIsNone(result["apply_url"])
        self.assertEqual(result["location"], "")
        self.store.save_profile({"cohort": "2027", "include_unknown_cohort": False})
        self.assertEqual(self.store.jobs([BOARD]), [])

    def test_unlisted_duplicate_and_malicious_urls(self):
        self.assertEqual(parse_ashby(BOARD, {"apiVersion": "1", "jobs": [job(listed=False)]}), [])
        for bad in (
            {"apiVersion": "1", "jobs": [job(), job()]},
            {"apiVersion": "1", "jobs": [{**job(), "jobUrl": "https://127.0.0.1/internal"}]},
            {"apiVersion": "1", "jobs": [{**job(), "jobUrl": f"https://jobs.ashbyhq.com/{BOARD}/{J1}?" + "tok" + "en=synthetic"}]},
        ):
            with self.assertRaises(ValueError):
                parse_ashby(BOARD, bad)
        odd_apply = {"apiVersion": "1", "jobs": [{**job(), "applyUrl": "https://evil.example/apply"}]}
        self.assertIsNone(parse_ashby(BOARD, odd_apply)[0]["apply_url"])
        with self.assertRaises(ValueError):
            source_url("../evil")

    def test_partial_parse_failure_does_not_replace_last_good(self):
        self.store.refresh(BOARD, FakeSource({"apiVersion": "1", "jobs": [job()]}), self.stamp(0))
        invalid = {"apiVersion": "1", "jobs": [job(J2), {**job(), "jobUrl": "http://localhost/job"}]}
        self.assertEqual(self.store.refresh(BOARD, FakeSource(invalid), self.stamp(2))["status"], "error")
        self.assertEqual([x["id"] for x in self.store.jobs([BOARD])], [J1])

    def test_storage_error_rolls_back_source_and_jobs(self):
        self.store.refresh(BOARD, FakeSource({"apiVersion": "1", "jobs": [job()]}), self.stamp(0))
        with sqlite3.connect(self.store.db_path) as db:
            db.execute("CREATE TRIGGER abort_discovery_update BEFORE UPDATE ON discovery_jobs BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.refresh(BOARD, FakeSource({"apiVersion": "1", "jobs": [job(title="Changed")]}), self.stamp(2))
        self.assertEqual(self.store.source_state(BOARD)["last_success_at"], self.stamp(0))
        self.assertEqual(self.store.jobs([BOARD])[0]["title"], "Data Intern")

    def test_redirect_is_rejected_without_following(self):
        with self.assertRaises(ValueError):
            _NoRedirect().redirect_request(None, None, 302, "moved", {}, "http://127.0.0.1/private")


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(Path(self.tmp.name) / "web")
        self.store.refresh(BOARD, FakeSource({"apiVersion": "1", "jobs": [job()]}), "2026-09-19T00:00:00+00:00")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store, [BOARD], "synthetic-csrf"))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def request(self, method, path, data=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        origin = f"http://127.0.0.1:{self.server.server_port}"
        payload = urlencode({"csrf_token": "synthetic-csrf", **data}).encode() if data is not None else None
        base = {"Host": f"127.0.0.1:{self.server.server_port}"}
        if method == "POST":
            base.update({"Origin": origin, "Content-Type": "application/x-www-form-urlencoded"})
        base.update(headers or {})
        conn.request(method, path, body=payload, headers=base)
        response = conn.getresponse()
        body = response.read().decode()
        status = response.status
        conn.close()
        return status, body

    def test_browser_page_has_separate_original_links_and_no_submission_claim(self):
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(f"https://jobs.ashbyhq.com/{BOARD}/{J1}/application", body)
        self.assertIn("打开原站职位详情", body)
        self.assertIn("不会记为“已投递”", body)
        self.assertNotIn("descriptionHtml", body)
        self.assertEqual(self.request("POST", "/flag", {"board": BOARD, "id": J1, "flag": "viewed", "value": "1"})[0], 303)
        self.assertTrue(self.store.jobs([BOARD])[0]["viewed"])

    def test_host_origin_and_private_path_rejected(self):
        self.assertEqual(self.request("GET", "/", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("POST", "/profile", {"city": "Shanghai"}, {"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.request("POST", "/profile", {"city": "Shanghai"}, {"Origin": "null"})[0], 303)
        self.assertEqual(self.request("POST", "/profile", {"csrf_token": "wrong", "city": "Beijing"}, {"Origin": "null"})[0], 403)
        self.assertEqual(self.request("GET", "/private/discovery.sqlite3")[0], 404)
        self.assertEqual(self.request("GET", "/%2e%2e/private/discovery.sqlite3")[0], 404)
        self.assertEqual(self.request("POST", "/refresh", {"board": "Other"})[0], 400)

    def test_source_text_is_escaped(self):
        sample = job(title="<script>alert(1)</script>")
        other = JobStore(Path(self.tmp.name) / "escaped")
        other.refresh(BOARD, FakeSource({"apiVersion": "1", "jobs": [sample]}), "2026-09-19T00:00:00+00:00")
        from workbench.web import render_page
        body = render_page(other, [BOARD], "synthetic-csrf").decode()
        self.assertIn("&lt;script&gt;", body)
        self.assertNotIn("<script>", body)

    def test_direction_questionnaire_saves_and_requires_valid_ratings(self):
        form = {
            "main_directions": "商品运营、用户运营", "secondary_directions": "运营分析",
            "watch_directions": "产品运营", "cities": "Shanghai", "cohort": "2027",
            "industries": "消费品牌", "exclusions": "纯销售", "confirmed_by_user": "1",
            **{question.key: "2" for question in QUESTIONS},
        }
        status, _ = self.request("POST", "/directions", form)
        self.assertEqual(status, 303)
        self.assertTrue(self.store.direction_profile()["confirmed_by_user"])
        self.assertEqual(self.store.direction_profile()["priorities"]["main"], "商品运营、用户运营")
        status, _ = self.request("POST", "/directions", {**form, "data_analysis": "9"})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
