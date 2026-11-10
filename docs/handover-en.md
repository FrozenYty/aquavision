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

### 2.0 The order, and the one thing to say first

The three tasks in this section are **not parallel**. The dependency is:

```
P2-06a  split on disk
   └─ P2-06b  baseline run
        └─ P2-06c  weights registered
             └─ P2-05b  the detection path          ← the only part that waits
P2-07   contract tests                              ← start here, nothing blocks it
P2-05a  queue consumer, synthetic rows              ← also unblocked
P2-15   contract §7 answers                         ← unblocked, and it unblocks the frontend
```

**Before any of it: say where the dataset is.** `scripts/prepare_dataset.py` reads `data/raw/DUO/DUO`,
and that directory does not exist in this workspace. If the data lives on one machine only, that is a
blocker and it belongs in the first hour — not in a message on Thursday explaining why nothing merged.

**Four rules for this week, and they are not style preferences:**

1. **A task is not started until a pull request exists.** No branch means not started, and the honest
   report is "not started", not "in progress".
2. **A pull request that is open at the end of the day needs a sentence saying why.** Silence reads as
   progress; it is not.
3. **Smaller pull requests, more often.** `P2-06` is three merges, not one. A branch that lives for
   three days cannot be reviewed, and its conflicts become someone else's problem.
4. **The checks are pasted in the pull request.** All of them, every time. §4 spells out which.

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

**What keeps `P1-02` open is exactly two routes**, and they are the two that need weights:

| Route | Requirement | Closes when |
|---|---|---|
| `POST /api/detect/frames/{id}` | FR-M3-01 | `P2-05b` |
| `POST /api/detect/batches` | FR-M3-02 | `P2-05b` |

`POST /api/compare/frames/{id}` used to be on this list and has been **moved to `P4-10`**: it needs two
registered versions loaded at once, so leaving it here would have made `P1-02` unclosable until P4.
That is a correction to the task, not a relaxation of it.

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

**Three questions the frontend sent to this lane, before you build the socket.** The capture page's
client exists and speaks `/ws/capture` today; the contract §7 it speaks to is incomplete:

1. **A binary frame carries no `frame_id`**, so §8's "correlate a result by frame id" has nothing to
   correlate. Either the frame message gets a header, or the first `detect` after each binary frame is
   the correlation.
2. **`detect` carries no quality score**, so the quality ring has nothing to show.
3. **The socket's authentication is unspecified.** The client puts the token in the query string
   because it has nothing better; tokens in URLs leak into logs and referrers. Decide it and write it
   into §7 — first-message authentication is the usual answer.

Answer all three in the contract before the route exists, not after: the page and the server have to
agree on a protocol neither can test alone.

### 2.2 Dataset and a first baseline (task `P2-06`)

`models.py` and `train_experiment` exist; nothing has been trained. This task is the **exploratory**
run: it proves the pipeline end to end and gives the dashboard real numbers. The official E0–E4
experiments remain `P4-01..03` on the frozen dataset — say so in the pull request, so no one thinks the
work is being done twice.

- **Split DUO once, deterministically**, and write the split to disk with a manifest: 7782 images, the
  official test 1111 frozen, and the remaining 6671 divided 85:15 into train and validation. That is
  what `docs/test-plan-en.md` §2 asks for — validation at 10–15 %, a frozen test set of at least 500,
  reported on and never tuned against. The same seed must produce the same split, and the counts must
  sum to the total — checked, not assumed.
- **`7:2:1` is not this split.** It is the ratio of the dataset-export feature (FR-M4-04), which the
  application writes at run time from a reviewed pool. The earlier wording of this task copied it onto
  the training split; that was the lead's error, not yours to reconcile.
- **`scripts/prepare_dataset.py` has to change.** It hard-codes `VAL_RATIO = 0.15`, takes no `--seed`,
  and writes no manifest. Adding them is part of this task, with a test for the determinism claim — the
  grouping hash it already uses stays, because the test plan requires dropping test images that nearly
  duplicate training ones.
