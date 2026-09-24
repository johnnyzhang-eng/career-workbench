"""Run the R2 skinned-character proof in real Godot windows and record evidence."""

import hashlib
import json
import platform
import re
import shutil
import struct
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PROJECT = ROOT / "prototype" / "godot"
GODOT = Path("/Applications/Godot.app/Contents/MacOS/Godot")
GLB = PROJECT / "comparison" / "assets" / "adult_student_rigged.glb"
KEYS = (
    "sit-start", "sit-mid", "sit-end", "typing-start",
    "typing-left-down", "typing-right-down", "typing-mid",
    "typing-end", "typing-loop-end",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_size(path):
    raw = path.read_bytes()[:24]
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    return [int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")]


def glb_info():
    raw = GLB.read_bytes()
    magic, version, length = struct.unpack_from("<III", raw)
    assert magic == 0x46546C67 and version == 2 and length == len(raw)
    json_length, json_type = struct.unpack_from("<II", raw, 12)
    assert json_type == 0x4E4F534A
    payload = json.loads(raw[20:20 + json_length].rstrip(b" \0"))
    animations = [item["name"] for item in payload["animations"]]
    assert len(payload["skins"]) == 1 and animations == ["SitToType", "TypingLoop"]
    assert len(payload["skins"][0]["joints"]) == 8
    return {
        "file": str(GLB.relative_to(ROOT)), "bytes": len(raw), "sha256": sha(GLB),
        "meshes": len(payload["meshes"]), "skins": 1, "joints": 8,
        "animations": animations,
    }


def run():
    assert GODOT.is_file() and shutil.which("ffmpeg")
    blend = HERE / "adult_student_rigged.blend"
    assert blend.is_file()
    asset = glb_info()
    records = []
    for width, height in ((360, 320), (1280, 720)):
        for phase in ("day", "evening"):
            folder = HERE / "R2" / f"{width}x{height}-{phase}"
            folder.mkdir(parents=True, exist_ok=True)
            command = [
                str(GODOT), "--path", str(PROJECT),
                "res://comparison/rigged_character_experiment.tscn", "--",
                "--route=baseline", f"--size={width}x{height}", f"--phase={phase}",
                f"--out={folder}", "--capture", "--quit", "--r2-sequence",
            ]
            if width == 360 and phase == "day":
                command.append("--r2-video")
            started = time.monotonic()
            result = subprocess.run(command, text=True, capture_output=True, timeout=90)
            output = (result.stdout + result.stderr).replace(str(ROOT), "<repo>")
            output = re.sub(r"/Users/[^/]+/", "/Users/<local>/", output)
            log = folder / "godot.log"
            log.write_text(output)
            frame_rows = [json.loads(line.split("R2_FRAME ", 1)[1])
                          for line in output.splitlines() if "R2_FRAME " in line]
            row_by_key = {row["label"]: row for row in frame_rows}
            images = {key: folder / f"{key}-{width}x{height}-{phase}.png" for key in KEYS}
            ok = (
                result.returncode == 0 and "SCRIPT ERROR" not in output
                and "ERROR:" not in output
                and 'R2_GODOT_IMPORT skeleton_bones=8 animations=["SitToType", "TypingLoop"] meshes=1 camera_fov=45' in output
                and "typing_loop_mode=1" in output
                and all(key in row_by_key and image.is_file() for key, image in images.items())
                and all(png_size(image) == [width * 2, height * 2] for image in images.values())
            )
            record = {
                "logical_size": [width, height], "phase": phase, "ok": ok,
                "wall_seconds": round(time.monotonic() - started, 3),
                "log": str(log.relative_to(HERE)),
            }
            if not ok:
                raise RuntimeError(f"Godot proof failed: {log}\n{output}")
            record["keyframes"] = {
                key: {
                    "file": str(image.relative_to(HERE)), "sha256": sha(image),
                    "physical_pixels": png_size(image),
                    "animation": row_by_key[key]["animation"],
                    "seconds": row_by_key[key]["seconds"],
                    "wrists_world": row_by_key[key]["wrists_world"],
                } for key, image in images.items()
            }
            if width == 360 and phase == "day":
                frames = folder / "video_frames"
                frames_found = sorted(frames.glob("frame-*.png"))
                assert (len(frames_found) >= 70 and "R2_VIDEO_CAPTURE frames=" in output
                        and "R2_LOOP_STARTED" in output)
                movie = HERE / "R2" / "sit-and-type-360x320-day.mp4"
                encode = subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", "30",
                    "-i", str(frames / "frame-%03d.png"), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "21", "-movflags", "+faststart", str(movie),
                ], text=True, capture_output=True, timeout=60)
                assert encode.returncode == 0 and movie.is_file(), encode.stderr
                record["video"] = {
                    "file": str(movie.relative_to(HERE)), "sha256": sha(movie),
                    "bytes": movie.stat().st_size, "frames": len(frames_found),
                    "encoding_fps": 30,
                }
                shutil.rmtree(frames)
            records.append(record)
            print(f"R2 {width}x{height} {phase}: Godot import, keyframes and contact telemetry OK", flush=True)
    manifest = {
        "purpose": "Original R1 seated student with one skinned sit-to-type action; original A room and R0/R1 controls retained",
        "platform": platform.platform(), "engine": "Godot 4.7 Compatibility",
        "license": "Self-authored Blender geometry and animation, repository MIT; no downloaded assets",
        "asset": asset,
        "editable_blend": {"file": str(blend.relative_to(ROOT)), "bytes": blend.stat().st_size, "sha256": sha(blend)},
        "builder_sha256": sha(HERE / "build_rigged_character.py"),
        "fixed": {"camera_fov_degrees": 45, "room": "original A", "light": "original A", "UI": "original A", "task": "virtual comparison fixture"},
        "records": records,
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    run()
