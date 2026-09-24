#!/usr/bin/env python3
"""Run the private goal companion on loopback only."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workbench.goal_web import serve


def main():
    parser = argparse.ArgumentParser(description="本机目标工作台")
    parser.add_argument("--workspace", default="private/goal-companion",
                        help="本机私有数据目录，默认 private/goal-companion")
    parser.add_argument("--port", type=int, default=8794, help="本机端口，默认 8794")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("端口需要在 0–65535 之间")
    serve(args.workspace, args.port)


if __name__ == "__main__":
    main()
