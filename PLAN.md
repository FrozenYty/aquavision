# Tasks

> Owner: every lane · Revisit when: a task is delivered or re-scoped

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
| P1 | Every layer has a minimal implementation | `uvicorn` starts, `/api/health` returns the envelope, 13 tables created, 13 pages open |
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

- [x] **P1-01** DDL script and species dictionary seed · @Gtechson · done when `scripts/init_db.py`
      runs on an empty database and four classes are seeded
- [ ] **P1-02** FastAPI skeleton: every contract route, envelope, error codes, JWT · @Gtechson ·
      done when `/api/health` answers in the envelope, every route in `docs/api-contract-en.md` §6 is
      mounted, and the ones marked P0 return real data while the rest return 501 in the same envelope
      - mounted by @FrozenYty on 11-06: envelope, guards, all 42 routes, 21 of them returning real
        data. What remains is detection, the queue consumer and the reviewed statistics — the
        acceptance list for those is `docs/handover-en.md` §2
- [ ] **P1-03** Capture module: open device, lock exposure, grab, score, persist · @FrozenYty · done
      when 20 frames are captured and file, score and `frame_id` all agree
- [x] **P1-04** Thirteen static pages · @chemflowers · done when every page opens, uses mock data and
      shares one visual language
- [x] **P1-05** Test case draft against the 36 acceptance items · @IkeaFyj · done when each item has
      at least one case, marked not-yet-implemented — 49 cases in `docs/test-cases-en.md`, all 36
      items covered, every case marked not implemented
- [ ] **P1-06** Hardware arrival check and rig assembly · @FrozenYty · done when
      `python scripts/test_exposure.py` exits 0 — the device opens, the picture answers the exposure
      property, and 20 pinned frames stay inside a 10 % spread — and the rig meets its numbers:
      left/right brightness ratio ≥ 0.7, a 5 cm target ≥ 45 px at 640 input, no flicker

- [ ] **GATE P1** — `uvicorn app.main:app` starts on a clean machine, `/api/health` answers, 13 tables
      exist, 13 pages render

### P2 — vertical slice

- [ ] **P2-01** Capture → detection, single frame · @FrozenYty @Gtechson · done when one call returns
      boxes with `model_version` and `latency_ms`
- [ ] **P2-02** Result persistence and query API · @Gtechson · done when boxes land in
      `detect_object` and querying by `frame_id` returns them
- [ ] **P2-03** Capture and review pages on real data · @chemflowers · closes AC-08, AC-13 · done when no mock data is left
      on those two pages
- [ ] **P2-04** Minimal review loop: delete, add, relabel · @chemflowers @Gtechson · closes AC-17 · done when the
      edit persists and the count updates without a page reload

      **Backend and model · @Gtechson**

- [ ] **P2-05** Finish P1-02: detection, the queue consumer, reviewed statistics · @Gtechson · closes
      AC-05, AC-07, AC-10, AC-12 · done
      when `POST /api/detect/frames/{id}` returns boxes from real weights, a batch task advances to
      `done` on its own, and `/api/stats/*` matches the dashboard — the acceptance list is
      `docs/handover-en.md` §2
- [ ] **P2-06** DUO dataset preparation and a first baseline run · @Gtechson · done when the split is
      written to disk with a manifest, one baseline experiment is recorded in `train_experiment`, and
      its weights load through `model_version`
      - this is the **exploratory** run that unblocks P2-01 and gives the dashboard real numbers; the
        official E0–E4 experiments stay at P4-01..03 on the frozen dataset, and the difference is
        stated in the pull request so nobody thinks the work is done twice
- [ ] **P2-07** API contract tests for every route · @Gtechson · done when each P0 route has at least
      one test asserting status, envelope and payload shape, and the suite still runs without a
      database server

      **Frontend and interface · @chemflowers**

- [ ] **P2-08** The capture page streams real frames · @chemflowers · done when `capture.html` shows
      live detections from `/ws/capture` (or polling if the socket is unavailable), and the mock path
      stays behind `USE_MOCK`
