"""Record comparison interactions from real Godot windows, without paid services.

Run only when no other comparison capture is active. Each run owns a temporary
frame directory; existing matrix PNGs and JSON files are never overwritten.
The videos are 10 fps encodes of sampled frames, not constant-clock recordings.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent / "godot"
REPO = HERE.parent.parent
ROUTES = ("baseline", "3d", "2d", "pixel")
SIZES = ("1280x720", "360x320")
SAMPLING = (
    "Real Godot window; viewport images sampled after frame_post_draw, followed "
    "by a 0.07-second SceneTree timer. Rendering, timer scheduling and PNG writes "
    "make the effective sampling approximately 10 fps, not a constant-clock "
    "screen recording. Selected proof phases are concatenated at 10 fps."
)


def sanitize(text: str, temporary: Path) -> str:
    for value, replacement in (
        (str(temporary), "<temporary-frames>"),
        (str(REPO), "<repo>"),
        (str(Path.home()), "<home>"),
    ):
        text = text.replace(value, replacement)
    return re.sub(r"/var/folders/[^\s\"']+", "<system-temp>", text)


def output_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def run_logged(command: list[str], log_path: Path, temporary: Path,
               timeout: float) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        log = output_text(exc.stdout) + output_text(exc.stderr)
        log_path.write_text(sanitize(log, temporary) + "\nCAPTURE_TIMEOUT\n")
        raise RuntimeError(f"Timed out; see {log_path.name}") from exc
    log_path.write_text(sanitize(result.stdout + result.stderr, temporary))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", default="/Applications/Godot.app/Contents/MacOS/Godot")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--routes", nargs="+", choices=ROUTES,
                        help="Re-record selected routes while preserving other manifest entries")
    args = parser.parse_args()
    for executable in (args.godot, args.ffmpeg):
        if shutil.which(executable) is None:
            parser.error(f"Executable not found: {executable}")
    evidence = HERE / "evidence"
    logs = HERE / "logs"
    evidence.mkdir(exist_ok=True)
    logs.mkdir(exist_ok=True)
    manifest_path = evidence / "interaction-recordings.json"
    selected_routes = tuple(dict.fromkeys(args.routes)) if args.routes else ROUTES
    manifest = {"sampling": SAMPLING, "encoded_fps": 10, "phase": "day", "runs": []}
    if args.routes and manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            if not isinstance(manifest, dict) or not isinstance(manifest.get("runs"), list):
                raise ValueError("Expected an object containing a runs array")
            if any(not isinstance(item, dict) for item in manifest["runs"]):
                raise ValueError("Expected each run entry to be an object")
        except (ValueError, OSError) as exc:
            parser.error(f"Cannot preserve existing interaction manifest: {exc}")
        manifest.update(sampling=SAMPLING, encoded_fps=10, phase="day")
    for route in selected_routes:
        for size in SIZES:
            name = f"{route}-{size}-day-interaction"
            record = {"run": name, "ok": False}
            # Replace only the exact run being attempted. Unattempted sizes and
            # other routes retain their prior evidence if this capture stops.
            manifest["runs"] = [item for item in manifest["runs"] if item.get("run") != name]
            manifest["runs"].append(record)
            started = time.monotonic()
            try:
                with tempfile.TemporaryDirectory(prefix="workbench-interaction-") as raw:
                    temporary = Path(raw)
                    command = [args.godot, "--path", str(PROJECT),
                               "res://comparison/main.tscn", "--",
                               f"--route={route}", f"--size={size}", "--phase=day",
                               f"--out={temporary}", "--proof", "--film", "--quit"]
                    result = run_logged(command, logs / f"{name}.log", temporary,
                                        args.timeout)
                    log = result.stdout + result.stderr
                    record["godot_returncode"] = result.returncode
                    record["proof_pass"] = f"COMPARISON_PROOF_PASS {route}" in log
                    if (result.returncode != 0 or not record["proof_pass"]
                            or "SCRIPT ERROR" in log or "ERROR:" in log):
                        raise RuntimeError(f"Godot proof not accepted; see {name}.log")
                    prefix = f"{route}-{size}-day-motion-"
                    frames = sorted(temporary.glob(f"{prefix}*.png"))
                    expected = [temporary / f"{prefix}{i:03d}.png" for i in range(len(frames))]
                    record["input_frame_count"] = len(frames)
                    if not frames or frames != expected:
                        raise RuntimeError("Missing or non-contiguous motion frames")
                    if any(frame.stat().st_size == 0 for frame in frames):
                        raise RuntimeError("Empty motion PNG")
                    # Encode into the temporary directory, then publish only a complete file.
                    video = temporary / f"{name}.mp4"
                    encode = [args.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                              "-framerate", "10", "-start_number", "0", "-i",
                              str(temporary / f"{prefix}%03d.png"), "-frames:v", str(len(frames)),
                              "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                              "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(video)]
                    encoded = run_logged(encode, logs / f"{name}-ffmpeg.log", temporary,
                                         args.timeout)
                    record["ffmpeg_returncode"] = encoded.returncode
                    if encoded.returncode != 0 or not video.is_file() or video.stat().st_size == 0:
                        raise RuntimeError(f"Video encode not accepted; see {name}-ffmpeg.log")
                    destination = evidence / video.name
                    shutil.copyfile(video, destination)
                    record.update(ok=True, video=destination.name,
                                  encoded_duration_seconds=len(frames) / 10.0)
            except (RuntimeError, OSError) as exc:
                record["error"] = str(exc)
                print(f"{name}: {exc}", flush=True)
                return 1
            finally:
                record["wall_seconds"] = round(time.monotonic() - started, 3)
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            print(f"{name}: {record['input_frame_count']} frames encoded at 10 fps", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
