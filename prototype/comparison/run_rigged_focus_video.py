"""Record the real R2 action in the room-first 360×320 Godot window."""

import json
import re
import subprocess
from pathlib import Path

from run_activity_focus_layout import GODOT, PROJECT, SCENE, digest


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "prototype" / "comparison" / "activity_focus_layout" / "rigged" / "L1"
FRAMES = OUT / "_video_frames"
VIDEO = OUT / "sit-and-type-focus-360x320-day.mp4"


def run():
    FRAMES.mkdir(parents=True, exist_ok=True)
    cmd = [str(GODOT), "--path", str(PROJECT), SCENE, "--", "--route=baseline",
           "--size=360x320", "--phase=day", f"--out={FRAMES.resolve()}",
           "--rigged-character", "--activity-focus-layout", "--film",
           "--capture", "--proof", "--quit"]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=90)
    log = (proc.stdout + proc.stderr).replace(str(ROOT), "<repo>")
    log = re.sub(r"/Users/[^/]+/", "/Users/<local>/", log)
    (OUT / "focus-video.log").write_text(log)
    frames = sorted(FRAMES.glob("baseline-360x320-day-focus-motion-*.png"))
    if proc.returncode or "SCRIPT ERROR" in log or "ERROR:" in log or len(frames) != 60:
        raise RuntimeError("Godot 视频采集没有完整产生 60 帧")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-framerate", "24",
                    "-i", str(FRAMES / "baseline-360x320-day-focus-motion-%03d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(VIDEO)], check=True)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
                            "-of", "json", str(VIDEO)], check=True, capture_output=True, text=True)
    metadata = {"godot_frames": len(frames), "encode_fps": 24,
                "input": "R2 SitToType then TypingLoop in L1 compact room",
                "video": VIDEO.name, "sha256": digest(VIDEO),
                "ffprobe": json.loads(probe.stdout)}
    (OUT / "focus-video.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    run()
