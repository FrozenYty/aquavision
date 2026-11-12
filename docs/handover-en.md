# Handovers

> Chinese version: [handover-zh.md](handover-zh.md). This file is the source of truth.
> Owner: @FrozenYty · Revisit when: an item closes or a new one opens

Work that has changed hands, with the bar it must clear. This document is **living**: an item is
deleted when it is accepted, not left as history. What was done stays in `PROGRESS.md`; what must be
true next lives here.

## 1. How this document works

- One section per person. Each item states **what exists**, **what is left**, and **how it is checked**.
- A criterion is something a stranger can run or read and settle. "Works well" is not a criterion.
- Task ids match `PLAN.md`; if the two disagree, `PLAN.md` wins and this file is corrected.
- §4 applies to every item here, including the ones written for someone else.

## 2. For Gao Tianxiang — the backend and the model

### 2.0 Where the dataset is, and what is left

The backend tasks this section used to sequence — `P2-06a/b/c`, `P2-05a/b/c`, `P2-07` and `P2-15` —
are delivered and tested; `PLAN.md` records what each delivery had to prove. What is left in this lane:
`P3-03` (model versions and activation), `P3-04` (account management), `P3-08` (retention cleanup),
`P3-09` (parameters, monitoring and messages), `P3-11` (the permission matrix), `P3-13` (scheduled
capture) and `P3-15` (species thresholds, shared with the interface lane) — plus the weight file, in
§2.2.

**The dataset is on the training machine, not in this checkout:** `data/raw/DUO/DUO` (6671 + 1111) and
`data/dataset` (5671 / 1000 / 1111). Nothing here is blocked by its absence.

**Four rules for whoever picks this up, and they are not style preferences:**

1. **A task is not started until a pull request exists.** No branch means not started, and the honest
   report is "not started", not "in progress".
2. **A pull request that is open at the end of the day needs a sentence saying why.** Silence reads as
   progress; it is not.
3. **Smaller pull requests, more often.** A branch that lives for three days cannot be reviewed, and
   its conflicts become someone else's problem.
4. **The checks are pasted in the pull request.** All of them, every time. §4 spells out which.

### 2.1 `P1-02` and the detection routes (task `P2-05`)

`P1-02` closed on 2026-11-11 with `P2-05a` (queue consumer), `P2-05b` (detection path) and `P2-05c`
(statistics against the rows detection wrote); `PLAN.md` carries the record of what each delivery had
to prove.

What exists and must not be rewritten:

| Piece | Where | State |
|---|---|---|
| App factory, envelope, error codes, JWT, role guards | `server/app/main.py`, `envelope.py`, `security.py`, `deps.py` | 45 contract routes mounted |
| Capture ingest, quality scoring, dedup, clock guard | `routers/capture.py` | done |
| Review, hard-example pool | `routers/review.py`, `routers/hard_samples.py` | done |
| Datasets, reports, parameters | `routers/datasets.py`, `reports.py`, `system.py` | done |
| Fourteen tables | `server/app/models.py` | done; ADR 08 explains the four from V1.5, ADR 12 the task-item table |
| Contract coverage and payload-shape tests | `tests/test_api_skeleton.py` | passing — **do not weaken it** |

Every detection route now runs the model the `model_version` row puts online:

| Route | Requirement | State |
|---|---|---|
| `POST /api/detect/frames/{id}` | FR-M3-01 | delivered (`P2-05b`); boxes, `model_version` and a measured latency |
| `POST /api/detect/batches` | FR-M3-02 | delivered; queues a task the worker consumes, and answers 501 only when no frame exists |
| `POST /api/compare/frames/{id}` | FR-M6-03 | `P4-10`; needs two registered versions loaded at once |

**What is still open in this area:** per-class thresholds and `class_filter` are `P3-15`. The worker
ignores `class_filter` today, and detection uses the caller's `conf_thr`, not the per-class values in
`species_dict`.