- [ ] **P2-09** Dataset export page against the real API · @chemflowers · closes AC-18 · done when a snapshot can be
      exported, listed and refreshed with no mock data, and the split counts match the server
- [x] **P2-10** `api.js` tells the truth · @chemflowers · done when no `provisional` marker remains, a
      test fails if the word returns, and every exported function maps to a route in the contract
- [ ] **P2-11** Sign-in against the real endpoint · @chemflowers · closes AC-01 · done when the login page calls
      `POST /api/auth/login`, stores the token, shows the server's own lockout message, and a 401 from
      any page returns the user to the form
- [ ] **P2-12** Loading, empty and failure states · @chemflowers · done when every page that calls the
      API renders all three states, and a killed server produces a message rather than a blank screen

      **Together**

- [ ] **P2-13** Rehearse the P2 gate end to end · @Gtechson @chemflowers · done when someone who has
      not seen the system completes the slice from a cold start in under two minutes, twice in a row
- [ ] **P2-14** Requirements traceability matrix over every prototype screen · @chemflowers · done
      when each screen in `web/templates/` has rows in `docs/traceability-en/zh.md`, every referenced
      screenshot exists in the repository, and every requirement id it cites exists in the SRS

- [ ] **GATE P2** — from a cold start, someone who has not seen the system completes the slice in
      three minutes, no restart, no manual database edit

### P3 — breadth

- [ ] **P3-01** Batch detection, the pool and progress · @Gtechson · closes AC-11 · done when a
      100-frame task completes, progress is queryable while it runs, and a restart mid-task resumes
      it rather than losing it
- [ ] **P3-02** Statistics dashboard · @chemflowers · closes AC-19, AC-20, AC-21 · done when the four
      charts render from `/api/stats/*`, the basis switch changes both the figures and the caption,
      and the empty site shows an empty state rather than a blank chart
- [ ] **P3-03** Model versions and activation · @Gtechson · closes AC-23, AC-24 · done when exactly one
      model is online, a version without metrics cannot go online, and each result records the version
      that produced it
- [ ] **P3-04** Account management · @Gtechson · closes AC-03, AC-04 · done when an account can be created,
      disabled and restored, a disabled account cannot sign in, and its history stays queryable
- [ ] **P3-05** Review canvas: drag, zoom, add, delete · @chemflowers · closes AC-15, AC-16 · done when
      all four gestures work on one frame without a reload, and two reviews produce two versions that
      can be rolled back between
- [ ] **P3-06** Demo mode · @FrozenYty · closes AC-36 · done when one action resets the data, hides
      debug output, and leaves the system in the state a rehearsal starts from
- [ ] **P3-07** Report generation and history · @chemflowers · closes AC-22 · done when a report is
      generated as Markdown from the same queries the dashboard uses, its figures equal the dashboard,
      and the footer carries the model version and the basis — **not Word or PDF; SRS V1.6 settled that**
- [ ] **P3-08** Retention cleanup and reference nulling · @Gtechson · closes AC-09 · done when the
      cleanup job removes intermediate files older than the retention period, nulls the references,
      never touches originals by default, and reports what it deleted
- [ ] **P3-09** Parameters, monitoring and messages · @Gtechson · closes AC-27, AC-28, AC-29 · done
      when a parameter change persists and is audited with before and after values, the queue and disk
      levels are visible, and a repeated failure message is not duplicated
- [ ] **P3-10** Performance budget, measured · @FrozenYty · closes AC-34 · done when a committed script
      measures single-frame latency and the list endpoints' P90 against a database at design capacity,
      and the numbers are pasted into the pull request — a claim is not a measurement
- [ ] **P3-11** The permission matrix, negatively tested · @Gtechson · closes AC-02 · done when a test
      asserts 403 for every (role, guarded route) pair where access must be refused, and the list of
      pairs lives in the test file rather than in someone's head
