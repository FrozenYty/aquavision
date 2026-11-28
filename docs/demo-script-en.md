# Demo script — eight minutes, ten questions

> Chinese version: [demo-script-zh.md](demo-script-zh.md). This file is the source of truth.
> Owner: @IkeaFyj · Revisit when: a rehearsal changes a step, a page, a question or a slide

One judged run, eight minutes, one injected failure, ten answers. The clock in section 4 is cumulative: a rehearsal is timed against it, and a step that starts late is a defect in this script or in the system, never in the room. The plan that owns the three rehearsals is `PLAN.md` P4-07; the kit and the room are `docs/demo-kit-card-en.md`; the commands are `docs/runbook-en.md`; what may be claimed afterwards is `docs/test-cases-en.md`. This page adds no command and no kit item of its own — it only says what to say while those are used.

## 1. The one rule

Eight minutes is the bound and seven minutes fifty seconds is the target: the last ten seconds are reserved rather than spent. If the clock passes a step's mark by more than ten seconds, drop the sentence, not the screen: every page in section 4 is a page the panel came to see. The rehearsal that matters is the third one, the one where nothing is fixed between it and the run before (`PLAN.md` P4-07).

## 2. Before the room

| Clock | What happens | Evidence |
|---|---|---|
| −10:00 | The kit is ticked line by line with a pen, not from memory | `docs/demo-kit-card-en.md` §1–§3 |
| −8:00 | The offline database copy is restored and one frame opens | kit card §3; `docs/runbook-en.md` §5 |
| −7:00 | The camera answers at index 1 and the lens-side polariser is on | `python scripts/test_exposure.py --index 1` |
| −6:00 | The service is started from the repository root | `docs/runbook-en.md` §3 |
| −5:00 | Radio off, 100 % zoom, demo resolution, no console error | `PLAN.md` P4-19 |
| −4:00 | Every page in the run is opened once and signed in | `PLAN.md` P4-14 |
| −3:00 | Lamp on USB, one socket free, spare cable taped to the table | `docs/demo-kit-card-en.md` §2 |
| −1:00 | Phone away; this script and the card on the table; clock started | this page |

## 3. The minute budget

| Block | From | To | Length |
|---|---|---|---|
| Before the room | −10:00 | 0:00 | 10:00 |
| Opening | 0:00 | 0:50 | 0:50 |
| The chain | 0:50 | 6:20 | 5:30 |
| Failure injection | 6:20 | 6:50 | 0:30 |
| Closing | 6:50 | 7:50 | 1:00 |
| Reserved | 7:50 | 8:00 | 0:10 |

The in-room blocks add to 8:00 and the spoken run ends at 7:50; the ten reserved seconds are how the bound is met rather than approached. The five chain screens are the five `P4-14` drills (capture, result detail, review, statistics, reports); login and overview are the way in and the way out, not two more pages to drill.

## 4. The run, page by page

| At | Page | The click | What appears | The one sentence |
|---|---|---|---|---|
| 0:00 | Login (`login.html`), already open | Stand at the tank; click nothing | A signed-out form | "AquaVision turns one tank frame into a counted, corrected and downloaded inspection record in under a minute." |
| 0:50 | Login (`login.html`) | Type the demo account, submit | The overview loads with four metric cards | "One sign-in, and the system already knows today: frames, reviews waiting, rejection rate, the model online." |
| 1:10 | Overview (`home.html`) | Point at `#kpis`, then `#trend` | Four cards and a seven-day line | "These are the figures the report will carry, not a second set." |
| 1:35 | Capture (`capture.html`) | Select site A3, click `#btn-open` | A live frame with boxes, a quality ring at 86, per-class counts, latency | "Every frame is scored before it is counted: 86 is above 60, so this one enters the queue." |
| 2:50 | Result detail (`result-detail.html`) | Click the newest thumbnail in `#strip` | A large frame with boxes, the object list, class counts | "Detection wrote these boxes and this record, and the report counts exactly this record." |
| 3:30 | Review (`review.html`) | Click `#btn-review`; select the false box, click `#tool-delete`; click `#btn-add` and draw the missed one; set `#class-select`; click `#btn-submit` | The count change, a new version row, a toast | "A person corrects the model; the correction is a new version, not an overwrite, and the frame joins the hard-example pool." |
| 4:40 | Statistics (`stats.html`) | Open it from the sidebar; switch `#basis` from reviewed to raw | Four charts whose captions and totals move with the basis | "The basis is printed beside the number, so reviewed and raw can never be read as the same total." |
| 5:25 | Reports (`reports.html`) | Choose the week and the reviewed basis, click `#btn-generate`; when it is ready, click the download control in `#history` | A preview with figures, then a ready history row and a downloaded document | "The report is the dashboard's figures with the model version and the basis in the footer, stored and downloadable as Markdown." |
| 6:20 | Capture (`capture.html`) | Unplug the camera's USB cable | `#feed-mode` says the live connection is closed; the counts stop changing | "No new frames: the camera is unplugged, and the page says so instead of inventing a count." |
| 6:50 | Reports (`reports.html`) | Return to the report and point at its footer and history row | The same figures, the model version, the basis, the stored row | "That is the whole loop — capture, detect, correct, count, report — and the model's own loop, dataset to experiment to activation, is one page behind it." |

