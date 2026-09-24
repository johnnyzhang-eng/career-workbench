"""Capture a one-factor ambient-light comparison in actual Godot windows."""

import hashlib
import json
import platform
import re
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "prototype" / "godot"
OUT = ROOT / "prototype" / "comparison" / "ambient_experiment"
GODOT = Path("/Applications/Godot.app/Contents/MacOS/Godot")
VARIANTS = {"A0": 1.0, "A1": 2.0 / 3.0}
SIZES = ((360, 320), (1280, 720))
PHASES = ("day", "evening")
SOURCES = (
    PROJECT / "main.gd",
    PROJECT / "comparison" / "room_3d.gd",
    PROJECT / "comparison" / "comparison.gd",
    PROJECT / "project.godot",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_dimensions(path):
    data = path.read_bytes()[:24]
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return [int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")]


def run():
    if not GODOT.is_file():
        raise SystemExit(f"Godot executable not found: {GODOT}")
    OUT.mkdir(parents=True, exist_ok=True)
    source_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in SOURCES}
    records = []
    for variant, multiplier in VARIANTS.items():
        folder = OUT / variant
        folder.mkdir(exist_ok=True)
        for width, height in SIZES:
            for phase in PHASES:
                cmd = [
                    str(GODOT), "--path", str(PROJECT),
                    "res://comparison/ambient_experiment.tscn", "--",
                    "--route=baseline", f"--size={width}x{height}",
                    f"--phase={phase}", f"--ambient-multiplier={multiplier:.12f}",
                    f"--out={folder}", "--capture", "--quit",
                ]
                started = time.monotonic()
                result = subprocess.run(cmd, text=True, capture_output=True, timeout=45)
                output = (result.stdout + result.stderr).replace(str(ROOT), "<repo>")
                output = re.sub(r"/Users/[^/]+/", "/Users/<local>/", output)
                log_file = folder / f"{width}x{height}-{phase}.log"
                log_file.write_text(output)
                png = folder / f"baseline-{width}x{height}-{phase}-idle.png"
                info = folder / f"baseline-{width}x{height}-{phase}.json"
                measured = re.findall(r"AMBIENT_ACTUAL phase=(\w+) multiplier=([\d.]+) energy=([\d.]+)", output)
                expected_energy = (0.36 if phase == "day" else 0.48) * multiplier
                matching = [item for item in measured if item[0] == phase]
                actual_ok = bool(matching) and measured[-1][0] == phase and all(
                    abs(float(item[2]) - expected_energy) < 0.0001
                    for item in matching
                )
                ok = result.returncode == 0 and "SCRIPT ERROR" not in output and "ERROR:" not in output and png.is_file() and info.is_file() and actual_ok
                record = {
                    "variant": variant, "ambient_multiplier": multiplier,
                    "logical_size": [width, height], "phase": phase,
                    "ok": ok, "wall_seconds": round(time.monotonic() - started, 3),
                    "reported_ambient_energy": [float(item[2]) for item in matching],
                    "png": str(png.relative_to(OUT)), "json": str(info.relative_to(OUT)),
                    "log": str(log_file.relative_to(OUT)),
                }
                if ok:
                    record["png_pixels"] = png_dimensions(png)
                    record["png_sha256"] = sha256(png)
                    record["capture"] = json.loads(info.read_text())
                records.append(record)
                print(f"{variant} {width}x{height} {phase}: {'OK' if ok else 'FAIL'}", flush=True)
                if not ok:
                    raise SystemExit(output)
    manifest = {
        "purpose": "single-factor A-baseline ambient-light test",
        "platform": platform.platform(), "source_sha256": source_hashes,
        "settings": {"renderer": "GL Compatibility", "route": "baseline", "state": "idle", "changed_parameter": "environment.ambient_light_energy", "A0": {"day": 0.36, "evening": 0.48}, "A1": {"day": 0.24, "evening": 0.32}},
        "records": records,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    run()
