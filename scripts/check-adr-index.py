#!/usr/bin/env python3
"""Every decision record must be listed, and every listed one must exist.

Adding an ADR is a two-file change — the record itself, and the table in both architecture
documents — and the second half was forgotten three times in one day. This check makes the
forgotten half a failing build instead of a reader's confusion.

It also checks the range written in the documentation index, `adr/01-NN`, since that number rots
the same way. Both directions are checked: a file missing from the table, and a table row pointing
at a file that is not there.

    python scripts/check-adr-index.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADR_DIR = ROOT / "docs" / "adr"
ARCHITECTURE = (ROOT / "docs" / "architecture-en.md", ROOT / "docs" / "architecture-zh.md")
INDEX = (ROOT / "docs" / "INDEX-en.md", ROOT / "docs" / "INDEX-zh.md")

LINK = re.compile(r"\]\(adr/([^)]+\.md)\)")
RANGE = re.compile(r"`adr/01-(\d{2})`")


def adr_files() -> list[str]:
    return sorted(path.name for path in ADR_DIR.glob("*.md"))


def main() -> int:
    files = adr_files()
    problems: list[str] = []

    if not files:
        print(f"no decision records in {ADR_DIR.relative_to(ROOT)}", file=sys.stderr)
        return 1

    for path in ARCHITECTURE:
        listed = sorted(set(LINK.findall(path.read_text(encoding="utf-8"))))
        for name in files:
            if name not in listed:
                problems.append(f"{path.name}: {name} is not in the decision table")
        for name in listed:
            if name not in files:
                problems.append(f"{path.name}: lists {name}, which does not exist")

    highest = int(files[-1][:2])
    for path in INDEX:
        match = RANGE.search(path.read_text(encoding="utf-8"))
        if match is None:
            problems.append(f"{path.name}: no `adr/01-NN` range found")
            continue
        if int(match.group(1)) != highest:
            problems.append(
                f"{path.name}: says adr/01-{match.group(1)}, the latest record is {highest:02d}"
            )

    if problems:
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(f"\n{len(problems)} problem(s) with the decision-record index.", file=sys.stderr)
        return 1

    print(f"all {len(files)} decision records are listed, and the index range matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
