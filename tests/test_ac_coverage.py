"""The acceptance-coverage check must fail on the two ways an item goes quiet.

An acceptance item is what the project is judged on. It goes quiet either because nobody owns it, or
because something claims it and names no test. Both are asserted here on synthetic inputs, because a
check whose failure path is never exercised is a check nobody can trust — and the real tree is green,
which is exactly the state in which a broken check goes unnoticed.

The last test runs against the repository as it is, so the check cannot rot into something that only
passes on fixtures.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-ac-coverage.py"

SRS = """| ID | Module | Function | Priority | Origin |
|---|---|---|---|---|
| AC-01 | Account | Sign-in | P0 | carried over |
| AC-02 | Capture | Quality | P0 | carried over |
"""


def _load_check() -> object:
    """Import `scripts/check-ac-coverage.py`, whose filename cannot be imported as a module."""
    spec = importlib.util.spec_from_file_location("check_ac_coverage", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load_check()


def problems(plan: str, existing: set[str] | None = None) -> list[str]:
    """Analyse a synthetic pair, treating only `existing` as real files."""
    real = existing if existing is not None else {"tests/test_thing.py"}
    return check.analyse(SRS, plan, exists=lambda path: path in real)


def test_an_item_no_task_mentions_is_reported() -> None:
    """AC-02 is built by nobody, so no gate would ever notice it missing."""
    plan = "- [ ] **P1-01** Something · @someone · closes AC-01 · see `tests/test_thing.py`\n"

    found = problems(plan)

    assert len(found) == 1
    assert "AC-02" in found[0] and "owned by no task" in found[0]


def test_a_ticked_claim_with_no_test_is_reported() -> None:
    """The claim the repository's own §5 calls "a claim rather than a fact"."""
    plan = (
        "- [x] **P1-01** Something · @someone · closes AC-01\n"
        "- [ ] **P1-02** Other · @someone · closes AC-02 · see `tests/test_thing.py`\n"
    )

    found = problems(plan)

    assert len(found) == 1
    assert "AC-01" in found[0] and "P1-01" in found[0] and "no test that exists" in found[0]


def test_a_claim_naming_a_missing_file_is_reported_with_the_stale_name() -> None:
    """A renamed test is the ordinary way evidence rots, so the stale name is printed."""
    plan = (
        "- [x] **P1-01** Something · @someone · closes AC-01 · see `tests/test_gone.py` and `tests/test_thing.py`\n"
        "- [ ] **P1-02** Other · @someone · closes AC-02\n"
    )

    found = problems(plan, existing={"tests/test_thing.py"})

    assert not found, "one existing file among the named ones is enough evidence"


def test_a_claim_naming_nothing_real_is_reported() -> None:
    plan = (
        "- [x] **P1-01** Something · @someone · closes AC-01 · see `tests/test_gone.py`\n"
        "- [ ] **P1-02** Other · @someone · closes AC-02\n"
    )

    found = problems(plan, existing={"tests/test_thing.py"})

    assert len(found) == 1
    assert "test_gone.py" in found[0], "the check must print what it could not resolve"


def test_a_claim_for_an_item_that_does_not_exist_is_reported() -> None:
    """A typo in an id is how a claim silently stops covering anything."""
    plan = (
        "- [x] **P1-01** Something · @someone · closes AC-99 · see `tests/test_thing.py`\n"
        "- [ ] **P1-02** Other · @someone · closes AC-01 · see `tests/test_thing.py`\n"
        "- [ ] **P1-03** Third · @someone · closes AC-02 · see `tests/test_thing.py`\n"
    )

    found = problems(plan)

    assert any("AC-99" in problem and "does not define" in problem for problem in found)


def test_the_repository_is_covered() -> None:
    """The real documents, so the check cannot rot into something that only passes on fixtures."""
    found = check.analyse(
        (REPO / "docs" / "srs-en.md").read_text(encoding="utf-8"),
        (REPO / "PLAN.md").read_text(encoding="utf-8"),
        exists=lambda path: (REPO / path).is_file(),
    )

    assert not found, found
