"""Capture A versus a single Blender-authored desk top in real Godot windows."""

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
OUT = ROOT / "prototype" / "comparison" / "hero_desk_experiment"
GODOT = Path("/Applications/Godot.app/Contents/MacOS/Godot")
GLB = PROJECT / "comparison" / "assets" / "hero_desk_top.glb"
BLEND = OUT / "hero_desk_top.blend"
BUILD = OUT / "build_asset.py"
SOURCES = (
    PROJECT / "main.gd",
    PROJECT / "comparison" / "room_3d.gd",
    PROJECT / "comparison" / "comparison.gd",
    PROJECT / "project.godot",
)
SIZES = ((360, 320), (1280, 720))
PHASES = ("day", "evening")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_dimensions(path):
    data = path.read_bytes()[:24]
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return [int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")]


def glb_audit():
    data = GLB.read_bytes()
    magic, version, length = struct.unpack_from("<III", data)
    assert magic == 0x46546C67 and version == 2 and length == len(data)
    json_length, chunk_type = struct.unpack_from("<II", data, 12)
    assert chunk_type == 0x4E4F534A
    body = json.loads(data[20:20 + json_length].rstrip(b" \0"))
    meshes = body["meshes"]
    materials = body["materials"]
    assert len(meshes) == 1 and len(materials) == 3
    primitives = meshes[0]["primitives"]
    assert len(primitives) == 3
    bounds = [body["accessors"][part["attributes"]["POSITION"]] for part in primitives]
    assert all("NORMAL" in part["attributes"] for part in primitives)
    assert max(accessor["count"] for accessor in bounds) > 100  # applied bevel, not a plain box
    return {
        "bytes": len(data), "sha256": sha256(GLB),
        "mesh_count": len(meshes), "material_names": [m["name"] for m in materials],
        "primitive_count": len(primitives),
        "vertex_counts_by_material": [accessor["count"] for accessor in bounds],
    }


def run():
    if not GODOT.is_file():
        raise SystemExit(f"Godot executable not found: {GODOT}")
    for required in (GLB, BLEND, BUILD):
        if not required.is_file():
            raise SystemExit(f"Missing reproducible asset: {required}")
    asset = glb_audit()
    source_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in SOURCES}
    records = []
    for variant in ("D0", "D1"):
        folder = OUT / variant
        folder.mkdir(exist_ok=True)
        for width, height in SIZES:
            for phase in PHASES:
                cmd = [
                    str(GODOT), "--path", str(PROJECT),
                    "res://comparison/hero_desk_experiment.tscn", "--",
                    "--route=baseline", f"--size={width}x{height}",
                    f"--phase={phase}", f"--out={folder}",
                    "--capture", "--quit",
                ]
                if variant == "D1":
                    cmd.append("--hero-desk")
                started = time.monotonic()
                result = subprocess.run(cmd, text=True, capture_output=True, timeout=45)
                output = (result.stdout + result.stderr).replace(str(ROOT), "<repo>")
                output = re.sub(r"/Users/[^/]+/", "/Users/<local>/", output)
                log_file = folder / f"{width}x{height}-{phase}.log"
                log_file.write_text(output)
                png = folder / f"baseline-{width}x{height}-{phase}-idle.png"
                info = folder / f"baseline-{width}x{height}-{phase}.json"
                expected_variant = f"HERO_DESK_VARIANT {variant}"
                import_ok = ("HERO_DESK_IMPORTED mesh_count=1" in output) == (variant == "D1")
                bounds_ok = variant == "D0" or bool(re.search(
                    r"HERO_DESK_IMPORTED mesh_count=1 size=\(3\.55, 0\.17[\d]*, 1\.35\)", output
                ))
                ok = (result.returncode == 0 and "SCRIPT ERROR" not in output
                      and "ERROR:" not in output and png.is_file() and info.is_file()
                      and expected_variant in output and import_ok and bounds_ok)
                record = {
                    "variant": variant, "logical_size": [width, height], "phase": phase,
                    "ok": ok, "wall_seconds": round(time.monotonic() - started, 3),
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
        "purpose": "single-object original A desk-top mesh replacement",
        "platform": platform.platform(), "source_sha256": source_hashes,
        "asset": {
            "authored_with": "Blender 5.1.2", "license": "repository MIT, original authored mesh",
            "blend": str(BLEND.relative_to(ROOT)), "blend_bytes": BLEND.stat().st_size,
            "blend_sha256": sha256(BLEND), "build_script": str(BUILD.relative_to(ROOT)),
            "build_script_sha256": sha256(BUILD),
            "glb": str(GLB.relative_to(ROOT)), **asset,
        },
        "settings": {
            "renderer": "GL Compatibility", "route": "baseline", "state": "idle",
            "changed_object": "Desk top", "unchanged_fov_degrees": 45.0,
            "unchanged_ambient_energy": {"day": 0.36, "evening": 0.48},
            "unchanged_key_energy": {"day": 0.65, "evening": 0.35},
            "unchanged_key_rotation_degrees": [-55.0, -32.0, 0.0],
        },
        "records": records,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    run()
