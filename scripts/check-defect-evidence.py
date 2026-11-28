#!/usr/bin/env python3
"""Check that every closed defect in PLAN.md P4-05 names the evidence that guards it.

P4-05 is the defect log: one bullet per defect, and a closure is written into the entry with the
log's own marker - ``closed`` followed by the day, ``closed 11-27``. A closure is a claim, and PLAN
section 5 already says a ticked box without a merged pull request is a claim rather than a fact; the
mechanical half of that sentence is the evidence named in the entry. Two rules:

- **a closed entry names its regression check.** It must name at least one ``tests/...py`` or
  ``tests/...mjs`` path that exists, optionally as ``tests/test_thing.py::test_name``. A regression
  check that is not in the repository cannot fail when the defect returns, and a check that was renamed
  is the ordinary way this rots. ``docs/adr/...`` is accepted instead for a defect whose closure is a
  decision record rather than a test: an accepted ADR is superseded rather than edited, so the record
  is what a reviewer reads if the retired rule comes back. That is how the ADR-16/17 item is closed -
  by a document, not a test. An entry whose severity says ``minor, documentation`` is closed by the
  document that carries the correction, so any existing ``docs/...md`` counts. And a defect with no
  host harness - the firmware line parser - names a written bench procedure with the ``manual:`` form;
  that closure is accepted and printed as a note, so the manual ones stay visible instead of passing as
  if they had a test.
- **an open entry names nothing that is gone.** An open, cosmetic or left-open entry need not name
  a test, but if it names one it must exist - otherwise the log is describing a file that moved.

The defect this exists for: P3-35 asks that every closed defect carry a regression test, and until
this check existed an entry could be closed with prose and no file named, and nothing would notice.
A defect closed without a regression check is the one that quietly returns.

A closure here is the dated marker only. The log also narrates its review and measurement closures
in prose ("four majors closed outside the audit's list"); those are reported by the audit that
accompanies this check, not read as closures here, so an entry that is closed only in prose is not
required to name evidence. When such an entry gains the marker, this check enforces it.

Usage: python scripts/check-defect-evidence.py
Exit code: 0 when every closed entry names existing evidence and no entry names a missing path, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "PLAN.md"

#: A task line. The defect log runs from P4-05's task line to the next task line.
TASK = re.compile(r"(?m)^-\s+\[[ xX]\]\s+\*\*(P\d+-\d+)\*\*")
#: A bullet inside the log - one defect entry, at either indentation.
BULLET = re.compile(r"(?m)^[ \t]*- ")
#: The closure marker: the word "closed" and the day the entry was closed.
CLOSED = re.compile(r"\bclosed\s+11-\d{2}\b")
#: Evidence an entry can name: a test (Python or a node page suite, optionally with its function),
#: a decision record, and - for a documentation defect - the document that carries the correction.
EVIDENCE = re.compile(
    r"(?P<test>tests/[A-Za-z0-9_.\-/]+\.(?:py|mjs))(?:::[A-Za-z0-9_]+)?"
    r"|(?P<adr>docs/adr/[A-Za-z0-9_.\-/]+\.md)"
)
#: A documentation defect that is closed by a document, not a test: the entry says so in its severity.
DOCUMENTATION = re.compile(r"minor,\s*documentation")
#: The manual form: a defect with no host harness (the firmware) names a written bench procedure.
#: `manual: path/to/procedure.md` is accepted, and reported as a warning rather than silently.
MANUAL = re.compile(r"manual:\s*(?P<manual>[A-Za-z0-9_.\-/]+\.md)")
#: The document a documentation defect is closed by, when its severity says "minor, documentation".
DOCUMENT = re.compile(r"docs/(?!adr/)[A-Za-z0-9_.\-/]+\.md")


def defect_log(plan_text: str) -> tuple[int, int]:
    """The offset range of the P4-05 block: its task line to the next task line."""
    tasks = list(TASK.finditer(plan_text))
    for position, match in enumerate(tasks):
        if match.group(1) != "P4-05":
            continue
        end = tasks[position + 1].start() if position + 1 < len(tasks) else len(plan_text)
        return match.start(), end
    raise ValueError("PLAN.md has no P4-05 task line - the defect log moved")


def defect_entries(plan_text: str) -> list[tuple[int, str]]:
    """Every bullet in the P4-05 block as (line number in PLAN.md, entry text).

    The first bullet is P4-05's own task line and is not an entry. Each entry runs to the next
    bullet line, so a continuation line belongs to the entry it follows.
    """
    start, end = defect_log(plan_text)
    block = plan_text[start:end]
    bullets = list(BULLET.finditer(block))
    entries: list[tuple[int, str]] = []
    for index, bullet in enumerate(bullets):
        if bullet.start() == 0:
            continue
        stop = bullets[index + 1].start() if index + 1 < len(bullets) else len(block)
        line = plan_text.count("\n", 0, start + bullet.start()) + 1
        entries.append((line, block[bullet.start() : stop]))
    return entries


def evidence(entry: str) -> list[str]:
    """The repository files an entry names as its evidence, in the order they appear."""
    named: list[str] = []
    for match in EVIDENCE.finditer(entry):
        path = match.group("test") or match.group("adr")
        if path not in named:
            named.append(path)
    return named


def manual_evidence(entry: str) -> list[str]:
    """The written bench procedures an entry names with the `manual:` form."""
    return [match.group("manual") for match in MANUAL.finditer(entry)]


def label(entry: str) -> str:
    """The entry's first line, without its bullet marker - what a failure prints."""
    first = entry.splitlines()[0].strip()
    return first[2:] if first.startswith("- ") else first


