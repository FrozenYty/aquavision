# AGENTS.md

Instructions for AI assistants working in this repository. Read this before your first task.

> This file only holds what is not written elsewhere. If a rule already lives in `CONTRIBUTING.md`,
> `PLAN.md` or `docs/`, delete the copy here instead of maintaining two versions.

## 1. Before you start

Read, in this order:

```
PLAN.md  ->  PROGRESS.md  ->  CONTRIBUTING.md  ->  docs/architecture-en.md  ->  the ADR that touches your change
```

- Find out **who you are helping** (§3). Ask your user if it is not stated.
- The files beat your memory. This repository is edited by four people and four assistants between
  your sessions; anything you remember may already be wrong.
- When something is unclear, say what is unclear and what would make it clear. Do not guess at
  another lane's intent.

## 2. The project

AquaVision — underwater species detection and monitoring. A USB camera feeds a quality check, then
YOLOv8 detection, then human review; corrections flow back into training. Four classes: sea
cucumber, sea urchin, scallop, starfish.

One FastAPI process, a static frontend, and an ESP32 that only handles the trigger, the turbidity sensor and its panel.

Phase and task state live in `PLAN.md`. Recent changes live in `PROGRESS.md`. Do not restate either
one here — stale summaries are worse than none.

## 3. Who you are helping

| User | Lane | Default: read-only |
|---|---|---|
| Yao Tianyu | A — capture, architecture, documents | B, C |
| Gao Tianxiang | B — data, model, backend | A, C |
| Sun Jianheng | C — frontend, annotation | A, B |
| Fu Yijia | D — test cases, acceptance, demo material | everything else |

Only take tasks that `PLAN.md` assigns to your user. Everything else is read-only by default.

- **Small change in another lane** — go ahead and submit the PR, but say so in the description:
  “touches lane B: added a field to the detection response”.
- **Large change in another lane** — ask first. Two assistants editing one file is the most
  expensive accident this repository can have.

## 4. Working principles

**1. Look before you move.** Read the file, list the directory, check the branch. Never edit from
memory — three other people have been working here since your last session.

**2. Smallest change that works.** Every line you touch is a line someone else may be editing.
If you write 200 lines and it could be 50, rewrite it.

**3. Simple beats clever.** No abstraction for single-use code, no configurability nobody asked for,
no error handling for situations that cannot happen. Would a senior engineer call this overbuilt?

**4. Define done before coding.** `PLAN.md` already gives a “done when” for most tasks. If yours has
none, write one in the PR description before you start — a check you can run, not a feeling.

**5. Change one thing, search the whole repository.** Deleting a file, renaming a field, changing an
ID: grep for every reference. Stale links and stale names are the most common silent defect here.

**6. Read the error.** A non-zero exit is information. Read it, then adjust or report; do not retry
the identical command and hope.

**7. A blocked operation is a request for permission, not an invitation to work around it.** When the
sandbox or the filesystem refuses something, say what was refused and ask for the access you need.
Routing around it — an exclude pattern here, a hand-delete there — leaves the cause in place and hands
the user a list of chores you could have done yourself. Ask once, plainly, with the exact command.

**8. Specify the state matrix before you write the code.** Before writing firmware, or any code that
talks to hardware, write the states, the events, and the cell each pair lands in. The pairs nobody
wrote down are where the demo fails — a second press that fires two frames, a verdict that arrives
after the operator was told the shot failed. `docs/rig-state-machine-en.md` is the example: five
screens and two link states against every event, every cell filled, and the invariant — `Offline` if
and only if the link is `Gone` — checked in the firmware loop rather than assumed.

## 5. Rules of the shared repository

- Branch names, commit format and PR rules live in `CONTRIBUTING.md`. Follow them; they are not
  repeated here.
- **Never force-push.** Never push to `main` — it is protected, and the branch is shared.
- **Never tick a box in `PLAN.md`** for work you did not deliver.
- **`PROGRESS.md` is append-only.** Add a dated entry; never rewrite an older one.
- **An accepted ADR is closed.** To change a decision, write a new ADR that supersedes it — do not
  quietly code around it.
- **A problem outside your lane: report it, do not fix it.** One sentence in the PR description or
  the weekly sync is enough. Fixing it in your commit makes the diff unreviewable.

## 6. Verify and report

```bash
python scripts/check-bilingual.py      # bilingual pairs in sync
python scripts/check-language.py       # no Chinese in English documents
python scripts/check-progress.py       # PROGRESS.md well formed
python scripts/check-paths.py          # no machine-specific paths
python scripts/check-adr-index.py      # every decision record is listed in the architecture table
python scripts/check-commit-messages.py --range origin/main..HEAD   # no tool credited as co-author
python -m ruff check .                 # lint
python -m ruff format --check .        # format
pytest -q                              # tests
```

`check-paths.py` reads the repository's documents, but the rule it enforces is wider than its reach:
anything you write for someone else to read — a task brief, a message meant to be forwarded, an answer
that will be pasted into a group chat — uses paths relative to the repository root, never an absolute
path on the machine that wrote it. Say "the repository root" rather than where the repository is.

If `ruff` is missing, install it rather than skipping the check. On Windows a sandbox can block pip's
unpack directory; run the install outside the sandbox or with elevated permission. CI is the final
authority, but "CI will catch it" is not a reason to push without looking.

**A passing local run proves less than it looks.** The five document checks never look at Python
code, and a script can execute correctly while still failing static analysis: a name read before the
branch that assigns it is an `F821` that no runtime test will hit. Run `ruff` on every change to
Python — that is what catches it.

Report in three parts:

1. **What changed** — files and behaviour, not intentions.
2. **How it was verified** — commands run and their result.
3. **What is left undone** — be explicit; “it works” is not a report.

## 7. Delegation

When assistants are used, work is split along **two axes, and both are required**: the lane says *where
an agent may write*, the task type says *how the work is done and what finished means*. Type alone lets
one agent be asked to touch `server/`, `web/` and `firmware/` in a single turn, which is how two
assistants end up in one file (§3).

**Finding and fixing are different jobs, and separating them is what makes either trustworthy.** An agent
that both audits and repairs has no reason to report the findings it would rather not touch - and one
that repairs inside a named file list cannot quietly rewrite a decision record or an old `PROGRESS.md`
entry to match the present.

**Every brief carries five things**: the repository and the lane, the exact files or modules in scope,
the acceptance as a command that can fail, the checks to run, and the report format. A brief that says
"review the docs" produces a summary of intentions; a brief that says which files may change and which
command must pass produces a diff.

Who the standing helpers are, and what each is currently called, is a working detail of whoever is running
the session - it changes, and it does not belong in a shared repository.

## 8. Language

Talk to your user in Chinese. Write everything to disk in English: code, comments, commit messages,
documents, PR descriptions.

Chinese prose uses full-width punctuation — “”、，。；：（） — never ASCII quotes or commas wedged
into a Chinese sentence.
