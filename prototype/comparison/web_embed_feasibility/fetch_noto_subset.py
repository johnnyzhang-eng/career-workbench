#!/usr/bin/env python3
"""Fetch a tiny Noto Sans SC subset for the fictional comparison UI only.

Source: Google Fonts CSS API; font family Noto Sans SC (SIL OFL 1.1).
The source font/license live at https://github.com/notofonts/noto-cjk/tree/main/Sans.
The fetched subset stays in _local_templates and is not committed.
"""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path


HERE = Path(__file__).resolve().parent
COMPARISON = HERE.parents[1] / "godot/comparison"
DESTINATION = HERE / "_local_templates/NotoSansSC-fictional-subset.ttf"


def main() -> None:
    sources = [COMPARISON / "comparison.gd", COMPARISON / "tasks.json"]
    text = "".join(path.read_text() for path in sources)
    chars = "".join(sorted(set(char for char in text if char.isprintable())))
    css_url = "https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400&text=" + urllib.parse.quote(chars)
    request = urllib.request.Request(css_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        css = response.read().decode("utf-8")
    match = re.search(r"src:\s*url\((https://fonts\.gstatic\.com/[^)]+)\) format\('truetype'\)", css)
    if not match:
        raise RuntimeError(f"Unexpected Google Fonts CSS format: {css[:200]}")
    with urllib.request.urlopen(match.group(1), timeout=30) as response:
        font_data = response.read()
    if not font_data.startswith((b"\x00\x01\x00\x00", b"OTTO")):
        raise RuntimeError("Downloaded data is not a TTF/OTF font")
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_bytes(font_data)
    print(f"characters={len(chars)} font_bytes={len(font_data)} destination={DESTINATION}")


if __name__ == "__main__":
    main()
