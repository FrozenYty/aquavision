#!/usr/bin/env python3
"""Keep PROGRESS.md scannable.

Three rules, each cheap to check and each easy to break silently:
  1. every entry starts with a heading of the form ``## YYYY-MM-DD``;
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


def read_entries() -> list[dict[str, object]]:
    """Return one record per dated section: its title, its date and its line count."""
    entries: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for line in LOG.read_text(encoding="utf-8").splitlines():
        heading = HEADING.match(line)
        if heading:
            current = {"title": heading.group(1).strip(), "lines": 0}
            entries.append(current)
            continue
        if current is not None:
            current["lines"] = int(current["lines"]) + 1

    return entries


def main() -> int:
    problems = 0
    previous_date = ""

    for entry in read_entries():
        title = str(entry["title"])
        lines = int(entry["lines"])
        dated = DATED.match(title)

        if not dated:
            print(f"  bad heading: '## {title}' - expected '## YYYY-MM-DD'")
            problems += 1
            continue

        date = dated.group(1)
        if previous_date and date > previous_date:
            print(f"  out of order: {date} appears after {previous_date}")
            problems += 1
        previous_date = date

        if lines > MAX_LINES:
            print(f"  too long: {date} has {lines} lines, limit {MAX_LINES}")
            problems += 1

    print()
    if problems:
        print(f"{problems} problem(s) in PROGRESS.md")
        return 1

    print(f"PROGRESS.md is well formed ({len(read_entries())} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
