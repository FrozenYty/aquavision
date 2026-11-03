#!/usr/bin/env python3
"""Check that paired documents share the same heading structure.

Text is not compared — only the sequence of heading levels. If the structures diverge, one side
was edited without the other, which is the most common way bilingual documents rot.

Pairs covered:
  docs/<name>-en.md  ↔  docs/<name>-zh.md
  README.md          ↔  README-zh.md

Usage: python scripts/check-bilingual.py
Exit code: 0 when every pair matches, 1 otherwise.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def heading_levels(path: Path) -> list[int]:
    levels: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING.match(line)
        if match:
            levels.append(len(match.group(1)))
    return levels


def iter_pairs() -> Iterator[tuple[Path, Path]]:
    for en_path in sorted(DOCS.glob("*-en.md")):
        yield en_path, en_path.with_name(en_path.name[: -len("-en.md")] + "-zh.md")

    readme_en = ROOT / "README.md"
    if readme_en.exists():
        yield readme_en, ROOT / "README-zh.md"


def main() -> int:
    pairs = list(iter_pairs())
    if not pairs:
        print("no document pairs found")
        return 0

    failures = 0
    for en_path, zh_path in pairs:
        if not zh_path.exists():
            print(f"MISSING  {zh_path.name}  (pair of {en_path.name})")
            failures += 1
            continue

        en_levels = heading_levels(en_path)
        zh_levels = heading_levels(zh_path)

        if en_levels == zh_levels:
            print(f"OK       {en_path.name}  ({len(en_levels)} headings)")
            continue

        failures += 1
        print(f"MISMATCH {en_path.name} vs {zh_path.name}")
        print(f"         en={len(en_levels)} headings, zh={len(zh_levels)} headings")
        for index, (a, b) in enumerate(zip(en_levels, zh_levels), start=1):
            if a != b:
                print(f"         first difference at heading #{index}: level {a} vs {b}")
                break
        else:
            longer = "en" if len(en_levels) > len(zh_levels) else "zh"
            print(f"         {longer} has extra headings after #{min(len(en_levels), len(zh_levels))}")

    print()
    if failures:
        print(f"{failures} pair(s) out of sync — update both files in the same commit.")
        return 1
    print("all pairs in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
