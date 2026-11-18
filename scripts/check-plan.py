#!/usr/bin/env python3
"""Check that PLAN.md keeps its shape: tasks belong to a phase, and a gate comes last.

PLAN §1 states the rules this script enforces, because a rule nobody can break quietly is worth more
than a rule everybody is asked to remember:

- A task id is ``P<phase>-<nn>``, appears once, and the numbers run 01..n with no gap.
- Every task sits between its phase heading and that phase's gate.
- Every phase has exactly one gate, and no task line follows it.
- A task names an owner from the handles listed in PLAN §2.

It also reports, as a warning rather than a failure, a task with no obvious acceptance sentence
("done when" / "closes when"). The plan never mandated that wording — twenty older tasks phrase
their acceptance another way — so treating it as a hard error would block the check for reasons the
document does not hold.

The defect this exists for: a task added after ``GATE P4`` still reads like a task, and PLAN §1 says
the next phase does not start until the gate is ticked, so the task would be invisible to the gate
that is supposed to wait for it. P3-37 and P3-38 sat exactly there until this check was written.

Usage: python scripts/check-plan.py
Exit code: 0 when the plan's shape is sound, 1 otherwise.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "PLAN.md"

PHASE = re.compile(r"^###\s+P(\d+)\s")
TASK = re.compile(r"^-\s+\[[ xX]\]\s+\*\*P(\d+)-(\d+)\*\*")
GATE = re.compile(r"^-\s+\[[ xX]\]\s+\*\*GATE\s+P(\d+)\*\*")
SECTION = re.compile(r"^##\s")
OWNER = re.compile(r"@([A-Za-z][A-Za-z0-9_]+)")
HANDLES = {"FrozenYty", "Gtechson", "chemflowers", "IkeaFyj"}
ACCEPTANCE = re.compile(r"(?:done|closes) when")


def main() -> int:
    lines = PLAN.read_text(encoding="utf-8").splitlines()
    problems: list[str] = []
    warnings: list[str] = []

    phase: int | None = None
    gate_seen = False
    tasks: dict[int, list[int]] = {}
    task_line: dict[tuple[int, int], int] = {}
    gate_line: dict[int, int] = {}
    phase_seen: set[int] = set()

    def problem(line_no: int, message: str) -> None:
        problems.append(f"PLAN.md:{line_no}: {message}")

    for number, line in enumerate(lines, start=1):
        heading = PHASE.match(line)
        if heading:
            if phase is not None and not gate_seen:
                problem(number, f"phase P{phase} ends without a GATE P{phase}")
            phase = int(heading.group(1))
            phase_seen.add(phase)
            gate_seen = False
            tasks.setdefault(phase, [])
            continue

        if phase is None:
            continue

        gate = GATE.match(line)
        if gate:
            if gate.group(1) != str(phase):
                problem(number, f"GATE P{gate.group(1)} sits inside phase P{phase}")
            if gate_seen:
                problem(number, f"phase P{phase} has more than one gate")
            gate_seen = True
            gate_line[phase] = number
            continue

        task = TASK.match(line)
        if task:
            if task.group(1) != str(phase):
                problem(number, f"task P{task.group(1)}-{task.group(2)} sits inside phase P{phase}")
                continue
            if gate_seen:
                problem(
                    number,
                    f"task P{phase}-{int(task.group(2)):02d} comes after GATE P{phase}; a task a gate "
                    "cannot wait for is invisible to the gate",
                )
            tasks[phase].append(int(task.group(2)))
            task_line[(phase, int(task.group(2)))] = number

    if phase is not None and not gate_seen:
        problem(len(lines), f"phase P{phase} ends without a GATE P{phase}")

    for phase_number, numbers in sorted(tasks.items()):
        if not numbers:
            problem(0, f"phase P{phase_number} has no tasks")
            continue
        expected = list(range(1, max(numbers) + 1))
        if sorted(numbers) != expected:
            duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
            missing = sorted(set(expected) - set(numbers))
            problem(
                0,
                f"phase P{phase_number} numbering is not 01..{max(numbers):02d}: "
                f"duplicates={duplicates} missing={missing}",
            )

    # A task's text runs from its line to the next task, gate or heading — blank lines and its
    # indented continuation lines are part of it. Two details cost a round each to learn: stopping at
    # a blank line reported nineteen tasks as lacking anything, and comparing the raw join missed
    # "done       when" because the continuation line is indented. Collapse whitespace first.
    for key, start in sorted(task_line.items(), key=lambda item: item[1]):
        end = len(lines)
        for index in range(start, len(lines)):
            candidate = lines[index]
            if (
                TASK.match(candidate)
                or GATE.match(candidate)
                or PHASE.match(candidate)
                or SECTION.match(candidate)
            ):
                end = index
                break
        text = re.sub(r"\s+", " ", " ".join(lines[start - 1 : end]))
        owners = set(OWNER.findall(text))
        unknown = owners - HANDLES
        if not owners:
            problem(start, f"task P{key[0]}-{key[1]:02d} names no owner")
        if unknown:
            problem(start, f"task P{key[0]}-{key[1]:02d} names unknown owner(s) {sorted(unknown)}")
        if not ACCEPTANCE.search(text):
            warnings.append(
                f"PLAN.md:{start}: task P{key[0]}-{key[1]:02d} has no 'done when' sentence"
            )

    for warning in warnings:
        print(f"warning: {warning}")
    if problems:
        for line in problems:
            print(line)
        print(f"\n{len(problems)} problem(s), {len(warnings)} warning(s)")
        return 1

    phases = sorted(phase_seen)
    task_total = sum(len(value) for value in tasks.values())
    print(f"phases: {len(phases)} (P{phases[0]}..P{phases[-1]}), tasks: {task_total}")
    for phase_number in phases:
        print(
            f"  P{phase_number}: {len(tasks[phase_number])} tasks, "
            f"gate at line {gate_line.get(phase_number, '?')}",
        )
    print(f"plan shape ok ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
