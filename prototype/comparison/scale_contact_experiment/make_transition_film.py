"""Record the actual M3 task-start camera motion in a Godot window."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from run_capture import GODOT, HERE, M3_FLAGS, PROJECT, RAW


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    imported = subprocess.run(
        (str(GODOT), "--headless", "--editor", "--import", "--path", str(PROJECT)),
        capture_output=True, text=True, timeout=180,
    )
    assert imported.returncode == 0 and "ERROR:" not in imported.stdout + imported.stderr, (
        imported.stdout + imported.stderr
    )
    raw = RAW / "M3-camera-film"
    raw.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        (str(GODOT), "--path", str(PROJECT),
         "res://comparison/mpfb_character_experiment.tscn", "--",
         "--route=baseline", "--size=360x320", "--phase=day", f"--out={raw}",
         "--capture", "--proof", "--film", "--quit", *M3_FLAGS),
        capture_output=True, text=True, timeout=90,
    )
    log = result.stdout + result.stderr
    assert result.returncode == 0 and "COMPARISON_PROOF_PASS baseline" in log, log
    assert "ERROR:" not in log and "SCRIPT ERROR" not in log, log
    assert "M3_CAMERA_TWEEN in_progress" in log, log
    for i in range(26):
        assert (raw / f"baseline-360x320-day-motion-{i:03d}.png").is_file()
    output = HERE / "captures/m3-camera-transition.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = subprocess.run(
        ("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", "14",
         "-i", str(raw / "baseline-360x320-day-motion-%03d.png"), "-frames:v", "26",
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
         "-map_metadata", "-1", "-movflags", "+faststart", str(output)),
        capture_output=True, text=True, timeout=45,
    )
    assert encoded.returncode == 0 and output.is_file(), encoded.stderr
    probed = subprocess.run(
        ("ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=width,height,nb_read_frames", "-of", "json", str(output)),
        capture_output=True, text=True, timeout=30, check=True,
    )
    stream = json.loads(probed.stdout)["streams"][0]
    assert (stream["width"], stream["height"], int(stream["nb_read_frames"])) == (720, 640, 26)
    preview = HERE / "captures/m3-camera-transition.gif"
    gif = subprocess.run(
        ("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(output),
         "-filter_complex", "fps=14,scale=360:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
         "-loop", "0", str(preview)),
        capture_output=True, text=True, timeout=45,
    )
    assert gif.returncode == 0 and preview.is_file(), gif.stderr
    gif_probe = subprocess.run(
        ("ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=width,height,nb_read_frames", "-of", "json", str(preview)),
        capture_output=True, text=True, timeout=30, check=True,
    )
    gif_stream = json.loads(gif_probe.stdout)["streams"][0]
    assert (gif_stream["width"], gif_stream["height"], int(gif_stream["nb_read_frames"])) == (360, 320, 26)
    record = {
        "capture": output.relative_to(HERE).as_posix(),
        "sha256": sha256(output),
        "physical_pixels": [720, 640],
        "frames": 26,
        "browser_preview": preview.relative_to(HERE).as_posix(),
        "browser_preview_sha256": sha256(preview),
        "browser_preview_pixels": [360, 320],
        "capture_frame_interval_seconds": 0.07,
        "encoded_fps": 14,
        "camera_tween_seconds": 0.65,
        "source_sha256": {
            "make_transition_film.py": sha256(Path(__file__)),
            "scale_contact_room.gd": sha256(PROJECT / "comparison/scale_contact_room.gd"),
        },
        "notes": "Contains immediate standing-placeholder to seated-static-model switch; camera motion alone does not create character animation.",
    }
    (HERE / "camera_film.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print("M3_CAMERA_FILM", output, stream, "GIF_PREVIEW", gif_stream)


if __name__ == "__main__":
    main()
