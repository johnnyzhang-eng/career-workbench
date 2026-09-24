"""Compare compact-only camera distance in real Godot windows, without FOV edits."""

import hashlib
import json
import platform
import re
import struct
import subprocess
import time
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "prototype" / "godot"
OUT = ROOT / "prototype" / "comparison" / "compact_distance_experiment"
GODOT = Path("/Applications/Godot.app/Contents/MacOS/Godot")
VARIANTS = {"P0": 1.0, "P1": 0.93}
SIZES = ((360, 320), (1280, 720))
PHASES = ("day", "evening")
SOURCES = (
    PROJECT / "main.gd", PROJECT / "comparison" / "room_3d.gd",
    PROJECT / "comparison" / "comparison.gd", PROJECT / "project.godot",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_rgba(path):
    """Decode the engine's 8-bit RGBA PNG for exact scene-only comparison."""
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    chunks = []
    offset = 8
    while offset < len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + size]
        chunks.append((kind, payload))
        offset += size + 12
    header = next(payload for kind, payload in chunks if kind == b"IHDR")
    width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", header)
    assert (depth, color, interlace) == (8, 6, 0)
    stream = zlib.decompress(b"".join(payload for kind, payload in chunks if kind == b"IDAT"))
    stride = width * 4
    rows = []
    previous = bytearray(stride)
    index = 0
    for _ in range(height):
        filter_type = stream[index]
        current = bytearray(stream[index + 1:index + 1 + stride])
        index += stride + 1
        for x in range(stride):
            a = current[x - 4] if x >= 4 else 0
            b = previous[x]
            c = previous[x - 4] if x >= 4 else 0
            if filter_type == 1:
                current[x] = (current[x] + a) & 255
            elif filter_type == 2:
                current[x] = (current[x] + b) & 255
            elif filter_type == 3:
                current[x] = (current[x] + ((a + b) // 2)) & 255
            elif filter_type == 4:
                p = a + b - c
                distances = (abs(p - a), abs(p - b), abs(p - c))
                current[x] = (current[x] + (a, b, c)[distances.index(min(distances))]) & 255
            else:
                assert filter_type == 0
        rows.append(bytes(current))
        previous = current
    assert index == len(stream)
    return width, height, rows


def scene_digest(path, rect, display_scale):
    width, height, rows = png_rgba(path)
    x, y, w, h = (round(value * display_scale) for value in rect)
    assert x >= 0 and y >= 0 and x + w <= width and y + h <= height
    content = b"".join(row[x * 4:(x + w) * 4] for row in rows[y:y + h])
    return hashlib.sha256(content).hexdigest()


def run():
    if not GODOT.is_file():
        raise SystemExit(f"Godot executable not found: {GODOT}")
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for variant, scale in VARIANTS.items():
        folder = OUT / variant
        folder.mkdir(exist_ok=True)
        for width, height in SIZES:
            for phase in PHASES:
                proof = width == 360
                cmd = [
                    str(GODOT), "--path", str(PROJECT),
                    "res://comparison/compact_distance_experiment.tscn", "--",
                    "--route=baseline", f"--size={width}x{height}",
                    f"--phase={phase}", f"--compact-distance-scale={scale}",
                    f"--out={folder}", "--capture", "--quit",
                ]
                if proof:
                    cmd.append("--proof")
                started = time.monotonic()
                result = subprocess.run(cmd, text=True, capture_output=True, timeout=50)
                output = result.stdout + result.stderr
                log = re.sub(r"/Users/[^/]+/", "/Users/<local>/", output.replace(str(ROOT), "<repo>"))
                log_path = folder / f"{width}x{height}-{phase}.log"
                log_path.write_text(log)
                metrics_lines = [line.removeprefix("COMPACT_METRICS ") for line in output.splitlines()
                                 if line.startswith("COMPACT_METRICS ")]
                png = folder / f"baseline-{width}x{height}-{phase}-idle.png"
                info = folder / f"baseline-{width}x{height}-{phase}.json"
                ok = (result.returncode == 0 and "SCRIPT ERROR" not in output
                      and "ERROR:" not in output and len(metrics_lines) == 1
                      and png.is_file() and info.is_file()
                      and (not proof or "COMPARISON_PROOF_PASS baseline" in output))
                if not ok:
                    raise RuntimeError(f"{variant} {width}x{height} {phase}: {log[-4000:]}")
                metrics = json.loads(metrics_lines[0])
                assert metrics["fov_degrees"] == 45.0
                assert metrics["distance_scale"] == (scale if proof else 1.0)
                capture = json.loads(info.read_text())
                if proof:
                    assert any(event.get("check") == "hotspot_clicks_pass" for event in capture["events"])
                png_width, png_height, _ = png_rgba(png)
                assert [png_width, png_height] == capture["window_pixels"]
                record = {
                    "variant": variant, "compact_distance_scale": scale,
                    "logical_size": [width, height], "phase": phase,
                    "wall_seconds": round(time.monotonic() - started, 3),
                    "png": str(png.relative_to(OUT)), "png_sha256": sha256(png),
                    "json": str(info.relative_to(OUT)), "log": str(log_path.relative_to(OUT)),
                    "scene_sha256": scene_digest(png, metrics["scene_rect"], capture["display_scale"]),
                    "metrics": metrics, "capture": capture,
                }
                records.append(record)
                print(f"{variant} {width}x{height} {phase}: OK", flush=True)
    for phase in PHASES:
        old = next(r for r in records if r["variant"] == "P0" and r["phase"] == phase and r["logical_size"][0] == 1280)
        new = next(r for r in records if r["variant"] == "P1" and r["phase"] == phase and r["logical_size"][0] == 1280)
        assert old["scene_sha256"] == new["scene_sha256"], "Full-window scene changed"
    manifest = {
        "purpose": "A-baseline compact-only camera distance along unchanged view ray",
        "platform": platform.platform(),
        "source_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in SOURCES},
        "settings": {"route": "baseline", "changed_parameter": "compact_camera_distance_scale",
                     "P0": 1.0, "P1": 0.93, "fov_degrees": 45.0,
                     "camera_target": [0, 1.25, 0], "full_window_distance_scale": 1.0},
        "records": records,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    run()
