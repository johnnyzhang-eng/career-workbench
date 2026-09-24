#!/usr/bin/env python3
"""Local daily checklist commands; all personal data stays in private/."""

import argparse
import json
import sqlite3
from pathlib import Path

from workbench.daily import DailyStore, require


ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default="private/me")
    sub = parser.add_subparsers(dest="command", required=True)
    view = sub.add_parser("snapshot")
    view.add_argument("--timezone", default="Asia/Shanghai")
    sub.add_parser("reminders")
    for name in ("schedule", "start", "complete", "defer", "block", "cancel"):
        sub.add_parser(name).add_argument("file", help="JSON command envelope inside private/")
    args = parser.parse_args()
    try:
        workspace = (ROOT / args.workspace).resolve()
        require(workspace.is_relative_to(ROOT / "private"), "workspace 必须在仓库 private/ 内")
        store = DailyStore(workspace)
        try:
            if args.command == "snapshot":
                result = store.snapshot(args.timezone)
            elif args.command == "reminders":
                result = store.claim_reminders()
            else:
                path = Path(args.file).resolve()
                require(path.is_relative_to(ROOT / "private"), "命令文件必须放在 private/ 内")
                envelope = json.loads(path.read_text(encoding="utf-8"))
                require(isinstance(envelope, dict)
                        and set(envelope) <= {"event_id", "task_id", "payload", "at"}
                        and {"event_id", "task_id"} <= set(envelope), "命令文件格式无效")
                result = store.command(args.command, **envelope)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        finally:
            store.close()
    except (ValueError, OSError, sqlite3.Error, TypeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"未执行：{exc}\n")


if __name__ == "__main__":
    main()
