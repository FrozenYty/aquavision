# 07 — Verification happens locally before a push

- **Status:** Accepted
- **Date:** 2026-11-05
- **Supersedes:** —

## Context

Branch protection makes CI the only gate that blocks a merge, and that is the right place for it. But
it drifted into being the *first* check rather than the *last*. Several pull requests were pushed
unverified, the run was watched, and the result read afterwards.

One cycle was lost to `F821 Undefined name 'date'` in a script that ran correctly under every local
test: the name was read one line above the branch that assigned it, so no runtime exercise could reach
the fault. A single `ruff check .` would have caught it in two seconds.

The reason the check was skipped was not laziness. `ruff` was missing from the environment, three
install attempts failed on a permissions error, and the conclusion drawn was “this machine cannot run
it”. That conclusion was wrong: the sandbox was blocking pip's unpack directory, and an install run
with elevated permission succeeded in four seconds. A temporary obstacle had been promoted to a
permanent constraint, and the habit that grew around it — push, then read the runner — outlived the
obstacle.

## Decision

Run the full check set locally before every push. CI confirms; it does not discover.

```
python -m ruff check .
python -m ruff format --check .
python scripts/check-bilingual.py
python scripts/check-language.py
python scripts/check-progress.py
```

`pytest` stays CI-only until its dependencies can be installed on every workstation without pulling
torch.

## Rationale

- **The checks are cheap locally and expensive in the queue.** Two seconds against forty, plus the
  context switch of watching a run.
- **The failures CI catches are exactly the cheap ones.** Lint, formatting and document drift are all
  decidable without the full environment. The expensive things — integration, model metrics — are not
  in CI yet, so there is nothing to wait for.
- **“CI will catch it” hides ownership.** When the runner goes red, the question becomes whose job the
  diagnosis is. Locally, it is unambiguous.
- **A missing tool is a task, not a constraint.** The distinction matters: one has a fix, the other
  breeds workarounds.

## Consequences

- A missing tool gets installed, not skipped. If an install fails, quote the actual error and treat it
  as a problem to solve; do not generalise from repeated failures. “Cannot be installed here” is a
  conclusion that needs evidence, not an inference from three attempts.
- When CI does fail, the log is fetched before anything is changed. The `F821` above was diagnosed by
  guessing at the cause and pushing a rewrite, which happened to work — that is luck, not method.
- Commits get slightly smaller, because a red local run is fixed before the branch is shared.
- CI keeps its role: the merge gate. Nothing in this decision weakens branch protection.

## Revisit when

A check can only run in CI — GPU work, or an environment that cannot be reproduced on a workstation.
At that point the rule becomes “everything reproducible runs locally”, not “nothing runs locally”.
