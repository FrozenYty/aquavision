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
| P1 | Every layer has a minimal implementation | `uvicorn` starts, `/api/health` returns the envelope, 14 tables created, 13 pages open |
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
- [x] **P1-02** FastAPI skeleton: every contract route, envelope, error codes, JWT · @Gtechson ·
      closes when the queue consumer, the two detection routes and the reviewed statistics are real —
      that is `P2-05a`, `P2-05b` and `P2-05c`, and nothing else
      - delivered 11-11: the three checkpoints are in, so no route answers 501 by default any more —
        the two detection routes run the registered model, or say why it could not run
      - mounted by @FrozenYty on 11-06: envelope, guards, all 42 routes, 21 of them returning real data
      - **no route answers 501 by default any more** (11-11): `POST /api/detect/frames/{id}` runs the
        online model, and `POST /api/detect/batches` queues a task the worker consumes. It answers 501
        only when the database holds no frame yet, which is a state, not an unimplemented route. What
        remains of batch detection is `P3-01`'s acceptance - a 100-frame run, queryable progress, and a
        restart that resumes instead of losing the task - not the endpoint
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
- [x] **P1-06** Hardware arrival check · @FrozenYty · **narrowed 11-11**: the assembly half moved to
      `P3-17`, because `GATE P1` measures software (uvicorn, health, the tables, the pages) and a
      workbench task was holding it open. Nothing was dropped - the assembly is `P3-17` with the parts
      list intact
      - **camera.** `scripts/test_exposure.py --index 1` exits 0 on the arrival camera: 1080p, exposure
        lockable, 5 fps, 20 pinned frames inside a 0.5 % spread (11-10)
      - **panel and link.** The OLED at `0x3C` draws and answers, the serial command path works, and the
        five screens were driven over it without a button (11-10)
      - not verified here, and not claimed: the two LEDs, the button, the turbidity sensor, and the
        optical numbers - all of them are `P3-17`

- [x] **GATE P1** — `uvicorn app.main:app` starts on a clean machine, `/api/health` answers, 14 tables
      exist, 13 pages render · **passed 11-11**, all four criteria run rather than argued:
      `scripts/init_db.py` exits 0 on an empty database, a real `uvicorn` process answers
      `{"status": "ok", "database": "ok", "routes": 47, "contract_routes": 45}`, the database holds the
      fourteen tables by name, and all thirteen templates answer 200

### P2 — vertical slice

- [x] **P2-01** Capture → detection, single frame · @FrozenYty @Gtechson · done when one call returns
      boxes with `model_version` and `latency_ms`
      - delivered 11-11: a frame posted through the capture route went through
        `POST /api/detect/frames` on the online baseline, and the response carried 20 boxes,
        `model_version` and a measured `latency_ms`
- [x] **P2-02** Result persistence and query API · @Gtechson · done when boxes land in
      `detect_object` and querying by `frame_id` returns them
      - delivered 11-11: detection writes the rows, the query route returns them with their counts,
        and a re-run replaces the automatic set instead of duplicating it (the policy is in
        `docs/data-model-*.md` §3.5)
- [x] **P2-03** Capture and review pages on real data · @chemflowers · closes AC-08, AC-13 · done when no mock data is left
      on those two pages
- [x] **P2-04** Minimal review loop: delete, add, relabel · @chemflowers @Gtechson · closes AC-17 · done when the
      edit persists and the count updates without a page reload

      **Backend and model · @Gtechson**