- **Train on the GPU, in a separate environment.** The runtime environment has the CPU build of torch;
  leave it alone and create a second environment for training. Four experiments plus an ablation on CPU
  is not a schedule anyone can keep, and a CPU-only run would also make every metric incomparable to
  the speed targets later.
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
- **Contract §7 is now settled, and `live.js` does not match it in two places.** The token travels in
  the query string, which §7 forbids outright — query strings leak into access logs and referrers — so
  it has to become the first `auth` message after the connection opens. And §7 now names `auth_ok`,
  `4401` and `4408`, which the client has to handle. `P2-16` asks for a test of that protocol, in the
  same shape as `tests/test_api_js.py`: when the client and the contract disagree, the test fails.

### 3.5 Dataset export page (task `P2-09`)

The routes exist: `GET`/`POST /api/datasets`, with a real split and a manifest.

- Export a snapshot, list it, refresh — no mock data on that page.
- The split counts shown must equal what the server returned; a mismatch here is the defect that makes
  the export untrustworthy.

### 3.6 Requirements traceability matrix (task `P2-14`)

The course asks for a matrix built from the SRS and the UI prototype, covering **every screen in the
prototype**. The template it is modelled on is a five-sheet workbook: a cover, a change history, the
matrix, and one annotated screenshot per screen.

**The matrix is one row per UI element, not one per screen.** Each row carries: number, module (the
screen), sub-module (header / form / actions / content), function point (the control), a description
that says what it looks like and what it does, three review columns (PD / COD / UT), the author and the
accountable owner.

The description refers to the screenshot by figure and callout — "refer to figure 1, callout 4". That
reference is the whole point of the exercise: it is what lets a reviewer find the element on the image
instead of trusting the prose.

Deliver it in the repository as Markdown, because a spreadsheet cannot be reviewed in a pull request:

- `docs/traceability-en.md` and `docs/traceability-zh.md`, paired like every other document; the English
  is the source of truth and the Chinese is the reference version.
- Screenshots under `docs/images/traceability/`, one per page, named for the page id — `p02-home.png`
  and so on. Callouts may be drawn on the image or, if that is impractical, the rows for a page are
  grouped in reading order and the page states that the numbering is by row.
- The cover fields and the change history from the template, as short sections.
- The status legend — done, in progress, not started — applied honestly. A page that is a prototype
  with mock data is not "done" in the sense a reviewer reads it.

What settles it:

| Claim | The check |
|---|---|
| Every prototype screen is covered | Every file in `web/templates/` appears as a module in the matrix |
| The images are real | Every path referenced under `docs/images/traceability/` exists in the repository |
| The requirement ids are real | Every `FR-Mx-xx` cited exists in `docs/srs-en.md` Table 3-1 |
| A reader can follow it | Someone who has not seen the app finds three named elements on their screenshots |

### 3.7 One page name per page (task `P2-18`)

The pages had three names each. The menu said `Capture control`, SRS §5.2 said `Capture control page`,
the traceability matrix said `Capture control page`; the English disagreed with itself on nine of
thirteen (`Frame browser` against `Image browser`, `Detection tasks` against `Detection jobs`,
`Administration` against `System administration`). And the scheme itself mixed grammars: `capture control`
beside `image browsing`, `workbench` used both as a page type and as a modifier, `models **and**
experiments` the only name with a conjunction in it.

**SRS V1.11 settles it**, and §5.2 is now the authority. The scheme:

Object plus action, four characters where the language allows, no "page" suffix, no conjunction. **The
SRS §5.2 table and `docs/traceability-en/zh.md` already use these names; the interface still uses the old
ones.**

What to do:

- **Rename in the menu** (`web/static/js/layout.js`), **in both page titles** (the `<title>` and the
  `<h1>` of each template), and in anything that names a page to the user.
- **Rename the two templates whose names differ by one letter.** `frames.html` is the image browser and
  `frame.html` is the result detail; one letter apart is a wrong-file edit waiting to happen. Name them
  for what they are.
- **Add the test that keeps four lists equal**: the menu labels, each template's title, SRS §5.2 and the
  traceability matrix, for all thirteen pages. Four hand-maintained copies are exactly the drift this
  repository keeps rediscovering; the test is the part that makes the task stay done.
- **Do not rename the features.** `FR-M4-01` carries its own name in the SRS (a review bench) and stays that way; a page
  name and a requirement's name are different things. Same for route names and table names.

**A note on what this is worth.** A menu is scanned, not read: parallel entries are quicker to find. That
is the reason for the scheme, and it is also why the test matters more than the rename.

### 3.8 The copy review

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
