#!/usr/bin/env python3
"""Keep PROGRESS.md scannable.

Four rules, each cheap to check and each easy to break silently:
  1. every entry starts with a heading of the form ``## YYYY-MM-DD`` — a date and nothing else;
  2. one entry per day, never two;
  3. entries run newest first;
  4. a day stays within 40 lines.

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
DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})$")
MAX_LINES = 40


def read_entries() -> list[dict[str, object]]:
    """Return one record per section: its title and how many body lines follow it."""
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
    seen: set[str] = set()

    for entry in read_entries():
        title = str(entry["title"])
        lines = int(entry["lines"])
        dated = DATED.match(title)

        if not dated:
            print(f"  bad heading: '## {title}' - expected '## YYYY-MM-DD' and nothing else")
            problems += 1
            continue

        date = dated.group(1)
        if date in seen:
            print(f"  duplicate entry: {date} appears twice - merge it into one")
            problems += 1
        seen.add(date)

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
