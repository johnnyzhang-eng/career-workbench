"""Capture the original A keyboard and one self-authored replacement in Godot."""

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
OUT = ROOT / "prototype" / "comparison" / "keyboard_contact_experiment"
GODOT = Path("/Applications/Godot.app/Contents/MacOS/Godot")
GLB = PROJECT / "comparison" / "assets" / "keyboard_contact.glb"
BLEND = OUT / "keyboard_contact.blend"
BUILD = OUT / "build_asset.py"
SOURCES = (
    PROJECT / "main.gd", PROJECT / "comparison" / "room_3d.gd",
    PROJECT / "comparison" / "comparison.gd", PROJECT / "project.godot",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_size(path):
    data = path.read_bytes()[:24]
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return [int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")]


def glb_audit():
    data = GLB.read_bytes()
    magic, version, length = struct.unpack_from("<III", data)
    assert (magic, version, length) == (0x46546C67, 2, len(data))
    json_length, kind = struct.unpack_from("<II", data, 12)
    assert kind == 0x4E4F534A
    body = json.loads(data[20:20 + json_length].rstrip(b" \0"))
    assert len(body["meshes"]) == 4 and len(body["materials"]) == 4
    primitives = [part for mesh in body["meshes"] for part in mesh["primitives"]]
    assert len(primitives) == 4
    assert all("POSITION" in part["attributes"] and "NORMAL" in part["attributes"] for part in primitives)
    return {
        "bytes": len(data), "sha256": digest(GLB),
        "mesh_count": len(body["meshes"]),
        "material_names": [item["name"] for item in body["materials"]],
        "primitive_count": len(primitives),
        "vertices": sum(body["accessors"][part["attributes"]["POSITION"]]["count"] for part in primitives),
    }


def run():
    for required in (GODOT, GLB, BLEND, BUILD):
        if not required.is_file():
            raise SystemExit(f"Missing required file: {required}")
    asset = glb_audit()
    records = []
    for variant in ("K0", "K1"):
        folder = OUT / variant
        folder.mkdir(parents=True, exist_ok=True)
        for width, height in ((360, 320), (1280, 720)):
            for phase in ("day", "evening"):
                command = [
                    str(GODOT), "--path", str(PROJECT),
                    "res://comparison/keyboard_contact_experiment.tscn", "--",
                    "--route=baseline", f"--size={width}x{height}",
                    f"--phase={phase}", f"--out={folder}", "--capture", "--quit",
                ]
                if variant == "K1":
                    command.append("--keyboard-contact")
                start = time.monotonic()
                result = subprocess.run(command, capture_output=True, text=True, timeout=45)
                output = (result.stdout + result.stderr).replace(str(ROOT), "<repo>")
                output = re.sub(r"/Users/[^/]+/", "/Users/<local>/", output)
                log = folder / f"{width}x{height}-{phase}.log"
                log.write_text(output)
                png = folder / f"baseline-{width}x{height}-{phase}-idle.png"
                info = folder / f"baseline-{width}x{height}-{phase}.json"
                ok = (
                    result.returncode == 0 and "SCRIPT ERROR" not in output
                    and "ERROR:" not in output and png.is_file() and info.is_file()
                    and f"KEYBOARD_CONTACT_VARIANT {variant}" in output
                    and ("KEYBOARD_CONTACT_IMPORTED mesh_count=4" in output) == (variant == "K1")
                )
                record = {
                    "variant": variant, "logical_size": [width, height], "phase": phase,
                    "ok": ok, "wall_seconds": round(time.monotonic() - start, 3),
                    "png": str(png.relative_to(OUT)), "json": str(info.relative_to(OUT)),
                    "log": str(log.relative_to(OUT)),
                }
                if ok:
                    record["png_pixels"] = png_size(png)
                    record["png_sha256"] = digest(png)
                    record["capture"] = json.loads(info.read_text())
                records.append(record)
                print(f"{variant} {width}x{height} {phase}: {'OK' if ok else 'FAIL'}", flush=True)
                if not ok:
                    raise SystemExit(output)
    manifest = {
        "purpose": "single replacement of original A Keyboard with self-authored contact surface",
        "platform": platform.platform(),
        "source_sha256": {str(path.relative_to(ROOT)): digest(path) for path in SOURCES},
        "asset": {
            "license": "repository MIT, original authored mesh", "authored_with": "Blender 5.1.2",
            "blend": str(BLEND.relative_to(ROOT)), "blend_bytes": BLEND.stat().st_size,
            "blend_sha256": digest(BLEND), "build_script": str(BUILD.relative_to(ROOT)),
            "build_script_sha256": digest(BUILD),
            "glb": str(GLB.relative_to(ROOT)), **asset,
        },
        "settings": {
            "renderer": "GL Compatibility", "route": "baseline", "state": "idle",
            "changed_object": "Keyboard", "unchanged_fov_degrees": 45.0,
            "unchanged_ambient_energy": {"day": 0.36, "evening": 0.48},
            "unchanged_key_energy": {"day": 0.65, "evening": 0.35},
            "unchanged_key_rotation_degrees": [-55.0, -32.0, 0.0],
        },
        "records": records,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    run()
