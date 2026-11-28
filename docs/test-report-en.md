# Test report

> Chinese version: [test-report-zh.md](test-report-zh.md). This file is the source of truth.

> Owner: @IkeaFyj · Revisit when: the suite is run again, or an acceptance case changes

## 1. What this report answers

Four questions, each answered below by a command rather than by a recollection: what the test plan
asks for, what was executed at one commit, what passed, and what is still skipped and why. The
defects the work found are in §6 with their severity and the check that fails if one returns.

The rule this report follows is the one `P4-11` states: a reader can reproduce the number instead of
trusting it. Every figure below is a count printed by a command in §7, taken at one commit, and no
figure is an estimate.

## 2. The plan

`docs/test-plan-en.md` §1 fixes the levels and §6 the severity classes; `docs/test-cases-en.md` holds
one case per acceptance item of SRS Table 8-1, with a verdict for each one. This table is the plan,
not a summary of the run:

| Level | What it covers | Owning document | How it runs |
|---|---|---|---|
| Unit | quality scoring, coordinate conversion, threshold logic, deduplication, statistics | `docs/test-plan-en.md` §1 | `pytest`, 74 files in `tests/` |
| API | envelope, error codes, permissions, pagination, the real routes | `docs/test-plan-en.md` §1 and `docs/api-contract-en.md` | `pytest` with the starlette test client |
| Document | the bilingual pairs, the plan's rules, the progress log, portable paths, the ADR index, acceptance coverage, defect evidence, the frontend budget | `docs/test-plan-en.md` §5 and `CONTRIBUTING.md` | ten `scripts/check-*.py`, all wired into CI |
| Node page suites | the pure page functions: canvas undo, CSV, statistics view, report preview, page failures, keyboard, place, operating time | `docs/test-plan-en.md` §1 and `docs/design-en.md` | `node tests/*.mjs`, invoked by pytest |
| Manual | the cases that need hardware, a bench, the deployment machine, a training run or the rehearsal rig | `docs/test-cases-en.md` §3 | a person, against a seeded database |

## 3. What was executed

### 3.1 The suite, once

| Field | Value |
|---|---|
| Commit | `3259dfb` — `chore(checks): every closed defect names the check that guards it (P3-35)` |
| Tree | a `git clone` of that commit plus the git-ignored `data/` directory (the development database and its recorded frames); no tracked file modified |
| Interpreter | the `aquavision` conda environment: CPython 3.11.18, pytest 9.2.0, torch 2.15.0+cpu |
| Command | `python -m pytest -v -p no:cacheprovider -o addopts=""` in the clone root |
| Collected | 563 tests in 74 files |
| Result | 563 passed, 0 failed, 0 skipped (116 warnings) |
| Duration | 432.21 s (7 min 12 s) |

`-v` is the only difference from a plain `pytest -q` on this tree: it prints one line per
test, which is what makes each case checkable by name in the log, and it does not change the counts.
The report lands after `f3e02e9` (the P4-06 documentation merge); `tests/` and `server/` are identical
between the two, so the same command on the merged tree returns the same counts.

The number is one completed run at the commit above, in a copy of the tree; the report does not merge
several runs into one number. It is the full suite, not a subset: the three cases that need torch and the
development database were executed here because both are on this machine, and the two that need the
conda environment were executed for the same reason. §3.2 states what CI's environment changes.

### 3.2 What CI runs, and what it skips

The `check` job installs `requirements-server.txt`, so it has no torch, no `ultralytics` and no
`aquavision` conda environment; it also has no `data/` directory, because that root is git-ignored.
Its steps are the repository's fixed checks, not a selection made for this report:

| Step | Command | What it needs |
|---|---|---|
| Dependencies | `python -m pip install -r requirements-server.txt` | nothing else; the pins decide the versions every other step runs |
| Style | `ruff check .` and `ruff format --check .` | the same file |
| Document checks | the ten `python scripts/check-*.py` — bilingual, language, progress, paths, ADR index, plan, mermaid, acceptance coverage, defect evidence, frontend budget | nothing beyond the server requirements |
| Commit messages | `python scripts/check-commit-messages.py --range origin/<base>..HEAD` | a full checkout (`fetch-depth: 0`); pull requests only |
| Tests | `pytest -q` | a GitHub-hosted Ubuntu image, Python 3.11, Node and `g++` already installed |
| Firmware | `pio run` in `firmware/main` | PlatformIO and the cached ESP32 toolchain, in a second job |

