#!/usr/bin/env python3
"""Check that every acceptance item is owned, and that a claimed one names its evidence.

An acceptance item is what the project is judged on, so the two ways it can go quiet are both failures:

- **nobody owns it.** No task in `PLAN.md` mentions it, so it will not be built, and no gate will notice.
- **something claims it without evidence.** A ticked task says it closes the item and names no test that
  exists. `PLAN.md` section 5 already says a ticked box without a merged pull request is a claim rather
  than a fact; this is the mechanical half of that sentence.

The evidence rule is deliberately a **link, not a proof**: the check confirms the named file exists, and a
person confirms it asserts the right thing. That is the strongest thing a script can honestly do, and it is
enough to catch the two ways this rots - a test that was renamed, and a claim that never had a test.

The 11-11 audit found 14 of the 36 items traced, which is why this exists.

Usage: python scripts/check-ac-coverage.py
Exit code: 0 when every item is owned and every claim names existing evidence, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRS = ROOT / "docs" / "srs-en.md"
PLAN = ROOT / "PLAN.md"

#: An acceptance row in the SRS: `| AC-01 | Module | Function | ... |`.
SRS_ROW = re.compile(r"^\|\s*(AC-[0-9]{2})\s*\|\s*([^|]*)\|\s*([^|]*)\|", re.M)
#: A task block start. The block runs to the next task, so a mention anywhere in it counts.
TASK_START = re.compile(r"(?m)^- \[( |x)\] \*\*(P[0-9]-[0-9]+)\*\*")
#: Any acceptance id, and any repository file a task can point at as evidence.
AC_ID = re.compile(r"\bAC-[0-9]{2}\b")
EVIDENCE = re.compile(r"\b((?:tests|scripts)/[A-Za-z0-9_./-]+\.py)")


def acceptance_items(srs_text: str) -> dict[str, tuple[str, str]]:
    """Every acceptance item in the SRS, mapped to (module, function)."""
    return {
        ac: (module.strip(), function.strip()) for ac, module, function in SRS_ROW.findall(srs_text)
    }


def task_blocks(plan_text: str) -> list[tuple[str, bool, str]]:
    """Every task as (id, ticked, block text)."""
    starts = list(TASK_START.finditer(plan_text))
    blocks = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(plan_text)
        blocks.append((match.group(2), match.group(1) == "x", plan_text[match.start() : end]))
    return blocks


def analyse(srs_text: str, plan_text: str, exists) -> list[str]:
    """Return the problems, ready to print. `exists` decides whether a named file is real."""
    items = acceptance_items(srs_text)
    blocks = task_blocks(plan_text)
    problems: list[str] = []

    owns: dict[str, list[tuple[str, bool]]] = {ac: [] for ac in items}
    for task_id, ticked, block in blocks:
        for ac in set(AC_ID.findall(block)):
            if ac in items:
                owns[ac].append((task_id, ticked))
            else:
                problems.append(
                    f"{task_id} claims {ac}, which the SRS does not define - a typo, or an item that moved"
                )

    for ac, owners in sorted(owns.items()):
        module, function = items[ac]
        if not owners:
            problems.append(
                f"{ac} ({module} / {function}) is owned by no task, so nothing will build it"
            )
            continue

        claimed_done = [task_id for task_id, ticked in owners if ticked]
        if not claimed_done:
            continue

        with_evidence = []
        for task_id, ticked, block in blocks:
            if not ticked or ac not in block:
                continue
            named = [path for path in set(EVIDENCE.findall(block)) if exists(path)]
            if named:
                with_evidence.append(task_id)
            else:
                stale = sorted(set(EVIDENCE.findall(block)))
                detail = f" (it names {', '.join(stale)}, which does not exist)" if stale else ""
                problems.append(
                    f"{ac} ({module} / {function}) is closed by {task_id}, which names no test that exists{detail}"
                )
        if not with_evidence and not any("names no test" in p for p in problems):
            problems.append(f"{ac} has no test named by any task that claims it")

    return problems


def report(problems: list[str]) -> int:
    if not problems:
        return 0
    print("acceptance coverage:")
    for problem in problems:
        print(f"  - {problem}")
    return len(problems)


def main() -> int:
    if not SRS.is_file() or not PLAN.is_file():
        print(f"missing input: {SRS.name} or {PLAN.name}")
        return 1

    items = acceptance_items(SRS.read_text(encoding="utf-8"))
    if not items:
        print(
            f"no acceptance items found in {SRS.name} - the table moved, so this check proves nothing"
        )
        return 1

    problems = analyse(
        SRS.read_text(encoding="utf-8"),
        PLAN.read_text(encoding="utf-8"),
        exists=lambda path: (ROOT / path).is_file(),
    )
    failures = report(problems)
    print()
    if failures:
        print(
            f"{len(items)} acceptance items, {failures} problem(s) - each needs an owner or its evidence."
        )
        return 1
    print(
        f"all {len(items)} acceptance items are owned, and every closed one names a test that exists"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
