import http.client
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode
from http.server import ThreadingHTTPServer

from workbench.import_candidates import ROOT, import_file, public_url
from workbench.jobs import JobStore
from workbench.web import make_handler, render_page

JOB_URL = "https://careers.example.com/jobs/data-intern"
OTHER_URL = "https://careers.example.com/jobs/solutions-intern"
AT = "2026-09-19T02:00:00+08:00"


def batch(agent="agent_one", batch_id="run_001", job_url=JOB_URL):
    return {
        "schema_version": 1, "agent_id": agent, "batch_id": batch_id,
        "generated_at": AT,
        "candidates": [{
            "title": "虚构数据实习", "job_url": job_url,
            "apply_url": job_url + "/apply", "location": "Shanghai",
            "department": "Data", "description": "SQL 2027 届，条件待核查", "employment_type": "实习",
            "source": {"name": "虚构雇主招聘页", "url": job_url, "observed_at": AT},
            "reason": "与数据方向关键词相符；资格尚未核验",
            "evidence_refs": [{"url": job_url, "locator": "职位描述的要求段落"}],
            "unknowns": ["学历", "开放状态"],
        }],
    }


class AgentImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.alice = JobStore(self.root / "alice")
        self.bob = JobStore(self.root / "bob")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, store, data, name="agent-output.json"):
        path = store.workspace / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def test_two_agents_dedupe_one_job_and_keep_separate_reports(self):
        first = self.write(self.alice, batch())
        self.assertEqual(import_file(self.alice, first, AT), {"status": "imported", "total": 1, "new": 1})
        self.assertEqual(import_file(self.alice, first, AT)["status"], "already_imported")
        self.alice.set_flag("local", self.alice.jobs([])[0]["id"], "bookmarked", source="agent")
        second = batch("agent_two", "run_002")
        second["candidates"][0]["reason"] = "另一位 agent 根据同一原站页推荐"
        path = self.write(self.alice, second, "second.json")
        self.assertEqual(import_file(self.alice, path, AT)["new"], 0)
        jobs = self.alice.jobs([])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["list_state"], "待核查")
        self.assertTrue(jobs[0]["bookmarked"])
        self.assertEqual({r["agent_id"] for r in jobs[0]["agent_reports"]}, {"agent_one", "agent_two"})
        self.assertEqual(self.alice.agent_state()["batches"], 2)
        self.assertFalse((self.alice.workspace / "state.sqlite3").exists())

    def test_two_workspaces_keep_candidates_and_profiles_separate(self):
        import_file(self.alice, self.write(self.alice, batch()), AT)
        import_file(self.bob, self.write(self.bob, batch("bob_agent", "run_001", OTHER_URL)), AT)
        self.alice.save_profile({"city": "Shanghai", "direction": "Data", "include_unknown_cohort": True})
        self.bob.save_profile({"city": "Beijing", "include_unknown_cohort": True})
        self.assertEqual(len(self.alice.jobs([])), 1)
        self.assertEqual(len(self.bob.jobs([])), 0)
        self.assertEqual(self.bob.agent_state()["candidates"], 1)
        self.assertNotEqual(self.alice.jobs([])[0]["id"], self.bob.jobs([], {"include_unknown_cohort": True})[0]["id"])

    def test_shanghai_filter_matches_chinese_and_english_location_names(self):
        data = batch()
        chinese = deepcopy(data["candidates"][0])
        chinese["title"] = "上海运营实习"
        chinese["job_url"] = OTHER_URL
        chinese["apply_url"] = OTHER_URL + "/apply"
        chinese["location"] = "上海"
        chinese["source"] = {"name": "虚构雇主招聘页", "url": OTHER_URL, "observed_at": AT}
        chinese["evidence_refs"] = [{"url": OTHER_URL, "locator": "地点字段"}]
        data["candidates"].append(chinese)
        import_file(self.alice, self.write(self.alice, data), AT)

        for city in ("上海", "Shanghai"):
            with self.subTest(city=city):
                self.alice.save_profile({"city": city, "include_unknown_cohort": True})
                self.assertEqual(len(self.alice.jobs([])), 2)

    def test_conflicting_batch_and_invalid_input_leave_old_snapshot(self):
        path = self.write(self.alice, batch())
        import_file(self.alice, path, AT)
        changed = batch()
        changed["candidates"][0]["title"] = "Changed"
        self.write(self.alice, changed)
        with self.assertRaises(ValueError):
            import_file(self.alice, path, AT)
        self.assertEqual(self.alice.jobs([])[0]["title"], "虚构数据实习")
        invalid = batch("agent_one", "run_003")
        invalid["candidates"].append({**deepcopy(invalid["candidates"][0]), "job_url": "http://127.0.0.1/private"})
        with self.assertRaises(ValueError):
            import_file(self.alice, self.write(self.alice, invalid, "invalid.json"), AT)
        self.assertEqual(self.alice.agent_state()["batches"], 1)

    def test_path_and_url_boundaries(self):
        outside = self.write(self.bob, batch())
        with self.assertRaises(ValueError):
            import_file(self.alice, outside, AT)
        link = self.alice.workspace / "linked.json"
        link.symlink_to(outside)
        with self.assertRaises(ValueError):
            import_file(self.alice, link, AT)
        middle = self.alice.workspace / "other_user"
        middle.symlink_to(self.bob.workspace, target_is_directory=True)
        with self.assertRaises(ValueError):
            import_file(self.alice, middle / outside.name, AT)
        self.assertEqual(public_url("https://careers.example.com/jobs?gh_jid=12345", "job_url"), "https://careers.example.com/jobs?gh_jid=12345")
        moka_url = "https://app.mokahr.com/campus-recruitment/example/1234#/job/04f4b340-ff59-4457-bdf1-38916610c96c"
        self.assertEqual(public_url(moka_url, "job_url"), moka_url)
        for bad in (
            "file:///private/data", "https://127.0.0.1/jobs/1", "https://user:pass" + "@" + "jobs.example.com/1",
            "https://jobs.example.com/1?" + "tok" + "en=x", "https://jobs.example.com", "javascript:alert(1)",
            "https://host.local/jobs/1", "https://[::1]/jobs/1", "https://jobs.example.com/1#/job/04f4b340-ff59-4457-bdf1-38916610c96c",
            "https://app.mokahr.com/campus-recruitment/example/1234#javascript:alert(1)",
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                public_url(bad, "job_url")

    def test_parent_directory_swap_cannot_escape_workspace(self):
        nested = self.alice.workspace / "nested"
        nested.mkdir()
        file = nested / "batch.json"
        file.write_text(json.dumps(batch(), ensure_ascii=False), encoding="utf-8")
        self.write(self.bob, batch("other_agent"), "batch.json")
        real_open = os.open
        swapped = False

        def swap_then_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if path == "nested" and kwargs.get("dir_fd") is not None and not swapped:
                nested.rename(self.alice.workspace / "nested_original")
                nested.symlink_to(self.bob.workspace, target_is_directory=True)
                swapped = True
            return real_open(path, flags, *args, **kwargs)

        with patch("workbench.import_candidates.os.open", side_effect=swap_then_open):
            with self.assertRaises(ValueError):
                import_file(self.alice, file, AT)
        self.assertTrue(swapped)
        self.assertEqual(self.alice.agent_state()["candidates"], 0)

    def test_untrusted_markup_is_escaped_in_page(self):
        data = batch()
        data["candidates"][0]["title"] = "<script>alert(1)</script>"
        data["candidates"][0]["reason"] = "<img src=x onerror=alert(1)>"
        import_file(self.alice, self.write(self.alice, data), AT)
        page = render_page(self.alice, [], "synthetic-csrf").decode()
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("&lt;img", page)
        self.assertNotIn("<script>", page)
        self.assertNotIn("<img", page)
        self.assertIn("待本人核查", page)
        self.assertIn(JOB_URL + "/apply", page)
        self.assertNotIn("submitted", page)

    def test_application_tracks_are_visible_and_graduate_jobs_sort_first(self):
        data = batch()
        data["candidates"][0]["title"] = "实习岗位"
        graduate = deepcopy(data["candidates"][0])
        graduate["title"] = "应届正式岗位"
        graduate["employment_type"] = "应届正式"
        graduate["job_url"] = OTHER_URL
        graduate["apply_url"] = OTHER_URL + "/apply"
        graduate["source"] = {"name": "虚构雇主招聘页", "url": OTHER_URL, "observed_at": AT}
        graduate["evidence_refs"] = [{"url": OTHER_URL, "locator": "职位要求"}]
        data["candidates"].append(graduate)
        import_file(self.alice, self.write(self.alice, data), AT)

        page = render_page(self.alice, [], "synthetic-csrf").decode()
        self.assertIn("应届正式 1", page)
        self.assertIn("实习 1", page)
        self.assertNotIn("方向样本 1", page)
        self.assertLess(page.index("<h3>应届正式岗位</h3>"), page.index("<h3>实习岗位</h3>"))

    def test_agent_only_web_list_and_local_flag(self):
        import_file(self.alice, self.write(self.alice, batch()), AT)
        candidate_id = self.alice.jobs([])[0]["id"]
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.alice, [], "synthetic-csrf"))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
            host = f"127.0.0.1:{server.server_port}"
            connection.request("GET", "/", headers={"Host": host})
            response = connection.getresponse()
            page = response.read().decode()
            self.assertEqual(response.status, 200)
            self.assertIn("本地 agent 候选", page)
            self.assertIn("打开待核验申请入口", page)
            self.assertIn("与数据方向关键词相符", page)
            connection.close()

            connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
            payload = urlencode({"csrf_token": "synthetic-csrf", "source": "agent", "board": "local", "id": candidate_id, "flag": "viewed", "value": "1"})
            connection.request("POST", "/flag", body=payload, headers={"Host": host, "Origin": f"http://{host}", "Content-Type": "application/x-www-form-urlencoded"})
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 303)
            connection.close()
            self.assertTrue(self.alice.jobs([])[0]["viewed"])
            self.assertEqual(self.alice.jobs([])[0]["list_state"], "待核查")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_existing_ashby_database_is_preserved(self):
        db_path = self.root / "legacy" / "discovery.sqlite3"
        db_path.parent.mkdir()
        with sqlite3.connect(db_path) as db:
            db.executescript("""
                CREATE TABLE discovery_sources(source TEXT NOT NULL,board TEXT NOT NULL,source_url TEXT NOT NULL,last_attempt_at TEXT,last_success_at TEXT,last_error TEXT,failures INTEGER NOT NULL DEFAULT 0,next_allowed_at TEXT,PRIMARY KEY(source,board));
                CREATE TABLE discovery_jobs(source TEXT NOT NULL,board TEXT NOT NULL,source_job_id TEXT NOT NULL,payload TEXT NOT NULL,first_seen_at TEXT NOT NULL,last_seen_at TEXT NOT NULL,present_latest INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(source,board,source_job_id));
                CREATE TABLE discovery_profile(singleton INTEGER PRIMARY KEY CHECK(singleton=1),payload TEXT NOT NULL);
                CREATE TABLE discovery_flags(source TEXT NOT NULL,board TEXT NOT NULL,source_job_id TEXT NOT NULL,viewed INTEGER NOT NULL DEFAULT 0,bookmarked INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(source,board,source_job_id));
            """)
            db.execute("INSERT INTO discovery_sources(source,board,source_url,last_success_at) VALUES(?,?,?,?)", ("ashby", "ExampleBoard", "https://api.ashbyhq.com/posting-api/job-board/ExampleBoard", AT))
            old_job = {"id": "11111111-1111-4111-8111-111111111111", "title": "Old Ashby Job", "location": "Beijing", "secondary_locations": [], "department": "Data", "team": "", "description": "", "employment_type": "Intern", "published_at": AT, "job_url": "https://jobs.ashbyhq.com/ExampleBoard/11111111-1111-4111-8111-111111111111", "apply_url": None, "raw_fields": {}}
            db.execute("INSERT INTO discovery_jobs VALUES(?,?,?,?,?,?,1)", ("ashby", "ExampleBoard", old_job["id"], json.dumps(old_job), AT, AT))
        store = JobStore(db_path.parent)
        import_file(store, self.write(store, batch()), AT)
        self.assertEqual({j["source"] for j in store.jobs(["ExampleBoard"])}, {"ashby", "agent"})
        self.assertEqual(len(store.jobs(["ExampleBoard"])), 2)

    def test_cli_import_from_private_workspace(self):
        private_root = ROOT / "private"
        private_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="agent-import-qa-", dir=private_root) as directory:
            workspace = Path(directory)
            data_file = workspace / "batch.json"
            data_file.write_text(json.dumps(batch(), ensure_ascii=False), encoding="utf-8")
            result = subprocess.run([sys.executable, "-m", "workbench.import_candidates", "--workspace", str(workspace), "--file", str(data_file)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "imported")
            self.assertEqual(JobStore(workspace).agent_state()["candidates"], 1)


class AgentPasteWebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = JobStore(Path(self.temp.name) / "web")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store, [], "synthetic-csrf"))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method, path, data=None, origin=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        headers = {"Host": f"127.0.0.1:{self.server.server_port}"}
        payload = None
        if method == "POST":
            headers.update({"Origin": origin or f"http://127.0.0.1:{self.server.server_port}",
                            "Content-Type": "application/x-www-form-urlencoded"})
            payload = urlencode({"csrf_token": "synthetic-csrf", **(data or {})}).encode()
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        body = response.read().decode()
        status = response.status
        conn.close()
        return status, body

    def test_profile_prompt_paste_and_original_links(self):
        self.assertIn("让自己的 agent 找岗位", self.request("GET", "/")[1])
        self.assertEqual(self.request("POST", "/profile", {"city": "Shanghai", "direction": "Data"})[0], 303)
        self.assertIn("城市或地区：Shanghai", self.request("GET", "/")[1])
        raw = json.dumps(batch(), ensure_ascii=False)
        self.assertEqual(self.request("POST", "/import", {"agent_json": raw})[0], 303)
        status, page = self.request("GET", "/?result=imported")
        self.assertEqual(status, 200)
        self.assertIn("候选已导入当前工作区", page)
        self.assertIn(JOB_URL, page)
        self.assertIn(JOB_URL + "/apply", page)
        self.assertIn("待本人核查", page)
        self.assertEqual(self.request("POST", "/import", {"agent_json": raw})[0], 303)
        self.assertEqual(self.store.agent_state()["candidates"], 1)
        self.assertFalse((self.store.workspace / "state.sqlite3").exists())

    def test_bad_paste_shows_reason_without_losing_existing_candidate(self):
        self.request("POST", "/import", {"agent_json": json.dumps(batch())})
        invalid = batch("agent_two", "run_002")
        invalid["candidates"][0]["job_url"] = "http://127.0.0.1/private"
        invalid["candidates"][0]["title"] = "</textarea><script>alert(1)</script>"
        status, page = self.request("POST", "/import", {"agent_json": json.dumps(invalid)})
        self.assertEqual(status, 400)
        self.assertIn("导入未完成", page)
        self.assertIn("&lt;/textarea&gt;&lt;script&gt;", page)
        self.assertNotIn("<script>", page)
        self.assertIn(JOB_URL, page)
        self.assertEqual(self.store.agent_state()["batches"], 1)
        self.assertEqual(self.request("POST", "/import", {"agent_json": "{}"}, origin="http://evil.example")[0], 403)
        self.assertEqual(self.request("POST", "/import", {"csrf_token": "wrong", "agent_json": "{}"})[0], 403)


if __name__ == "__main__":
    unittest.main()