Six of the 563 cases cannot run under that environment. The skip is written in the test, and each one
names its own missing piece:

| Case(s) | Where the skip is in the code | What turns it into a run |
|---|---|---|
| `tests/test_detect_real.py` — 3 cases | the `real_client` fixture skips when `data/app.db` is missing or `import ultralytics` fails; every test in the file uses it | a development database with exactly one online `model_version` row, its weight file, and ultralytics with torch |
| `tests/test_demo_driver.py` — 2 cases | the module fixture skips when the `aquavision` conda environment is not on the machine | that environment, because the driver is run as a subprocess with its interpreter |
| `tests/test_delivered_weights.py` — 1 case | `test_the_development_database_online_version_points_at_the_delivered_weight` skips when `data/app.db` is missing; the other four cases read `git ls-files` and run anywhere | a development database carrying the delivered version |

So a CI run has 563 collected, 6 skipped and 557 executed; the six are derived from the conditions
above and the measured run is §3.1. **None of the six is skipped because it needs the server stack** —
the missing pieces are the development database, the torch/ultralytics training stack and the conda
environment. A green CI run is therefore not a run of the whole suite, and the skip lines in its log
are the only honest way to say which part did not run.

## 4. What passed

The 22 automated cases of `docs/test-cases-en.md` are the claims a test asserts; the run above
contains every test they name. The rest of the 49 cases are not passes and are not counted as such:

| State | Cases | Acceptance items | What it means |
|---|---|---|---|
| automated | 22 | 19 of 36 | a test asserts the claim; all 22 named tests are in the passing run |
| manual | 21 | 17 of 36 | a person, the bench, the deployment machine, a training run or the rig has to run it |
| uncovered | 6 | 5 of 36 | neither a test nor the feature exists |

The columns overlap on AC-07, which carries one manual case and one uncovered one and no automated
one, so the three rows do not add up to 36; every item is touched by at least one of them.

| Check | Command | Result |
|---|---|---|
| Python suite | `python -m pytest -v -p no:cacheprovider -o addopts=""` | 563 passed |
| Document checks | the ten `scripts/check-*.py` | ten checks, all exit 0 |
| Node page suites | `node tests/*.mjs` | 8 suites, all exit 0 |
| Acceptance coverage | `python scripts/check-ac-coverage.py` | all 36 items owned; every closed item names a test that exists |
| Demo driver and measurement | `tests/test_demo_driver.py` and `tests/test_measure_performance.py` | passed, on throwaway databases seeded by the tests themselves |

The coverage number is checked, not asserted: `scripts/check-ac-coverage.py` fails when an item has no
owning task, when a ticked claim names no test, and when a claim names a file that has moved. The
full-scale performance run — 100,000 assets and 5,000,000 objects — is not part of this suite; its
numbers are in `PROGRESS.md` (2026-11-28), and §6.1 records the defect it found.

## 5. What was skipped, and why

Every case `docs/test-cases-en.md` marks `manual` or `uncovered` is listed here, because those are
exactly the cases this report cannot pass. A manual case is not a pass, an uncovered case is not a
pass, and neither becomes one because the automated half is green. The 21 manual cases:

