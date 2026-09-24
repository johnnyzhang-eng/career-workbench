"""Count changed physical pixels between left/right typing peaks at compact size.

The fixed crop covers the character, chair and keyboard only. This numerical
check complements inspection at 360 logical pixels; it cannot rate aesthetics.
"""

import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
WIDTH, HEIGHT = 720, 640  # Retina capture of a 360x320 logical window.
CROP = (320, 190, 385, 260)  # Physical pixels, inclusive left/top.
THRESHOLD = 16


def rgb(path):
    data = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo",
        "-pix_fmt", "rgb24", "-",
    ])
    assert len(data) == WIDTH * HEIGHT * 3
    return data


def count(variant):
    folder = HERE / variant / "360x320-day"
    before = rgb(folder / "typing-left-down-360x320-day.png")
    after = rgb(folder / "typing-right-down-360x320-day.png")
    x0, y0, x1, y1 = CROP
    changed = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            offset = (y * WIDTH + x) * 3
            if max(abs(before[offset + c] - after[offset + c]) for c in range(3)) > THRESHOLD:
                changed += 1
    return changed


def main():
    counts = {variant: count(variant) for variant in ("R2", "R3")}
    report = {
        "logical_window": [360, 320],
        "physical_capture": [WIDTH, HEIGHT],
        "crop_physical_xyxy": list(CROP),
        "rgb_channel_difference_threshold_exclusive": THRESHOLD,
        "changed_pixels_between_typing_peaks": counts,
        "interpretation": "R3's contact-constrained action changes almost the same small number of pixels as R2; this is not proof of compact-size readability.",
    }
    target = HERE / "R3" / "motion_measure.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
