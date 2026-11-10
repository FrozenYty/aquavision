# 11 — pytest runs on every workstation

- **Status:** Accepted
- **Date:** 2026-11-10
- **Supersedes:** the `pytest` clause of ADR 07 — “`pytest` stays CI-only until its dependencies can be
  installed on every workstation without pulling torch”

## Context

ADR 07 was right about the checks that cost two seconds and wrong about the one it excluded. It kept
`pytest` CI-only on a condition: *until its dependencies can be installed on every workstation without
pulling torch.* That condition was honest when it was written. `requirements.txt` is the full
environment — it pins `ultralytics`, which pulls torch and torchvision, several gigabytes, plus a
second OpenCV build that shares the `cv2` namespace with the headless one the server uses. Nobody
installs that to run a test client.

The condition is met now. `requirements-server.txt` at the repository root pins the server's
dependencies and the test tools on their own — pytest, httpx, ruff — with no torch anywhere. A
workstation that serves the app already has most of that list; the file only makes the test half
explicit. The tests import neither torch nor ultralytics: the models are exercised through fakes, and
the web layer through `TestClient` against a temporary database.

The practice had also left the record behind. `AGENTS.md` §6, `.github/PULL_REQUEST_TEMPLATE.md` and
the README's “Getting started” section all require `pytest -q` before a push. ADR 07 was the last
place still saying otherwise.

## Decision

`pytest -q` is part of the local check set, on every workstation, before every push.

It joins the commands ADR 07 already listed; the full set is one block:

```
python -m ruff check .
python -m ruff format --check .
python scripts/check-bilingual.py
python scripts/check-language.py
python scripts/check-progress.py
pytest -q
```

CI confirms; it does not discover. That was ADR 07's claim about the checks it listed, and it is now
the claim about the tests as well.

## Alternatives considered

**Keep `pytest` CI-only and let the runner be the tester.** Costless on paper, and it is the
arrangement ADR 07 recorded. Rejected because it is the arrangement that trains people to push and read
the result later, and because **a suite that only runs in CI is a suite people push past.** A test is
worth most in the ten seconds after it breaks locally, not in a queue the author has already moved on
from.

**Run only the tests near the change.** Cheap, and it keeps the local loop short. Rejected: the
application is one process, the suite is small, and selecting the subset means deciding which tests
count as “near” — a guess that is wrong exactly where a coupling was not obvious, which is where a test
would have earned its keep.

**Wait until the suite is fast enough.** The reason the tests were CI-only was dependency weight, not
runtime, and “fast enough” is a threshold nobody writes down. The dependency set is now one file away;
keeping a check out of the local loop for an unmeasured reason is the obstacle ADR 07 warns about.

## Consequences

- The pre-push set grows by one command. A failing test becomes the author's finding before it becomes
  the reviewer's question.
- CI keeps its role as the merge gate. Nothing here weakens branch protection, and a local pass still
  proves less than a green run.
- The dependency rule now has a name: **anything the tests import must be installable from
  `requirements-server.txt`.** A test that needs torch is a training test, and the training stack is
  still not part of the local gate.
- The rest of ADR 07 stands. Its argument about the cheap checks — install, do not skip, quote the
  actual error — is untouched, and so is its ownership argument.

## Revisit when

A test needs the training stack or a GPU, or the suite outgrows a few seconds on an ordinary
workstation. At that point the rule becomes what ADR 07 already named: everything reproducible runs
locally, and the expensive part stays in CI.