| Claim | The check |
|---|---|
| Detection is real inference, not fixtures | One frame end to end; boxes match a manual run of the same weights on the same image; rows carry the model version that produced them |
| The queue actually runs | Submit 100 frames; progress advances monotonically; the task reaches `done`; `obj_count` equals the row count |
| Cancel takes effect | Cancel at frame 40; no new result after five seconds; the task reads `cancelled` |
| A failure is retryable | Force one; the task reads `failed` with a reason; retry completes it |
| Nothing regressed | `pytest` at or above its current count; **no test skipped, no assertion deleted** |

**Contract §7 is settled and implemented on both sides.** The socket authenticates with a first-message
`auth` and answers `auth_ok`; a bad token closes with `4401` and no `auth` within five seconds with
`4408`; one binary JPEG follows its `frame` message and results are correlated by `frame_id`; the
quality score rides on the `frame` message. `server/app/routers/live.py` serves it,
`tests/test_ws_capture.py` holds the server to the contract, and `tests/test_live_socket.py` holds the
client.

### 2.2 Dataset and a first baseline (task `P2-06`)

`P2-06` is delivered: the split is deterministic and on disk (85:15 over the 6671 non-test images, the
official 1111 frozen); `test-manifest.txt` is committed with 1111 `filename md5` lines;
`scripts/prepare_dataset.py` takes `--seed` and `--manifest`; the exploratory baseline (YOLOv8n,
1800 train / 200 val, 30 epochs, seed 42) is recorded in `train_experiment` with mAP@0.5 0.770,
mAP@0.5:0.95 0.561 and mean recall 0.692; and its version is registered and online as
`v8n-E0-exploratory`. `tests/test_prepare_dataset.py` holds the determinism and manifest claims.

**What is left:**

- **The weight file.** The delivered `best.pt` is not in the repository yet, so `P2-13` and `GATE P2`
  stay blocked on it; ADR 13 fixes where it goes — `models/<version_name>/best.pt`, `labels.txt` and
  `metrics.json`.
- **The official runs.** E0–E4 remain `P4-01..03` on the frozen dataset; `PLAN.md` keeps the
  exploratory run and the official runs apart.

### 2.3 Contract tests for every route (task `P2-07`)

`P2-07` is delivered: `tests/test_api_skeleton.py` asserts the envelope, the guards and the documented
payload shape of every P0 route, and `tests/test_api_js.py` mirrors the contract for the client's
exports. The suite runs on SQLite with no database server. **Do not weaken either test.** The rule
behind them: test what `docs/api-contract-en.md` promises, not the framework.

## 3. For Sun Jianheng — the interface

Everything in this section is delivered and tested; this lane's remaining work is `P3-02` (statistics
dashboard), `P3-07` (report generation and history) and `P3-15` (the species-threshold page, shared
with the backend lane).

### 3.1 `api.js` tells the truth (task `P2-10`)

The client is honest about the contract: `api.js` carries no `provisional` markers, every exported
function maps to a route in `docs/api-contract-en.md` §6, and `tests/test_api_js.py` fails if either
claim stops holding. Four contract routes still have no frontend caller (`auth/me`, `tasks/{id}`,
`detect/frames`, `compare/frames`) — they are listed for the backend, not to be invented.

### 3.2 Sign-in (task `P2-11`)

Sign-in is wired to the real endpoint: the page calls `POST /api/auth/login`, stores the token and
sends it as `Authorization: Bearer`; a refusal shows the server's own sentence, which carries the
remaining attempts and the lockout time; and a 401 from any page returns the user to the form. Lockout,
JWT and the audit row are covered in `tests/test_api_skeleton.py`.

### 3.3 Loading, empty and failure (task `P2-12`)

Every page that calls the API draws three states through `loadInto` in `web/static/js/ui.js`: a loading
line, the empty-state message, and an error with a retry. A slow answer says so instead of looking
empty. Keep new callers on that helper, so a page added later cannot quietly render only the success
case.

### 3.4 The capture page streams real frames (task `P2-08`)