- [ ] **P3-12** Failure and recovery · @FrozenYty · covers the states between AC items · done when a
      killed worker, an unreachable database and a full disk each produce a message the operator can
      act on, instead of a blank page or a stuck spinner
- [ ] **P3-13** Scheduled capture · @Gtechson · closes AC-06 · there is no timer anywhere in the system
      yet: done when a schedule of N captures every M minutes produces exactly N batches, a run whose
      device is unavailable is marked failed with a reason, and the schedule survives a restart
- [ ] **P3-14** Result export · @chemflowers · closes AC-14 · done when a result set exports as CSV with
      one row per box, the row count equals the page's count, and Chinese class names open correctly in
      Excel — the encoding is the part that usually breaks
- [ ] **P3-15** Species dictionary and per-class thresholds · @chemflowers · closes AC-26 · done when the
      four classes and their thresholds can be viewed and edited on P-12, a threshold change applies to
      new jobs and not to finished ones, and a class code that disagrees with `labels.txt` is refused

- [ ] **GATE P3** — all 36 acceptance items demonstrated live, one after another, no manual database
      edits in between, and every item traceable to the task that closed it

### P4 — close

- [ ] **P4-01** Dataset freeze, then baseline E0 · @Gtechson · closes AC-30 · done when the snapshot is
      frozen **before** the first official run — name, split, seed and manifest written down — and E0
      is recorded with every metric column filled
      - freezing first is the point: a baseline trained on a moving dataset cannot be compared to
        anything, and every later number inherits the mistake
- [ ] **P4-02** The three improvements · @Gtechson · closes AC-32 · done when each is isolated on top of
      the previous one, each has a row in the experiment table, and each reports its delta against E0
      - E1 underwater colour correction
      - E2 EMA attention
      - E3 WIoU v3 loss
- [ ] **P4-03** Ablation and tank fine-tuning · @Gtechson · closes AC-32 · done when the ablation table
      shows each improvement's own contribution, and the fine-tune on tank images is evaluated against
      the same test set
- [ ] **P4-04** Metric acceptance, per class · @Gtechson @IkeaFyj · closes AC-30, AC-31, AC-33 · done
      when all **seven** metrics of SRS Table 6-1 (AL-01..AL-07) are recorded — the count was nine
      before V1.3 deleted AL-08 and AL-09 — and any miss is explained in writing
- [ ] **P4-05** Defect closure · all · done when every defect has a recorded severity, a fix and a
      regression check, and blocker and major counts are zero — "no defects" is not a number
- [ ] **P4-06** Acceptance checklist, demo script, slides · @IkeaFyj · done when every acceptance item
      is ticked with the evidence beside it, and the demo runs end to end on paper without a question
      left unanswerable
- [ ] **P4-07** Three rehearsals · @FrozenYty · done when each run finishes under eight minutes with no
      dead air, and the third run needs no fix made between it and the previous one
- [ ] **P4-08** Reproducibility · @Gtechson · closes AC-25 · done when the same configuration run twice
      differs by less than 1 % on every metric, and both runs are in the table — a single run proves
      nothing about the next one
- [ ] **P4-09** Submission package · @FrozenYty · closes AC-35 · done when the SRS, the traceability
      matrix, the test report and this plan agree with each other and with the code at one commit, and
      the document index lists nothing that does not exist

- [ ] **GATE P4** — four tables full: metrics, ablation, reproducibility, acceptance checklist

## 5. Text constraints

These replace process tooling. Short on purpose.

1. **One task, one PR, one owner.** If a task needs two people, the owner is whoever merges.
2. **Status rides with the delivering PR.** A ticked box without a merged PR is a claim, not a fact.
3. **A gate is checked by someone other than the lane owner.** Two minutes, eyeballs only.
4. **Blocked is stated, not hidden.** A task sitting open for more than three days gets one sentence
   in the weekly sync saying what blocks it.
5. **This file beats memory.** When the plan and recollection disagree, the file wins until edited.
