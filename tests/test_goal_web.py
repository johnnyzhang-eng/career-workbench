"""HTTP-level checks for the private goal workbench and shared views."""

import http.client
import json
import tempfile
import threading
import unittest
import base64
from datetime import datetime, timezone
from pathlib import Path

from workbench.avatar_photo import AvatarPhotoStore
from workbench.goal_web import GoalHTTPServer


class GoalWebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = datetime(2026, 10, 5, 2, 0, tzinfo=timezone.utc)
        self.clock = lambda: self.now
        self.start_server()

    def start_server(self):
        self.server = GoalHTTPServer(("127.0.0.1", 0), self.temp.name, self.clock)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def tearDown(self):
        self.stop_server()
        self.temp.cleanup()

    def request(self, method, path, payload=None, *, origin=None, host=None, csrf=None, content_type=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {"Host": host or f"127.0.0.1:{self.port}"}
        if origin is not None:
            headers["Origin"] = origin
        if csrf is not None:
            headers["X-CSRF-Token"] = csrf
        if content_type is not None:
            headers["Content-Type"] = content_type
        body = json.dumps(payload).encode() if payload is not None else None
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read()
        headers = dict(response.getheaders())
        result = (response.status, json.loads(data) if headers["Content-Type"].startswith("application/json")
                  else data.decode(), headers)
        connection.close()
        return result

    def post(self, path, payload, token):
        return self.request("POST", path, payload, origin=f"http://127.0.0.1:{self.port}",
                            csrf=token, content_type="application/json")

    def goal(self, token, operation="A" * 24, path="cet6"):
        status, body, _ = self.post("/api/goals", {
            "operation_id": operation, "path": path, "title": "虚构七日目标",
            "weekly_minutes": 300, "baseline": "虚构起点 12/25",
            "success_criterion": "保存每次首次作答与复盘", "timezone": "Asia/Shanghai"}, token)
        self.assertEqual(status, 200, body)
        return body

    def test_cet6_proposal_is_inactive_until_accept_and_sync_then_survives_restart(self):
        status, initial, headers = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        token = initial["csrf_token"]
        created = self.goal(token)
        goal_id = created["selected_goal_id"]
        self.assertEqual(created["selected"]["goal"]["active_version"], 0)
        status, proposed, _ = self.post("/api/plans/propose", {
            "operation_id": "B" * 24, "goal_id": goal_id, "start_on": "2026-10-05"}, token)
        self.assertEqual(status, 200, proposed)
        proposal = proposed["selected"]["pending_proposals"][0]
        self.assertEqual(len(proposal["items"]), 7)
        self.assertTrue(all(item["reason"] and item["source_ref"] for item in proposal["items"]))
        self.assertIsNone(proposed["selected"]["active_plan"])
        self.assertEqual(proposed["selected"]["sync"]["state"], "no_plan")
        status, accepted, _ = self.post("/api/plans/decide", {
            "operation_id": "C" * 24, "proposal_id": proposal["id"], "decision": "accept"}, token)
        self.assertEqual(status, 200, accepted)
        self.assertEqual(accepted["selected"]["sync"]["state"], "sync_pending")
        status, applied, _ = self.post("/api/plans/sync", {
            "operation_id": "D" * 24, "goal_id": goal_id}, token)
        self.assertEqual(status, 200, applied)
        self.assertEqual(applied["selected"]["sync"]["state"], "applied")
        self.assertEqual(len(applied["selected"]["active_plan"]["items"]), 7)
        task_id = applied["selected"]["active_plan"]["items"][0]["task_id"]
        self.now = datetime(2026, 10, 6, 2, 0, tzinfo=timezone.utc)
        carryover = self.request("GET", "/api/state?goal_id=" + goal_id)[1]["selected"]
        self.assertIn(task_id, {item["task_id"] for item in carryover["today_tasks"]})
        self.assertIn("不会扣分", carryover["feedback"])
        status, invalid, _ = self.post("/api/tasks/complete", {
            "operation_id": "E" * 24, "goal_id": goal_id, "task_id": task_id,
            "evidence": {"material_ref": "虚构材料", "reflection_ref": "虚构错因"}}, token)
        self.assertEqual(status, 400, invalid)
        status, done, _ = self.post("/api/tasks/complete", {
            "operation_id": "F" * 24, "goal_id": goal_id, "task_id": task_id,
            "evidence": {"material_ref": "虚构材料", "first_attempt_ref": "虚构首次答案",
                         "reflection_ref": "虚构错因"}}, token)
        self.assertEqual(status, 200, done)
        self.assertEqual(done["selected"]["active_plan"]["items"][0]["daily_state"], "completed")
        self.assertEqual(done["selected"]["results"], [])  # #32 bridge is still separate.
        self.stop_server()
        self.start_server()
        status, restored, _ = self.request("GET", "/api/state?goal_id=" + goal_id)
        self.assertEqual(status, 200, restored)
        self.assertEqual(restored["selected"]["active_plan"]["items"][0]["daily_state"], "completed")
        self.assertEqual(restored["selected"]["sync"]["state"], "applied")
        self.now = datetime(2026, 10, 7, 2, 0, tzinfo=timezone.utc)
        next_day = self.request("GET", "/api/state?goal_id=" + goal_id)[1]["selected"]
        self.assertNotIn(task_id, {item["task_id"] for item in next_day["today_tasks"]})

    def test_decline_recruiting_proposal_and_compact_share_state(self):
        token = self.request("GET", "/api/state")[1]["csrf_token"]
        created = self.goal(token, "R" * 24, "recruiting")
        goal_id = created["selected_goal_id"]
        proposal = self.post("/api/plans/propose", {
            "operation_id": "S" * 24, "goal_id": goal_id, "start_on": "2026-10-05"}, token)[1]["selected"]["pending_proposals"][0]
        self.assertEqual(proposal["items"][0]["source_kind"], "goal")
        self.assertIn("没有已核对的岗位截止", proposal["reason"])
        status, declined, _ = self.post("/api/plans/decide", {
            "operation_id": "T" * 24, "proposal_id": proposal["id"], "decision": "decline"}, token)
        self.assertEqual(status, 200, declined)
        self.assertEqual(declined["selected"]["goal"]["active_version"], 0)
        self.assertEqual(declined["selected"]["sync"]["state"], "no_plan")
        compact_status, compact_html, compact_headers = self.request("GET", "/compact")
        full_status, full_html, _ = self.request("GET", "/")
        self.assertEqual((compact_status, full_status), (200, 200))
        self.assertIn("location.pathname === '/compact'", compact_html)
        self.assertIn("location.pathname === '/compact'", full_html)
        self.assertIn("frame-ancestors 'none'", compact_headers["Content-Security-Policy"])

    def test_host_origin_csrf_and_content_type_gates(self):
        token = self.request("GET", "/api/state")[1]["csrf_token"]
        self.assertEqual(self.request("GET", "/api/state", host="evil.example")[0], 403)
        self.assertEqual(self.request("POST", "/api/goals", {}, origin="http://evil.example",
                                      csrf=token, content_type="application/json")[0], 403)
        self.assertEqual(self.request("POST", "/api/goals", {}, origin=f"http://127.0.0.1:{self.port}",
                                      content_type="application/json")[0], 403)
        self.assertEqual(self.request("POST", "/api/goals", {}, origin=f"http://127.0.0.1:{self.port}",
                                      csrf=token, content_type="text/plain")[0], 415)
        with self.assertRaises(ValueError):
            GoalHTTPServer(("0.0.0.0", 0), self.temp.name)

    def test_three_shell_routes_and_local_scene_script(self):
        for route in ("/", "/compact", "/collapsed"):
            status, body, headers = self.request("GET", route)
            self.assertEqual(status, 200, route)
            self.assertIn("goal-room-scene", body)
            self.assertIn('script-src \'self\' \'nonce-', headers["Content-Security-Policy"])
            self.assertNotIn("unsafe-inline", headers["Content-Security-Policy"])
        status, script, headers = self.request("GET", "/goal-scene.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/javascript; charset=utf-8")
        self.assertIn("customElements.define('goal-room-scene'", script)
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        connection.request("GET", "/scene-assets/room-day.png",
                           headers={"Host": f"127.0.0.1:{self.port}"})
        asset = connection.getresponse()
        self.assertEqual(asset.status, 200)
        self.assertEqual(asset.getheader("Content-Type"), "image/png")
        self.assertTrue(asset.read().startswith(b"\x89PNG\r\n\x1a\n"))
        connection.close()
        self.assertEqual(self.request("GET", "/scene-assets/../goal-scene.js")[0], 404)
        self.assertEqual(self.request("GET", "/scene-assets/unlisted.png")[0], 404)

    def test_explicit_room_actions_do_not_complete_daily_task(self):
        token = self.request("GET", "/api/state")[1]["csrf_token"]
        goal_id = self.goal(token, "U" * 24)["selected_goal_id"]
        proposal = self.post("/api/plans/propose", {
            "operation_id": "V" * 24, "goal_id": goal_id, "start_on": "2026-10-05"}, token)[1]["selected"]["pending_proposals"][0]
        self.post("/api/plans/decide", {
            "operation_id": "W" * 24, "proposal_id": proposal["id"], "decision": "accept"}, token)
        applied = self.post("/api/plans/sync", {
            "operation_id": "X" * 24, "goal_id": goal_id}, token)[1]
        task_id = applied["selected"]["today_tasks"][0]["task_id"]
        self.assertEqual(applied["scene"]["mode"], "idle")
        for index, (action, scene_mode, action_state) in enumerate((
                ("start", "study", "active"), ("pause", "idle", "paused"),
                ("resume", "study", "active"), ("stop", "idle", "stopped"))):
            status, changed, _ = self.post("/api/actions/" + action, {
                "operation_id": "ACT" + str(index) * 20, "goal_id": goal_id, "task_id": task_id}, token)
            self.assertEqual(status, 200, changed)
            self.assertEqual(changed["scene"]["mode"], scene_mode)
            self.assertEqual(changed["scene"]["action"]["state"], action_state)
            self.assertEqual(changed["selected"]["today_tasks"][0]["daily_state"], "scheduled")

    def test_private_photo_upload_read_delete_and_restart(self):
        token = self.request("GET", "/api/state")[1]["csrf_token"]
        self.assertFalse(self.request("GET", "/api/avatar/photo/status")[1]["present"])
        source = Path(__file__).resolve().parents[1] / "docs/scene-assets/room-day.png"
        data = source.read_bytes()
        payload = {"mime_type": "image/png", "data_base64": base64.b64encode(data).decode("ascii")}
        self.assertEqual(self.request("POST", "/api/avatar/photo", payload,
                                      origin="http://evil.example", csrf=token,
                                      content_type="application/json")[0], 403)
        status, result, _ = self.post("/api/avatar/photo", payload, token)
        self.assertEqual(status, 200, result)
        self.assertTrue(result["present"])
        self.assertFalse(result["generated_avatar"])
        private_path = Path(self.temp.name) / "private_avatar/source.png"
        self.assertEqual(private_path.read_bytes(), data)
        self.assertEqual(private_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.request("GET", "/api/avatar/photo/image")[0], 403)
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        connection.request("GET", "/api/avatar/photo/image", headers={
            "Host": f"127.0.0.1:{self.port}", "X-CSRF-Token": token})
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "image/png")
        self.assertEqual(response.read(), data)
        connection.close()
        self.stop_server()
        self.start_server()
        self.assertTrue(self.request("GET", "/api/avatar/photo/status")[1]["present"])
        token = self.request("GET", "/api/state")[1]["csrf_token"]
        self.assertEqual(self.post("/api/avatar/photo/delete", {}, token)[0], 200)
        self.assertFalse(private_path.exists())
        self.assertFalse(self.request("GET", "/api/avatar/photo/status")[1]["present"])
        self.assertEqual(self.request("GET", "/api/avatar/photo/image", csrf=token)[0], 404)

    def test_private_photo_rejects_invalid_content(self):
        token = self.request("GET", "/api/state")[1]["csrf_token"]
        for payload in ({"mime_type": "image/svg+xml", "data_base64": "PHN2Zy8+"},
                        {"mime_type": "image/png", "data_base64": "aW52YWxpZA=="},
                        {"mime_type": "image/jpeg", "data_base64": "aW52YWxpZA=="}):
            self.assertEqual(self.post("/api/avatar/photo", payload, token)[0], 400)
        with self.assertRaisesRegex(ValueError, "最多 2 MB"):
            AvatarPhotoStore(self.temp.name).save(base64.b64encode(b"x" * 2_000_001).decode("ascii"), "image/png")
        self.assertFalse((Path(self.temp.name) / "private_avatar").exists())


if __name__ == "__main__":
    unittest.main()
