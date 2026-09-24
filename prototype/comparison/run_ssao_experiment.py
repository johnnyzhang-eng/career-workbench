"""Capture a single Godot 4.7 Compatibility SSAO toggle on the original A scene."""

import hashlib
import json
import re
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "prototype" / "godot"
OUT = ROOT / "prototype" / "comparison" / "ssao_experiment"
GODOT = Path("/Applications/Godot.app/Contents/MacOS/Godot")
SIZES = ((360, 320), (1280, 720))
PHASES = ("day", "evening")
SOURCES = (
    PROJECT / "main.gd",
    PROJECT / "comparison" / "room_3d.gd",
    PROJECT / "comparison" / "comparison.gd",
    PROJECT / "project.godot",
    PROJECT / "comparison" / "ssao_room.gd",
    PROJECT / "comparison" / "ssao_experiment.gd",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_dimensions(path):
    data = path.read_bytes()[:24]
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return [int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")]


def scene_crop(size):
    width, height = size
    if width == 360:
        return (16, 92, 688, 282)
    return (32, 188, (width - 310 - 48) * 2, (height - 170) * 2)


def rgb_crop(path, rect):
    x, y, width, height = rect
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"crop={width}:{height}:{x}:{y}",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
        capture_output=True, check=True,
    )
    assert len(result.stdout) == width * height * 3
    return result.stdout


def scene_difference(first, second, size):
    rect = scene_crop(size)
    a, b = rgb_crop(first, rect), rgb_crop(second, rect)
    total = sum(abs(x - y) for x, y in zip(a, b))
    changed = sum(1 for i in range(0, len(a), 3)
                  if max(abs(a[i + j] - b[i + j]) for j in range(3)) >= 3)
    return {"crop_physical_xywh": rect, "mean_absolute_rgb_0_255": round(total / len(a), 4),
            "pixels_changed_at_least_3": changed, "crop_pixels": len(a) // 3,
            "changed_percent": round(changed / (len(a) // 3) * 100, 3)}


def run():
    if not GODOT.is_file():
        raise SystemExit(f"Godot executable missing: {GODOT}")
    OUT.mkdir(exist_ok=True)
    records = []
    for variant, enabled in (("S0", False), ("S1", True)):
        folder = OUT / variant
        folder.mkdir(exist_ok=True)
        for size in SIZES:
            width, height = size
            for phase in PHASES:
                cmd = [str(GODOT), "--path", str(PROJECT),
                       "res://comparison/ssao_experiment.tscn", "--", "--route=baseline",
                       f"--size={width}x{height}", f"--phase={phase}",
                       f"--out={folder}", "--capture", "--quit"]
                if enabled:
                    cmd.append("--experiment-ssao")
                started = time.monotonic()
                result = subprocess.run(cmd, text=True, capture_output=True, timeout=45)
                output = (result.stdout + result.stderr).replace(str(ROOT), "<repo>")
                output = re.sub(r"/Users/[^/]+/", "/Users/<local>/", output)
                stem = f"baseline-{width}x{height}-{phase}"
                png = folder / f"{stem}-idle.png"
                capture = folder / f"{stem}.json"
                log = folder / f"{width}x{height}-{phase}.log"
                log.write_text(output)
                ok = (result.returncode == 0 and "SCRIPT ERROR" not in output and "ERROR:" not in output
                      and f"SSAO_VARIANT {variant}" in output
                      and f"SSAO_ENABLED {str(enabled).lower()}" in output
                      and png.is_file() and capture.is_file())
                record = {"variant": variant, "logical_size": size, "phase": phase,
                          "ok": ok, "wall_seconds": round(time.monotonic() - started, 3),
                          "png": str(png.relative_to(OUT)), "capture": str(capture.relative_to(OUT)),
                          "log": str(log.relative_to(OUT))}
                if ok:
                    record["physical_pixels"] = png_dimensions(png)
                    record["sha256"] = sha256(png)
                records.append(record)
                print(f"{variant} {width}x{height} {phase}: {'OK' if ok else 'FAIL'}", flush=True)
                if not ok:
                    raise SystemExit(output)
    differences = []
    for size in SIZES:
        width, height = size
        for phase in PHASES:
            name = f"baseline-{width}x{height}-{phase}-idle.png"
            differences.append({"logical_size": size, "phase": phase,
                                **scene_difference(OUT / "S0" / name, OUT / "S1" / name, size)})
    manifest = {
        "purpose": "single-toggle SSAO on original A 3D scene",
        "godot_version": subprocess.check_output([str(GODOT), "--version"], text=True).strip(),
        "renderer": "Godot 4.7 GL Compatibility",
        "variable": "Environment.ssao_enabled false to true; default radius and intensity",
        "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in SOURCES},
        "records": records, "scene_difference": differences,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    run()
