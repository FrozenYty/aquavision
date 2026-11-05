# Plan

Single source of truth for tasks. No issue tracker — this file is the contract.

Phase status lives here. Why it moved lives in `PROGRESS.md`.

## 1. How to use this file

- Every task has an ID (`P1-03`). Reference it in the PR title when the PR delivers that task:
  `feat(capture): frame quality scoring (P1-03)`.
- Tick the box **in the same PR that delivers the task**. Nobody ticks it for someone else.
- A phase gate is a hard stop. The next phase does not start until every box in the current phase
  is ticked and the gate box is ticked too.
- Editing a task is a normal commit. Moving a **gate** needs the whole team to agree first — a gate
  is the only thing here meant to be expensive to move.

## 2. Lanes

| Lane | Owner | Scope |
|---|---|---|
| A — capture | @FrozenYty | camera, trigger, sensors, serial, storage |
| B — server | @Gtechson | database, API, detection, scheduling, training |
| C — web | @chemflowers | pages, canvas review, charts |
| D — quality | @IkeaFyj | test cases, acceptance checks, documents, demo script |

Handles: `@FrozenYty` Yao Tianyu · `@Gtechson` Gao Tianxiang · `@chemflowers` Sun Jianheng ·
`@IkeaFyj` Fu Yijia.

## 3. Phases

| Phase | Goal | Gate |
|---|---|---|
| P0 | Decisions made and external dependencies committed | dataset ≥ 3000 images and split; three environments identical; purchase list final; rig design final |
| P1 | Every layer has a minimal implementation | `uvicorn` starts, `/api/health` returns the envelope, 9 tables created, 13 pages open |
| P2 | One real end-to-end slice | press capture → boxes and counts on screen within 3 s; edit one box → count changes |
| P3 | All 29 requirements implemented | the 36 acceptance items can each be demonstrated live |
| P4 | Metrics, tests, defence | nine metrics recorded; blocker defects at zero; three rehearsals |

## 4. Tasks

### P0 — foundation

- [x] **P0-01** Dataset acquisition, cleaning, statistics, split · @Gtechson · done when
      `data/dataset-stats.json` is written, the split is by video, and the test set is ≥ 500 images
- [x] **P0-02** Environment and dependency lock · @Gtechson · done when `requirements.txt` exists and
      three machines install identically
- [x] **P0-03** Hardware purchase list final and ordered · @FrozenYty · done when the list is frozen at
      9 items and an order number exists
- [x] **P0-04** Page skeleton and design tokens · @chemflowers · done when `tokens.css` is final and
      three pages navigate
- [x] **P0-05** Requirement review record · @IkeaFyj · done when the review outcome is recorded in
      SRS annex B — four internal rounds, V1.1 to V1.4, approver column filled
- [x] **P0-06** Rig design: lighting, camera position, tank layout · @FrozenYty · done when the single
      lamp rig is specified with fallbacks and the acceptance numbers are fixed — see `PROGRESS.md`
      2026-11-05

- [x] **GATE P0** — every task above ticked

### P1 — skeleton

- [ ] **P1-01** DDL script and species dictionary seed · @Gtechson · done when `scripts/init_db.py`
      runs on an empty database and four classes are seeded
- [ ] **P1-02** FastAPI skeleton: 18 routes, envelope, error codes, JWT · @Gtechson · done when
      `/api/health` returns `{code, message, data, request_id}`
- [ ] **P1-03** Capture module: open device, lock exposure, grab, score, persist · @FrozenYty · done
      when 20 frames are captured and file, score and `frame_id` all agree
- [ ] **P1-04** Thirteen static pages · @chemflowers · done when every page opens, uses mock data and
      shares one visual language
- [ ] **P1-05** Test case draft against the 36 acceptance items · @IkeaFyj · done when each item has
      at least one case, marked not-yet-implemented
- [ ] **P1-06** Hardware arrival check and rig assembly · @FrozenYty · done when the camera outputs
      frames, exposure can be locked, and the rig meets its numbers: left/right brightness ratio
      ≥ 0.7, a 5 cm target ≥ 45 px at 640 input, no flicker, 20-frame mean brightness spread < 10%

- [ ] **GATE P1** — `uvicorn app.main:app` starts on a clean machine, `/api/health` answers, 9 tables
      exist, 13 pages render

### P2 — vertical slice

- [ ] **P2-01** Capture → detection, single frame · @FrozenYty @Gtechson · done when one call returns
      boxes with `model_version` and `latency_ms`
- [ ] **P2-02** Result persistence and query API · @Gtechson · done when boxes land in
      `detect_object` and querying by `frame_id` returns them
- [ ] **P2-03** Capture and review pages on real data · @chemflowers · done when no mock data is left
      on those two pages
- [ ] **P2-04** Minimal review loop: delete, add, relabel · @chemflowers @Gtechson · done when the
      edit persists and the count updates without a page reload

- [ ] **GATE P2** — from a cold start, someone who has not seen the system completes the slice in
      three minutes, no restart, no manual database edit

### P3 — breadth

- [ ] **P3-01** Batch detection, thread pool, progress · @Gtechson · done when a 100-frame task
      completes, progress is queryable and state survives a restart
- [ ] **P3-02** Statistics dashboard and report export · @chemflowers · done when four charts render
      and Word and PDF export both work
- [ ] **P3-03** Model version management and activation · @Gtechson · done when exactly one model is
      online and results record the version
- [ ] **P3-04** Accounts, roles, permissions · @Gtechson · done when the role is enforced server-side
- [ ] **P3-05** Review canvas: drag, zoom, add, delete · @chemflowers · done when all four gestures
      work on one frame without a reload
- [ ] **P3-06** Demo mode · @FrozenYty · done when one action resets data and hides debug output

- [ ] **GATE P3** — all 36 acceptance items demonstrated live, one after another, no manual database
      edits in between

### P4 — close

- [ ] **P4-01** Baseline training E0 · @Gtechson · done when the experiment is recorded with data
      snapshot, seed and metrics
- [ ] **P4-02** Three improvements E1–E3 · @Gtechson · done when each is isolated and the metrics are
      comparable to the baseline
- [ ] **P4-03** Ablation E4 and fine-tuning · @Gtechson · done when the ablation table is complete and
      the tank fine-tune is evaluated
- [ ] **P4-04** Metric acceptance, per class · @Gtechson @IkeaFyj · done when nine metrics are
      recorded and any failure is explained in writing
- [ ] **P4-05** Defect fixing and regression · all · done when blocker and major defects are at zero
- [ ] **P4-06** Acceptance checklist, demo script, slides · @IkeaFyj · done when every acceptance item
      is ticked and the demo runs end to end on paper
- [ ] **P4-07** Three rehearsals · @FrozenYty · done when each run finishes under eight minutes with no
      dead air

- [ ] **GATE P4** — three tables full: metrics, ablation, acceptance checklist

## 5. Text constraints

These replace process tooling. Short on purpose.

1. **One task, one PR, one owner.** If a task needs two people, the owner is whoever merges.
2. **Status rides with the delivering PR.** A ticked box without a merged PR is a claim, not a fact.
3. **A gate is checked by someone other than the lane owner.** Two minutes, eyeballs only.
4. **Blocked is stated, not hidden.** A task sitting open for more than three days gets one sentence
   in the weekly sync saying what blocks it.
5. **This file beats memory.** When the plan and recollection disagree, the file wins until edited.
