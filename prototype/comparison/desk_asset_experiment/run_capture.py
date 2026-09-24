"""Render A/M2 desk comparison in actual Godot windows and log image deltas."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PROJECT = ROOT / "prototype/godot"
GODOT = Path("/Applications/Godot.app/Contents/MacOS/Godot")
SOURCE = PROJECT / "comparison/desk_asset_experiment.tscn"
GLB = PROJECT / "comparison/assets/polyhaven_wooden_table_02_1k.glb"
OUT = HERE / "captures"
RAW = ROOT / "private/desk-asset-captures"
CASES = ((route, width, height, phase)
         for route in ("A", "M2")
         for width, height in ((360, 320), (1280, 720))
         for phase in ("day", "evening"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strip_png_metadata(source: Path, target: Path) -> tuple[int, int]:
    blob = source.read_bytes()
    assert blob[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8
    output = bytearray(blob[:8])
    kinds = []
    while offset < len(blob):
        length = struct.unpack_from(">I", blob, offset)[0]
        end = offset + length + 12
        assert end <= len(blob)
        kind = blob[offset + 4:offset + 8]
        if kind in (b"IHDR", b"IDAT", b"IEND"):
            output.extend(blob[offset:end])
            kinds.append(kind)
        offset = end
    assert kinds[0] == b"IHDR" and kinds[-1] == b"IEND" and b"IDAT" in kinds
    target.write_bytes(output)
    return struct.unpack_from(">II", output, 16)


def rgba(path: Path) -> bytes:
    result = subprocess.run(
        ("ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgba", "-"),
        capture_output=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


def scene_changed_pixels(before: Path, after: Path, width: int, height: int) -> dict:
    a, b = rgba(before), rgba(after)
    assert len(a) == len(b) == width * height * 4 * 4
    # The region comes from comparison.gd's compact/full texture layout.
    x, y, w, h = ((16, 92, 688, 282) if width == 360
                  else (32, 188, (width - 310 - 48) * 2, (height - 170) * 2))
    changed = 0
    for row in range(y, y + h):
        for col in range(x, x + w):
            at = (row * width * 2 + col) * 4
            if a[at:at + 3] != b[at:at + 3]:
                changed += 1
    return {"scene_roi_physical_xywh": [x, y, w, h],
            "changed_physical_pixels": changed, "roi_pixels": w * h,
            "changed_fraction": round(changed / (w * h), 6)}


def main() -> None:
    assert GODOT.is_file() and SOURCE.is_file() and GLB.is_file()
    imported = subprocess.run(
        (str(GODOT), "--headless", "--editor", "--import", "--path", str(PROJECT)),
        capture_output=True, text=True, timeout=180,
    )
    assert imported.returncode == 0 and "ERROR:" not in imported.stdout + imported.stderr, (
        imported.stdout + imported.stderr
    )
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    records = []
    for route, width, height, phase in CASES:
        key = f"{route}-{width}x{height}-{phase}"
        raw = RAW / key
        raw.mkdir(exist_ok=True)
        command = (str(GODOT), "--path", str(PROJECT),
                   "res://comparison/desk_asset_experiment.tscn", "--",
                   "--route=baseline", f"--size={width}x{height}",
                   f"--phase={phase}", f"--out={raw}",
                   "--capture", "--proof", "--quit")
        if route == "M2":
            command += ("--asset-desk",)
        result = subprocess.run(command, capture_output=True, text=True, timeout=75)
        log = result.stdout + result.stderr
        assert result.returncode == 0 and "COMPARISON_PROOF_PASS baseline" in log, log
        assert "SCRIPT ERROR" not in log and "ERROR:" not in log, log
        safe = log.replace(str(ROOT), "<repo>")
        safe = re.sub(r"/Users/[^/]+/", "/Users/<local>/", safe)
        (raw / "godot-sanitized.log").write_text(safe)
        for state in ("idle", "started"):
            source = raw / f"baseline-{width}x{height}-{phase}-{state}.png"
            target = OUT / f"{key}-{state}.png"
            assert source.is_file()
            physical = strip_png_metadata(source, target)
            assert physical == (width * 2, height * 2)
            records.append({"variant": route, "size": [width, height],
                            "phase": phase, "state": state,
                            "capture": target.relative_to(HERE).as_posix(),
                            "sha256": digest(target), "physical_pixels": list(physical)})
        print("DESK_CAPTURE", key, flush=True)
    comparisons = []
    for width, height in ((360, 320), (1280, 720)):
        for phase in ("day", "evening"):
            before = OUT / f"A-{width}x{height}-{phase}-idle.png"
            after = OUT / f"M2-{width}x{height}-{phase}-idle.png"
            comparisons.append({"size": [width, height], "phase": phase,
                                "idle_scene_difference": scene_changed_pixels(before, after, width, height)})
    manifest = {
        "purpose": "Original A vs a single CC0 1K wood table asset fitted to A's desk footprint",
        "asset_page": "https://polyhaven.com/a/wooden_table_02",
        "license_page": "https://polyhaven.com/license",
        "source_files_sha256": json.loads((ROOT / "private/polyhaven-desk/source_hashes.json").read_text()),
        "glb_bytes": GLB.stat().st_size, "glb_sha256": digest(GLB),
        "source_code_sha256": {name: digest(HERE / name) for name in ("fetch_source.py", "build_asset.py", "run_capture.py")},
        "godot_source_sha256": {name: digest(PROJECT / "comparison" / name)
                                for name in ("desk_asset_room.gd", "desk_asset_experiment.gd")},
        "notes": [
            "The asset was non-uniformly stretched to preserve A's oversized desk footprint; this is a visual trial, not a realistic-scale furniture placement.",
            "Pixel difference counts compare the idle scene region only, excluding changing clock text, but include shadow and aliasing changes from the desk geometry.",
            "No claim about all-day resource use, character animation, or final 3D art route.",
        ],
        "records": records, "comparisons": comparisons,
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
