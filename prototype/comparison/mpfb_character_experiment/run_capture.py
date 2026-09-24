"""Capture a fixed R2/R4 3D character matrix in actual Godot windows."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import struct
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PROJECT = ROOT / "prototype/godot"
GODOT = Path("/Applications/Godot.app/Contents/MacOS/Godot")
SOURCE = PROJECT / "comparison/mpfb_character_experiment.tscn"
CAPTURES = HERE / "captures"
RAW = ROOT / "private/mpfb-captures"
CASES = (
    ("r2-original", 360, 320, "day", ("--rigged-student",)),
    ("r4-original", 360, 320, "day", ("--mpfb-student",)),
    ("r2-focus", 360, 320, "day", ("--rigged-student", "--chair-low", "--task-focus")),
    ("r4-focus", 360, 320, "day", ("--mpfb-student", "--chair-low", "--task-focus")),
    ("r4-contact", 360, 320, "day", ("--mpfb-student", "--mpfb-ik", "--chair-low", "--task-focus", "--contact-layout")),
    ("r4-contact", 360, 320, "evening", ("--mpfb-student", "--mpfb-ik", "--chair-low", "--task-focus", "--contact-layout")),
    ("r4-contact", 1280, 720, "day", ("--mpfb-student", "--mpfb-ik", "--chair-low", "--contact-layout")),
    ("r4-contact", 1280, 720, "evening", ("--mpfb-student", "--mpfb-ik", "--chair-low", "--contact-layout")),
    ("r2-roomfirst", 360, 320, "day", ("--rigged-student", "--chair-low", "--task-focus", "--activity-focus-layout", "--contact-layout")),
    ("r4-roomfirst", 360, 320, "day", ("--mpfb-student", "--mpfb-ik", "--chair-low", "--task-focus", "--activity-focus-layout", "--contact-layout")),
    ("r4-hero-scaled", 360, 320, "day", ("--mpfb-student", "--mpfb-ik", "--chair-low", "--hero-focus", "--activity-focus-layout", "--contact-layout", "--scaled-character")),
    ("r4-hero-scaled", 360, 320, "evening", ("--mpfb-student", "--mpfb-ik", "--chair-low", "--hero-focus", "--activity-focus-layout", "--contact-layout", "--scaled-character")),
    ("r4-casual-scaled", 360, 320, "day", ("--mpfb-student", "--mpfb-ik", "--mpfb-casual", "--chair-low", "--hero-focus", "--activity-focus-layout", "--contact-layout", "--scaled-character")),
    ("r4-casual-scaled", 360, 320, "evening", ("--mpfb-student", "--mpfb-ik", "--mpfb-casual", "--chair-low", "--hero-focus", "--activity-focus-layout", "--contact-layout", "--scaled-character")),
    ("r4-product-casual", 360, 320, "day", ("--mpfb-student", "--mpfb-ik", "--mpfb-casual", "--chair-low", "--hero-focus", "--contact-layout", "--scaled-character")),
    ("r4-product-casual", 360, 320, "evening", ("--mpfb-student", "--mpfb-ik", "--mpfb-casual", "--chair-low", "--hero-focus", "--contact-layout", "--scaled-character")),
    ("r4-full-casual", 1280, 720, "day", ("--mpfb-student", "--mpfb-ik", "--mpfb-casual", "--chair-low", "--hero-focus", "--contact-layout", "--scaled-character")),
    ("r4-full-casual", 1280, 720, "evening", ("--mpfb-student", "--mpfb-ik", "--mpfb-casual", "--chair-low", "--hero-focus", "--contact-layout", "--scaled-character")),
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strip_png_metadata(source: Path, target: Path) -> tuple[int, int]:
    blob = source.read_bytes()
    assert blob[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8
    output = bytearray(blob[:8])
    kinds = []
    while offset < len(blob):
        size = struct.unpack_from(">I", blob, offset)[0]
        end = offset + size + 12
        assert end <= len(blob)
        kind = blob[offset + 4:offset + 8]
        if kind in (b"IHDR", b"IDAT", b"IEND"):
            output.extend(blob[offset:end])
            kinds.append(kind)
        offset = end
    assert kinds[0] == b"IHDR" and kinds[-1] == b"IEND" and b"IDAT" in kinds
    target.write_bytes(output)
    return struct.unpack_from(">II", output, 16)


def main() -> None:
    assert GODOT.is_file() and SOURCE.is_file()
    # A fresh checkout has no imported GLB cache. Import explicitly before
    # launching the normal window, rather than mistaking missing cache for a
    # model or animation failure.
    imported = subprocess.run(
        (str(GODOT), "--headless", "--editor", "--import", "--path", str(PROJECT)),
        capture_output=True, text=True, timeout=180,
    )
    assert imported.returncode == 0 and "ERROR:" not in imported.stdout + imported.stderr, (
        imported.stdout + imported.stderr
    )
    CAPTURES.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    records = []
    for name, width, height, phase, flags in CASES:
        key = f"{name}-{width}x{height}-{phase}"
        out = RAW / key
        out.mkdir(exist_ok=True)
        command = (
            str(GODOT), "--path", str(PROJECT),
            "res://comparison/mpfb_character_experiment.tscn", "--",
            "--route=baseline", f"--size={width}x{height}", f"--phase={phase}",
            f"--out={out}", "--capture", "--proof", "--quit", *flags,
        )
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        output = result.stdout + result.stderr
        assert result.returncode == 0 and "COMPARISON_PROOF_PASS baseline" in output, output
        assert "SCRIPT ERROR" not in output and "ERROR:" not in output, output
        rows = [json.loads(line.split("CHARACTER_BOUNDS ", 1)[1])
                for line in output.splitlines() if "CHARACTER_BOUNDS " in line]
        bounds = next(row["logical_xywh"] for row in rows if row["state"] == "started")
        source = out / f"baseline-{width}x{height}-{phase}-started.png"
        target = CAPTURES / f"{key}.png"
        assert source.is_file()
        physical = strip_png_metadata(source, target)
        assert physical == (width * 2, height * 2)
        safe_log = output.replace(str(ROOT), "<repo>")
        safe_log = re.sub(r"/Users/[^/]+/", "/Users/<local>/", safe_log)
        (out / "godot-sanitized.log").write_text(safe_log)
        records.append({
            "case": name, "size": [width, height], "phase": phase,
            "flags": list(flags), "capture": target.relative_to(HERE).as_posix(),
            "physical_pixels": list(physical), "sha256": digest(target),
            "projected_mesh_bounds_logical_xywh": bounds,
        })
        print("R4_CAPTURE", key, bounds, flush=True)
    manifest = {
        "purpose": "Static MPFB student candidate versus prior R2, original room and task facts",
        "platform": platform.platform(), "engine": "Godot 4.7 Compatibility",
        "asset_sources": {
            "mpfb": "https://extensions.blender.org/add-ons/mpfb/",
            "system_pack": "https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html",
            "pose": "https://static.makehumancommunity.org/assets/assetpacks/poses01.html#sweetan008_sitting-pose",
            "pose_license_in_embedded_meta": "CC0",
        },
        "source_sha256": {
            "build_character.py": digest(HERE / "build_character.py"),
            "mpfb_character_room.gd": digest(PROJECT / "comparison/mpfb_character_room.gd"),
            "mpfb_character_experiment.gd": digest(PROJECT / "comparison/mpfb_character_experiment.gd"),
        },
        "glb_sha256": {
            "seated": digest(PROJECT / "comparison/assets/fictional_student_mpfb.glb"),
            "keyboard_ik": digest(PROJECT / "comparison/assets/fictional_student_mpfb_ik.glb"),
            "casual_keyboard_ik": digest(PROJECT / "comparison/assets/fictional_student_mpfb_casual_ik.glb"),
        },
        "notes": [
            "The projected AABB is not an occlusion-tested visible-pixel count.",
            "R4 is a static baked pose; it does not claim animation or personal-photo generation.",
            "r4-contact changes chair depth/back height, keyboard depth and camera only in the compact capture; full capture keeps original camera.",
            "roomfirst/hero-scaled use the #43 art-only larger scene viewport and hide task action controls; they are not product UI candidates.",
            "hero-scaled also enlarges and lowers the character to reveal A room's furniture scale mismatch; this is a controlled correction, not a finished asset.",
            "product-casual uses the original compact UI with task status and controls visible, testing the art/UI trade-off.",
        ],
        "records": records,
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