- [x] **P2-05** Finish P1-02: detection, the queue consumer, reviewed statistics · @Gtechson · closes
      AC-05, AC-07, AC-10, AC-12 · three checkpoints, each its own pull request
      - delivered 11-11: 05a merged 11-10, 05b runs the online weights and writes the results, and
        05c checked the four `/api/stats/*` figures against those rows with a direct count on the
        same database
      - **P2-05a** the queue consumer, driven by synthetic `detect_task` rows — **no weights needed,
        start here**
        - delivered 11-10: `server/app/worker.py` claims queued tasks, advances `progress`, honours
          cancel, records a failure reason, and requeues stale rows on restart; the detector is
          injected, so this checkpoint never invents boxes
        - **P2-05b** the detection path — **unblocked 11-10**: `P2-06c` registered and activated
          the baseline weights, so the blocker that stood here is gone. It is the only part of this task
          that needs a trained model; the other two checkpoints run without one. Done when
          - `/api/detect/frames/{frame_id}` returns real boxes for whichever version is online, each with
            class, confidence and a normalised box, and the response carries `model_version` and a
            **measured** `latency_ms` - not an estimate, and the measurement's scope stated in a comment
          - the version is read from the `model_version` row, never from a path in the code; the
            delivered weight set is tracked under `models/`, which ADR 13 decided on 11-11 and
            **P2-06d** delivered on 11-12
          - a missing model, a missing torch or a corrupt weight answers a stated error code with a message
            an operator can act on - **never an empty box list dressed up as a result**
          - `torch` and `ultralytics` are imported lazily: the server starts and serves on
            `requirements-server.txt` alone, and only the detection route reports the missing dependency
          - tests: a stubbed detector for the response shape and every failure code, plus one real-inference
            smoke test that skips **with a written reason** when no weights are present
          - delivered 11-11: the route runs the online weights loaded at start-up, writes `detect_object`
            and the task statistics, and answers boxes with `model_version` and a measured `latency_ms`;
            the queue consumer was given the same detector and the task's own inference parameters
      - **P2-05c** `/api/stats/*` verified against rows written by 05b, figures equal to the dashboard
- [x] **P2-06** DUO dataset preparation and a first baseline run · @Gtechson · four checkpoints
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
      - **P2-06d** the delivered weight set, in the repository as ADR 13 decides, so that a clone can
        register it and run it
        - delivered 11-12: `models/v8n-E0-exploratory/` holds `best.pt`, `labels.txt` and
          `metrics.json`, all three tracked; `scripts/init_db.py` registers the delivered version on a
          fresh database and puts it online, and `scripts/register_model.py` stores the weight path
          relative to the repository root. `tests/test_delivered_weights.py` holds the layout and the
          class order without needing torch; `tests/test_detect_real.py` runs the delivered weights for
          real on this machine (3 passed, not skipped)
      - this is the **exploratory** run that gives the dashboard real numbers; the official E0–E4 stay
        at `P4-01..03` on the frozen dataset, and the difference is stated in the pull request
- [x] **P2-07** API contract tests for every route · @Gtechson · done when each P0 route has at least
      one test asserting status, envelope and payload shape, and the suite still runs without a
      database server

      **Frontend and interface · @chemflowers**

