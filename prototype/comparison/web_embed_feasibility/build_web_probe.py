#!/usr/bin/env python3
"""Build the original A scene as a local-only 360x320 Godot Web export."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SOURCE = REPO / "prototype/godot"
BUILD = HERE / "_build"
PROJECT = BUILD / "project"
WEB = BUILD / "web"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", type=Path, default=Path("/Applications/Godot.app/Contents/MacOS/Godot"))
    parser.add_argument("--template", type=Path, default=HERE / "_local_templates/web_nothreads_release.zip")
    parser.add_argument("--font", type=Path, help="Optional local OFL font subset for Web text probe")
    args = parser.parse_args()
    godot = args.godot.resolve()
    template = args.template.resolve()
    if not godot.is_file() or not template.is_file():
        parser.error("Godot 4.7 and the matching web_nothreads_release.zip are required")
    shutil.rmtree(PROJECT, ignore_errors=True)
    shutil.copytree(SOURCE, PROJECT, ignore=shutil.ignore_patterns(".godot"))
    WEB.mkdir(parents=True, exist_ok=True)
    config_path = PROJECT / "project.godot"
    config = config_path.read_text()
    assert 'run/main_scene="res://main.tscn"' in config
    assert "window/size/viewport_width=1280" in config
    assert "window/size/viewport_height=720" in config
    config_path.write_text(
        config.replace('run/main_scene="res://main.tscn"', 'run/main_scene="res://comparison/main.tscn"')
        .replace("window/size/viewport_width=1280", "window/size/viewport_width=360")
        .replace("window/size/viewport_height=720", "window/size/viewport_height=320")
    )
    comparison_path = PROJECT / "comparison/comparison.gd"
    comparison = comparison_path.read_text()
    assert 'var route := "3d"' in comparison
    assert 'display_scale = DisplayServer.screen_get_scale()' in comparison
    assert 'DisplayServer.window_set_size(Vector2i(Vector2(value)*display_scale))' in comparison
    if args.font:
        font = args.font.resolve()
        if not font.is_file():
            parser.error(f"font does not exist: {font}")
        fonts = PROJECT / "fonts"
        fonts.mkdir(exist_ok=True)
        shutil.copy2(font, fonts / font.name)
        assert '\t_build_ui()' in comparison
        comparison = comparison.replace(
            '\t_build_ui()',
            f'\tvar web_theme := Theme.new()\n\tweb_theme.default_font = load("res://fonts/{font.name}")\n\ttheme = web_theme\n\t_build_ui()',
            1,
        )
    comparison_path.write_text(
        comparison.replace('var route := "3d"', 'var route := "baseline"')
        .replace(
            'display_scale = DisplayServer.screen_get_scale()',
            'display_scale = 1.0 if OS.has_feature("web") else DisplayServer.screen_get_scale()',
        )
        .replace(
            'DisplayServer.window_set_size(Vector2i(Vector2(value)*display_scale))',
            'if not OS.has_feature("web"): DisplayServer.window_set_size(Vector2i(Vector2(value)*display_scale))',
        )
    )
    (PROJECT / "export_presets.cfg").write_text(
        '[preset.0]\n'
        'name="Web A 360"\n'
        'platform="Web"\n'
        'runnable=true\n'
        'advanced_options=false\n'
        'export_filter="all_resources"\n'
        'include_filter=""\n'
        'exclude_filter=""\n'
        'export_path="../web/index.html"\n'
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
        [str(godot), "--headless", "--path", str(PROJECT), "--export-release", "Web A 360", str(WEB / "index.html")],
        check=True,
    )
    for output in sorted(WEB.iterdir()):
        print(f"{output.name}\t{output.stat().st_size} bytes")


if __name__ == "__main__":
    main()
