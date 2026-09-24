#!/usr/bin/env python3
"""Export an isolated scene-only Godot A canvas for the read-only bridge probe."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SOURCE = REPO / "prototype/godot"
BUILD = HERE / "_build"
PROJECT = BUILD / "project"
WEB = BUILD / "web/godot"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", type=Path, default=Path("/Applications/Godot.app/Contents/MacOS/Godot"))
    parser.add_argument("--template", type=Path, default=HERE / "_local_templates/web_nothreads_release.zip")
    args = parser.parse_args()
    godot = args.godot.resolve()
    template = args.template.resolve()
    if not godot.is_file() or not template.is_file():
        parser.error("Godot 4.7 and a matching nonthreaded Web template are required")
    shutil.rmtree(PROJECT, ignore_errors=True)
    shutil.copytree(SOURCE, PROJECT, ignore=shutil.ignore_patterns(".godot"))
    shutil.copy2(HERE / "room_scene_only.gd", PROJECT / "comparison/room_scene_only.gd")
    shutil.copy2(HERE / "room_scene_only.tscn", PROJECT / "comparison/room_scene_only.tscn")
    WEB.mkdir(parents=True, exist_ok=True)
    config_path = PROJECT / "project.godot"
    config = config_path.read_text()
    assert 'run/main_scene="res://main.tscn"' in config
    assert "window/size/viewport_width=1280" in config
    assert "window/size/viewport_height=720" in config
    config_path.write_text(
        config.replace('run/main_scene="res://main.tscn"', 'run/main_scene="res://comparison/room_scene_only.tscn"')
        .replace("window/size/viewport_width=1280", "window/size/viewport_width=360")
        .replace("window/size/viewport_height=720", "window/size/viewport_height=320")
    )
    (PROJECT / "export_presets.cfg").write_text(
        '[preset.0]\n'
        'name="Room Only Web"\n'
        'platform="Web"\n'
        'runnable=true\n'
        'advanced_options=false\n'
        'export_filter="all_resources"\n'
        'include_filter=""\n'
        'exclude_filter=""\n'
        '\n[preset.0.options]\n'
        f'custom_template/release="{template}"\n'
        'variant/thread_support=false\n'
        'variant/extensions_support=false\n'
        'html/canvas_resize_policy=2\n'
        'html/focus_canvas_on_start=false\n'
        'progressive_web_app/enabled=false\n'
    )
    subprocess.run([str(godot), "--headless", "--path", str(PROJECT), "--import"], check=True)
    subprocess.run(
        [str(godot), "--headless", "--path", str(PROJECT), "--export-release", "Room Only Web", str(WEB / "index.html")],
        check=True,
    )
    for output in sorted(WEB.iterdir()):
        print(f"{output.name}\t{output.stat().st_size} bytes")


if __name__ == "__main__":
    main()
