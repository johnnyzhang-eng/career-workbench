"""Capture one compact layout change against the original A comparison UI."""

import hashlib
import json
import platform
import re
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "prototype" / "godot"
OUT = ROOT / "prototype" / "comparison" / "activity_focus_layout"
GODOT = Path("/Applications/Godot.app/Contents/MacOS/Godot")
SCENE = "res://comparison/activity_focus_layout.tscn"
SIZES = ((360, 320), (1280, 720))
PHASES = ("day", "evening")
SOURCES = (
    PROJECT / "main.gd",
    PROJECT / "comparison" / "room_3d.gd",
    PROJECT / "comparison" / "comparison.gd",
    PROJECT / "comparison" / "activity_focus_layout.gd",
    PROJECT / "project.godot",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_size(path):
    data = path.read_bytes()[:24]
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return [int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")]


def run():
    if not GODOT.is_file():
        raise SystemExit("本机没有预期的 Godot 可执行文件")
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for name, focus in (("L0", False), ("L1", True)):
        folder = OUT / name
        folder.mkdir(exist_ok=True)
        for width, height in SIZES:
            for phase in PHASES:
                cmd = [str(GODOT), "--path", str(PROJECT), SCENE, "--",
                       "--route=baseline", f"--size={width}x{height}",
                       f"--phase={phase}", f"--out={folder}",
                       "--fixed-clock", "--capture", "--proof", "--quit"]
                if focus:
                    cmd.append("--activity-focus-layout")
                start = time.monotonic()
                result = subprocess.run(cmd, text=True, capture_output=True, timeout=60)
                log = (result.stdout + result.stderr).replace(str(ROOT), "<repo>")
                log = re.sub(r"/Users/[^/]+/", "/Users/<local>/", log)
                (folder / f"{width}x{height}-{phase}.log").write_text(log)
                captures = []
                for state in ("idle", "started"):
                    path = folder / f"baseline-{width}x{height}-{phase}-{state}.png"
                    if path.is_file():
                        captures.append({"state": state, "file": str(path.relative_to(OUT)),
                                         "size_pixels": png_size(path), "sha256": digest(path)})
                metadata = folder / f"baseline-{width}x{height}-{phase}.json"
                ok = (result.returncode == 0 and "SCRIPT ERROR" not in log
                      and "ERROR:" not in log and len(captures) == 2
                      and metadata.is_file())
                records.append({"variant": name, "focus_layout": focus,
                                "logical_size": [width, height], "phase": phase,
                                "ok": ok, "wall_seconds": round(time.monotonic() - start, 3),
                                "captures": captures,
                                "capture_meta": json.loads(metadata.read_text()) if metadata.is_file() else None})
                print(f"{name} {width}x{height} {phase}: {'OK' if ok else 'FAIL'}", flush=True)
                if not ok:
                    raise SystemExit(log)
    (OUT / "manifest.json").write_text(json.dumps({
        "purpose": "original A compact scene allocation, 141 vs 222 logical pixels high",
        "platform": platform.platform(), "renderer": "GL Compatibility",
        "source_sha256": {str(path.relative_to(ROOT)): digest(path) for path in SOURCES},
        "records": records,
    }, ensure_ascii=False, indent=2) + "\n")
    for phase in PHASES:
        left = OUT / "L0" / f"baseline-1280x720-{phase}-idle.png"
        right = OUT / "L1" / f"baseline-1280x720-{phase}-idle.png"
        assert digest(left) == digest(right), "布局试验不应改动全窗待机画面"


if __name__ == "__main__":
    run()
