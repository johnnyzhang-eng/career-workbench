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

    def active_goal(self, token, prefix="A", path="cet6"):
        goal_id = self.goal(token, prefix * 24, path)["selected_goal_id"]
        proposal = self.post("/api/plans/propose", {
            "operation_id": prefix + "P" * 20, "goal_id": goal_id,
            "start_on": "2026-10-05"}, token)[1]["selected"]["pending_proposals"][0]
        self.post("/api/plans/decide", {"operation_id": prefix + "D" * 20,
                  "proposal_id": proposal["id"], "decision": "accept"}, token)
        state = self.post("/api/plans/sync", {"operation_id": prefix + "S" * 20,
                                             "goal_id": goal_id}, token)[1]
        self.assertEqual(state["selected"]["sync"]["state"], "applied")
        return goal_id, state["selected"]["today_tasks"][0]["task_id"]

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
        for filename in ("room-day.png", "desk-front.png"):
            connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
            connection.request("GET", "/scene-assets/" + filename,
                               headers={"Host": f"127.0.0.1:{self.port}"})
            asset = connection.getresponse()
            self.assertEqual(asset.status, 200, filename)
            self.assertEqual(asset.getheader("Content-Type"), "image/png")
            self.assertTrue(asset.read().startswith(b"\x89PNG\r\n\x1a\n"))
            connection.close()
        self.assertEqual(self.request("GET", "/scene-assets/../goal-scene.js")[0], 404)
        self.assertEqual(self.request("GET", "/scene-assets/unlisted.png")[0], 404)
        self.assertEqual(self.request("GET", "/scene-assets/desk-front.png?extra=1")[0], 404)

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

    def test_completed_result_waits_across_restart_then_is_confirmed_once(self):
        token = self.request("GET", "/api/state")[1]["csrf_token"]
        goal_id, task_id = self.active_goal(token, "C")
        evidence = {"material_ref": "虚构练习材料", "first_attempt_ref": "虚构首次作答",
                    "reflection_ref": "虚构错因复盘"}
        self.assertEqual(self.post("/api/tasks/complete", {
            "operation_id": "C" * 22, "goal_id": goal_id, "task_id": task_id,
            "evidence": {"material_ref": evidence["material_ref"],
                         "reflection_ref": evidence["reflection_ref"]}}, token)[0], 400)
        status, done, _ = self.post("/api/tasks/complete", {
            "operation_id": "D" * 22, "goal_id": goal_id, "task_id": task_id,
            "evidence": evidence}, token)
        self.assertEqual(status, 200, done)
        self.assertEqual(done["selected"]["result_status"]["tasks"][0]["state"],
                         "awaiting_user_confirmation")
        self.stop_server()
        self.start_server()
        self.now = datetime(2026, 10, 7, 2, 0, tzinfo=timezone.utc)
        state = self.request("GET", "/api/state?goal_id=" + goal_id)[1]
        self.assertNotIn(task_id, {item["task_id"] for item in state["selected"]["today_tasks"]})
        self.assertEqual(state["selected"]["result_status"]["tasks"][0]["state"],
                         "awaiting_user_confirmation")
        token = state["csrf_token"]
        payload = {"operation_id": "R" * 22, "goal_id": goal_id, "task_id": task_id,
                   "actual_minutes": 27, "metric": {"correct": 11, "total": 20, "expected": 14},
                   "evidence_ref": "虚构首次作答位置", "note": "本人只记录首次得分"}
        self.assertEqual(self.request("POST", "/api/results/confirm", payload,
                                      origin="http://evil.example", csrf=token,
                                      content_type="application/json")[0], 403)
        self.assertEqual(self.post("/api/results/confirm", payload, token)[0], 200)
        again = self.post("/api/results/confirm", {**payload, "operation_id": "Q" * 22}, token)[1]
        self.assertEqual(len(again["selected"]["results"]), 1)
        self.assertEqual(again["selected"]["result_status"]["tasks"][0]["state"], "recorded")
        self.assertEqual(again["selected"]["results"][0]["metric"]["correct"], 11)
        corrected = self.post("/api/results/confirm", {
            **payload, "operation_id": "Z" * 22, "correct": True,
            "metric": {"correct": 12, "total": 20, "expected": 14},
            "note": "本人更正首次得分"}, token)[1]
        self.assertEqual([item["metric"]["correct"] for item in corrected["selected"]["results"]], [11, 12])

    def test_unfinished_report_review_accept_decline_and_goal_isolation(self):
        token = self.request("GET", "/api/state")[1]["csrf_token"]
        first_goal, first_task = self.active_goal(token, "M")
        second_goal, second_task = self.active_goal(token, "N")
        report = {"operation_id": "U" * 22, "goal_id": first_goal, "task_id": first_task,
                  "outcome": "missed", "actual_minutes": 0, "metric": None,
                  "evidence_ref": None, "note": "虚构课程冲突"}
        first = self.post("/api/results/report", report, token)[1]
        self.assertEqual(first["selected"]["active_plan"]["items"][0]["daily_state"], "scheduled")
        self.assertEqual(first["selected"]["results"][0]["outcome"], "missed")
        repeat = self.post("/api/results/report", {**report, "operation_id": "V" * 22}, token)[1]
        self.assertEqual(len(repeat["selected"]["results"]), 1)
        self.now = datetime(2026, 10, 6, 2, 0, tzinfo=timezone.utc)
        next_day = self.post("/api/results/report", {**report, "operation_id": "B" * 22}, token)[1]
        self.assertEqual(len(next_day["selected"]["results"]), 2)
        self.assertNotEqual(next_day["selected"]["results"][0]["id"],
                            next_day["selected"]["results"][1]["id"])
        same_next_day = self.post("/api/results/report", {**report, "operation_id": "E" * 22}, token)[1]
        self.assertEqual(len(same_next_day["selected"]["results"]), 2)
        self.assertEqual(self.request("GET", "/api/state?goal_id=" + second_goal)[1]
                         ["selected"]["results"], [])
        result_id = first["selected"]["results"][0]["id"]
        reviewed = self.post("/api/reviews/propose", {"operation_id": "W" * 22,
            "goal_id": first_goal, "result_id": result_id}, token)[1]
        self.assertEqual(len(reviewed["selected"]["reviews"]), 1)
        proposal = reviewed["selected"]["pending_proposals"][0]
        self.assertEqual(proposal["method"], "manual")
        self.assertEqual(proposal["base_version"], 1)
        self.assertEqual(reviewed["selected"]["sync"]["state"], "applied")
        accepted = self.post("/api/plans/decide", {"operation_id": "X" * 22,
            "proposal_id": proposal["id"], "decision": "accept"}, token)[1]
        self.assertEqual(accepted["selected"]["goal"]["active_version"], 2)
        self.assertEqual(accepted["selected"]["sync"]["state"], "applied")
        retried_review = self.post("/api/reviews/propose", {"operation_id": "K" * 22,
            "goal_id": first_goal, "result_id": result_id}, token)[1]
        self.assertEqual(retried_review["selected"]["goal"]["active_version"], 2)
        self.assertEqual(len(retried_review["selected"]["reviews"]), 1)
        self.assertEqual(retried_review["selected"]["pending_proposals"], [])
        second_report = self.post("/api/results/report", {**report,
            "operation_id": "Y" * 22, "goal_id": second_goal, "task_id": second_task,
            "outcome": "partial", "actual_minutes": 12, "note": "虚构只练了一部分"}, token)[1]
        second_result_id = second_report["selected"]["results"][0]["id"]
        second_review = self.post("/api/reviews/propose", {"operation_id": "I" * 22,
            "goal_id": second_goal, "result_id": second_result_id}, token)[1]
        declined = self.post("/api/plans/decide", {"operation_id": "J" * 22,
            "proposal_id": second_review["selected"]["pending_proposals"][0]["id"],
            "decision": "decline"}, token)[1]
        self.assertEqual(declined["selected"]["goal"]["active_version"], 1)
        self.assertEqual(declined["selected"]["sync"]["state"], "applied")
        retried_declined = self.post("/api/reviews/propose", {"operation_id": "L" * 22,
            "goal_id": second_goal, "result_id": second_result_id}, token)[1]
        self.assertEqual(len(retried_declined["selected"]["reviews"]), 1)
        self.assertEqual(retried_declined["selected"]["pending_proposals"], [])
        self.assertEqual(len(self.request("GET", "/api/state?goal_id=" + first_goal)[1]
                             ["selected"]["results"]), 2)


if __name__ == "__main__":
    unittest.main()
