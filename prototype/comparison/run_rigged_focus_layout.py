"""Compare original and room-first compact UI with the same R2 typing pose."""

import json
import re
import subprocess
from pathlib import Path

from run_activity_focus_layout import GODOT, PROJECT, SCENE, digest, png_size


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "prototype" / "comparison" / "activity_focus_layout" / "rigged"


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for variant, focus in (("L0", False), ("L1", True)):
        folder = OUT / variant
        folder.mkdir(exist_ok=True)
        for phase in ("day", "evening"):
            cmd = [str(GODOT), "--path", str(PROJECT), SCENE, "--",
                   "--route=baseline", "--size=360x320", f"--phase={phase}",
                   f"--out={folder}", "--rigged-character", "--capture", "--proof", "--quit"]
            if focus:
                cmd.append("--activity-focus-layout")
            result = subprocess.run(cmd, text=True, capture_output=True, timeout=60)
            log = (result.stdout + result.stderr).replace(str(ROOT), "<repo>")
            log = re.sub(r"/Users/[^/]+/", "/Users/<local>/", log)
            (folder / f"360x320-{phase}.log").write_text(log)
            captures = []
            for state in ("idle", "started"):
                path = folder / f"baseline-360x320-{phase}-{state}.png"
                if path.is_file():
                    captures.append({"state": state, "file": str(path.relative_to(OUT)),
                                     "size_pixels": png_size(path), "sha256": digest(path)})
            info = folder / f"baseline-360x320-{phase}.json"
            ok = (result.returncode == 0 and "SCRIPT ERROR" not in log and "ERROR:" not in log
                  and "R2_GODOT_IMPORT" in log and len(captures) == 2 and info.is_file())
            records.append({"variant": variant, "phase": phase, "ok": ok,
                            "capture": json.loads(info.read_text()) if info.is_file() else None,
                            "captures": captures})
            print(f"rigged {variant} {phase}: {'OK' if ok else 'FAIL'}", flush=True)
            if not ok:
                raise SystemExit(log)
    (OUT / "manifest.json").write_text(json.dumps({
        "purpose": "R2 fixed typing pose under L0/L1 compact layouts",
        "source_commit": "de9335f", "animation": "TypingLoop at 0.45 s; speed_scale=0",
        "records": records,
    }, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    run()
