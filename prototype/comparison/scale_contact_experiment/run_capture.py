"""Capture R4 art fit versus M3 scale/contact + task-state camera in Godot."""

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
OUT = HERE / "captures"
RAW = ROOT / "private/scale-contact-captures"
BASE_FLAGS = ("--mpfb-student", "--mpfb-ik", "--mpfb-casual", "--chair-low",
              "--hero-focus", "--contact-layout", "--scaled-character")
M3_FLAGS = ("--mpfb-student", "--mpfb-ik", "--mpfb-casual", "--scale-contact-m3")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strip_png_metadata(source: Path, target: Path) -> tuple[int, int]:
    data = source.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8
    out = bytearray(data[:8])
    kinds = []
    while offset < len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        end = offset + size + 12
        assert end <= len(data)
        kind = data[offset + 4:offset + 8]
        if kind in (b"IHDR", b"IDAT", b"IEND"):
            out.extend(data[offset:end])
            kinds.append(kind)
        offset = end
    assert kinds[0] == b"IHDR" and kinds[-1] == b"IEND" and b"IDAT" in kinds
    target.write_bytes(out)
    return struct.unpack_from(">II", out, 16)


def main() -> None:
    assert GODOT.is_file()
    assert (PROJECT / "comparison/mpfb_character_experiment.tscn").is_file()
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
    for variant, flags in (("R4", BASE_FLAGS), ("M3", M3_FLAGS)):
        for width, height in ((360, 320), (1280, 720)):
            for phase in ("day", "evening"):
                key = f"{variant}-{width}x{height}-{phase}"
                raw = RAW / key
                raw.mkdir(exist_ok=True)
                command = (str(GODOT), "--path", str(PROJECT),
                           "res://comparison/mpfb_character_experiment.tscn", "--",
                           "--route=baseline", f"--size={width}x{height}",
                           f"--phase={phase}", f"--out={raw}",
                           "--capture", "--proof", "--quit", *flags)
                result = subprocess.run(command, capture_output=True, text=True, timeout=75)
                log = result.stdout + result.stderr
                assert result.returncode == 0 and "COMPARISON_PROOF_PASS baseline" in log, log
                assert "SCRIPT ERROR" not in log and "ERROR:" not in log, log
                if variant == "M3":
                    assert "R4_M3_SCALE_CONTACT true" in log and "M3_CONTACT heights=" in log, log
                safe = log.replace(str(ROOT), "<repo>")
                safe = re.sub(r"/Users/[^/]+/", "/Users/<local>/", safe)
                (raw / "godot-sanitized.log").write_text(safe)
                bounds = {row["state"]: row for row in (
                    json.loads(line.split("CHARACTER_BOUNDS ", 1)[1])
                    for line in log.splitlines() if "CHARACTER_BOUNDS " in line
                )}
                for state in ("idle", "started"):
                    source = raw / f"baseline-{width}x{height}-{phase}-{state}.png"
                    target = OUT / f"{key}-{state}.png"
                    assert source.is_file()
                    physical = strip_png_metadata(source, target)
                    assert physical == (width * 2, height * 2)
                    records.append({
                        "variant": variant, "size": [width, height], "phase": phase,
                        "state": state, "flags": list(flags),
                        "capture": target.relative_to(HERE).as_posix(),
                        "sha256": digest(target), "physical_pixels": list(physical),
                        "projected_mesh_bounds_logical_xywh": bounds[state]["logical_xywh"],
                        "scene_view_physical_pixels": bounds[state]["viewport_pixels"],
                    })
                print("M3_CAPTURE", key, flush=True)
    manifest = {
        "purpose": "R4 scale-fit candidate versus M3 contact and explicit-task camera",
        "license_sources": ["https://github.com/makehumancommunity/mpfb2/blob/master/LICENSE.md",
                            "https://polyhaven.com/a/wooden_table_02"],
        "glb_sha256": {p.name: digest(p) for p in (
            PROJECT / "comparison/assets/fictional_student_mpfb_casual_ik.glb",
            PROJECT / "comparison/assets/polyhaven_wooden_table_02_1k.glb")},
        "source_sha256": {p.name: digest(p) for p in (
            HERE / "run_capture.py", PROJECT / "comparison/scale_contact_room.gd",
            PROJECT / "comparison/mpfb_character_experiment.gd")},
        "notes": [
            "R4 control uses enlarged character and fixed near camera; M3 uses unscaled seated mesh and state-dependent camera.",
            "M3 lowers desk/monitor/chair/student together and moves chair forward; the 3.55 m desk width is still distorted to A's footprint.",
            "Projected mesh bounds include hidden/clipped pixels and are not a visible-pixel count or quality score.",
            "M3 camera eases over 0.65 s after explicit task state changes, but the standing placeholder and seated MPFB mesh still switch abruptly; no automatic task inference or completion.",
        ],
        "records": records,
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
