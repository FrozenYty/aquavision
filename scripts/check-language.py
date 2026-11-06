#!/usr/bin/env python3
"""Reject Chinese characters in English documents and in configuration files.

An English document describes the thing in English. Chinese product names and search strings belong
in its ``-zh`` counterpart, where the reader needs them verbatim. The single exception is the README
language switcher: it is navigation, not prose.

Configuration files are covered too — .gitignore, .gitattributes, pyproject.toml, requirements.txt and
the GitHub workflows — because their comments are read by the same people. Product strings are not
covered: the interface is Chinese by requirement (SRS §2.5.2), so web/ and the messages the capture
code prints are legitimately Chinese.

Usage: python scripts/check-language.py
Exit code: 0 when every file checked is clean, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CJK = re.compile(r"[\u4e00-\u9fff]")
SWITCHER = re.compile(r"\[中文\]\([^)]*-zh\.md\)")


CONFIG_FILES = [".gitignore", ".gitattributes", "pyproject.toml", "requirements.txt"]
CONFIG_GLOBS = [".github/**/*.yml", ".github/**/*.md"]


def english_documents() -> list[Path]:
    """English Markdown that is not a Chinese counterpart, plus the configuration files."""
    files = sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").rglob("*.md"))
    english = [path for path in files if not path.name.endswith("-zh.md")]

    config = [ROOT / name for name in CONFIG_FILES if (ROOT / name).is_file()]
    for pattern in CONFIG_GLOBS:
        config.extend(sorted(ROOT.glob(pattern)))

    return [path for path in english + config if path.is_file()]


def is_switcher(line: str) -> bool:
    """True when the only Chinese on the line sits inside a language switcher link."""
    stripped = SWITCHER.sub("", line)
    return not CJK.search(stripped)


def main() -> int:
    problems = 0
    for path in english_documents():
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            if not CJK.search(line) or is_switcher(line):
                continue
            shown = line.strip()
            if len(shown) > 80:
                shown = shown[:77] + "..."
            print(f"{path.relative_to(ROOT)}:{number}: {shown}")
            problems += 1

    print()
    if problems:
        print(f"{problems} line(s) carry Chinese in an English document.")
        print("Move product names and search strings into the -zh counterpart.")
        return 1
    print("all English documents are free of Chinese")
    return 0


if __name__ == "__main__":
    sys.exit(main())
