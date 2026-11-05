#!/usr/bin/env python3
"""Keep PROGRESS.md scannable.

Two rules, both cheap to check and both easy to break silently:
  1. every entry starts with ``## YYYY-MM-DD`` (an optional suffix in parentheses is allowed);
  2. entries run newest first;
  3. an entry stays within 20 lines, roughly one screen.

Usage: python scripts/check-progress.py
Exit code: 0 when the log is well formed, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "PROGRESS.md"
HEADING = re.compile(r"^## (.+)$")
DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:\s*\(.+\))?$")
MAX_LINES = 20


def main() -> int:
    text = LOG.read_text(encoding="utf-8")
    entries: list[tuple[str, str, int]] = []
    title = None
    count = 0
    for line in text.splitlines():
        match = HEADING.match(line)
        if match:
            if title is not None:
                entries.append((title, date, count))
            title = match.group(1).strip()
            date = ""
            count = 0
            continue
        if title is not None:
            count += 1
    if title is not None:
        entries.append((title, date, count))

    problems = 0
    previous = ""
    for entry_title, _unused, lines in entries:
        match = DATED.match(entry_title)
        if not match:
            print(f"  bad heading: '## {entry_title}' - expected '## YYYY-MM-DD'")
            problems += 1
            continue
        date = match.group(1)
        if previous and date > previous:
            print(f"  out of order: {date} appears after {previous}")
            problems += 1
        previous = date
        if lines > MAX_LINES:
            print(f"  too long: {date} has {lines} lines, limit {MAX_LINES}")
            problems += 1

    print()
    if problems:
        print(f"{problems} problem(s) in PROGRESS.md")
        return 1
    print(f"PROGRESS.md is well formed ({len(entries)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
