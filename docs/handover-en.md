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

### 2.1 Finish `P1-02` (task `P2-05`)

**Read this before opening a branch.** Most of `P1-02` is already built, by the lead, because the phase
gate could not wait. Rebuilding it costs a day and loses the tests.

What exists and must not be rewritten:

| Piece | Where | State |
|---|---|---|
| App factory, envelope, error codes, JWT, role guards | `server/app/main.py`, `envelope.py`, `security.py`, `deps.py` | 42 routes mounted |
| Capture ingest, quality scoring, dedup, clock guard | `routers/capture.py` | done |
| Review, hard-example pool | `routers/review.py`, `routers/hard_samples.py` | done |
| Datasets, reports, parameters | `routers/datasets.py`, `reports.py`, `system.py` | done |
| Thirteen tables | `server/app/models.py` | done; ADR 08 explains the last four |
| Contract coverage test | `tests/test_api_skeleton.py` | passing — **do not weaken it** |

What is left:

1. **A real detection path.** `POST /api/detect/frames/{id}` and `/api/detect/batches` return 501
   because no weight file exists. Load the model once at start-up from `model_version.weight_path`, run
   inference, write `detect_object`, and delete the 501.
2. **A queue consumer.** `detect_task` rows are written and never processed. A worker that picks up
   queued tasks, updates `progress` per frame, honours cancel within five seconds (AC-11), and marks a
   failure with a reason.
3. **`POST /api/detect/frames` must refuse a frame that never came through capture** (AC-10) — the
   guard belongs in the handler, not only in the interface.
4. **Statistics on real results.** `/api/stats/*` filters by review status already; confirm the figures
   match the dashboard once detection writes rows.

| Claim | The check |
|---|---|
| Detection is real inference, not fixtures | One frame end to end; boxes match a manual run of the same weights on the same image; rows carry the model version that produced them |
| The queue actually runs | Submit 100 frames; progress advances monotonically; the task reaches `done`; `obj_count` equals the row count |
| Cancel takes effect | Cancel at frame 40; no new result after five seconds; the task reads `cancelled` |
| A failure is retryable | Force one; the task reads `failed` with a reason; retry completes it |
| Nothing regressed | `pytest` at or above its current count; **no test skipped, no assertion deleted** |

### 2.2 Dataset and a first baseline (task `P2-06`)

`models.py` and `train_experiment` exist; nothing has been trained. This task is the **exploratory**
run: it proves the pipeline end to end and gives the dashboard real numbers. The official E0–E4
experiments remain `P4-01..03` on the frozen dataset — say so in the pull request, so no one thinks the
work is being done twice.

- **Split DUO once, deterministically**, and write the split to disk with a manifest: 7782 images,
  official test 1111 held out, the rest split 7:2:1 by the rule the data model already describes. The
  same seed must produce the same split, and the counts must sum to the total — checked, not assumed.
- **One baseline run recorded in `train_experiment`** with every metric column filled: `map50`,
  `map50_95`, `recall_avg`, `fps`, `params_m`, plus the snapshot name, seed, epochs and batch size.
  An empty metric cell fails this task.
- **The weights load through `model_version`.** Register the version, activate it, and show that
  `POST /api/detect/frames` uses it — that is what closes §2.1 item 1.
- **Say what the numbers mean.** If mAP@0.5 lands far from the 0.75 target, say so in the pull request
  with a hypothesis, rather than leaving a low number for someone to discover later.

### 2.3 Contract tests for every route (task `P2-07`)

The skeleton tests cover the envelope, the guards and the 501s. They do not cover **the shape of each
route's payload**, which is the thing the frontend breaks against.

- At least one test per **P0** route: status code, `code` field, and the presence and type of the
  documented fields.
- A failing reference: delete a field from a serializer and the suite must go red. Demonstrate that
  once and say so in the pull request.
- The suite stays runnable with no database server — SQLite, as now.
- Do not test the framework. Test what this project promises in `docs/api-contract-en.md`.

## 3. For Sun Jianheng — the interface

Order matters: 3.1 and 3.2 are mechanical and unblock the rest.

### 3.1 `api.js` tells the truth (task `P2-10`)

The contract went from 18 routes to 42; every route once called "provisional" is in it. The comments
still say otherwise, which now misleads every reader.

- Remove every `// provisional` marker.
- **Add a test that fails if the word returns** — read `api.js`, assert zero occurrences.
- **Add the mirror check**: every exported function maps to a route in `docs/api-contract-en.md` §6.
  Five contract routes have no frontend caller yet (`auth/login`, `auth/me`, `tasks/{id}`,
  `detect/frames`, `compare/frames`) — they are not to be invented; they are listed for the backend.

### 3.2 Sign-in (task `P2-11`)

`POST /api/auth/login` works — lockout, JWT, audit row. The page validates and redirects.

- Call the endpoint; store the token; send it as `Authorization: Bearer`.
- **Show the server's own message** on refusal: it carries the remaining attempts and the lockout time.
- A 401 from any page returns the user to the form instead of an empty table.

### 3.3 Loading, empty and failure (task `P2-12`)

Mock data never fails, so the pages have never rendered a failure. Real data will.

- Every page that calls the API renders three states: loading, empty, and error.
- **Stop the server and reload the page** — a plain sentence, not a blank panel or a stuck spinner.
- A slow response must not look like an empty one.

### 3.4 The capture page streams real frames (task `P2-08`)

`capture.html` currently animates mock detections. `/ws/capture` is specified in the contract §7.

- Live boxes from the socket; polling as the fallback when it cannot connect.
- The mock path stays reachable through `USE_MOCK` — the prototype must still open on a machine with no
  backend.
- The quality ring, the frame strip and the latency figure take their values from the same messages,
  not from a second source.

### 3.5 Dataset export page (task `P2-09`)

The routes exist: `GET`/`POST /api/datasets`, with a real split and a manifest.

- Export a snapshot, list it, refresh — no mock data on that page.
- The split counts shown must equal what the server returned; a mismatch here is the defect that makes
  the export untrustworthy.

### 3.6 The copy review

`docs/copy-review-zh.md` holds nine findings; three are marked as worth doing first. Apply what the lead
approves; the document already records what was applied, so nothing is done twice.

## 4. The bar every handover is held to

1. **The repository's own checks pass locally and the output is pasted in the pull request.** All of
   them, not a summary: `ruff check`, `ruff format --check`, the five document checks, `pytest`, and
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
