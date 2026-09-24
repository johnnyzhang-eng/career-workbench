"""Command-hook entrypoint. The user installs/trusts this explicitly in Codex."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workbench.codex_hooks import ingest_codex_hook  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--connection", default="codex-hooks")
    args = parser.parse_args(argv)
    try:
        payload = json.load(sys.stdin)
        ingest_codex_hook(args.workspace, args.connection, payload)
    except Exception:
        # Never print hook input, paths, exception strings, or a traceback.
        print("Career Workbench activity hook skipped an event", file=sys.stderr)
    # Hook failure must never block a user's Codex turn. Stop requires JSON stdout.
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
