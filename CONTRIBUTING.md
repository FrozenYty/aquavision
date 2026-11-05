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

## 3. Pull requests

- Keep a PR under **400 changed lines**. Larger work is split.
- Fill in the template: what changed, how it was verified, what else is affected.
- **CI is the only gate.** When `check` is green the PR may merge; no approval is required.
- Review is still welcome — leave a comment instead of blocking. Fix it in a follow-up if it is
  not worth another round trip.
- Turn on **auto-merge** right after opening the PR: it merges itself once `check` passes.
- Merge with **squash** — one feature, one commit on `main`.
- Name the task ID in the title when the PR delivers one: `feat(capture): frame scoring (P1-03)`.

## 4. What CI checks

Five jobs, and any failure blocks the merge:

| Job | Command | Fix |
|---|---|---|
| Lint | `ruff check .` | `ruff check . --fix` |
| Format | `ruff format --check .` | `ruff format .` |
| Docs | `python scripts/check-bilingual.py` | update the missing language |
| Language | `python scripts/check-language.py` | move the Chinese into the `-zh` file |
| Tests | `pytest -q` | write the failing test first |

Python style is whatever `ruff` accepts — the configured line length is 100, nothing else is
negotiated. Comments and docstrings are English.

## 5. Files and data

- **Filenames are English**, lowercase, hyphen-separated. Content may be Chinese.
- Deliverables carry a version, not a date: `srs-v1.2.docx`.
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
checksum. Keep the repository under 20 MB.

## 6. Definition of done

A change is done when:

- [ ] `check` is green on the PR
- [ ] The PR template is filled in
- [ ] Bilingual pairs are updated in the same commit
- [ ] The task box in `PLAN.md` is ticked by whoever merged
