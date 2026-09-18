#!/usr/bin/env python3
"""Heuristic outbound-content check; never prints matching private text."""
import fnmatch
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOW = ("README.md", "AGENTS.md", "CONTRIBUTING.md", "LICENSE", ".gitignore", "career.py",
         "docs/*.md", "docs/*.html", "docs/product/*.md", "docs/product/*.html", "templates/*.json", "scripts/*.py", "tests/*.py",
         "workbench/*.py",
         ".agents/skills/*/SKILL.md", ".github/ISSUE_TEMPLATE/*.md", ".github/PULL_REQUEST_TEMPLATE.md",
         ".github/workflows/*.yml")
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
