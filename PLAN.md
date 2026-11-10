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
      closes when the queue consumer, the two detection routes and the reviewed statistics are real —
      that is `P2-05a`, `P2-05b` and `P2-05c`, and nothing else
      - mounted by @FrozenYty on 11-06: envelope, guards, all 42 routes, 21 of them returning real data
      - **two P0 routes still answer 501**: `POST /api/detect/frames/{id}` (FR-M3-01) and
        `POST /api/detect/batches` (FR-M3-02) — they need weights, so they close with `P2-06c`
      - **`POST /api/compare/frames/{id}` moved out of this task.** It needs *two registered model
        versions loaded at once*, which cannot exist before the improved models do; keeping it here
        would have made P1-02 unclosable until P4. It is now `P4-10`
      - the acceptance list for what remains is `docs/handover-en.md` §2.1
- [x] **P1-03** Capture module: open device, lock exposure, grab, score, persist · @FrozenYty · done
      when 20 frames are captured and file, score and `frame_id` all agree
      - verified on the arrival camera 11-10: 20 frames captured, and the run closed by confirming
        on disk that file, quality score and `frame_id` agree, exit 0
- [x] **P1-04** Thirteen static pages · @chemflowers · done when every page opens, uses mock data and
      shares one visual language
- [x] **P1-05** Test case draft against the 36 acceptance items · @IkeaFyj · done when each item has
      at least one case, marked not-yet-implemented — 49 cases in `docs/test-cases-en.md`, all 36
      items covered, every case marked not implemented
- [ ] **P1-06** Hardware arrival check and rig assembly · @FrozenYty · **camera half done 11-10** —
      `scripts/test_exposure.py --index 1` exits 0 (1080p, exposure lockable, 5 fps, 0.5 % spread);
      `scripts/test_rig.py` exists and measures the three numbers below, but they still need the
      assembled rig · **electrical half partly done 11-10**: OLED at `0x3C` draws and answers, the
      serial command path works, and the five screens were driven without a button; LEDs wait for the
      resistors, the button has not arrived, the turbidity sensor needs the level shifter · done when
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
- [x] **P2-03** Capture and review pages on real data · @chemflowers · closes AC-08, AC-13 · done when no mock data is left
      on those two pages
- [x] **P2-04** Minimal review loop: delete, add, relabel · @chemflowers @Gtechson · closes AC-17 · done when the
      edit persists and the count updates without a page reload

      **Backend and model · @Gtechson**

- [ ] **P2-05** Finish P1-02: detection, the queue consumer, reviewed statistics · @Gtechson · closes
      AC-05, AC-07, AC-10, AC-12 · three checkpoints, each its own pull request
      - **P2-05a** the queue consumer, driven by synthetic `detect_task` rows — **no weights needed,
        start here**
        - delivered 11-10: `server/app/worker.py` claims queued tasks, advances `progress`, honours
          cancel, records a failure reason, and requeues stale rows on restart; the detector is
          injected, so this checkpoint never invents boxes
      - **P2-05b** the detection path — **blocked until `P2-06c` produces weights**, and it is the only
        part of this task that is
      - **P2-05c** `/api/stats/*` verified against rows written by 05b, figures equal to the dashboard
- [x] **P2-06** DUO dataset preparation and a first baseline run · @Gtechson · three checkpoints
      - the dataset is on the **training machine**, not on the lead's: `data/raw/DUO/DUO` (6671 + 1111)
        and `data/dataset` (5671 / 1000 / 1111). Nothing here is blocked by its absence elsewhere
      - **P2-06a** the split, and the script that produces it
        - **the split is 85:15 train/validation over the 6671 non-test images**, and DUO's official
          1111 stays frozen as the reported test set — `docs/test-plan-en.md` §2 asks for validation at
          10–15 % and a frozen test set of at least 500 images, and this satisfies both
        - **`7:2:1` does not apply here.** It is the ratio of the *dataset-export feature* (FR-M4-04,
          SRS §5 table `split_ratio`), a different thing that the application writes at run time. The
          earlier wording of this task copied it onto the training split and was wrong
        - `scripts/prepare_dataset.py` needs `--seed` and a manifest; the grouping hash it already uses
          stays, because the test plan requires dropping test images that nearly duplicate training ones
        - the manifest is `test-manifest.txt`, one `filename md5` per line, committed — the test plan
          already promised it
        - delivered 11-10: `--seed` and `--manifest` are in the script; `test-manifest.txt` is
          committed with 1111 lines; a test fixes the real group sizes to 5671 / 1000 and the total
          7782. The on-disk split was not regenerated — the lead confirmed it is correct
      - **P2-06b** one baseline run recorded in `train_experiment` with every metric column filled
        - training runs on the GPU: install a **separate** environment with the CUDA build of torch.
          The runtime environment must not be touched, and a CPU run of four future experiments plus
          an ablation is not a schedule anyone can keep
        - delivered 11-10: YOLOv8n, 1800 train / 200 val, 30 epochs, seed 42; frozen test mAP@0.5
          0.770, mAP@0.5:0.95 0.561, mean recall 0.692, 499 fps, 3.14 M params; `train_experiment`
          row 1; weights under `runs/detect/data/models/baseline-e0/weights/best.pt`
      - **P2-06c** the weights registered and loadable through `model_version`, which unblocks `P2-05b`
        - delivered 11-10: `model_version` row 1 `v8n-E0-exploratory` is online; `scripts/register_model.py`
          turns `metrics.json` into that row; a captured frame went through `POST /api/detect/frames`
          with the P2-05b branch and matched a manual run of the same weights
      - this is the **exploratory** run that gives the dashboard real numbers; the official E0–E4 stay
        at `P4-01..03` on the frozen dataset, and the difference is stated in the pull request