| Case | AC | Why a person must run it | Where the evidence will land |
|---|---|---|---|
| TC-AUTH-02 | AC-01 | reads the `password_hash` and `salt` columns of a seeded database; no test compares two hashes | the defence run sheet, with the query's output |
| TC-ACC-01 | AC-03 | disables an account, signs in and queries its history; no test calls the status route with `0` | the same sheet |
| TC-AUD-02 | AC-04 | walks the 45 operations of `docs/api-contract-en.md` to see that none deletes a log row | the contract walk, recorded with the acceptance checklist |
| TC-CAP-06 | AC-07 | needs a defocused frame from the camera; the score and the verdict are already tested | the bench capture figure, filed with the rehearsal record |
| TC-DET-01 | AC-10 | times three seconds with a stopwatch on the deployment machine | the deployment machine's run log, at `P4-04` |
| TC-DET-04 | AC-12 | runs two thresholds against the loaded model on one frame | the deployment machine's run log |
| TC-DET-05 | AC-12 | walks the contract for a route that could change a finished job's parameters | the contract walk |
| TC-STA-04 | AC-22 | compares a generated report's figures with the dashboard by eye; `tests/test_report_dashboard_agree.py` now asserts the equality, so the verdict can be revisited | the report page figure, and the case's re-adjudication |
| TC-MOD-03 | AC-25 | needs two real training runs for its reproducibility half | the experiment rows of `P4-02`, `P4-08` |
| TC-MOD-04 | AC-26 | adds a species whose code is absent from `labels.txt`; the class-order half is the torch-only case above | the dictionary run on the deployment machine, dated |
| TC-SYS-02 | AC-28 | fills a disk past the threshold; the queue half is tested | the monitoring panel figure at the rehearsal |
| TC-ALG-01 | AC-30 | the evaluation run on the frozen test set | the metric report of `P4-04` |
| TC-ALG-02 | AC-31 | the same evaluation read per class | the metric report of `P4-04` |
| TC-ALG-03 | AC-32 | baseline and improved runs sharing data, epochs and seed | the experiment rows of `P4-02`, `P4-04` |
| TC-ALG-04 | AC-33 | a hand count of one clip against the pipeline's de-duplicated count | the metric report of `P4-04` |
| TC-PERF-01 | AC-34 | 100 single-frame detections on the deployment machine, whose GPU this machine does not have | the measurement script's printed median and P90 on that machine |
| TC-PERF-02 | AC-34 | a list load at design capacity; the 11-28 CPU run is lower-bound evidence, not the acceptance run | the measurement run at the deployment machine, at `P4-04` |
| TC-DOC-01 | AC-35 | reads every row of Table A-1 and checks each requirement has a case | `docs/traceability-en.md` §5 and the acceptance checklist |
| TC-DOC-02 | AC-35 | walks the deliverable list in SRS §7.3 | the submission package of `P4-09` |
| TC-DEMO-01 | AC-36 | the live chain on the assembled rig, with no reload | the three rehearsals of `P4-07` |
| TC-DEMO-02 | AC-36 | the same rig, told as an iteration story | the three rehearsals of `P4-07` |

The six `uncovered` cases are not skipped runs: nothing exists to run. They are named here so the gap
is a number instead of a silence:

| Case | AC | Why nothing exists | What would close it |
|---|---|---|---|
| TC-CAP-04 | AC-06 | there is no schedule: no route, no table and no timer anywhere in `server/` | a schedule table and a timer, then the six-batch test of `P3-13` |
| TC-CAP-05 | AC-06 | the same missing schedule; nothing records a failed trigger | the same, with a failure row on the trigger |
| TC-CAP-07 | AC-07 | `is_retake` is written as 0 on every capture and no route sets it | a retake operation, which no route provides today |
| TC-CAP-09 | AC-09 | no cleanup operation exists; `retention_days` is stored and read by nothing that deletes a file | a cleanup route and a test that the reference is nulled |
| TC-STA-02 | AC-20 | no heat map and no site distribution in the pages or the contract | the figure and a dashboard-agreement test, at `P3-02` |
| TC-STA-03 | AC-21 | the trend is daily capture volume; no two periods are compared and no rate is computed | a period comparison and an arithmetic test |

## 6. Defects, with severity

`docs/test-plan-en.md` §6 fixes the classes: blocker is a system unusable, data loss or metrics
unmet; major is a core path blocked or a permission bypass; minor is cosmetic or non-critical. At
`3259dfb` the counts are **0 blocker, 0 major open, 15 major closed**, every closure naming the check
that fails if the defect returns. `scripts/check-defect-evidence.py` reads the same log as **21 defect
entries, 16 closed**, because several entries group more than one finding; the defects inside them are
what this section counts. Ten minor findings are closed and one cosmetic one remains open, inside the
five-open budget §6 allows.

