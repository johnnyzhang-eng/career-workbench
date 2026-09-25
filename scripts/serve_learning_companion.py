#!/usr/bin/env python3
"""Serve the private learning resource workspace on loopback only."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workbench.learning_web import serve  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default="private/learning-demo")
    parser.add_argument("--port", type=int, default=8795)
    args = parser.parse_args()
    workspace = (ROOT / args.workspace).resolve()
    if not workspace.is_relative_to(ROOT / "private"):
        parser.error("本机工作区必须放在仓库 private/ 下")
    if not 0 <= args.port <= 65535:
        parser.error("端口需要在 0–65535 之间")
    serve(workspace, args.port)


if __name__ == "__main__":
    main()
