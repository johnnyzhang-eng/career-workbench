"""Loopback-only HTTP entrypoint for the local goal workbench."""

import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .avatar_photo import AvatarPhotoStore
from .goal_app import GoalApp


HTML = Path(__file__).resolve().parents[1] / "docs" / "goal-companion.html"
SCENE_JS = Path(__file__).resolve().parents[1] / "docs" / "goal-scene.js"
SCENE_ASSETS = Path(__file__).resolve().parents[1] / "docs" / "scene-assets"
SCENE_ASSET_NAMES = frozenset({"room-day.png", "room-evening.png", "avatar-idle.png",
                               "avatar-desk.png", "avatar-study.png", "avatar-interview.png",
                               "avatar-rest.png"})
ROUTES = {"/api/goals": "create_goal", "/api/plans/propose": "propose_plan",
          "/api/plans/decide": "decide_plan", "/api/plans/sync": "sync_plan",
          "/api/tasks/complete": "complete_task",
          "/api/actions/start": "start_action", "/api/actions/pause": "pause_action",
          "/api/actions/resume": "resume_action", "/api/actions/stop": "stop_action"}


class GoalHTTPServer(HTTPServer):
    allow_reuse_address = True

    def __init__(self, address, workspace, clock=None):
        host, _port = address
        if host != "127.0.0.1":
            raise ValueError("目标工作台只允许绑定 127.0.0.1")
        self.app = GoalApp(workspace, clock)
        self.avatar_photo = AvatarPhotoStore(workspace)
        self.csrf_token = secrets.token_urlsafe(32)
        super().__init__(address, GoalHandler)


class GoalHandler(BaseHTTPRequestHandler):
    server_version = "GoalCompanion/0.1"

    def log_message(self, _format, *_args):
        # Paths may contain personal goal IDs; never print them by default.
        pass

    def _allowed_host(self):
        host = self.headers.get("Host", "")
        port = self.server.server_address[1]
        return host in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _security_headers(self, nonce=None):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if nonce:
            self.send_header("Content-Security-Policy", "default-src 'none'; "
                             f"script-src 'self' 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                             "connect-src 'self'; img-src 'self' data: blob:; "
                             "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")

    def _send(self, code, data, content_type="application/json; charset=utf-8", nonce=None):
        body = (json.dumps(data, ensure_ascii=False).encode("utf-8")
                if isinstance(data, (dict, list)) else data)
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._security_headers(nonce)
        self.end_headers()
        self.wfile.write(body)

    def _origin_allowed(self):
        port = self.server.server_address[1]
        host = self.headers.get("Host", "")
        return (self.headers.get("Origin") == f"http://{host}"
                and host in {f"127.0.0.1:{port}", f"localhost:{port}"})

    def _checked_path(self):
        parsed = urlsplit(self.path)
        if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
            raise ValueError("请求路径无效")
        return parsed

    def do_GET(self):
        if not self._allowed_host():
            self._send(403, {"error": "请求来源无效"})
            return
        try:
            parsed = self._checked_path()
            if parsed.path in {"/", "/compact", "/collapsed"}:
                nonce = secrets.token_urlsafe(20)
                body = HTML.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8", nonce)
            elif parsed.path == "/goal-scene.js" and SCENE_JS.is_file():
                self._send(200, SCENE_JS.read_bytes(), "text/javascript; charset=utf-8")
            elif (parsed.path.startswith("/scene-assets/") and not parsed.query
                  and parsed.path.removeprefix("/scene-assets/") in SCENE_ASSET_NAMES):
                asset = SCENE_ASSETS / parsed.path.removeprefix("/scene-assets/")
                if asset.is_file():
                    self._send(200, asset.read_bytes(), "image/png")
                else:
                    self._send(404, {"error": "场景素材尚未准备好"})
            elif parsed.path == "/api/state":
                query = parse_qs(parsed.query)
                goal_id = query.get("goal_id", [None])[0]
                state = self.server.app.state(goal_id)
                state["csrf_token"] = self.server.csrf_token
                self._send(200, state)
            elif parsed.path == "/api/avatar/photo/status" and not parsed.query:
                self._send(200, self.server.avatar_photo.status())
            elif parsed.path == "/api/avatar/photo/image" and not parsed.query:
                if not secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), self.server.csrf_token):
                    self._send(403, {"error": "页面令牌无效，请刷新"})
                    return
                try:
                    data, mime_type = self.server.avatar_photo.read()
                except FileNotFoundError:
                    self._send(404, {"error": "还没有选择照片"})
                else:
                    self._send(200, data, mime_type)
            else:
                self._send(404, {"error": "页面不存在"})
        except ValueError as exc:
            self._send(400, {"error": str(exc)})

    def do_POST(self):
        if not self._allowed_host() or not self._origin_allowed():
            self._send(403, {"error": "写入只接受本窗口的同源请求"})
            return
        if not secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), self.server.csrf_token):
            self._send(403, {"error": "页面令牌无效，请刷新"})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self._send(415, {"error": "请求需要 JSON"})
            return
        try:
            parsed = self._checked_path()
            method_name = ROUTES.get(parsed.path)
            avatar_route = parsed.path in {"/api/avatar/photo", "/api/avatar/photo/delete"}
            if (method_name is None and not avatar_route) or parsed.query:
                self._send(404, {"error": "操作不存在"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            maximum = 2_700_000 if parsed.path == "/api/avatar/photo" else 32768
            if not 0 < length <= maximum:
                self._send(413, {"error": "请求体过大或为空"})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("请求需要对象")
            if parsed.path == "/api/avatar/photo":
                state = self.server.avatar_photo.save(payload.get("data_base64"), payload.get("mime_type"))
            elif parsed.path == "/api/avatar/photo/delete":
                state = self.server.avatar_photo.delete()
            else:
                state = getattr(self.server.app, method_name)(payload)
            state["csrf_token"] = self.server.csrf_token
            self._send(200, state)
        except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})


def serve(workspace, port=8794):
    server = GoalHTTPServer(("127.0.0.1", port), workspace)
    try:
        print(f"目标工作台：http://127.0.0.1:{server.server_address[1]}/", flush=True)
        print("仅本机访问；使用 Ctrl-C 停止。", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        print("目标工作台已停止。", flush=True)
    finally:
        server.server_close()