### 6.1 Majors

| Severity | Defect | Fix | Regression check that fails on the old code |
|---|---|---|---|
| major | a needs-retake frame entered a detection batch; `create_batch` never filtered `quality_flag` | the selection filters `MediaAsset.quality_flag` | `tests/test_batch_quality.py` |
| major | a batch could not be built from the frames the operator ticked; `BatchBody` had no `frame_ids` and Pydantic dropped it | the body accepts `frame_ids`, all-or-nothing against the queue rules, refusing with `40002` | `tests/test_batch_selection.py` |
| major | the BLE rig link was never built when `AV_RIG_PORT` was empty, so the cable-free configuration started no link | the link is chosen by transport, not by port | `tests/test_rig_ble.py::test_the_application_starts_the_ble_link_with_no_port` |
| major | `request_id` was returned in every response but never logged, against the contract's §1 | a logging filter puts it on every record | `tests/test_request_id_logging.py` |
| major | every validation failure answered `40001`, so a present-but-invalid value was reported as missing | only a missing field is `40001`; every other schema error answers `40002` | `tests/test_api_skeleton.py::test_validation_errors_use_the_envelope` |
| major | the quality threshold had two truths: a hard-coded pass mark and the configurable parameter | `score_frame` takes the pass mark in force, and the live route reads it per frame | `tests/test_capture.py::test_the_pass_mark_is_an_argument_with_a_documented_default` |
| major | `frame_id` had two formats, a counter and a content-hash prefix, while three documents describe one | the router reuses `vision.capture.make_frame_id` | `tests/test_capture.py::test_frame_id_shape` |
| major | `protocol.cpp` reset its buffer on an over-long line and parsed the tail as a new command | a `discarding` flag drops the whole line | `manual: firmware/README.md` bench procedure — firmware has no host harness |
| major | ADR 16 described the retired drop-storm rule and treated `Err0` as a live face | ADR 17 supersedes it, because an accepted ADR is superseded rather than edited | `docs/adr/17-drop-storm-and-err0-retired.md` |
| major | four statistics routes counted the last seven days over three different windows, so one page printed two frame totals | one `_window` built from `recent_days` and `day_bounds` | `tests/test_stats_windows.py` |
| major | the report history paged by page 1's live `total`, counting one report twice and dropping another when one was created mid-scan | it follows short pages and dedupes by `report_id` | `tests/report_preview.mjs` |
| major | a history refresh requested while another scan ran was dropped, so a freshly generated report never appeared | the refresh is queued | `tests/report_preview.mjs` |
| major | the brief template the select offered was not implemented in `_render` | brief now carries the period, species and footer only | `tests/test_report_preview.py` |
| major | a clean clone could not create its database: `data/` is ignored and `init_db.py` did not create the parent directory | a file-backed SQLite DSN's parent is created in `engine_from_dsn`, never for PostgreSQL or `:memory:` | `tests/test_init_db.py` |
| major | `GET /api/hard-samples` took 357,241 ms per request at design capacity, walking five million `detect_object` rows with no covering index | `detect_object` declares `(hard_flag, review_status, frame_id, hard_reason)`, `ensure_indexes` upgrades an existing database, and the re-measured P90 is 143.8 ms | `tests/test_init_db.py` |

### 6.2 Minors

