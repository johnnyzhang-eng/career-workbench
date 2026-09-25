"""Loopback-only browser entrypoint for external chapter navigation."""

import json
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .learning import LearningStore


HTML = Path(__file__).resolve().parents[1] / "docs" / "learning-companion.html"
ROUTES = {"/api/profile": "set_profile", "/api/requirements": "add_requirement",
          "/api/choice": "choose", "/api/event": "record_event",
          "/api/access-issue": "report_access_issue"}


class LearningHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, address, workspace, clock=None):
        if address[0] != "127.0.0.1":
            raise ValueError("学习资源页面只允许绑定 127.0.0.1")
        self.workspace = workspace
        self.clock = clock
        self.csrf_token = secrets.token_urlsafe(32)
        super().__init__(address, LearningHandler)


class LearningHandler(BaseHTTPRequestHandler):
    server_version = "LearningResources/0.1"

    def log_message(self, _format, *_args):
        # URLs may contain a private job ID; never print request paths.
        pass

    def _allowed_host(self):
        port = self.server.server_address[1]
        return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _origin_allowed(self):
        host = self.headers.get("Host", "")
        return self.headers.get("Origin") == "http://" + host and self._allowed_host()

    def _send(self, code, data, content_type="application/json; charset=utf-8", nonce=None):
        body = (json.dumps(data, ensure_ascii=False).encode("utf-8")
                if isinstance(data, (dict, list)) else data)
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if nonce:
            self.send_header("Content-Security-Policy", "default-src 'none'; "
                             f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                             "connect-src 'self'; base-uri 'none'; form-action 'none'; "
                             "frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _path(self):
        parsed = urlsplit(self.path)
        if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
            raise ValueError("请求路径无效")
        return parsed

    def do_GET(self):
        if not self._allowed_host():
            self._send(403, {"error": "请求来源无效"})
            return
        try:
            parsed = self._path()
            query = parse_qs(parsed.query)
            if parsed.path == "/" and set(query) <= {"job_id"} and len(query.get("job_id", [])) <= 1:
                nonce = secrets.token_urlsafe(20)
                body = HTML.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8", nonce)
            elif parsed.path == "/api/state":
                if set(query) - {"job_id"} or len(query.get("job_id", [])) > 1:
                    raise ValueError("查询参数无效")
                with LearningStore(self.server.workspace, self.server.clock) as store:
                    state = store.state(query.get("job_id", [None])[0])
                state["csrf_token"] = self.server.csrf_token
                self._send(200, state)
            else:
                self._send(404, {"error": "页面不存在"})
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
        except (OSError, sqlite3.Error):
            self._send(503, {"error": "本机存储暂不可用；未确认读取结果"})

    def do_POST(self):
        if not self._allowed_host() or not self._origin_allowed():
            self._send(403, {"error": "写入只接受本机同源页面"})
            return
        if not secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), self.server.csrf_token):
            self._send(403, {"error": "页面令牌无效，请刷新"})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self._send(415, {"error": "请求需要 JSON"})
            return
        try:
            parsed = self._path()
            if parsed.path not in ROUTES or parsed.query:
                self._send(404, {"error": "操作不存在"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                self._send(413, {"error": "请求体过大或为空"})
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("请求需要对象")
            with LearningStore(self.server.workspace, self.server.clock) as store:
                state = getattr(store, ROUTES[parsed.path])(payload)
            state["csrf_token"] = self.server.csrf_token
            self._send(200, state)
        except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})
        except (OSError, sqlite3.Error):
            self._send(503, {"error": "本机存储暂不可用；操作未确认，请刷新核对后重试"})


def serve(workspace, port=8795):
    server = LearningHTTPServer(("127.0.0.1", port), workspace)
    try:
        print(f"学习资源页面：http://127.0.0.1:{server.server_address[1]}/", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        print("学习资源页面已停止。", flush=True)
    finally:
        server.server_close()
