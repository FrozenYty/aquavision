# Handovers

> Chinese version: [handover-zh.md](handover-zh.md). This file is the source of truth.
> Owner: @FrozenYty · Revisit when: an item closes or a new one opens

Work that has changed hands, with the bar it must clear. This document is **living**: an item is
deleted when it is accepted, not left as history. What was done stays in `PROGRESS.md`; what must be
true next lives here.

## 1. How this document works

- One section per person. Each item states **what exists**, **what is left**, and **how it is checked**.
- A criterion is something a stranger can run or read and settle. "Works well" is not a criterion.
- Anything not listed here is not in scope. An unlisted change is welcome, but it arrives as its own
  pull request with its own reason, not folded into these.
- §4 applies to every item here, including the ones written for someone else.

## 2. For Gao Tianxiang — P1-02 and the detection path

**Read this before opening the branch.** Most of `P1-02` is already built, by the lead, because the
phase gate could not wait until Monday. Rebuilding it will waste a day and lose the tests.

### What already exists and must not be rewritten

| Piece | Where | State |
|---|---|---|
| App factory, envelope, error codes, JWT, role guards | `server/app/main.py`, `envelope.py`, `security.py`, `deps.py` | Done, 42 routes mounted |
| Task queue rows, cancel, retry | `server/app/routers/tasks.py` | Rows and state machine done; **nothing consumes the queue** |
| Capture ingest with quality scoring, dedup, clock guard | `server/app/routers/capture.py` | Done |
| Review, hard-example pool | `routers/review.py`, `routers/hard_samples.py` | Done |
| Datasets, reports, parameters | `routers/datasets.py`, `reports.py`, `system.py` | Done |
| The nine-table model and the four new tables | `server/app/models.py` | Done; ADR 08 explains the four |
| Contract coverage test | `tests/test_api_skeleton.py::test_every_contract_route_is_mounted` | Passing; **do not weaken it** |

### What is left

1. **A real detection path.** `POST /api/detect/frames/{id}` and `/api/detect/batches` return 501
   because there is no weight file. Load the model once at start-up from `model_version.weight_path`,
   run inference, write `detect_object` rows, and make the 501 disappear.
2. **A queue consumer.** `detect_task` rows are written and never processed. A worker that picks up
   queued tasks, updates `progress` per frame, honours cancel within five seconds (AC-11) and marks
   failures with a reason.
3. **Statistics that follow the reviewed basis.** `/api/stats/*` already filters by status; confirm
   the figures match the dashboard after real detection exists.
4. **`POST /api/detect/frames` must refuse a frame that never came from capture** (AC-10) — the guard
   belongs in the handler, not only in the interface.

### How each of those is checked

| Claim | The check |
|---|---|
| Detection is real inference, not fixtures | Run one frame end to end; the boxes match a manual run of the same weights on the same image; `detect_object` rows carry the model version that produced them |
| The queue actually runs | Submit 100 frames; progress advances monotonically; the task reaches `done`; `obj_count` matches the rows |
| Cancel takes effect | Cancel at frame 40; no new result appears after five seconds; the task reads `cancelled` |
| A failed frame can be retried | Force one failure; the task reads `failed` with a reason; retry resets it and it completes |
| No fake data anywhere | Every remaining 501 names what is missing in its message |
| Nothing regressed | `pytest -q` is at least 114 passed; no test skipped, no assertion deleted |

### Constraints

- **Do not change the vision module** (`server/app/vision/`) — it is lane A's, and the camera checks
  depend on its current behaviour.
- **Do not rename or drop a column** without an ADR; `EXPECTED_COLUMNS` will fail the suite, and the
  data model document must move in the same pull request.
- **Do not add a dependency** without pinning it and updating the CI dependency line in the same
  commit. CI installs a short explicit list and nothing else.
- **Do not silence a failing test** to make the gate green. If a test is wrong, say why in the review.

## 3. For Sun Jianheng — interface debt

Three items, in this order. The first two are mechanical and can be closed in one pull request.

### 3.1 The `provisional` markers are now false

The contract went from 18 routes to 42 (`docs/api-contract-en.md` §6); all 24 that were called
"provisional" are in it. The comments in `web/static/js/api.js` still say they are not, which now
misleads every reader.

- Remove every `// provisional` marker; none of those routes is provisional any more.
- Add a check that fails when the word comes back: a test that reads `api.js` and asserts it appears
  zero times, so a future edit cannot quietly reintroduce the confusion.
- Add the matching check on the other side: **every function in `api.js` maps to a route in the
  contract**. The five contract routes with no frontend caller — `auth/login`, `auth/me`,
  `tasks/{id}`, `detect/frames`, `compare/frames` — are not to be invented; they are listed in §6 for
  the backend and will get a caller when the page needs one.

### 3.2 The sign-in page does not call the backend

`web/templates/login.html` validates the form and redirects to `home.html`. `POST /api/auth/login`
exists and works — lockout, JWT, audit row and all.

- Call it when the API is reachable; keep the redirect for the mock-only prototype.
- A refused sign-in must show the message the server returns, not a generic one: the server's messages
  already carry the remaining attempts and the lockout time.

### 3.3 The copy suggestions

`docs/copy-review-zh.md` holds nine findings, three of them marked as worth doing first: the sidebar
group names, the four statistics subtitles, and the day prefix on the dashboard figures. Apply
whichever the lead approves; the document records what was already applied so nothing is done twice.

## 4. The bar every handover is held to

1. **The repository's own checks pass, run locally, and the output is pasted in the pull request.**
   All seven, not a summary of them.
2. **The thing is demonstrable.** A reviewer can perform the claim in the table above without asking
   the author how.
3. **The documents move with the code.** A route change updates the contract; a schema change updates
   the data model and `EXPECTED_COLUMNS`; anything a reader would now believe falsely is corrected in
   the same pull request.
4. **A decision that departs from a document gets an ADR.** Silent divergence is the one failure this
   project cannot afford four writers.
5. **No test is deleted or skipped to make the gate green.** If a test is wrong, the pull request says
   which and why.
6. **The pull request states what is not done.** "It works" is not a report; a known gap named in the
   description is worth more than a gap found in the defence.

## 5. Closing a handover

When an item is accepted, delete its section here and record the outcome in `PROGRESS.md` with the
date. A handover document that lists finished work stops being read, and the next person then misses
the one item that still matters.
