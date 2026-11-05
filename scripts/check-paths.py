#!/usr/bin/env python3
"""Reject machine-specific paths in shared documents.

An absolute path in a shared file is a dead link on every other machine, and it leaks how one
person's disk happens to be arranged. Commands belong relative to the repository root, and the
interpreter is written ``python``.

Usage: python scripts/check-paths.py
Exit code: 0 when every document is portable, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Drive letters, UNC shares, POSIX home directories, and the conda environment names this team uses.
PATTERNS = [
    re.compile(r"[A-Za-z]:[\\/](?![a-z]*/)"),  # D:\ or C:/ with a real path after it
    re.compile(r"\\\\[A-Za-z0-9_.-]+\\"),  # \\server\share
    re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+/"),  # /Users/name/ or /home/name/
    re.compile(r"anaconda3?[\\/]"),  # interpreter paths that pin an install
]


def documents() -> list[Path]:
    """Every Markdown file the team reads."""
    files = sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").rglob("*.md"))
    return [path for path in files if path.name != "check-paths.md"]


def main() -> int:
    problems = 0
    for path in documents():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not any(pattern.search(line) for pattern in PATTERNS):
                continue
            shown = line.strip()
            if len(shown) > 80:
                shown = shown[:77] + "..."
            print(f"{path.relative_to(ROOT)}:{number}: {shown}")
            problems += 1

    print()
    if problems:
        print(f"{problems} line(s) carry a machine-specific path.")
        print("Write commands relative to the repository root; use `python` as the interpreter.")
        return 1
    print("all documents are portable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
