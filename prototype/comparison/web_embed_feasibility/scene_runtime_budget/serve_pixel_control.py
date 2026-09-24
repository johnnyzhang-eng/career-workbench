#!/usr/bin/env python3
"""Serve only committed 2D scene files from a specified Career Workbench worktree."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSETS = frozenset({"room-day.png", "room-evening.png", "avatar-idle.png", "avatar-desk.png",
                    "avatar-study.png", "avatar-interview.png", "avatar-rest.png", "desk-front.png"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True,
                        help="A worktree containing the committed docs/goal-scene.js and docs/scene-assets files")
    parser.add_argument("--port", type=int, default=8834)
    args = parser.parse_args()
    source = args.source_root.resolve() / "docs"
    if not (source / "goal-scene.js").is_file() or not all((source / "scene-assets" / name).is_file() for name in ASSETS):
        parser.error("source root does not contain the committed 2D scene renderer and all assets")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/":
                file = HERE / "pixel_control.html"
                content_type = "text/html; charset=utf-8"
            elif path == "/goal-scene.js":
                file = source / "goal-scene.js"
                content_type = "text/javascript; charset=utf-8"
            elif path.startswith("/scene-assets/") and path.rsplit("/", 1)[-1] in ASSETS:
                file = source / "scene-assets" / path.rsplit("/", 1)[-1]
                content_type = "image/png"
            else:
                self.send_error(404)
                return
            body = file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Fictional 2D renderer control at http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
