#!/usr/bin/env python3
"""Check that paired documents share the same structure, not only the same headings.

Two comparisons, because one is not enough and this was learned the hard way:

1. **Heading levels.** If the structures diverge, one side was edited without the other.
2. **The shape of every section** - each table's row and column counts, and how many fenced code
   blocks it holds. Heading parity proves the pair has the same outline; it says nothing about the
   contents. A five-day-old defect lived in exactly that gap: the Chinese data model listed nine
   entities where the English listed thirteen, and every check passed because both files had the same
   headings.

What is deliberately **not** compared: the words. A translation differs by design, and a check that
quarrelled with prose would be switched off within a week. Row and column counts, and code-block
counts, are stable across languages - a command is a command and a table row is a table row.

Pairs covered:
  docs/<name>-en.md  <->  docs/<name>-zh.md
  README.md          <->  README-zh.md

Usage: python scripts/check-bilingual.py
Exit code: 0 when every pair matches, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEPARATOR = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
FENCE = re.compile(r"^\s*(?:```|~~~)")

#: README pairs outside `docs/`. Each is (english, chinese), relative to the repository root.
READMES = [
    ("README.md", "README-zh.md"),
    ("firmware/README.md", "README-zh.md"),
]


def heading_levels(path: Path) -> list[int]:
    """Return the level of every heading line, in order."""
    levels: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING.match(line)
        if match:
            levels.append(len(match.group(1)))
    return levels


def iter_pairs() -> Iterator[tuple[Path, Path]]:
    """Yield (english, chinese) document pairs to compare."""
    for en_path in sorted(DOCS.glob("*-en.md")):
        yield en_path, en_path.with_name(en_path.name[: -len("-en.md")] + "-zh.md")

    for en_name, zh_name in READMES:
        en_path = ROOT / en_name
        if en_path.exists():
            # The Chinese file sits beside the English one, not at the repository root.
            yield en_path, en_path.parent / zh_name


#: One section: its heading text, the line it starts on, and its body lines.
Section = tuple[str, int, list[str]]


def sections(path: Path) -> list[Section]:
    """Split a document into sections at its headings, keeping line numbers.

    The heading line is not part of the body, and text before the first heading is not a section:
    a preamble has no counterpart to compare against.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    found: list[Section] = []
    current_title: str | None = None
    current_line = 0
    current_body: list[str] = []

    for number, line in enumerate(lines, start=1):
        match = HEADING.match(line)
        if match:
            if current_title is not None:
                found.append((current_title, current_line, current_body))
            current_title = match.group(2).strip()
            current_line = number
            current_body = []
            continue
        if current_title is not None:
            current_body.append(line)

    if current_title is not None:
        found.append((current_title, current_line, current_body))
    return found


def tables(body: list[str], offset: int) -> list[tuple[int, int, int]]:
    """Every markdown table in a section: (rows, columns, line number of its first row).

    The header row counts as a row, deliberately. A table that lost its header in translation then
    holds one line fewer than its counterpart, which is the only way a row comparison can see that
    defect at all - counting data rows alone would make both sides equal again. Separator rows
    (`|---|---|`) are structure, not content, so they are not counted.
    """
    found: list[tuple[int, int, int]] = []
    rows = 0
    columns = 0
    first_line = 0
    for index, line in enumerate(body):
        if TABLE_ROW.match(line):
            if rows == 0:
                first_line = offset + index + 1
                columns = len(line.strip().strip("|").split("|"))
            if not TABLE_SEPARATOR.match(line):
                rows += 1
            continue
        if rows:
            found.append((rows, columns, first_line))
            rows = 0
            columns = 0
    if rows:
        found.append((rows, columns, first_line))
    return found


def code_blocks(body: list[str]) -> list[int]:
    """Line numbers where a fenced code block starts."""
    starts: list[int] = []
    inside = False
    for index, line in enumerate(body):
        if FENCE.match(line):
            if not inside:
                starts.append(index + 1)
            inside = not inside
    return starts


def compare_pair(en_path: Path, zh_path: Path) -> list[str]:
    """Return the structural differences between a pair, ready to print."""
    problems: list[str] = []
    en_sections = sections(en_path)
    zh_sections = sections(zh_path)

    for index, ((en_title, en_line, en_body), (_zh_title, zh_line, zh_body)) in enumerate(
        zip(en_sections, zh_sections, strict=False), start=1
    ):
        en_tables = tables(en_body, en_line)
        zh_tables = tables(zh_body, zh_line)
        if len(en_tables) != len(zh_tables):
            problems.append(
                f"         section {index} ({en_title!r}): en has {len(en_tables)} table(s), "
                f"zh has {len(zh_tables)}  [en line {en_line}, zh line {zh_line}]"
            )
        for position, (en_table, zh_table) in enumerate(
            zip(en_tables, zh_tables, strict=False), start=1
        ):
            en_rows, en_columns, en_at = en_table
            zh_rows, zh_columns, zh_at = zh_table
            if (en_rows, en_columns) != (zh_rows, zh_columns):
                problems.append(
                    f"         section {index} ({en_title!r}) table {position}: "
                    f"en {en_rows} rows x {en_columns} cols, zh {zh_rows} rows x {zh_columns} cols"
                    f"  [en line {en_at}, zh line {zh_at}]"
                )

        en_code = code_blocks(en_body)
        zh_code = code_blocks(zh_body)
        if len(en_code) != len(zh_code):
            problems.append(
                f"         section {index} ({en_title!r}): en has {len(en_code)} code block(s), "
                f"zh has {len(zh_code)}  [en line {en_code or en_line}, zh line {zh_code or zh_line}]"
            )

    return problems


def report(pairs: list[tuple[Path, Path]]) -> int:
    """Print one line per pair and return the number of failures."""
    failures = 0
    for en_path, zh_path in pairs:
        if not zh_path.exists():
            print(f"MISSING  {zh_path.name}  (pair of {en_path.name})")
            failures += 1
            continue

        en_levels = heading_levels(en_path)
        zh_levels = heading_levels(zh_path)

        if en_levels != zh_levels:
            failures += 1
            print(f"MISMATCH {en_path.name} vs {zh_path.name}")
            print(f"         en={len(en_levels)}, zh={len(zh_levels)} headings")
            for index, (a, b) in enumerate(zip(en_levels, zh_levels, strict=False), start=1):
                if a != b:
                    print(f"         difference at heading #{index}: level {a} vs {b}")
                    break
            else:
                common = min(len(en_levels), len(zh_levels))
                longer = "en" if len(en_levels) > len(zh_levels) else "zh"
                print(f"         {longer} has extra headings after #{common}")
            continue

        problems = compare_pair(en_path, zh_path)
        if problems:
            failures += 1
            print(f"SHAPE    {en_path.name} vs {zh_path.name}")
            for problem in problems:
                print(problem)
            continue

        table_count = sum(len(tables(body, line)) for _t, line, body in sections(en_path))
        code_count = sum(len(code_blocks(body)) for _t, _l, body in sections(en_path))
        print(
            f"OK       {en_path.name}  ({len(en_levels)} headings, "
            f"{table_count} tables, {code_count} code blocks)"
        )

    return failures


def main() -> int:
    pairs = list(iter_pairs())
    if not pairs:
        print("no document pairs found")
        return 0

    failures = report(pairs)
    print()
    if failures:
        print(f"{failures} pair(s) out of sync - update both files in the same commit.")
        return 1
    print("all pairs in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
