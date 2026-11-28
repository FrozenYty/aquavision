"""The defect-evidence check must fail on the two ways a defect log goes quiet.

`P4-05` is the defect log, and an entry's evidence goes quiet in one of two ways: a closed entry
names no test (or a test that was renamed), or an open entry points at a file that moved. Both are
asserted here against the repository's own `PLAN.md`, because a check whose failure path is only
exercised on fixtures is a check nobody can trust - and the real tree is green, which is exactly the
state in which a broken check goes unnoticed.

The last test runs the check against the repository as it is, so it cannot rot into something that
only passes on a synthetic plan.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-defect-evidence.py"
PLAN = (REPO / "PLAN.md").read_text(encoding="utf-8")

#: The one entry the log marks closed first (the needs-retake frame major); the mutations below are
#: built on it because its closure names exactly one test.
CLOSED_TEST = "tests/test_batch_quality.py"


def _load_check():
    """Import `scripts/check-defect-evidence.py`, whose filename cannot be imported as a module."""
    spec = importlib.util.spec_from_file_location("check_defect_evidence", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load_check()


def problems(plan_text: str, existing: set[str] | None = None) -> list[str]:
    """Analyse a plan, treating only `existing` as real files; the default is the repository."""
    found, _warnings = analyse(plan_text, existing)
    return found


def warnings(plan_text: str, existing: set[str] | None = None) -> list[str]:
    """The closures accepted as manual bench procedures rather than tests."""
    _found, notes = analyse(plan_text, existing)
    return notes


def analyse(plan_text: str, existing: set[str] | None = None) -> tuple[list[str], list[str]]:
    """(problems, warnings) for a plan; only `existing` counts as real files."""
    if existing is not None:
        return check.analyse(plan_text, lambda path: path in existing)
    return check.analyse(plan_text, lambda path: (REPO / path).is_file())


def test_a_closed_entry_naming_no_test_is_reported() -> None:
    """The closure P3-35 exists to prevent: prose says done, no file can fail if it returns."""
    mutated = PLAN.replace(f"`{CLOSED_TEST}`", "the fix", 1)
    assert mutated != PLAN, "the closed entry's test must still be in PLAN.md for this to mutate"

    found = problems(mutated)

    assert len(found) == 1
    assert "needs-retake" in found[0], "the failure must name the entry it is about"
    assert "no regression check" in found[0]


def test_a_closed_entry_naming_a_missing_test_is_reported_with_the_stale_name() -> None:
    """A renamed test is the ordinary way evidence rots, so the stale name is printed."""
    mutated = PLAN.replace(f"`{CLOSED_TEST}`", "`tests/test_batch_quality_gone.py`", 1)
    assert mutated != PLAN

    found = problems(mutated)

    assert len(found) == 1
    assert "needs-retake" in found[0]
    assert "test_batch_quality_gone.py" in found[0], (
        "the check must print what it could not resolve"
    )


def test_an_open_entry_naming_a_missing_test_is_reported() -> None:
    """An open entry need not name a test, but a stale one is still a log describing a moved file."""
    plan = (
        "- [ ] **P4-05** Defect closure · @owner · done when every defect names its check\n"
        "      - **major: still open.** Repro written against `tests/test_gone.py`.\n"
        "- [ ] **P4-06** The next task · @owner · done when it is done\n"
    )

    found = problems(plan, set())

    assert len(found) == 1
    assert "test_gone.py" in found[0]
    assert "does not exist" in found[0]
    assert "still open" in found[0], "the failure must name the entry it is about"


def test_a_closed_entry_may_name_a_decision_record_instead_of_a_test() -> None:
    """The ADR-16/17 item is closed by a document, so the ADR form is evidence too."""
    plan = (
        "- [ ] **P4-05** Defect closure · @owner · done when every defect names its check\n"
        "      - **major: a retired rule came back.** ADR 18 supersedes it,\n"
        "        **closed 11-28:** `docs/adr/18-something.md`.\n"
        "- [ ] **P4-06** The next task · @owner · done when it is done\n"
    )

    assert not problems(plan, {"docs/adr/18-something.md"})


def test_a_closed_entry_may_name_a_specific_test() -> None:
    """`file::function` is the shape the test-case document uses, so it is accepted here."""
    plan = (
        "- [ ] **P4-05** Defect closure · @owner · done when every defect names its check\n"
        "      - **major: one.** **closed 11-28:** `tests/test_thing.py::test_it`.\n"
        "- [ ] **P4-06** The next task · @owner · done when it is done\n"
    )

    assert not problems(plan, {"tests/test_thing.py"})


def test_a_documentation_defect_may_name_the_document_that_corrects_it() -> None:
    """A "minor, documentation" defect is closed by the document, and a missing one is still caught."""
    plan = (
        "- [ ] **P4-05** Defect closure · @owner · done when every defect names its check\n"
        "      - **minor, documentation: the text said two.** Corrected in `docs/test-cases-en.md`,\n"
        "        **closed 11-28:** the case text.\n"
        "- [ ] **P4-06** The next task · @owner · done when it is done\n"
    )

    assert not problems(plan, {"docs/test-cases-en.md"})
    assert problems(plan, {"docs/other.md"}), "a documentation closure must name a real document"


def test_a_manual_bench_procedure_is_evidence_and_stays_visible_as_a_note() -> None:
    """The firmware has no host harness, so a written bench procedure is the check - and is printed."""
    plan = (
        "- [ ] **P4-05** Defect closure · @owner · done when every defect names its check\n"
        "      - **major: the line parser keeps the tail.** Closed by a flag, checked at the bench:\n"
        "        manual: firmware/README.md\n"
        "        **closed 11-28:** the procedure.\n"
        "- [ ] **P4-06** The next task · @owner · done when it is done\n"
    )

    assert not problems(plan, {"firmware/README.md"})
    notes = warnings(plan, {"firmware/README.md"})
    assert len(notes) == 1 and "manual bench procedure" in notes[0]
    assert problems(plan, set()), "a manual procedure must exist"


def test_the_log_ends_at_the_next_task_line() -> None:
    """A closed entry outside P4-05 is another task's business, not this log's."""
    plan = (
        "- [ ] **P4-05** Defect closure · @owner · done when every defect names its check\n"
        "      - **major: one.** **closed 11-28:** `tests/test_thing.py`.\n"
        "- [ ] **P4-06** The next task · @owner · done when it is done\n"
        "      - **major: outside the log.** **closed 11-28:** no test named here\n"
    )

    assert not problems(plan, {"tests/test_thing.py"})


def test_a_plan_without_the_defect_log_is_a_failure() -> None:
    """If P4-05 moved, the check must say so instead of checking nothing."""
    with pytest.raises(ValueError, match="P4-05"):
        problems("- [ ] **P4-06** The next task · @owner · done when it is done\n")


def test_the_repository_is_green() -> None:
    """The real documents, so the check cannot rot into something that only passes on a fixture."""
    found = problems(PLAN)

    assert not found, found
    notes = warnings(PLAN)
    assert notes, "the firmware closure is manual, and the note is what keeps that visible"
    assert "firmware/README.md" in " ".join(notes)