| Severity | Defect | Fix | Held by |
|---|---|---|---|
| minor, documentation | the fifth failed sign-in promised the remaining seconds; the lock message reports fifteen minutes | the case says what the server answers | `docs/test-cases-en.md`, TC-AUTH-01 |
| minor, documentation | a case said no endpoint deletes a `sys_log` row, while `POST /api/demo/reset` clears them by design | the case names the reset as the exception | `docs/test-cases-en.md`, TC-AUD-02 |
| minor | count axes printed fractions and `0.6000000000000001` | the axis formats whole counts | `tests/stats_view.mjs` |
| minor | a one-day trend rendered `NaN` | the trend handles a single day | `tests/stats_view.mjs` |
| minor | the statistics mock echoed the wrong `days` and `cn_name` | the mock follows the route | `tests/stats_view.mjs` |
| minor | report-history mock rows and the contract's Report example carried a UTC offset where the operating zone belongs | the operating zone's instant | `tests/report_preview.mjs` |
| minor | the history filters said "period start/end" for an overlap test | they name the overlap | `tests/report_preview.mjs` |
| minor | the empty archive claimed a filter was set | the empty state says the archive is empty | `tests/report_preview.mjs` |
| minor | statistics empty states named no next step | each names the next step | `tests/stats_view.mjs` |
| minor | TM-087, TM-088 and TM-096 described pages that no longer existed | the rows were rewritten against the current pages | `docs/traceability-en.md` |

### 6.3 Still open

| Severity | Open item | Effect |
|---|---|---|
| minor, cosmetic | the species card alone bypasses `loadInto`'s slow-server notice | on a slow server that one card shows no notice; no figure is wrong |

## 7. How to reproduce the numbers

The commands below are the whole recipe: a clone at the commit, the interpreter, and the commands
that printed each figure in this report. `python` means the `aquavision` environment; the repository
is the working directory.

```
# the suite: one run, the number in §3.1 and §4
python -m pytest -v -p no:cacheprovider -o addopts=""

# the page suites, also invoked by the suite
node tests/operating_time.mjs
node tests/page_failures.mjs
node tests/report_preview.mjs
node tests/review_history.mjs
node tests/review_keyboard.mjs
node tests/review_place.mjs
node tests/species_thresholds.mjs
node tests/stats_view.mjs

# the ten document checks CI runs on every push
python scripts/check-ac-coverage.py
python scripts/check-adr-index.py
python scripts/check-bilingual.py
python scripts/check-defect-evidence.py
python scripts/check-frontend-budget.py
python scripts/check-language.py
python scripts/check-mermaid.py
python scripts/check-paths.py
python scripts/check-plan.py
python scripts/check-progress.py

# the two scripts the suite exercises on small inputs; the full runs are the report's evidence
python scripts/demo.py
python scripts/measure_performance.py
python scripts/measure_performance.py --frames 45000 --objects 135000
python scripts/measure_performance.py --detect-only
```

| Number | Produced by | Taken at |
|---|---|---|
| 563 collected, 563 passed | `python -m pytest -v …` in a clone | `3259dfb` |
| 6 skip under CI's environment | the same suite after `pip install -r requirements-server.txt`, with no `data/` | `3259dfb` |
| 8 page suites, ten document checks | `node tests/*.mjs`, `scripts/check-*.py` | `3259dfb` |
| 357,241 ms then 143.8 ms for `/api/hard-samples` | `python scripts/measure_performance.py` | 2026-11-28, recorded in `PROGRESS.md` |

The interpreter matters as much as the command: `datetime.UTC` needs Python 3.11 or newer, and the
pins in `requirements-server.txt` are what CI verifies. A run in another environment can report a
different count, and the difference is a finding rather than a footnote.

## 8. What this report does not claim

- **No manual case passed.** None of the 21 has been run; the table in §5 is what a person still has
  to do, and `P4-07`'s rehearsals and the deployment machine's runs are where that changes.
- **No metric is accepted here.** AL-01 to AL-07 belong to `P4-02`, `P4-04` and the frozen test set;
  nothing in §4 is a metric value.
- **A green CI run is 6 skips, not 0.** The three real-inference cases, the two driver cases and the
  development-database case do not run there, and no skip is a server dependency.
- **The performance figures are a CPU lower bound.** AC-34's acceptance run is on the deployment
  machine's GPU; this machine has `torch.cuda.is_available(): False`.
- **The six uncovered cases are gaps.** They are the list of what a reviewer cannot check yet, and
  they are the first thing to revisit when the feature behind one of them lands.
- **The screenshots were not regenerated.** `P3-36` owns that, and no figure in this report depends
  on one.
