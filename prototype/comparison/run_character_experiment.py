"""Capture R0 original A versus R1 self-authored student in actual Godot windows."""

import hashlib
import json
import platform
import re
import struct
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "prototype" / "godot"
OUT = ROOT / "prototype" / "comparison" / "character_experiment"
GODOT = Path("/Applications/Godot.app/Contents/MacOS/Godot")
ASSETS = PROJECT / "comparison" / "assets"
SOURCES = (
    PROJECT / "main.gd", PROJECT / "comparison" / "room_3d.gd",
    PROJECT / "comparison" / "comparison.gd", PROJECT / "project.godot",
)
SIZES = ((360, 320), (1280, 720))
PHASES = ("day", "evening")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pixels(path):
    raw = path.read_bytes()[:24]
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    return [int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")]


def glb_structure(path):
    raw = path.read_bytes()
    magic, version, length = struct.unpack_from("<III", raw)
    assert magic == 0x46546C67 and version == 2 and length == len(raw)
    json_length, json_type = struct.unpack_from("<II", raw, 12)
    assert json_type == 0x4E4F534A
    data = json.loads(raw[20:20 + json_length].rstrip(b" \0"))
    assert len(data["materials"]) == 8
    assert not data.get("animations") and not data.get("skins")
    return {
        "path": str(path.relative_to(ROOT)), "bytes": len(raw),
        "sha256": digest(path), "meshes": len(data["meshes"]),
        "materials": len(data["materials"]), "animations": 0, "skins": 0,
    }


def run():
    if not GODOT.is_file():
        raise SystemExit(f"Godot not found: {GODOT}")
    blend = OUT / "adult_student.blend"
    builder = OUT / "build_character.py"
    idle = ASSETS / "adult_student_idle.glb"
    typing = ASSETS / "adult_student_typing.glb"
    for path in (blend, builder, idle, typing):
        if not path.is_file():
            raise SystemExit(f"Missing asset source/output: {path}")
    assets = [glb_structure(idle), glb_structure(typing)]
    assert [asset["meshes"] for asset in assets] == [38, 40]
    records = []
    for variant in ("R0", "R1"):
        folder = OUT / variant
        folder.mkdir(exist_ok=True)
        for width, height in SIZES:
            for phase in PHASES:
                cmd = [
                    str(GODOT), "--path", str(PROJECT),
                    "res://comparison/character_experiment.tscn", "--",
                    "--route=baseline", f"--size={width}x{height}",
                    f"--phase={phase}", f"--out={folder}",
                    "--capture", "--proof", "--quit",
                ]
                if variant == "R1":
                    cmd.append("--adult-student")
                started = time.monotonic()
                process = subprocess.run(cmd, capture_output=True, text=True, timeout=50)
                output = (process.stdout + process.stderr).replace(str(ROOT), "<repo>")
                output = re.sub(r"/Users/[^/]+/", "/Users/<local>/", output)
                log_file = folder / f"{width}x{height}-{phase}.log"
                log_file.write_text(output)
                bound_rows = [json.loads(line.split("CHARACTER_BOUNDS ", 1)[1])
                              for line in output.splitlines() if "CHARACTER_BOUNDS " in line]
                bounds = {row["state"]: row for row in bound_rows}
                expected_pngs = [folder / f"baseline-{width}x{height}-{phase}-{state}.png"
                                 for state in ("idle", "started")]
                expected_info = folder / f"baseline-{width}x{height}-{phase}.json"
                ok = (
                    process.returncode == 0 and "SCRIPT ERROR" not in output
                    and "ERROR:" not in output and "COMPARISON_PROOF_PASS baseline" in output
                    and f"CHARACTER_VARIANT {variant}" in output
                    and ("CHARACTER_IMPORTED idle_meshes=38 typing_meshes=40 camera_fov=45" in output)
                    == (variant == "R1")
                    and all(p.is_file() for p in expected_pngs)
                    and expected_info.is_file() and all(state in bounds for state in ("idle", "started"))
                    and all(row["display_scale"] == 2.0 for row in bounds.values())
                )
                row = {
                    "variant": variant, "logical_size": [width, height], "phase": phase,
                    "ok": ok, "wall_seconds": round(time.monotonic() - started, 3),
                    "log": str(log_file.relative_to(OUT)),
                }
                if ok:
                    row["captures"] = {
                        state: {
                            "path": str(path.relative_to(OUT)), "physical_pixels": pixels(path),
                            "sha256": digest(path), "projected_character_bounds": bounds[state],
                        }
                        for state, path in zip(("idle", "started"), expected_pngs)
                    }
                    row["runtime"] = json.loads(expected_info.read_text())
                records.append(row)
                print(f"{variant} {width}x{height} {phase}: {'OK' if ok else 'FAIL'}", flush=True)
                if not ok:
                    raise SystemExit(output)
                # The inherited proof also saves completion/defer UI frames. They
                # verify virtual interactions but are not part of this art comparison.
                for state in ("completed", "deferred"):
                    extra = folder / f"baseline-{width}x{height}-{phase}-{state}.png"
                    if extra.is_file():
                        extra.unlink()
    manifest = {
        "purpose": "R0 original A versus R1 original editable character; idle geometry and one static typing pose",
        "platform": platform.platform(), "source_sha256": {
            str(path.relative_to(ROOT)): digest(path) for path in SOURCES
        },
        "asset": {
            "license": "repository MIT; self-authored with Blender 5.1.2; no external model/texture",
            "editable_blend": str(blend.relative_to(ROOT)), "blend_bytes": blend.stat().st_size,
            "blend_sha256": digest(blend), "build_script_sha256": digest(builder),
            "glbs": assets,
        },
        "fixed": {
            "route": "baseline", "camera_fov_degrees": 45,
            "key_rotation_degrees": [-55, -32, 0],
            "ambient_energy": {"day": 0.36, "evening": 0.48},
            "key_energy": {"day": 0.65, "evening": 0.35},
            "changed": "character only; R1 started additionally swaps static character pose/location",
        },
        "measurement_note": "projected_character_bounds.logical_xywh is Godot projected mesh AABB divided by Retina display_scale, within the 3D viewport, not an occlusion-tested visible-pixel mask",
        "records": records,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    run()
