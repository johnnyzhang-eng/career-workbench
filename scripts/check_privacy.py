#!/usr/bin/env python3
"""Heuristic outbound-content check; never prints matching private text."""
import fnmatch
import os
import re
import struct
import subprocess
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENE_PNG = tuple("docs/scene-assets/" + name for name in (
    "room-day.png", "room-evening.png", "avatar-idle.png", "avatar-desk.png",
    "avatar-study.png", "avatar-interview.png", "avatar-rest.png", "desk-front.png"))
COMPARISON_PNG = tuple("prototype/comparison/compact_ui_hierarchy/" + name for name in (
    "baseline-360x480-first-screen.png", "expanded-1100x760.png",
    "improved-360x480-first-screen.png", "native-360x480-retina-active.png",
    "native-360x480-retina-idle.png", "native-360x480-retina-paused.png"))
ALLOW = ("README.md", "AGENTS.md", "CONTRIBUTING.md", "LICENSE", ".gitignore", "career.py", "daily.py",
         "workbench/*.py",
         "docs/*.md", "docs/*.html", "docs/goal-scene.js", "docs/product/*.md", "docs/product/*.html", "templates/*.json", "scripts/*.py", "tests/*.py",
         "prototype/macos/CompanionWindow.swift", "prototype/macos/build.sh", "prototype/macos/README.md",
         *SCENE_PNG, *COMPARISON_PNG)
RULES = {
    "email": re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    "mobile": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "personal_path": re.compile(r"/(?:Users|home)/[^/\s]+/"),
    "credential": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"),
    "credential_url": re.compile(r"https?://[^\s]+[?&](?:token|access_token|auth|signature|email)="),
}


def findings(text, private_terms=()):
    hits = []
    for name, pattern in RULES.items():
        for match in pattern.finditer(text):
            if name == "email" and match.group().split("@")[-1] in {"example.com", "example.org", "example.net", "example.invalid"}:
                continue
            hits.append(name)
            break
    if any(term.casefold() in text.casefold() for term in private_terms if term.strip()):
        hits.append("private_term")
    return hits


def png_findings(data):
    """Reject unexpected PNG metadata or malformed chunks in public scene art."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ["invalid_png"]
    safe_chunks = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"sRGB", b"gAMA", b"cHRM", b"pHYs"}
    offset = 8
    seen = []
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        end = offset + 12 + length
        if end > len(data):
            return ["invalid_png"]
        chunk_type = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        checksum = struct.unpack(">I", data[offset + 8 + length:end])[0]
        if zlib.crc32(chunk_type + payload) & 0xffffffff != checksum:
            return ["invalid_png_crc"]
        if chunk_type not in safe_chunks:
            return ["png_metadata_or_unknown_chunk"]
        seen.append(chunk_type)
        offset = end
        if chunk_type == b"IEND":
            break
    if not seen or seen[0] != b"IHDR" or seen[-1] != b"IEND" or offset != len(data):
        return ["invalid_png"]
    return []


def main():
    terms = os.environ.get("CAREER_PRIVATE_TERMS", "").split("|")
    files = set()
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in {".git", "private", "__pycache__", ".venv"} for part in relative.parts):
            continue
        if path.name == ".DS_Store":
            continue  # Finder metadata is ignored; tracked copies are still checked below.
        if path.is_file() or path.is_symlink():
            files.add(relative.as_posix())
    # Include tracked ignored files: .gitignore cannot protect an already tracked secret.
    if (ROOT / ".git").exists():
        result = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True)
        files.update(x for x in result.stdout.decode().split("\0") if x)
    failures = []
    for relative in sorted(files):
        path = ROOT / relative
        if not any(fnmatch.fnmatchcase(relative, pattern) for pattern in ALLOW) or relative.startswith("private/"):
            failures.append((relative, ["not_in_share_allowlist"]))
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            failures.append((relative, ["symlink_missing_or_oversized"]))
            continue
        if relative in SCENE_PNG or relative in COMPARISON_PNG:
            hits = png_findings(path.read_bytes())
        else:
            try:
                hits = findings(path.read_text(encoding="utf-8"), terms)
            except UnicodeError:
                hits = ["non_text_file"]
        if hits:
            failures.append((relative, hits))
    for relative, hits in failures:
        print(f"REVIEW {relative}: {','.join(hits)}")
    print(f"Scanned {len(files)} share-candidate files; flagged {len(failures)}. Manual content/history/identity review still required.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