- [x] **P2-08** The capture page streams real frames · @Gtechson · delivered 11-11 (#154)
      - **the task was on the wrong lane.** Lane C had already built the client: `live.js` implements
        contract §7 in full and `tests/test_live_socket.py` holds it to the contract as text. The server
        had no WebSocket route at all, and that was the whole gap
      - `/ws/capture` answers §7: auth first, `auth_ok`, `4401` on a bad token, `4408` when no auth
        arrives within five seconds, `start`/`stop`, one binary JPEG immediately after its `frame`
        message, `detect` carrying `latency_ms` and `model_version`, `status` once a second. The
        adjacency is held by a send lock, not by timing
      - **inference runs in a threadpool**, one in flight at a time - awaited inline it would stall the
        other twelve pages for every connected tab
      - **no camera** (decided 11-11): the socket is served, the token validated, then closed with `1011`
        and a reason before `auth_ok`, and the client's own three-second timeout drives the fallback to
        REST polling. No synthetic frames. The close comes before `auth_ok` because after it the client
        only reports "closed" and never falls back
      - **known limit, moved to `P3-12`:** a socket that dies *after* `auth_ok` - a camera unplugged
        mid-demo - does not fall back at all
      - not decided here: live frames are not written to `media_asset` (`start` carries no site), there
        is no per-connection exposure lock or post-auth idle timeout, and the real detector over a live
        frame is not hardware-verified - no camera and no weights on this machine
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

- [ ] **P2-13** Rehearse the P2 gate end to end · @FrozenYty · done when someone who has
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

- [x] **P2-17** The PC side of the rig link · @FrozenYty · delivered 11-10; the architecture
      draws `MCU -. serial .-> CAP` and no task implements it · done when the server opens the port,
      keeps it alive with `CMD PING` every two seconds, turns an `EVT TRIGGER` into a capture, answers
      with `CMD RESULT`, and surfaces `EVT SCREEN`, `EVT TIMEOUT` and `EVT STRAY RESULT` in the log
      - the keepalive is not decoration: without it the rig declares a healthy idle system offline after
        ten seconds, and waiting for a button is what the rig does most of the time

- [x] **P2-18** One page name per page · @chemflowers · the SRS table and the traceability matrix
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

- [x] **P2-19** Two documents that disagree with the code, in other lanes · @Gtechson + @IkeaFyj ·
      found by the 11-10 audit, left alone because fixing another lane's document inside this diff is the
      habit the handover forbids · done when
      - **`docs/api-contract-en/zh.md` §5** documents `from=`/`to=` on `GET /api/frames`; the route reads
        `start`/`end`, and an undeclared query parameter is silently ignored, so a filter written from
        the contract returns unfiltered data (lane B)
      - **`docs/test-plan-en/zh.md`** names `scripts/evaluate.py` as the model-evaluation tool and
        describes `tests/fixtures/` as holding three JPEGs; neither exists - metrics come out of
        `train_baseline.py`, and the tests synthesise their frames (lane D)

- [ ] **P2-20** A machine that can load the delivered weights · @FrozenYty · unblocks `GATE P2`,
      `P2-13`, `P3-10` and `P4-10` · done when
      `python -m pytest tests/test_detect_real.py -o addopts="" -q` **runs and passes** on the
      demonstration machine instead of skipping, and a captured frame comes back with boxes and a class
      count through `POST /api/detect/frames`
      - the weights are delivered, tracked and registered, and this machine still refuses to load
        them, answering that the inference dependency is missing and naming the online version: the
        file half of the delivery is done and the **runtime half had no owner anywhere in this plan** -
        which is why the gate looked one step away for two days
      - two ways to close it, and the choice is a decision rather than a detail: a **dedicated
        environment** holding `ultralytics` and torch, which the server and the real-inference test
        point at, or installing the training stack into the environment that already runs the app. The
        dedicated one keeps `requirements-server.txt` light, which is ADR 11's argument
      - the three skipped tests in `tests/test_detect_real.py` are the only evidence that inference
        works at all; while they skip, `GATE P2` is a claim rather than a demonstration
- [ ] **GATE P2** — from a cold start, someone who has not seen the system completes the slice in
      three minutes, no restart, no manual database edit
      - **its prerequisites are part of the gate, because they are what makes it passable:** the
        delivered weights are tracked and registered (`P2-06d`, done), a machine that can load them
        (`P2-20`), and real targets in front of the camera. Two of those three were invisible when this
        line was written, so the gate read closer than it was

### P3 — breadth

- [x] **P3-01** Batch detection, the pool and progress · @Gtechson · closes AC-11 · done when a
      100-frame task completes, progress is queryable while it runs, and a restart mid-task resumes
      it rather than losing it
      - **delivered 11-11** (#145, #146). `tests/test_batch_acceptance.py` runs a 100-frame task to
        done, polls `GET /api/tasks/{id}` while it is in flight, and cuts a run short before restarting
        it through `Worker.start()`, after which the task resumes and finishes with one box per frame.
        The mid-flight assertion **was shown red** before it was trusted: with the worker's progress
        write frozen the readings sit at `('running', 0)` and the failure prints that series
      - **the pool defect found while verifying it is closed by ADR 12** (#146). A task is assigned its
        frames at creation and claims them by compare-and-swap, in the new `detect_task_item` table, so
        the work list is fixed rather than re-discovered. The measurement that exposed it - two tasks,
        `workers=2`, `asset_count=10` each - now reports `OVERLAP: 0` in `tests/test_batch_pool.py`,
        where a barrier makes the race deterministic instead of occasional. A frame the model finds
        nothing in finishes with `box_count=0` and is not picked up again by the next task
      - **not covered here:** the 100-frame run uses an injected stub detector, so it proves the queue
        and not the weights. The real-inference path is `tests/test_detect_real.py`, which skips without
        `ultralytics` on this workstation
- [ ] **P3-02** Statistics dashboard · @chemflowers · closes AC-19, AC-20, AC-21 · done when the four
      charts render from `/api/stats/*`, the basis switch changes both the figures and the caption,
      and the empty site shows an empty state rather than a blank chart
- [x] **P3-03** Model versions and activation · @Gtechson · closes AC-23, AC-24 · **delivered 11-12**:
      `tests/test_model_activation.py` calls `POST /api/models/{id}/activate` for the first time - two
      activations leave exactly one online row and the previous one at status 2; a version missing
      `map50` or `map50_95` is refused with `40901` and writes no audit row; an unknown id answers
      `40401`; the already-online version answers `40901`; observer and analyst answer `40301` while
      algo and admin pass. AC-24 is checked through the API: a task created after an activation records
      that version, and activating the earlier one again (the rollback) switches new tasks back to it.
      The single-frame route's response carries `model_version` and its task records
      `model_version_id` (a stub detector; the real weights are `tests/test_detect_real.py`)
      - with the route's exclusivity and metrics rules disabled the file reports
        `assert ['v8n-E0-candidate', 'v8n-E1-candidate'] == ['v8n-E1-candidate']` and `200 == 409`
      - the AC-23 conflict went to the user rather than being decided here: the SRS demanded a refused
        duplicate while `scripts/register_model.py` updates in place and `scripts/init_db.py`
        re-registers on every run. **Decided: keep idempotent registration**; AC-23 now states the
        outcome - a version name always has exactly one row and re-registering updates it (SRS V1.13)
- [ ] **P3-04** Account management · @Gtechson · closes AC-03, AC-04 · done when an account can be created,
      disabled and restored, a disabled account cannot sign in, and its history stays queryable
- [x] **P3-05** Review canvas: drag, zoom, add, delete · @chemflowers · closes AC-15, AC-16 ·
      delivered 11-11 (#137 zoom, #150 the version panel)
      - drag, select, draw and delete were already there; zoom (`#137`) changes the stage's real width
        inside a scrolling viewport, **never a CSS transform**, and `tests/test_review_canvas.py` runs the
        real `canvas.js` under Node, checking the coordinate conversion at two zoom levels
      - the version panel (`#150`) lists a frame's versions and restores one through the `P3-16` routes.
        Its decisions are pure functions in `web/static/js/versions.js`, run under Node by
        `tests/test_review_versions_page.py` rather than asserted by grepping the page
      - **a refused rollback returns before the two lines that write to the canvas**, which is asserted
        as an ordering: `409` is a normal outcome, shows the server's rule sentence, keeps the selection,
        and says the canvas was not touched
      - the panel's state-by-event matrix (idle / open / selected / confirming / restoring against open /
        select / confirm / cancel / Esc / a second click while restoring) is complete, every cell filled
        or marked ignored - it is in the #150 description
- [x] **P3-06** Demo mode · @FrozenYty · **supports** AC-36 - the live chain that AC-36 actually
      describes is closed by `P2-13` and the gate, not by this task · delivered 11-11 (#152)
      - **one action resets the data.** `POST /api/demo/reset` empties the ten business tables and the
        stored frame files, and answers with a per-table count, the number of files actually unlinked and
        the model still online - a boolean would make the operator trust the reset instead of seeing it.
        The page's control is on P-13 behind a typed `RESET`, and states what it deletes **and what it
        keeps** before it is pressed
      - **the endpoint cannot fire by accident.** Admin only, gated on `AV_DEMO_ENABLED` which defaults
        off, and when it is off the answer is **404, not 403** - a data-wiping route should not tell a
        prober it exists. The gate runs before the role check
      - **the rehearsal state is the kept state**: `model_version` stays online, `species_dict` stays so
        the model's class order can be validated, `sys_user` stays because deleting the caller's own
        account mid-request is a lockout. Tests assert the business tables empty **and** those four
        survive, and that a reset deployment still logs in afterwards
      - **"hides debug output" is satisfied by leaving no trace of the previous run**, and that is the
        reading this task was closed on: every count is zero after a reset, so no page shows a leftover
        figure, and the prototype notice appears only under `?mock=1`, which a rehearsal against the
        server never uses. If a future surface starts printing developer detail on a page, this bullet is
        where it should be caught
      - **prototype-mode parity is restored.** `?mock=1` answers both review-version routes from the
        tab's own recorded reviews - an empty list for a tab that reviewed nothing, never fixture entries
        presented as history - and answers the reset against its own store. That work exposed three mock
        id generators that assumed a non-empty list
      - **not covered:** the reset does not stop a running worker, so it assumes a rehearsal starts from a
        still system. Resetting mid-batch can leave the worker writing rows just deleted; `P3-12` is where
        that belongs if it ever bites
- [ ] **P3-07** Report generation and history · @chemflowers · closes AC-22 · done when a report is
      generated as Markdown from the same queries the dashboard uses, its figures equal the dashboard,
      and the footer carries the model version and the basis — **not Word or PDF; SRS V1.6 settled that**
- [ ] **P3-08** Retention cleanup and reference nulling · @Gtechson · closes AC-09 · done when the
      cleanup job removes intermediate files older than the retention period, nulls the references,
      never touches originals by default, and reports what it deleted
- [ ] **P3-09** Parameters, monitoring and messages · @Gtechson · closes AC-28, AC-29 · done when the
      queue and disk levels are visible, a repeated failure message is not duplicated, and a parameter
      change is still audited with its before and after values - the *effect* of that change is
      `P3-19`, delivered 11-12, so this task no longer owns it
- [ ] **P3-10** Performance budget, measured · @FrozenYty · closes AC-34 · done when a committed script
      measures single-frame latency and the list endpoints' P90 against a database at design capacity,
      and the numbers are pasted into the pull request — a claim is not a measurement
- [x] **P3-11** The permission matrix, negatively tested · @Gtechson · closes AC-02 · **delivered
      11-12**: `tests/test_permission_matrix.py` holds a (method, path, allowed roles) table derived
      from SRS Table 2-1, FR-M1-02 and the contract's own sentences, and exercises all four roles
      against every mounted route in both directions - a refused pair answers 403 with `40301`, an
      allowed one never answers 401 or 403, so an implementation that refuses everything fails. Every
      refusal must write exactly one `forbidden` row, and a route mounted without a row in the table
      fails the test rather than escaping to the next audit
      - the table collided with the code once: `DELETE /api/hard-samples/{frame_id}` had no guard, so
        an observer could take a frame out of the sample library. Table 2-1 gives the library to the
        analyst and the engineer and FR-M4-03 gathers it "for the algorithm staff", so the route now
        carries `SAMPLE_ROLES`; without it the matrix reports `observer was not refused DELETE
        /api/hard-samples/missing: 404`
      - the other direction was shown as well: making `GET /api/frames` admin-only makes the same
        test report `observer/analyst/algo was refused GET /api/frames`
- [ ] **P3-12** Failure and recovery · @FrozenYty · covers the states between AC items · done when a
      killed worker, an unreachable database and a full disk each produce a message the operator can
      act on, instead of a blank page or a stuck spinner
      - **inherited from `P2-08` (11-11):** the capture socket's fallback to REST polling is driven by
        the client's three-second timeout, so a socket that dies **after** `auth_ok` - a camera unplugged
        mid-demo - surfaces as "closed" and the page stops updating instead of polling. Fixing it needs
        `live.js` (lane C), so it belongs here rather than in the websocket task
- [ ] **P3-13** Scheduled capture · @FrozenYty · closes AC-06 · the capture schedule belongs with the
      capture module and needs no model and no training · there is no timer anywhere in the system
      yet: done when a schedule of N captures every M minutes produces exactly N batches, a run whose
      device is unavailable is marked failed with a reason, and the schedule survives a restart
- [x] **P3-14** Result export · @chemflowers · closes AC-14 · done when a result set exports as CSV with
      one row per box, the row count equals the page's count, and Chinese class names open correctly in
      Excel — the encoding is the part that usually breaks
      - escaping is tested as a pure function: a class name or note containing a comma, a double quote and
        a newline each survive a round trip
      - an empty result says so **instead of downloading an empty file**
      - the filename carries the frame id and a timestamp, so two exports are distinguishable
- [ ] **P3-15** Species dictionary and per-class thresholds · @chemflowers · closes AC-26 · done when the
      four classes and their thresholds can be viewed and edited on P-12, a threshold change applies to
      new jobs and not to finished ones, and a class code that disagrees with `labels.txt` is refused
      - **spans two lanes as written.** The page is lane C's; applying a threshold to new jobs and
        refusing a class code that disagrees with `labels.txt` are both in `server/`, which is lane B's
        and read-only for C. Agree the split with lane B before starting, rather than in review
      - the data already supports it: `species_dict.conf_thr` exists and **nothing reads it** -
        `detect.py` passes the caller's `conf_thr` straight to the model
      - **the server half is smaller than it was when this was written:** `P3-19` delivered
        `server/app/params.py`, so a per-class threshold has a place to be read from rather than needing
        a new mechanism, and refusing a class code that disagrees with `labels.txt` is one comparison
        against the delivered file

- [x] **P3-16** Review versions and rollback · @Gtechson · **unblocks `P3-05`** · delivered 11-11 (#148)
      - `GET /api/review/frames/{frame_id}/versions` lists each entry newest first with its action, time,
        author, and the box count before and after, read from the JSON `sys_log` recorded rather than
        recomputed from the boxes that survive now. No storage was added
      - `POST /api/review/frames/{frame_id}/rollback` restores a chosen entry's `after_value` as a **new**
        version and writes its own history row, so the rollback is in the record. Boxes leaving the set
        are marked `review_status = 3`, never deleted (AC-15). A rollback to the current set is refused
        as a no-op so the timeline is not filled with empty entries
      - the rule that turns a box list into rows was **extracted from `submit` into one shared helper**
        rather than copied, so the two paths cannot drift
      - nine tests in `tests/test_review_versions.py`, asserting the restored **classes and coordinates**
        rather than a count; the contract table, both contract documents and `/api/health`'s
        `contract_routes` moved together, 42 to 44, and that field is now tied to the table by a test
- [ ] **P3-17** Rig assembly and its optical numbers · @FrozenYty · split out of `P1-06` on 11-11 ·
      the parts still owed: resistors for the two LEDs, the button (not arrived), the turbidity sensor's
      level shifter, and **5 V for the sensor**. A 12 V adapter with a buck module was procured 11-11
      and replaces the earlier dead end - the board has no 5 V output - but it is untested until the
      bench session
      - wiring as agreed: 12 V adapter -> 5 V module -> sensor VCC, **common ground with the board**;
        the BSS138 level shifter runs VCCA 3V3, VCCB 5 V, A0 to B0 on GPIO8/SDA, A1 to B1 on GPIO9/SCL
      - done when `python scripts/test_rig.py` reports the three numbers the design fixed - left/right
        brightness ratio >= 0.7, a 5 cm target >= 45 px at 640 input, no flicker - and `CMD SCAN` shows
        `EVT I2C 49` with the sensor powered
      - **`P4-07`'s rehearsals cannot start before this is done**, and neither can the optical half of
        `P1-06`'s original acceptance
- [x] **P3-18** The time basis: one zone decides every calendar question · @Gtechson · with **ADR 14** ·
      closes the date half of AC-08 · **delivered 11-12**: `server/app/timebase.py` owns the arithmetic,
      `AV_TIMEZONE` defaults to Asia/Shanghai, and `tests/test_time_basis.py` pins a local 00:00:00 and
      23:59:59 inside their own day, the next day's 00:00 outside it, the exact offset on every emitted
      timestamp, and the same frames landing differently under `AV_TIMEZONE=UTC` - proving the setting is
      read rather than `+8` baked in
      - today the filter builds a naive date and compares it to a naive-UTC column, so an operator's
        03:00 capture on 2 November is absent from its own day. The contract said "the server time zone";
        nothing in the process knew a zone
      - the work is the module ADR 14 names, not a patch at the filter: the statistics buckets, the
        report periods and the retention cutoff all use it, or they will disagree within the month
- [x] **P3-19** Parameters take effect at the next decision point · @Gtechson · with **ADR 15** · closes
      AC-27 · **delivered 11-12**: `server/app/params.py` is the one accessor - the stored value, the
      configured default when the row is absent, a stated TTL, and a declared range per parameter, which
      the page and the accessor both read. The worker decides at each claim how many tasks may run: with
      the check removed `tests/test_params_live.py` reports
      `AssertionError: 2 tasks ran at once under a limit of 1`, and with it in place the same test sees
      one at a time while the tasks created before the change finish untouched. `quality_threshold` is
      read when a frame is judged, `camera_index` when a device is opened, `detect_interval_ms` when the
      live feed starts, and `/api/monitor` reports the limit in force rather than the start-up one. An
      out-of-range value is refused with the project envelope (`40001`) and no row is written
      - `sys_param` was written, audited and read by nobody; the consumers read `Settings` cached at
        process start, so the page edited a copy nobody consults. The page's own toast already promised
        that a change binds new jobs - until this delivery that sentence was false
      - a concurrency of zero genuinely stops detection, so the range is enforced on write **and**
        ignored on read, and `retention_days` has no consumer until `P3-08` reads it
- [ ] **P3-20** Two gaps from the audit with no other home · @Gtechson
      - **capture endpoints are not restricted to the local process**, though FR-M1-02 says they "accept
        only the local process and are never exposed"; they are ordinary routes behind a JWT, so any
        signed-in remote client may post frames
      - **a password change does not invalidate issued tokens**, though NFR-S-05 says it does; the tokens
        are stateless and `sys_user` has no column to revoke them, so it needs a `token_epoch` or
        `pwd_changed_at` checked by `get_current_user` - a schema change - or the requirement is reduced to
        what the design does
- [ ] **P3-21** The interface reads time the way ADR 14 says · @chemflowers · follows **ADR 14** · done
      when no page re-derives a date from the browser's zone, and a report period is not a hardcoded offset
      - `web/static/js/ui.js`'s formatter rebuilds every timestamp in the **browser's** zone, so a reviewer
        outside UTC+8 reads one date on the dashboard and another in a filtered list, each correct by its
        own rule. Eleven pages use it
      - `home.html` builds its trend axis from the browser's `new Date()` instead of the `date` the
        statistics route already returns in the operating zone, so the chart can be a day off across a
        boundary
      - `reports.html` hardcodes `T00:00:00+08:00` and `T23:59:59+08:00`; a deployment that changes
        `AV_TIMEZONE` then asks for a period the server interprets in a different zone
- [ ] **P3-22** A frame's identity keeps a different day from the operator's · @FrozenYty
      - `_frame_id` and the `frames/<site>/<day>/` directory are derived from UTC, so under the default
        zone a capture between 00:00 and 08:00 local carries **yesterday** in its id and its folder: the
        filter says 2 November, the frame id says 1 November
      - ADR 14 deliberately left storage and the layout alone, so this is its own change: either derive
        them in the operating zone (and let existing ids keep their basis) or write the basis into the id
        so the two can never be confused
- [ ] **GATE P3** — all 36 acceptance items demonstrated live, one after another, no manual database
      edits in between, and every item traceable to the task that closed it

### P4 — close

- [ ] **P4-01** Dataset freeze, then baseline E0 · @Gtechson · closes AC-30 · done when the snapshot is
      frozen **before** the first official run — name, split, seed and manifest written down — and E0
      is recorded with every metric column filled
      - freezing first is the point: a baseline trained on a moving dataset cannot be compared to
        anything, and every later number inherits the mistake
      - an **exploratory** baseline on a DUO subset is already delivered and is the version tracked in
        the repository (`models/v8n-E0-exploratory/`). It unblocked the slice; it is **not** the official
        E0, and the frozen-dataset run below is what the metrics table reports. The name stays as it is so
        nothing already pointing at it has to move
- [ ] **P4-02** The three improvements · @Gtechson · closes AC-32 · done when each is isolated on top of
      the previous one, each has a row in the experiment table, and each reports its delta against E0
      - E1 underwater colour correction
      - E2 EMA attention
      - E3 WIoU v3 loss
      - **one experiment per pull request**: E1, then E2 on top of it, then E3 - three runs and three PRs
        rather than one batch at the end, so a failure in E2 does not hold E1's record
- [ ] **P4-03** Ablation and tank fine-tuning · @Gtechson · closes AC-32 · done when the ablation table
      shows each improvement's own contribution, and the fine-tune on tank images is evaluated against
      the same test set
- [ ] **P4-04** Metric acceptance, per class · @Gtechson · closes AC-30, AC-31, AC-33 · done
      when all **seven** metrics of SRS Table 6-1 (AL-01..AL-07) are recorded — the count was nine
      before V1.3 deleted AL-08 and AL-09 — and any miss is explained in writing
      - it is a reporting task and can start as soon as E0 is recorded: the table fills run by run, so it
        does not sit on the critical path at the end. The acceptance check is §5.3's - someone other than
        the owner reads it
- [ ] **P4-05** Defect closure · @FrozenYty · done when every defect has a recorded severity, a fix and
      a regression check, and blocker and major counts are zero — "no defects" is not a number
      - **the owner is one person**, because §5.1 says so and "all" is not an owner. Each lane reports
        its own defects into the table; this task keeps the counts and the regression checks
- [ ] **P4-06** Acceptance checklist, demo script, slides · @IkeaFyj · done when every acceptance item
      is ticked with the evidence beside it, and the demo runs end to end on paper without a question
      left unanswerable
- [ ] **P4-07** Three rehearsals · @FrozenYty · done when each run finishes under eight minutes with no
      dead air, and the third run needs no fix made between it and the previous one
- [ ] **P4-08** Reproducibility · @Gtechson · closes AC-25 · done when the same configuration run twice
      differs by less than 1 % on every metric, and both runs are in the table — a single run proves
      nothing about the next one
      - the second run reuses E0's recorded configuration, so it is one repeat rather than a new
        experiment: a seed change with everything else pinned is what this measures
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
