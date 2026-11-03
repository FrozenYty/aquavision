# Contributing

Conventions for this repository. Read this before your first commit.

## 1. Branching

`main` is protected. All work happens on short-lived branches:

```
feat/capture-quality    fix/review-rollback    docs/api-contract
```

Merge into `main` through a pull request, then delete the branch.

Branch names are lowercase, hyphen-separated, and prefixed by type. No Chinese, no pinyin.

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
- At least **one reviewer** approves. The lead's PRs are reviewed by the module owner.
- Merge with **squash** — one feature, one commit on `main`.
- Link the issue (`Closes #12`) when one exists.

Use issues for anything larger than a small fix. Small fixes may go straight to a PR.

## 4. Code style

**Python** — enforced by `ruff` (lint + format). Run before every commit:

```
ruff check . && ruff format .
```

- Type hints on every public function.
- Comments and docstrings in English.
- Files under 300 lines, functions under 50 lines.
- Business errors raise `BizError`, never bare `Exception`.
- `logging`, not `print` (except under `scripts/`).
- Configuration through `.env` and `pydantic-settings`; no hard-coded paths or secrets.

**Web** — no framework, no build step.

- All HTTP calls go through `web/static/js/api.js`. No `fetch()` in page scripts.
- One page per module: `capture.html`, `review.html`, `stats.html`.
- Bootstrap utility classes plus `web/static/css/app.css`. No inline `style=`.
- Business logic lives in `.js`, not in markup.

**Firmware** — Arduino framework on ESP32.

- Pin assignments only in `config.h`.
- Serial commands and replies defined in `protocol.h`.
- `firmware/README.md` must list the wiring table, flashing steps and the serial protocol.

## 5. Documentation

- **Filenames are English**, lowercase, hyphen-separated. Content may be Chinese.
- Deliverables carry a version, not a date: `srs-v1.2.docx`.
- Design documents come in pairs: `architecture-en.md` and `architecture-zh.md`. The README is the same: `README.md` in English, `README-zh.md` as the Chinese reference.
- **English is the source of truth.** Change the English file first, then update the Chinese one in the same PR.
- Diagrams are Mermaid code blocks inside the Markdown, never image files.
- `PROGRESS.md` is updated every week, in English, five lines maximum.

## 6. Data and assets

Never commit:

```
*.pt  *.onnx          model weights
data/                 frames, thumbnails, exports
datasets/             training and test data
*.mp4  *.avi          video
.env                  secrets
```

Weights go to GitHub Releases. Datasets go to external storage; link them from the README together with a checksum.

Keep the repository under 20 MB.

## 7. Weekly rhythm

| When | What |
|---|---|
| Wednesday, after class | 20-minute sync: blockers only, not status reports |
| Friday | Merge the week's PRs; no branches left open over the weekend |
| Friday | 15-minute code walk-through of the week's PRs |

## 8. Definition of done

A change is done when all of these hold:

- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `pytest` passes locally
- [ ] Bilingual documents are in sync (`scripts/check-bilingual.py`)
- [ ] The PR template is filled in and a reviewer approved
- [ ] Any behaviour change is reflected in `docs/`