def analyse(plan_text: str, exists) -> tuple[list[str], list[str]]:
    """Return (problems, warnings) for the defect log. `exists` decides whether a named file is real."""
    entries = defect_entries(plan_text)
    problems: list[str] = []
    warnings: list[str] = []
    for line, entry in entries:
        named = evidence(entry)
        real = [path for path in named if exists(path)]
        manuals = manual_evidence(entry)
        manual_real = [path for path in manuals if exists(path)]
        documented = [
            path for path in DOCUMENT.findall(entry) if exists(path) and DOCUMENTATION.search(entry)
        ]
        if CLOSED.search(entry):
            if real or manual_real or documented:
                for path in manual_real:
                    warnings.append(
                        f"PLAN.md:{line}: closed by a manual bench procedure, not a test ({path}): "
                        f"{label(entry)}"
                    )
                continue
            if named or manuals:
                stale = named + manuals
                problems.append(
                    f"PLAN.md:{line}: closed defect names no evidence that exists - "
                    f"it names {', '.join(stale)}: {label(entry)}"
                )
            else:
                problems.append(
                    f"PLAN.md:{line}: closed defect names no regression check: {label(entry)}"
                )
        else:
            for path in named + manuals:
                if not exists(path):
                    problems.append(
                        f"PLAN.md:{line}: names {path}, which does not exist: {label(entry)}"
                    )
    return problems, warnings


def report(problems: list[str], warnings: list[str]) -> int:
    if not problems and not warnings:
        return 0
    if problems:
        print("defect evidence:")
        for problem in problems:
            print(f"  - {problem}")
    for warning in warnings:
        print(f"  note: {warning}")
    return len(problems)


def main() -> int:
    if not PLAN.is_file():
        print(f"missing input: {PLAN.name}")
        return 1

    plan_text = PLAN.read_text(encoding="utf-8")
    try:
        entries = defect_entries(plan_text)
    except ValueError as error:
        print(error)
        return 1
    closed = [entry for _line, entry in entries if CLOSED.search(entry)]
    if not closed:
        print(
            "no entry in the P4-05 block carries the closure marker `closed 11-DD` - "
            "the log moved or stopped marking closures, so this check proves nothing"
        )
        return 1

    problems, warnings = analyse(plan_text, exists=lambda path: (ROOT / path).is_file())
    failures = report(problems, warnings)
    if failures:
        print(
            f"\n{len(entries)} defect entries, {len(closed)} closed, {failures} problem(s) - "
            "a closed defect must name the check that fails if it returns."
        )
        return 1
    print(
        f"{len(entries)} defect entries, {len(closed)} closed, each names evidence that exists"
        + (f" ({len(warnings)} closed by a manual bench procedure)" if warnings else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