`capture.html` streams real frames over `/ws/capture`, which api-contract §7 defines and
`server/app/routers/live.py` serves; polling is only the fallback when the socket cannot be served.
The quality ring, the frame strip and the latency figure take their values from the same message
stream, never a second source, and the mock path stays reachable through `USE_MOCK`.

**Contract §7 and the client agree.** The token travels in the first `auth` message, never the URL;
`auth_ok`, `4401` and `4408` are handled; a binary JPEG follows its `frame` message; and results carry
the `frame_id` and the quality score. `tests/test_live_socket.py` holds the client to the contract,
`tests/test_ws_capture.py` the server. **Known limit, open as `P3-12`:** a socket that dies after
`auth_ok` reports "closed" and does not fall back to REST polling.

### 3.5 Dataset export page (task `P2-09`)

The page is wired to the real API: `GET`/`POST /api/datasets` back the snapshot form and the history,
the split counts shown come from the server's response, and the page runs with no mock data. A split
count that disagrees with the response is still the defect that makes the export untrustworthy.

### 3.6 Requirements traceability matrix (task `P2-14`)

`docs/traceability-en.md` and `docs/traceability-zh.md` are the matrix: one row per UI element, with a
cover, a change history, PD/COD/UT status and one annotated screenshot per screen under
`docs/images/traceability/`. Its authority is the SRS: the module names follow SRS §5.2 and every
`FR-Mx-xx` it cites exists in Table 3-1. When a screen or an element changes, update the matrix and
recapture the screenshot.

What it is checked against:

| Claim | The check |
|---|---|
| Every prototype screen is covered | Every file in `web/templates/` appears as a module in the matrix |
| The images are real | Every path referenced under `docs/images/traceability/` exists in the repository |
| The requirement ids are real | Every `FR-Mx-xx` cited exists in `docs/srs-en.md` Table 3-1 |
| A reader can follow it | Someone who has not seen the app finds three named elements on their screenshots |

### 3.7 One page name per page (task `P2-18`)

The SRS §5.2 names are the single scheme — object plus action, four characters where the language
allows, no "page" suffix, no conjunction — and the menu, both page titles, the SRS and the matrix all
use them:

| | | | |
|---|---|---|---|
| Sign-in | Running overview | Capture control | Image browser |
| Detection jobs | Result detail | Manual review | Hard samples |
| Data export | Statistics | Inspection reports | Model experiments |
| System settings | | | |

`tests/test_page_names.py` keeps the four lists equal and fails when a list drifts or when two template
names differ by one character. **Do not rename the features:** `FR-M4-01` is still the review bench,
and page names, requirement names, routes and table names are separate things.

### 3.8 The copy review

`docs/copy-review-zh.md` records the findings. The three priority items and the P2-18 batch are closed —
sidebar group names, statistics subtitles and the dashboard KPI prefixes — and §6 of that document
records each decision. What remains is optional polish, listed in its §4.

## 4. The bar every handover is held to

1. **The repository's own checks pass locally and the output is pasted in the pull request.** All of
   them, not a summary: `ruff check`, `ruff format --check`, the document checks, `pytest`, and
   `pio run` if firmware changed.
2. **The thing is demonstrable.** A reviewer performs the claim in the table without asking the author.
3. **Documents move with the code.** A route change updates the contract; a schema change updates the
   data model and `EXPECTED_COLUMNS`; anything a reader would now believe falsely is corrected in the
   same pull request.
4. **A decision that departs from a document gets an ADR.** Silent divergence is the one failure four
   writers cannot afford.
5. **No test is deleted or skipped to make the gate green.** If a test is wrong, the pull request says
   which and why.
6. **The pull request states what is not done.** "It works" is not a report; a known gap named in the
   description is worth more than one found in the defence.

## 5. Closing a handover

When an item is accepted, delete its section here, tick the task in `PLAN.md`, and record the outcome
in `PROGRESS.md` with the date. A handover document that lists finished work stops being read, and the
next person then misses the one item that still matters.
