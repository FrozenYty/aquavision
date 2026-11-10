# Contributing

How we work in this repository. GitHub collaboration only — code style beyond what CI enforces is
between the author and the reviewer.

## 1. Branching

`main` is protected. All work happens on short-lived branches:

```
feat/capture-quality    fix/review-rollback    docs/api-contract
```

Merge into `main` through a pull request, then delete the branch.

Branch names are lowercase, hyphen-separated, prefixed by type. No Chinese, no pinyin.

## 2. Commits

Conventional Commits, with the module as scope:

```
feat(capture): add frame quality scoring
fix(detect): drop stale boxes when frame_id changes
docs(adr): record decision to drop pan-tilt
chore(ci): run ruff on pull requests
```

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
Modules: `capture`, `detect`, `review`, `stats`, `model`, `web`, `firmware`, `docs`, `ci`.

One commit does one thing. If the message needs "and", split the commit.

**Never add a footer that credits a tool.** No `Co-authored-by:` naming an AI assistant or a code
generator, and do not leave one that an assistant wrote for you:

```
Co-authored-by: Claude Code <noreply@anthropic.com>     ← rejected
```

A squash merge copies the single commit's message onto `main` verbatim, and GitHub counts that trailer
as another contributor — so a one-line footer becomes a name on the repository's contributor list.
Removing it afterwards means rewriting `main`, which changes every hash on the branch and forces every
clone to reset. `scripts/check-commit-messages.py` fails the build when one appears, and CI runs it on
every pull request.

Human co-authors are ordinary teamwork and are allowed: the rule is about crediting a tool, not about
collaboration.

**If one lands anyway**, this is the repair, and it must be done when nobody has an open branch:

```bash
git fetch && git checkout main && git pull --ff-only
git branch backup/pre-trailer-rewrite && git branch tmp main

git checkout <bad-commit>
git commit --amend -m "<the same message, minus the footer>"
git rebase --onto HEAD <bad-commit> tmp

git diff <old-main-tip> tmp      # must be empty: content unchanged, only the message differs
git checkout main && git reset --hard tmp
git push --force-with-lease origin main
```

Force-pushing `main` needs branch protection relaxed for the minute it takes, and everyone else must
run `git fetch && git reset --hard origin/main` afterwards. That cost is why the check exists.

## 3. Pull requests

- Keep a PR under **400 changed lines**. Larger work is split.
- Fill in the template: what changed, how it was verified, what else is affected.
- **CI is the only gate.** When `check` is green the PR may merge; no approval is required.
- Review is still welcome — leave a comment instead of blocking. Fix it in a follow-up if it is
  not worth another round trip.
- **Auto-merge is applied by `.github/workflows/auto-merge.yml`** the moment a PR opens; nobody has to click anything. If a PR sits green without merging, that workflow printed a warning: the repository setting is off, tell the lead.
- Merge with **squash** — one feature, one commit on `main`.
- Name the task ID in the title when the PR delivers one: `feat(capture): frame scoring (P1-03)`.

## 4. What CI checks

Every job below blocks the merge. The list grows; the rule does not — if it is in this table, a red run stops the merge.

| Job | Command | Fix |
|---|---|---|
| Lint | `ruff check .` | `ruff check . --fix` |
| Format | `ruff format --check .` | `ruff format .` |
| Docs | `python scripts/check-bilingual.py` | update the missing language |
| Language | `python scripts/check-language.py` | move the Chinese into the `-zh` file |
| Progress | `python scripts/check-progress.py` | one entry per day, date heading only |
| Paths | `python scripts/check-paths.py` | write it relative to the repository root |
| Tests | `pytest -q` | write the failing test first |

Python style is whatever `ruff` accepts — the configured line length is 100, nothing else is
negotiated. Comments and docstrings are English.

## 5. Files and data

- **Filenames are English**, lowercase, hyphen-separated. Content may be Chinese.
- Deliverables carry a version, not a date: `srs-v1.4.docx`. Submission artefacts live outside the repository (see §6).
- Design documents come in pairs: `architecture-en.md` and `architecture-zh.md`, with English as
  the source of truth. `README.md` / `README-zh.md` follow the same rule.
- **An English document carries no Chinese prose.** Describe the part, not its Chinese brand name:
  “8-channel bidirectional level shifter” rather than the shop listing title. Product names,
  quotations and search strings that only exist in Chinese belong in the `-zh` counterpart. The one
  exception is the README language switcher, which is navigation rather than prose.
- Diagrams are Mermaid code blocks inside Markdown, never image files.
- Never commit:

```
*.pt  *.onnx          model weights
data/                 frames, thumbnails, exports
datasets/             training and test data
*.mp4  *.avi          video
.env                  secrets
```

Weights go to GitHub Releases. Datasets go to external storage; link them from the README with a
checksum.

Size is a consequence, not a target. What decides is whether a file needs to share history with the
code:

- **It does** for source, documents, and the small images a document references. A reader expects them
  beside the text, and they change a little at a time.
- **It does not** for weights, datasets, video, and generated documents. They are large, they change
  wholesale every time they are produced, and git keeps every version forever — a repository that
  accepted them would grow without ever becoming more useful.

A clone should feel quick and a diff should stay readable. If either stops being true, something moved
to the wrong side of that line. No number is written down: one would only be argued with at the
boundary, and the boundary is never where the problem is.

## 6. Documents

`docs/INDEX-en.md` is the map: which document answers what, which one wins when two disagree, and
what else has to change alongside a given change. Read it before adding or moving anything.

Naming and placement, so nobody has to guess:

| What | Where | Name |
|---|---|---|
| entry points and live state | repository root, uppercase | `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `PLAN.md`, `PROGRESS.md`, `LICENSE` |
| a design document | `docs/`, lowercase | `name-en.md` + `name-zh.md`, English as the source of truth |
| one bilingual file | `docs/`, lowercase | `name-en-zh.md`, both languages in one table |
| a decision | `docs/adr/` | `NN-short-title.md`, two digits, never renamed |

Root files are single-language and change often; `docs/` files are bilingual and change rarely. If a
file does not fit that split, the split is wrong, not the file.

**Nothing machine-specific goes into a shared document.** No absolute paths, no user names, no local
folder names: they are dead links on every other machine, and they leak how one person's disk happens
to be arranged. Write commands relative to the repository root and the interpreter as `python`. If
something exists only on your machine, it does not belong in a file the others read.

Conventions that keep the set from drifting:

- **Every design document carries an owner line** under its title: `> Owner: @handle · Revisit when:
  <trigger>`. A trigger, not a date — dates rot, triggers do not.
- **A decision that is expensive to reverse becomes an ADR**, not a paragraph in `PROGRESS.md`. When a
  phase gate passes, sweep that phase's entries in `PROGRESS.md` for decisions that changed the plan
  and promote them. One decision, one ADR; do not write it twice.

## 7. Definition of done

A change is done when:

- [ ] `check` is green on the PR
- [ ] The PR template is filled in
- [ ] Bilingual pairs are updated in the same commit
- [ ] The task box in `PLAN.md` is ticked by whoever merged
- [ ] `docs/INDEX-en.md` updated if a document was added, renamed or removed
