#!/usr/bin/env python3
"""Serve the scene-only export with fixture states or a local read-only API proxy."""

from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen


HERE = Path(__file__).resolve().parent
WEB = HERE / "_build/web"
DISPLAY_FIELDS = ("phase", "mode", "activity_state")
FIXTURES = {
    "planned_evening": {"phase": "evening", "mode": "idle", "activity_state": "planned"},
    "planned_study_evening": {"phase": "evening", "mode": "study", "activity_state": "planned"},
    "active_desk_day": {"phase": "day", "mode": "desk", "activity_state": "declared_active"},
    "active_study_day": {"phase": "day", "mode": "study", "activity_state": "declared_active"},
    "observed_interview_evening": {"phase": "evening", "mode": "interview", "activity_state": "observed"},
    "self_selected_rest_day": {"phase": "day", "mode": "rest", "activity_state": "self_selected"},
    "paused_evening": {"phase": "evening", "mode": "idle", "activity_state": "planned"},
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8822)
    parser.add_argument("--upstream", help="Only a loopback /api/state URL, e.g. http://127.0.0.1:8794/api/state")
    parser.add_argument("--fixture-file", type=Path, help="Optional local JSON scene read model, reread for each GET")
    args = parser.parse_args()
    if args.upstream and args.fixture_file:
        parser.error("choose --upstream or --fixture-file")
    if args.upstream:
        parsed_upstream = urlparse(args.upstream)
        if parsed_upstream.scheme != "http" or parsed_upstream.hostname not in {"127.0.0.1", "localhost"} or parsed_upstream.path != "/api/state":
            parser.error("--upstream must be an HTTP loopback /api/state URL")
    WEB.mkdir(parents=True, exist_ok=True)
    host_page = (HERE / "host.html").read_bytes()
    sequence_requests = [0]

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *handler_args, **kwargs):
            super().__init__(*handler_args, directory=str(WEB), **kwargs)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/host.html"}:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(host_page)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(host_page)
                return
            if parsed.path == "/api/state":
                try:
                    if args.upstream:
                        with urlopen(args.upstream, timeout=5) as response:
                            raw = response.read(2_000_000)
                        state = json.loads(raw)
                        scene = state.get("scene") or {}
                    elif args.fixture_file:
                        state = json.loads(args.fixture_file.read_text())
                        scene = state.get("scene") or {}
                    else:
                        key = parse_qs(parsed.query).get("demo", ["planned_evening"])[0]
                        if key == "sequence":
                            sequence_requests[0] += 1
                            request_number = sequence_requests[0]
                            scene = (FIXTURES["planned_evening"] if request_number <= 4 else
                                     FIXTURES["active_study_day"] if request_number <= 7 else
                                     FIXTURES["paused_evening"])
                        else:
                            scene = FIXTURES.get(key, FIXTURES["planned_evening"])
                    # Keep task IDs, titles, evidence and completion outside the bridge server.
                    payload = {"scene": {field: scene.get(field) for field in DISPLAY_FIELDS}}
                    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                except (OSError, ValueError, json.JSONDecodeError) as error:
                    body = json.dumps({"error": str(error)}).encode("utf-8")
                    self.send_response(502)
                else:
                    self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if not parsed.path.startswith("/godot/"):
                self.send_error(404)
                return
            self.path = parsed.path
            super().do_GET()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Scene bridge at http://127.0.0.1:{args.port}/; upstream={args.upstream or 'fictional fixture'}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
