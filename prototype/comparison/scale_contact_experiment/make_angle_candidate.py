"""Archive a camera-only composition candidate without changing the M3 default."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from run_capture import GODOT, HERE, M3_FLAGS, PROJECT, RAW, digest, strip_png_metadata


def main() -> None:
    imported = subprocess.run(
        (str(GODOT), "--headless", "--editor", "--import", "--path", str(PROJECT)),
        capture_output=True, text=True, timeout=180,
    )
    assert imported.returncode == 0 and "ERROR:" not in imported.stdout + imported.stderr, (
        imported.stdout + imported.stderr
    )
    records = []
    for width, height in ((360, 320), (1280, 720)):
        raw = RAW / f"G2a-side-{width}x{height}-day"
        raw.mkdir(parents=True, exist_ok=True)
        flags = (*M3_FLAGS, "--m3-side-angle")
        result = subprocess.run(
            (str(GODOT), "--path", str(PROJECT),
             "res://comparison/mpfb_character_experiment.tscn", "--",
             "--route=baseline", f"--size={width}x{height}", "--phase=day",
             f"--out={raw}", "--capture", "--proof", "--quit", *flags),
            capture_output=True, text=True, timeout=75,
        )
        log = result.stdout + result.stderr
        assert result.returncode == 0 and "COMPARISON_PROOF_PASS baseline" in log, log
        assert "ERROR:" not in log and "SCRIPT ERROR" not in log, log
        assert "M3_CAMERA_TWEEN in_progress target=(1.65, 1.9, 0.9)" in log, log
        bounds = [json.loads(line.split("CHARACTER_BOUNDS ", 1)[1])
                  for line in log.splitlines() if "CHARACTER_BOUNDS " in line]
        started = next(row for row in bounds if row["state"] == "started")
        source = raw / f"baseline-{width}x{height}-day-started.png"
        target = HERE / f"captures/G2a-side-{width}x{height}-day-started.png"
        physical = strip_png_metadata(source, target)
        assert physical == (width * 2, height * 2)
        records.append({
            "capture": target.relative_to(HERE).as_posix(), "sha256": digest(target),
            "size": [width, height], "physical_pixels": list(physical),
            "flags": list(flags), "projected_mesh_bounds_logical_xywh": started["logical_xywh"],
            "scene_view_physical_pixels": started["viewport_pixels"],
        })
        print("G2A_ANGLE_CAPTURE", target, flush=True)
    record = {
        "purpose": "Camera-only composition probe relative to M3 at the same explicit task state; not the default camera.",
        "near_camera_position": [1.65, 1.9, 0.9],
        "near_camera_target": [-0.78, 0.8, -0.53],
        "notes": "Character projects larger, but desk and room context are cropped; AABB includes occlusion and is not a quality score.",
        "source_sha256": {
            "make_angle_candidate.py": digest(Path(__file__)),
            "scale_contact_room.gd": digest(PROJECT / "comparison/scale_contact_room.gd"),
        },
        "records": records,
    }
    (HERE / "angle_candidate.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