The five pages above are the run. The model iteration loop is not one of them and is not timed: if the panel asks, open `models.html` from the sidebar, where the experiments tab shows each run's delta against the baseline and the versions tab shows the activation, and `dataset-export.html` is the snapshot that started it. Slide 10 carries the same three steps.

## 5. The failure injection

One of the three rehearsals injects this, and it is rehearsed as written (`PLAN.md` P4-07). The camera is the honest failure because the page has a face for it; removing the online model version would not show anything until the process reloaded its detector, and a restart is not a thirty-second recovery. Do not improvise a different failure on the day.

Say this exact sentence at second 0, with the cable in your hand:

> No new frames: the camera is unplugged, and the page says so instead of inventing a count.

| Second | Action | What the room sees |
|---|---|---|
| 0 | Unplug the camera and say the sentence | `#feed-mode` changes to the closed message; the last frame stays |
| 5–12 | Replug the same cable; keep talking | Nothing yet |
| 12–18 | Click `#btn-close`, then `#btn-open` | A new capture session; the feed reconnects |
| 18–25 | Wait for the first frame | Boxes and the quality score return |
| 25–30 | Say the recovery sentence and stop moving | A recovered page, not a spinner |

The recovery sentence is: "Back in twenty-five seconds — the session restarted and the report never lost a row." If no frame has appeared by second 20, say instead: "The camera did not come back, so I am using the recorded-frame path this rehearsal covers", and use `conda run -n aquavision python scripts/demo.py`, whose output states whether the frame came from a camera or a recorded file (`PLAN.md`'s risk table; P4-12). The thirty-second bound is to a number on screen, not to a live camera.

## 6. The ten questions

### Q1 — Why BLE and not Wi-Fi?

The network at the site is a campus one, either WPA2-Enterprise or a browser portal, and the ESP32 can join neither: the first wants an 802.1X supplicant, an identity, a certificate and a clock, the second wants a browser. BLE asks for no network, no SSID and no password, and the serial build stays as the fallback, so a dead radio costs a cable rather than the demonstration. Evidence: `docs/adr/16-rig-cable-free-over-ble.md` §Context and §Decision; `docs/adr/17-drop-storm-and-err0-retired.md`; `docs/rig-transport-en.md`; `tests/test_rig_ble.py`, `tests/test_rig_link.py`.

### Q2 — Why Markdown and not Word or PDF?

The repository's documents and the generated inspection report are both Markdown; the Word, PDF and Excel formats in SRS §7.3 are conversion targets for what is handed to the supervisor, and nothing is converted unless it is asked for, so there is one kept copy instead of two that drift (SRS §7.3 and change record V1.6). The download route serves the stored Markdown itself, so the file a panel opens is the one whose figures were checked. Evidence: `docs/srs-en.md` §7.3; `docs/api-contract-en.md` `GET /api/reports/{report_code}/file`; `tests/test_reports_route.py`.

### Q3 — Why SQLite and PostgreSQL both?

SRS §2.5 names PostgreSQL 14 for the single Linux deployment server; SQLite is the zero-install default that lets a clone and CI run without a database service, and `DB_DSN` is the only switch between them (`docs/architecture-en.md` §7–§8). The tables are one SQLAlchemy declaration, so the schema is not written twice; the dialect cost is recorded where it bites — SQLite has no row locks, which is why a task's frames are assigned in `detect_task_item` (ADR 12). Evidence: `docs/architecture-en.md` §7–§8; `docs/runbook-en.md` §3 and §5; `docs/adr/12-detect-task-items.md`; `docs/test-plan-en.md` §4.

### Q4 — How is a frame's day decided?

Every calendar question — the frame id's day, its `frames/<site>/<YYYYMMDD>/` folder, a date filter, a statistics bucket, a report period, retention age — is answered in one configured zone, `AV_TIMEZONE`, defaulting to `Asia/Shanghai`; the database stores UTC (ADR 14). A capture at 03:00 Beijing is stored as the previous UTC day but belongs to its own local day, and one module, `server/app/timebase.py`, owns the arithmetic. The boundary bug this replaced is written in the ADR with the two queries that disagreed. Evidence: `docs/adr/14-the-time-basis.md`; `docs/runbook-en.md` §10; `tests/test_time_basis.py`, `tests/test_stats_windows.py`, `tests/test_report_dashboard_agree.py`.

### Q5 — What happens when the model cannot load?

The server still starts and every page that does not need inference still works. The detector is loaded once at start-up; when it is absent, the single-frame route answers `501` with the loader's own sentence and invents no box, and a batch task is marked failed with that sentence and zero objects. The demo driver prints `no model loaded` and reports detection as not measured rather than guessing. Evidence: `server/app/routers/detect.py`; `tests/test_api_skeleton.py::test_detection_without_weights_says_why`; `tests/test_worker.py::test_a_missing_model_uses_the_loaders_reason`; `scripts/demo.py`.

### Q6 — Why four classes?

Sea cucumber, sea urchin and scallop are the marine ranch's commercial species, and starfish is the scallop's main predator; all four are annotated in DUO, so the labels were reusable (SRS §3.5). The marine-debris class was removed in V1.3 because no public labels existed and in-house data could not support an independent metric for it. Evidence: `docs/srs-en.md` §2.6 and §3.5, change record V1.3; `scripts/prepare_dataset.py`; `tests/test_detect_real.py::test_the_loader_refuses_a_model_whose_class_order_disagrees`.

### Q7 — How is quality scored, and why 60?

Sharpness (Laplacian variance), brightness (mean) and colour cast (channel mean difference) are weighted 0.5, 0.3 and 0.2 into a 0–100 score; below the pass mark the frame is stored but not queued, and the capture page shows the three meters (SRS FR-M2-03, Table 3-8). Sixty is the SRS's policy number, not a tuned one: it is the default in `server/app/config.py`, exposed as `quality_threshold` in the range 0–100 and read when a frame is captured, so an operator change binds the next frame (`docs/runbook-en.md` §10). Evidence: `server/app/vision/quality.py`; `docs/srs-en.md` Table 3-8; `tests/test_capture.py::test_flat_frame_is_a_retake`; `tests/test_params_live.py::test_the_capture_verdict_uses_the_threshold_in_force`.

### Q8 — What is not built?

Say it plainly, with the row: the site heat map and ranking (AC-20), scheduled capture and its failed-run record (AC-06), retake marking (AC-07), and the same-frame baseline/improved comparison, whose route answers `501` (P4-10); the seven metrics and the large-scale GPU numbers are not recorded yet (P4-04), and the delivered MySQL script has not been executed (P4-13). Each is a row in `docs/acceptance-checklist-en.md` §4, and the compare route's honest answer is pinned by a test. Evidence: `docs/acceptance-checklist-en.md` §3–§4; `docs/traceability-en.md` TM-089; `PLAN.md` P3-13, P4-10 and P4-13; `docs/test-cases-en.md` TC-STA-02; `tests/test_api_skeleton.py::test_compare_answers_not_built`.

### Q9 — How are the 48 routes and the ADR set verified?

The contract lists 48 operations, and one test compares that table with the app's mounted operations in both directions, so a route that disappears and a route that appears unannounced both fail; `/api/health` also reports the mounted count and `contract_routes: 48` (`server/app/main.py`). The decision records are 17 today — ADR 17 superseded two rules in ADR 16 on 11-27, which is why an examiner may have read the count as 16 — and `scripts/check-adr-index.py` checks that every file is listed in both architecture documents, that every listed file exists, and that the `adr/01-NN` range in this index matches the latest. Evidence: `tests/test_api_skeleton.py::test_every_contract_route_is_mounted`; `tests/test_permission_matrix.py::test_the_matrix_covers_every_mounted_route`; `scripts/check-adr-index.py`; `docs/INDEX-en.md` map row `adr/01-17`.

### Q10 — What happens if the camera or rig dies on stage?

The same prepared move as section 5: the page states that the live link is closed, the cable goes back, the session is restarted, and if the camera does not re-enumerate the recorded-frame path `scripts/demo.py` prints the same slice from a recorded frame. The rig keeps a `rig-serial` build that needs a cable and no radio, so a misbehaving BLE link costs thirty seconds and a spare cable rather than the demonstration (ADR 16 and ADR 17). What is not true is automatic fallback: the capture page does not poll by itself after the socket dies, which is `P3-12`'s open limit, so the recovery is the presenter's two clicks, rehearsed. Evidence: `PLAN.md`'s P4 risk table and P3-12; `docs/runbook-en.md` §9; `scripts/demo.py`; `docs/adr/16-rig-cable-free-over-ble.md`; `tests/test_rig_link.py`.

## 7. Slide outline

| # | Slide | One-line message | Evidence or screenshot to show |
|---|---|---|---|
| 1 | Title | One tank frame becomes a reviewed, counted, downloadable report | `docs/images/traceability/p02-home.png` |
| 2 | The problem | Counting by eye cannot be audited, and a detector alone cannot be trusted | SRS §1.2 and §2.3 |
| 3 | The four classes | Three commercial species and their predator, already labelled in DUO | `docs/srs-en.md` §3.5 |
| 4 | Architecture | Browser, FastAPI, one worker, SQLite or PostgreSQL, USB camera, optional BLE rig | `docs/architecture-en.md` §2 diagram |
| 5 | Capture | A frame is scored before it is counted; below 60 it is stored and kept out | `docs/images/traceability/p03-capture.png`; demo 1:35 |
| 6 | Detection | The model draws the boxes; no model means 501, never an invented box | `p06-result-detail.png`; `test_detection_without_weights_says_why` |
| 7 | Review | A correction is a new version with a before/after log, not an overwrite | `p07-review.png`; `tests/test_review_versions.py` |
| 8 | Statistics | The basis is stated beside the number, so reviewed and raw cannot merge | `p10-stats.png`; `tests/test_stats_view.py` |
| 9 | Report | The document carries the dashboard's figures, the model version and the basis | `p11-reports.png`; `tests/test_report_dashboard_agree.py` |
| 10 | Model iteration | Snapshot, experiment table with deltas, activation recorded per job | `p12-models.png`; `tests/test_model_activation.py` |
| 11 | What is proven | Every acceptance item has a state and its evidence beside it | `docs/acceptance-checklist-en.md` §3 |
| 12 | What is not | Heat map, compare, schedule and GPU numbers are named, owned and disclosed | `docs/acceptance-checklist-en.md` §4 |

The screenshots are the tracked ones under `docs/images/traceability/`; the file names `p06`, `p07` and the rest are the same directory. A slide deck is not a second copy of the design document: each slide points at the page or the test, and the pages are the ones the run already opened.

## 8. What this script does not own

- The kit list, the room order and the arrival checks: `docs/demo-kit-card-en.md`.
- The commands and the recovery procedures: `docs/runbook-en.md`.
- What is proven and how a case is run: `docs/test-cases-en.md`.
- The three rehearsals, the eight-minute bound and the injected failure: `PLAN.md` P4-07.
- The five screens' drill, the page profile and the offline check: `PLAN.md` P4-14 and P4-19.

If a rehearsal finds a step wrong, fix this page the same day; a script corrected only after the defence is a story.
