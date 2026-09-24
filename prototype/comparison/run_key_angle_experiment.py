"""Capture the original 3D scene with one directional-light pitch change."""

import hashlib
import json
import platform
import re
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "prototype" / "godot"
OUT = ROOT / "prototype" / "comparison" / "key_angle_experiment"
GODOT = Path("/Applications/Godot.app/Contents/MacOS/Godot")
VARIANTS = {"K0": -55.0, "K1": -65.0}
SIZES = ((360, 320), (1280, 720))
PHASES = ("day", "evening")
SOURCES = (
    PROJECT / "main.gd",
    PROJECT / "comparison" / "room_3d.gd",
    PROJECT / "comparison" / "comparison.gd",
    PROJECT / "project.godot",
)
LIGHT_RE = re.compile(
    r"KEY_LIGHT_ACTUAL phase=(\w+) pitch=([\d.-]+) yaw=([\d.-]+) "
    r"roll=([\d.-]+) energy=([\d.-]+) ambient=([\d.-]+)"
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
    for variant, pitch in VARIANTS.items():
        folder = OUT / variant
        folder.mkdir(exist_ok=True)
        for width, height in SIZES:
            for phase in PHASES:
                cmd = [
                    str(GODOT), "--path", str(PROJECT),
                    "res://comparison/key_angle_experiment.tscn", "--",
                    "--route=baseline", f"--size={width}x{height}",
                    f"--phase={phase}", f"--key-pitch-degrees={pitch}",
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
                measurements = [m.groups() for m in LIGHT_RE.finditer(output)]
                matching = [m for m in measurements if m[0] == phase]
                expected_main = 0.35 if phase == "evening" else 0.65
                expected_ambient = 0.48 if phase == "evening" else 0.36
                # Superclass construction briefly reports A's pitch before the
                # experiment sets it; the final phase report is the capture state.
                actual_ok = bool(matching) and measurements[-1][0] == phase and all(
                    abs(float(m[1]) - pitch) < 0.001
                    and abs(float(m[2]) + 32.0) < 0.001
                    and abs(float(m[3])) < 0.001
                    and abs(float(m[4]) - expected_main) < 0.001
                    and abs(float(m[5]) - expected_ambient) < 0.001
                    for m in matching[-1:]
                )
                ok = (result.returncode == 0 and "SCRIPT ERROR" not in output
                      and "ERROR:" not in output and png.is_file()
                      and info.is_file() and actual_ok)
                record = {
                    "variant": variant, "key_pitch_degrees": pitch,
                    "logical_size": [width, height], "phase": phase,
                    "ok": ok, "wall_seconds": round(time.monotonic() - started, 3),
                    "reported_light": [list(m) for m in matching],
                    "png": str(png.relative_to(OUT)),
                    "json": str(info.relative_to(OUT)),
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
        "purpose": "single-factor A-baseline directional key pitch test",
        "platform": platform.platform(),
        "source_sha256": source_hashes,
        "settings": {
            "renderer": "GL Compatibility", "route": "baseline", "state": "idle",
            "changed_parameter": "DirectionalLight3D.rotation_degrees.x",
            "K0_pitch_degrees": -55.0, "K1_pitch_degrees": -65.0,
            "unchanged_yaw_degrees": -32.0,
            "unchanged_ambient_energy": {"day": 0.36, "evening": 0.48},
            "unchanged_key_energy": {"day": 0.65, "evening": 0.35},
        },
        "records": records,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    run()