- [x] **P2-07** API contract tests for every route · @Gtechson · done when each P0 route has at least
      one test asserting status, envelope and payload shape, and the suite still runs without a
      database server

      **Frontend and interface · @chemflowers**

- [ ] **P2-08** The capture page streams real frames · @chemflowers · done when `capture.html` shows
      live detections from `/ws/capture` (or polling if the socket is unavailable), and the mock path
      stays behind `USE_MOCK`
- [x] **P2-09** Dataset export page against the real API · @chemflowers · closes AC-18 · done when a snapshot can be
      exported, listed and refreshed with no mock data, and the split counts match the server
- [x] **P2-10** `api.js` tells the truth · @chemflowers · done when no `provisional` marker remains, a
      test fails if the word returns, and every exported function maps to a route in the contract
- [x] **P2-11** Sign-in against the real endpoint · @chemflowers · closes AC-01 · done when the login page calls
      `POST /api/auth/login`, stores the token, shows the server's own lockout message, and a 401 from
      any page returns the user to the form
- [x] **P2-12** Loading, empty and failure states · @chemflowers · done when every page that calls the
      API renders all three states, and a killed server produces a message rather than a blank screen

      **Together**

- [ ] **P2-13** Rehearse the P2 gate end to end · @Gtechson @chemflowers · done when someone who has
      not seen the system completes the slice from a cold start in under two minutes, twice in a row
- [x] **P2-14** Requirements traceability matrix over every prototype screen · @chemflowers · done
      when each screen in `web/templates/` has rows in `docs/traceability-en/zh.md`, every referenced
      screenshot exists in the repository, and every requirement id it cites exists in the SRS
- [x] **P2-15** Answer contract §7's three open questions · @Gtechson · unblocks `P2-08` · done when
      §7 states how the socket authenticates, how a binary frame is correlated to its `frame_id`, and
      where that frame's quality score is carried — all three, in the contract, before the route exists
- [x] **P2-16** Hold `live.js` to contract §7 · @chemflowers · done when the socket sends the token in
      the first `auth` message rather than the query string, handles `4401` and `4408`, and a test fails
      when the client and §7 disagree about a message type or a field - the mirror of
      `tests/test_api_js.py`, which is what keeps the REST client honest

- [ ] **P2-17** The PC side of the rig link · @FrozenYty · **nothing owns this today** — the architecture
      draws `MCU -. serial .-> CAP` and no task implements it · done when the server opens the port,
      keeps it alive with `CMD PING` every two seconds, turns an `EVT TRIGGER` into a capture, answers
      with `CMD RESULT`, and surfaces `EVT SCREEN`, `EVT TIMEOUT` and `EVT STRAY RESULT` in the log
      - the keepalive is not decoration: without it the rig declares a healthy idle system offline after
        ten seconds, and waiting for a button is what the rig does most of the time

- [ ] **P2-18** One page name per page · @chemflowers · the SRS table and the traceability matrix
      already carry the new names (SRS V1.11); the interface still says the old ones · done when
      - **the menu, both page titles and the traceability matrix agree with SRS §5.2 for all thirteen
        pages.** The scheme is object plus action, four characters where the language allows, no "page"
        suffix, no conjunction; the names themselves are the §5.2 table, which is the authority
      - **a test enforces it**, comparing `layout.js` labels, each template's title, SRS §5.2 and
        `docs/traceability-en/zh.md`. Four lists that are only checked by eye drift; the drift is what
        this task exists to undo
      - **`frame.html` and `frames.html` stop differing by one letter** - they are the result detail and
        the image browser, and a one-letter difference is a wrong-file bug waiting to happen
      - **the copy review closes**: sidebar group names, statistics subtitles, dashboard KPI prefixes,
        applied or rejected with a reason
      - **the `P-xx` eyebrow leaves the twelve page headers**; the screen-to-SRS anchor now lives in the
        traceability matrix
      - **nothing regresses**: the page tests pass and every existing control survives

- [ ] **P2-19** Two documents that disagree with the code, in other lanes · @Gtechson + @IkeaFyj ·
      found by the 11-10 audit, left alone because fixing another lane's document inside this diff is the
      habit the handover forbids · done when
      - **`docs/api-contract-en/zh.md` §5** documents `from=`/`to=` on `GET /api/frames`; the route reads
        `start`/`end`, and an undeclared query parameter is silently ignored, so a filter written from
        the contract returns unfiltered data (lane B)
      - **`docs/test-plan-en/zh.md`** names `scripts/evaluate.py` as the model-evaluation tool and
        describes `tests/fixtures/` as holding three JPEGs; neither exists - metrics come out of
        `train_baseline.py`, and the tests synthesise their frames (lane D)

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
- [ ] **P4-10** Same-frame comparison · @Gtechson · moved from `P1-02` · done when
      `POST /api/compare/frames/{id}` runs the baseline and one improved model on the same frame, the
      response carries both sets of boxes and both version names, and the page can show them side by
      side — it could not be built earlier because it needs two registered versions

- [ ] **GATE P4** — four tables full: metrics, ablation, reproducibility, acceptance checklist

## 5. Text constraints

These replace process tooling. Short on purpose.

1. **One task, one PR, one owner.** If a task needs two people, the owner is whoever merges.
2. **Status rides with the delivering PR.** A ticked box without a merged PR is a claim, not a fact.
3. **A gate is checked by someone other than the lane owner.** Two minutes, eyeballs only.
4. **Blocked is stated, not hidden.** A task sitting open for more than three days gets one sentence
   in the weekly sync saying what blocks it.
5. **This file beats memory.** When the plan and recollection disagree, the file wins until edited.
