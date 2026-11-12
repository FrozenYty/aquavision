## 2026-11-12

- **A specification is allowed to describe behaviour that is not built; it is not allowed to contradict
  itself.** The audit had reported several "SRS says X, code does Y" items, and most of them are not
  defects - an SRS states requirements, and a requirement whose implementation is still open is what an
  open task looks like. What is a defect is the pair of places where **the SRS contradicts another
  document or the code about a decision already taken**: FR-M4-02 said only analysts and algorithm
  engineers may review while the contract and the code both allow administrators, so the SRS was
  corrected to the decision. The rest were moved into a task rather than edited away.
- **`P3-18` now carries the four gaps that had no home**, each with the evidence and the choice it needs:
  the date filters are a UTC day while the contract says the server's day; `PATCH /api/params` writes
  rows nothing reads, so AC-27's "a new concurrency limit constrains new jobs" does not hold; the capture
  endpoints are not restricted to the local process as FR-M1-02 claims; and a password change does not
  invalidate tokens as NFR-S-05 requires. **None of the four was quietly weakened to match the code** -
  a security requirement is not mine to downgrade.
- **A refusal now leaves a record.** FR-M1-02 and AC-02 require the attempt to be logged and the guard
  logged nothing; there were fourteen `SysLog` sites in the server and not one on a refusal. The guard
  writes the row and **commits before raising**, because `get_db` closes the session without committing
  and the row would vanish with the exception. The test reads the row through a fresh session after the
  response, so only a real commit satisfies it - reading it in the request's own session would have
  passed against the broken shape.
- **Failed authentication is deliberately still not logged**, and that is a decision rather than an
  omission: an unauthenticated request never reaches the role matrix, it has no `user_id` to record, and
  logging every malformed `Authorization` header would turn `sys_log` into an unbounded write sink
  reachable without credentials. If the team wants that audited it needs its own rule, not a fold-in.
- **The handover stopped describing finished work as homework.** Nine sections still instructed the
  reader to add a test, rename a page or answer a socket question for tasks that were ticked and tested -
  the document's own rule is that accepted items are deleted, but its headings had stayed. Each was
  turned into a statement of what exists, with the `PLAN.md` line or test that proves it, and the English
  side gained the thirteen-name table it had been missing. What is genuinely open stays open: `P2-13`,
  `P3-17`, the weight file, and the client-side socket fallback recorded under `P3-12`.

- **`P3-12` closed by making three failures say what the operator should do**, and the first thing it
  found was a lie in the *success* path: when OpenCV's `imwrite` returns `False` - it does not raise -
  the request answered `code: 0` and wrote a `media_asset` row pointing at an image that was never
  stored. A phantom record, not a lost frame. It is now a refusal that names the data root, and the
  partial file is removed. An unreachable database answers the project envelope naming `DB_DSN`
  instead of a bare 500 that looked like a code bug; a full or unwritable disk keeps its cause
  instead of collapsing into a generic error; and `/api/monitor` reports whether the detection worker
  is alive, so a stopped worker no longer looks like a task that is merely slow. All three reproduced
  without hardware: an engine aimed at a database path sitting inside a regular file, `ENOSPC` and
  `EACCES` injected at the write, and a `Worker` stopped with tasks left queued.

- **The audit's most expensive lesson became a check.** `check-bilingual.py` compared heading levels and
  nothing else - its own docstring said so - which is why every real defect of the 11-11 audit survived:
  a table that lost four entities, a version of Table 2-3 missing two rows, six NFR tables whose header
  row was lost in translation. They all had matching headings. The script now also compares the **shape of
  every section**: each table's row and column counts, and how many fenced code blocks it holds. Words are
  still not compared, because a translation differs by design and a check that quarrelled with prose would
  be switched off within a week.
- **It found a live defect on its first run**, and one nobody had fixed: the Chinese firmware README's
  protocol table was missing the `CMD SCAN` row the English has, and the firmware implements it. Heading
  parity had hidden it for as long as the row had been missing.
- **Proven against the past, not just the present.** Replayed against the tree as it stood before the
  audit fixes, the new comparison reports seven differences: the SRS equipment table (nine rows against
  eleven) and all six NFR tables, each one line short on the Chinese side - exactly the defects the
  auditors had found. A check is only worth its runtime if it fails on the defect it was written for.
- **The false positive is guarded too**: a pair with the same structure and completely different wording
  must report nothing, and there is a test for that, because the failure mode of a structural check is
  not missing a defect - it is crying wolf until someone turns it off.
- **"Which day is it" now has one answer, and it is a decision rather than an arithmetic patch.** The
  frame filter compared a naive date to a naive-UTC column, so an operator's 03:00 capture on 2 November
  was absent from its own day and appeared under 1 November. The tempting fix - add eight hours where the
  filter is - would have left statistics, reports, retention and the interface each computing a calendar
  boundary their own way, which is how the defect arose. **ADR 14** fixes the shape instead: storage stays
  naive UTC, one configured zone (`AV_TIMEZONE`, Asia/Shanghai by default) answers every calendar question,
  every emitted timestamp carries its offset, and `server/app/timebase.py` is the only place the conversion
  happens. It rejected the process's local zone for the reason this repository already treats
  machine-dependence as a defect.
- **The boundary is now a test, not an intention.** A capture at local 00:00:00 and one at 23:59:59 are
  inside `start=end=<that date>`; local 00:00:00 the next day is not; and the same three frames land in
  different days under `AV_TIMEZONE=UTC`, which is what proves the setting is read rather than `+8` coded
  into a module. Against the old code the test failed on exactly the reported frames.
- **ADR 14 says the emitted timestamps match the contract's example, and the first implementation did
  not** - it truncated to whole seconds while that example carries `.418`. At five frames a second,
  same-second frames then render as the same moment and the operator cannot tell which came first. Caught
  on review, fixed to milliseconds, and the three exact-string assertions moved with it.
- **What the change deliberately did not do, so it is tracked instead of forgotten.** The frame id and the
  `frames/<site>/<day>/` folder still derive their day from UTC, so a small-hours capture is filed under
  yesterday (`P3-22`); and the interface still reformats timestamps in the browser's zone while
  `reports.html` hardcodes `+08:00` (`P3-21`). Both are recorded with their evidence rather than folded in.
- **ADR 15 records the second decision but implements nothing yet**: a parameter the operator can change
  takes effect at the next decision point, through one accessor with a short TTL and a declared range.
  `sys_param` is written, audited and read by nobody today, so `AC-27` is currently false - and that is now
  a task (`P3-19`) with a decision behind it rather than a bug report.
- **The delivered weights are in the repository, and a clean clone registers them by itself.** The
  exploratory baseline's three artefacts now live in `models/v8n-E0-exploratory/` - `best.pt`,
  `labels.txt`, `metrics.json`, tracked - which is the gap ADR 13 was written to close: `models/` was
  empty, so whoever cloned the repository got the code and no model, and `P2-13` and `GATE P2` were
  waiting on a file. `scripts/init_db.py` now registers every delivered version it finds and puts the
  only one online on a database that has none, so an install carrying nothing but this repository and
  `requirements-server.txt` reaches detection without a manual step. The restraint that keeps a script
  from doing damage: a re-run never overrides an operator's activation, and a second delivered version
  stays a candidate.
- **A registration that names this machine is not a registration.** `model_version.weight_path` is
  written relative to the repository root whenever the file sits inside it; the online row on this
  machine had carried a drive-letter path since 11-10 and would have meant nothing on anyone else's
  clone.
  `tests/test_delivered_weights.py` checks the three-file layout, the class order against
  `species_dict`, and that the stored path resolves to a tracked file - without torch, so it runs on
  every machine and in CI. It was shown red before it was trusted: with `models/` still empty the
  layout and clean-database tests failed, and the development-database test failed on that absolute
  path. `tests/test_detect_real.py`, which had been three skips on this workstation, now runs the
  delivered weights for real: **3 passed, none skipped**.
- **A parameter nobody read now has an effect, and the value in force is the operator's.** `sys_param`
  was written, audited and consulted by nobody: every consumer used `Settings`, fixed at process start,
  so the parameters page edited a copy nothing read and `AC-27` was false while the whole suite passed.
  `server/app/params.py` is now the one accessor - the stored value, the configured default when the row
  is absent, a stated two-second TTL, and a range per parameter - and the consumers call it where the
  decision is made: the worker at each claim, the capture route when it judges a frame, the camera when
  it is opened, the live feed when a session starts. The limit is a claim gate rather than a pool size,
  so lowering it stops new work at once and raising it starts more threads without a restart. The pool
  never shrinks: an idle thread costs nothing, and shrinking would have to interrupt work in progress.
- **The range is part of the decision, not a later refinement.** A concurrency of zero does not slow
  detection down, it stops it, so one declaration is read by the page - refused with the project
  envelope `40001`, and no row written - and by the accessor, which logs a stored value outside its
  range and uses the configured default instead of obeying it. `retention_days` keeps no consumer until
  `P3-08` reads it, and the pull request says so rather than calling the parameter live. Shown red
  before green: with the claim check removed the acceptance test reports "2 tasks ran at once under a
  limit of 1", and every other test in the file fails against the old behaviour - the capture verdict
  taken from the start-up setting, the range accepted silently, the cache never expiring.
- **The permission matrix is now a table in a test, and the first thing it caught was a missing guard.**
  `tests/test_permission_matrix.py` derives (method, path, allowed roles) from SRS Table 2-1's four
  role profiles, FR-M1-02's "algorithm and configuration endpoints are restricted to the engineer and
  administrator", and the three restrictions the contract states in words; then it points that table at
  the running application for all four roles. Both directions are asserted - a refused pair must answer
  403 with `40301`, an allowed one must answer anything but 401 or 403 - because a guard that refuses
  everything would pass the negative half alone. `DELETE /api/hard-samples/{frame_id}` had no guard at
  all: an observer could take a frame out of the sample library, which Table 2-1 gives to the analyst
  and the engineer. It now carries `SAMPLE_ROLES`, and the matrix reports that as
  `observer was not refused DELETE /api/hard-samples/missing: 404` when the guard is removed again.
- **The expectations were written before the guards were read, and that is the whole method.** A table
  generated from `require(...)` would only prove the code equals itself; this one was written from the
  documents and then collided with the code. Two drift alarms come with it: every route the application
  mounts must have a row in the table (a new endpoint without one fails the test), and every refusal
  must leave exactly one `forbidden` row in `sys_log`, which is FR-M1-02's processing step and not a
  substitute for the permission assertion. The reverse direction was shown too - guarding
  `GET /api/frames` to admin-only makes the matrix name the three roles it refuses.
- **The activation route got its first test, and it was an implementation nobody had called.**
  `POST /api/models/{id}/activate` has carried the `404`/`409`/exclusivity rules since 11-10 and no
  test ever touched it - `test_register_model.py` covers the script that writes rows, not the route
  that changes which row is live. `tests/test_model_activation.py` now activates through the API and
  holds the three sentences `PLAN.md` asks for: exactly one online row across two activations and a
  rollback, a version missing `map50` or `map50_95` refused with `40901` and no audit row, and every
  task carrying the version that was online when it was created - the last one asserted without torch,
  because a batch task reads the online row at creation. Shown red first: with the route's exclusivity
  and metrics rules switched off, the file reports two online rows (`assert ['v8n-E0-candidate',
  'v8n-E1-candidate'] == ['v8n-E1-candidate']`) and a metrics-less version answering `200` where `409`
  was expected.
- **AC-23 asked for something the system never did, and the user decided which half to change.** The
  SRS said "duplicate names refused"; `scripts/register_model.py` has updated in place since P2-06c,
  its test asserts exactly that idempotency, and `scripts/init_db.py` registers the delivered version on
  every run - so a refused duplicate would make a fresh install non-repeatable. **Decided: keep the
  idempotent registration** and make AC-23 state the outcome it actually cares about: a version name
  always has exactly one row, and registering an existing name updates it. The SRS moves to V1.13 in
  both languages with a change-record row, the traceability pair follows the document number, and
  `test_register_model.py` asserts the one-row claim rather than leaving it implied.
- **A cached parameter belonged to whichever database read it first (review finding).** The cache was
  keyed by parameter name alone, and one process can talk to more than one database - the test suite
  does, and so does a developer running it beside the application - so for up to a TTL one database's
  limit was handed to another. No error, just a wrong number: the kind that surfaces months later as
  "the limit sometimes does not apply". The key is now `(database, parameter)`, and
  `tests/test_params_cache_scope.py` reads 1 from one database and 7 from another with no `forget()`
  between them - red on the old key (`assert 1 == 7`), green on the new one.
- **A test that fails on someone else's machine has to say what to do (review finding).** The
  delivered-weights check of the local development database failed with "0 online versions" for anyone
  whose `data/app.db` predates the delivery - a machine state, not a defect, and one CI cannot catch
  (no local database there means skip). It now skips with the command to run when the database serves
  no model, and still fails hard when two versions are online, because that one is the defect.

## 2026-11-11

- **A four-way audit ran read-only, and none of it fixed its own findings.** Four agents with disjoint
  scopes - document normalization, code-versus-documents, acceptance traceability, repository hygiene -
  reported without touching a file; five different agents then did the repairs. That separation is the
  repository's own rule, and it is what let the hygiene auditor report a gigabyte of leaked test
  directories it did not clean up itself.
- **What the audit found clean is worth recording so nobody re-derives it.** The contract's 45 route rows
  match the mounted routes one for one; the data model matches `models.py` on all 14 tables, every
  column and every type, with zero differences; no orphan documents, orphan modules or broken relative
  links across 48 files; and `.gitignore` told the truth about the tracked tree (no path both tracked and
  ignored). The `from`/`to` defect this repository once fixed stayed fixed.
- **The systemic finding is the one that matters: the checks compare headings, and every real defect was
  row-level or block-level.** Four shapes appeared - a header row lost in all six Chinese NFR tables, two
  table rows missing from the *English* SRS version of Table 2-3 while its own revision record said they
  were added, a whole page-name table present only in Chinese, and counts that silently diverged (the
  handover said four uncalled routes, the Chinese said five). Heading parity proves the pair has the same
  shape, never that it says the same thing.
- **"English is the source of truth" was not being enforced in either direction.** The report format and
  the token lifetime were corrected in Chinese and left stale in English; the uncalled-route list was the
  reverse. Whichever side a reader trusted, one language carried the wrong fact.
- **Eight blockers closed**, including the two this session itself introduced: the architecture document
  still called `/ws/capture` "planned and not yet implemented" hours after it was mounted, and three
  documents described `models/` as holding a delivered model when the directory was empty. Both were
  mine, and both are now what the code actually does.
- **A real bug came out of the documents disagreeing.** A relative `weight_path` was resolved against
  `Path.cwd()`, so detection worked from the repository root and failed from any other working directory
  - contradicting ADR 13 and the anchor `app/db.py` already used. The fix has a test that fails on the
  old code (it did: `load_online failed from the working directory …second-working-directory`).
- **The leaked test directories were a silent `ignore_errors=True`.** `tests/tmp/` held **5,432
  directories and 1,080 MiB**, one database per test run, because the Windows handle was still open when
  the fixture tried to remove it. The fixture now disposes the engines and retries, and a directory it
  genuinely cannot remove fails the test instead of being swallowed. Measured after a full run: **0
  directories, 0 MiB**.
- **Two acceptance items that had no test now have one**: the four frame filters (AC-08 - session, site,
  quality and date range, alone and as an intersection, with the filtered total) and the hard-example
  pool (AC-17 - a correction enters it, each frame appears once, removal clears the flag and keeps the
  evidence). The contract test also gained the **reverse** direction, so a mounted route missing from the
  contract now fails; it had only ever checked the forward one.
- **One finding was held back on purpose.** The date filter compares a naive local-looking date against
  a naive-UTC column, so an operator's 03:00 local capture on 2 November falls into the 1 November filter
  and is silently absent from its own day. The contract says "server time zone". That is either a
  contract bug or a code bug, and choosing needs a decision rather than a patch - a test now pins the
  present behaviour so it cannot change by accident.

- **The delivered model now lives in the repository, and the rule that forbade it is rewritten rather
  than bypassed.** Putting a `.pt` under a directory the ignore file excludes would have been a
  contradiction the next reader would find in a `git status`. ADR 13 records the reversal, including
  why the old rule lost: it enforced its useful half by keeping weights out and never executed the half
  that would have made them available - **zero releases, zero tags, and no download link or checksum in
  the README**, so a clean clone could not produce a model at all.
- **The layout choice was the substance, not a detail.** The data model put weights under `data/models/`,
  which is the runtime data root and moves with `AV_DATA_DIR` - a tracked artefact there is a file whose
  address is a configuration value. Delivered weights sit at the repository root instead, and
  `model_version.weight_path` stays relative so a registration made on one machine resolves on another.
  That is the one place this change deliberately departs from the data model, and the data model says so
  now.
- **The negative ignore rules were tested, not assumed.** `models/<version>/best.pt` is seen by `git`
  while a `.pt` in `data/` stays ignored; re-including a path under an excluded directory does not work
  in git, so the patterns had to be ordered and the result verified with a throwaway file.
- **Provenance is now part of the deliverable.** DUO declares **no licence of its own** - the upstream
  repository's licence field is empty and the data ships through cloud links for academic use - so the
  README states what the weights are, that they are the exploratory baseline rather than the official
  E0, that **no DUO image is redistributed here**, and how to cite the dataset. Silence would have been
  the one indefensible option.
- **What is still owed: the file itself.** No `.pt` exists yet on the development machine, so this change
  prepares the repository to receive it - the rule, the layout, the licence statement and the
  registration path are settled. `P2-13` and `GATE P2` remain blocked on a real 4-class weight file,
  which is training's to produce.

- **`GATE P1` is passed, on four criteria that were run rather than argued.** A real `uvicorn` process
  answered `/api/health` with `{"status": "ok", "database": "ok", "routes": 47, "contract_routes": 45}`;
  `scripts/init_db.py` exited 0 against an empty database; the file held the fourteen tables by name;
  all thirteen templates answered 200. The gate had been open since the first phase while everything
  after it was built ahead of it.
- **What held it open was a workbench, not the software.** `P1-06` was "hardware arrival check **and rig
  assembly**", and the assembly needs resistors, a button and a level shifter that are not here. The task
  was narrowed to the arrival check - which is genuinely done, camera and panel and serial all verified
  on 11-10 - and the assembly became `P3-17`, keeping its parts list and its three optical numbers
  intact. Nothing was dropped to make a gate pass; a gate stopped measuring the wrong thing.
- **The 5 V dead end is gone.** The board has no 5 V output, so the turbidity sensor had nowhere to draw
  power; a 12 V adapter with a buck module was bought on 11-11 and is recorded in `P3-17` as procured but
  **untested**. The wiring is written down there too, including the common ground, because a sensor
  without one looks exactly like a dead sensor.
- **Tomorrow is a bench session, so today's deliverable is a runbook.** It orders the work by what
  unblocks what - camera first, because `GATE P2` waits on it and the capture page has its own start and
  stop controls so the slice needs no button; power next, because a wrong voltage kills parts quietly;
  then the sensor's reading direction, which has to be measured before any firmware is written about it;
  then the LEDs, the button and the optics.

- **`P2-08` is ticked, and its real shape is worth remembering.** The task said "the capture page streams
  real frames"; the page had been finished for a week and the server had no WebSocket at all. Three of
  the last four tasks I opened this session were filed against the wrong half - `P3-05`, `P3-15` and
  `P2-08` all named a frontend deliverable while the missing work sat in the backend, or the reverse.
  **Reading the task title is not reading the task**; grepping for the capability is.
- **The fallback works, and its limit is now `P3-12`'s problem.** Closing the socket before `auth_ok` is
  what makes the client fall back at all, and the close is placed there on purpose after reading
  `live.js`: after `auth_ok` a close only reports "closed". The same reading shows the gap - a camera
  unplugged mid-demo never falls back - and that needs the client, so it was moved to the failure-and-
  recovery task instead of being noted in a PR description nobody reopens.

- **`P2-08` was not a page task at all.** It was filed against lane C as "the capture page streams real
  frames", and lane C had already delivered: `live.js` implements contract §7 in full and
  `tests/test_live_socket.py` holds it to the contract as text. Grepping the server for `websocket`
  returned nothing. **The only missing piece was the endpoint**, and the task had been sitting on the
  wrong lane. Corrected in the plan, with the reason, so the next person who opens it does not re-derive
  it.
- **An acceptance wording let a half-answer pass.** The task said "live detections from `/ws/capture`
  (or polling if the socket is unavailable)". That "or" meant a polling-only page could tick the box, so
  it now says the socket is the required path and polling is the fallback - with a test that shows the
  fallback happening instead of the page going quiet.
- **The server keeps inference off the event loop.** Detection is synchronous CPU work; awaited inline it
  would stall every other page for each connected tab. It runs in a threadpool, one inference in flight
  at a time, and the `frame` header and its JPEG are sent under one lock so `detect` or `status` cannot
  land between them - §7's adjacency is held by the lock rather than by timing.
- **No camera, so no pictures, and the page says so.** The socket is served, the token is validated, and
  the connection closes with `1011` and a reason; the client falls back to REST polling. No synthetic
  frames were invented. Reading the client first showed why the close has to come **before** `auth_ok`:
  after `auth_ok` a close only calls `onState("closed")` and never rejects, so the fallback would not run.
- **That reading also exposed the limit of the fix.** The client's fallback is driven by its own
  three-second timeout rather than by the close, and a socket that dies **after** `auth_ok` - a camera
  unplugged mid-demo - reports "closed" and does not fall back at all. Out of this task's scope, recorded
  for `P3-12` failure and recovery rather than left to be discovered on stage.

- **`P3-06` is ticked, and one of its three clauses needed a reading rather than a claim.** "One action
  resets the data" and "leaves the system in the state a rehearsal starts from" are both evidenced by
  tests. "Hides debug output" was met by the reset leaving no trace of the previous run - every count
  returns zero, so no page shows a leftover figure - and the prototype notice is a `?mock=1` surface a
  rehearsal never uses. That interpretation is written into the task, so a future surface that starts
  printing developer detail on a page is caught by a sentence rather than by memory.
- **CI caught what my own check had not, and the cause was my ordering.** I ran the document checks and
  then edited `PROGRESS.md`, quoting the server's Chinese refusal message inside English prose. The check
  had already passed on the older state, so it proved nothing about what I committed. The lesson is not
  "be careful with quotes" - it is that **a check is only evidence about the revision it ran on**, which
  is why the progress entry now describes the reason in English instead of reproducing it.

- **Demo mode exists, and the destructive endpoint is hard to fire by accident.** `POST /api/demo/reset`
  is admin-only and gated on `AV_DEMO_ENABLED`, which defaults to off; when it is off the route answers
  **404, not 403** - a data-wiping endpoint should not tell a prober it exists. The gate runs before the
  role check, so a non-admin on a disabled deployment also gets the 404 rather than learning there is
  something behind the door.
- **The reset reports what it deleted instead of a boolean.** Per-table counts, the number of image files
  actually unlinked, and the model still online. The keep-list is deliberate and commented: `model_version`
  (a rehearsal whose first capture answers the "no model weights registered" reason is the
  opposite of rehearsal-ready),
  `species_dict` (detection validates the model's class order against it), `sys_user` and `sys_param`
  (deleting the caller's account mid-request is a lockout, not a reset).
- **A file another process still holds cannot fail a reset that has already committed** - the unlink
  count only counts what was really removed, so nothing is reported as deleted that is still on disk.
- **Prototype mode is whole again.** `?mock=1` answered neither review-version route, so the version
  panel showed a load failure there. The mock now keeps a per-tab timeline of the reviews the tab itself
  submitted and answers both routes from it - an empty list for a tab that reviewed nothing, not fixture
  entries dressed up as history. A reset makes lists empty for the first time, which exposed three id
  generators that assumed a non-empty list; they no longer produce negative ids.
- **Known boundary, recorded rather than hidden:** the reset does not stop the running worker, so it
  assumes a rehearsal starts from a still system. Resetting mid-batch can leave the worker writing rows
  it just deleted. That is outside this change; `P3-12` failure and recovery is where it belongs if it
  ever bites.

- **`P3-05` is ticked. The three tasks I opened this session around the review flow are now all closed** -
  the acceptance that exposed the pool defect, the decision that fixed it, the versions and rollback API
  it needed, and the panel that uses them.
- **A gap the panel PR flagged went to the task that owns it, not to a new one.** Prototype mode
  (`?mock=1`) is documented as running every page without a backend, and the mock does not answer the two
  new review routes, so the version panel shows a load-failure there. That is honest - it invents no
  timeline - but a documented mode that half-works is a demo liability, so the requirement sits under
  `P3-06` demo mode, whose owner is already responsible for the demo working in every mode it claims.

- **`P3-05` closes with a panel, and its decisions are tested rather than inspected.** The review page
  can now list a frame's versions and restore one; the panel's choices - how an entry reads, whether the
  restore button may act, and what a finished rollback means for the canvas - live in
  `web/static/js/versions.js` as pure functions and run under Node, the same way `canvas.js` is tested.
  Asserting a page's wiring by grepping for a string proves it contains a word, not that it behaves.
- **A refused rollback is a normal outcome and the page treats it as one.** The server answers `409` for
  a no-op or for another frame's entry; the reviewer gets a warning saying the canvas was not touched,
  the selection is kept so another version can be picked, and the code returns **before** the two lines
  that write to the canvas. That ordering is itself asserted, because "the UI must not appear to
  succeed" is a statement about sequence, not about text.
- **The panel got its own state-by-event matrix** - idle, open, selected, confirming, restoring against
  open, select, confirm, cancel, Esc and a second click while restoring. This panel deletes nothing but
  overwrites the reviewer's canvas, which is exactly the kind of action whose unstated interactions fail
  on the day.
- **Known gap, recorded not hidden:** `web/static/mock/index.js` has no versions or rollback route, so
  with `?mock=1` the panel shows its load-failure state rather than an invented timeline. That is the
  correct behaviour under the no-fabricated-data rule, but the mock needs the two routes for demo parity.

- **`P3-16` is ticked and `P3-05` is down to one thing.** The rollback API is merged, so the canvas is
  no longer waiting on the server for anything; what is left there is the version panel, and the task now
  says so instead of naming a blocker that has been cleared. The delivered box carries the evidence -
  both routes, the shared conversion helper, the nine tests - and the remaining box carries what the new
  panel itself must prove, including a state-by-event matrix of its own and the requirement that a
  refused rollback leaves the canvas untouched.
- **Two notes were rewritten in place rather than left to be discovered.** A task whose blocker is gone
  but whose text still says "blocked" costs the next reader the same investigation that found it, and the
  plan is the one document everybody reads first.

- **`P3-05` is unblocked.** Its rollback half needed an API that returns a frame's review versions and
  restores one of them, and `P3-16` delivered both. The material was already there and no storage was
  added: `review` has always written the complete before/after box list into `sys_log`, so the timeline
  is read from what was recorded rather than recomputed from whatever boxes survive now.
- **The rule that turns a box list into rows was extracted, not copied.** `submit` and the new rollback
  share one helper, so a version arriving by either path is applied identically - two copies of that
  rule is how the two paths would drift apart. Rejected boxes are still marked, never deleted (AC-15),
  and a rollback writes its own history entry, so the rollback is part of the record instead of an
  invisible correction.
- **A no-op rollback is refused rather than recorded.** Rolling back to the set the frame already has
  answers `CONFLICT` and writes nothing: an entry saying "nothing changed" pushes the versions that
  matter out of a reader's attention. The two refusal codes are distinguished on purpose - an unknown
  `log_id` is a `404`, a `log_id` belonging to another frame is a `409`.
- **A stale number that was visible to clients is fixed and now cannot drift.** `/api/health` published
  `contract_routes: 42` as a literal; the two new routes made it 44 and only the count in the test was
  moving. The field is now tied to the contract table by an assertion, which is the difference between
  fixing a number once and fixing the class of defect.

- **`P3-01` is ticked, with the evidence written next to it rather than a bare box.** Its three
  acceptance points were verified through the API on #145 and the pool defect that verification exposed
  was closed by ADR 12 on #146, so the box now carries what proved it: the two test files, the red
  mid-flight assertion, the `OVERLAP: 0` measurement, and the one thing it does not prove - that the
  100-frame run uses an injected stub detector and the weights are a separate test.

- **The pool defect is fixed by a decision, not a patch.** ADR 12 makes a task own its frames: a new
  table `detect_task_item` (fourteen tables), the frames assigned when the task is created, a
  compare-and-swap claim that holds no lock across inference, and a frame the model finds nothing in
  recorded as done with `box_count=0` instead of staying available forever. The measurement that opened
  this - two tasks, `workers=2`, `asset_count=10` - now reports `OVERLAP: 0`.
- **The test that proves it was made deterministic before it was trusted.** `tests/test_batch_pool.py`
  holds both workers at their first frame with a barrier until the second has chosen its work, so the
  race is reproduced every run rather than when the scheduler feels like it. It failed on the old code
  with `OVERLAP: 10 frame(s) were claimed by both tasks`, and passes five runs in a row after.
- **A restart no longer throws away finished frames.** `requeue_stale` returns only the interrupted
  items to pending and keeps the finished ones, so a resumed task continues where it stopped. That
  inverted the old restart test's expectations on purpose - it asserted `progress == 0` and
  `count_objects == 0`, which encoded "start over". Retry keeps the old meaning: the operator asking for
  the run again resets every item and drops the boxes. The two paths are different on purpose and the
  difference is now a comment on each.
- **A five-day-old bilingual defect was found by the sweep and fixed.** `srs-zh.md` Table 4-1 listed nine
  entities against the English table's thirteen - it never got the four V1.5 rows. The pair passed every
  check, because `check-bilingual.py` compares headings and never table rows. The four rows were restored
  while the table was open; the check gap itself is recorded, not papered over.
- **The selection rule is written down, with its consequences.** `create_batch` skips frames already
  detected or already owned, which is what makes the duplicate claim impossible before a worker starts.
  Two consequences are deliberate and are in ADR 12 rather than left to be discovered: a cancelled task's
  items keep holding their frames, and a path needing already-detected frames names them instead of
  asking for the next batch - which is exactly what the same-frame comparison of `P4-10` does.
- **Known cost, no migration mechanism exists:** `create_all` adds the empty table to an existing
  development database, but tasks already queued before the upgrade own no items and finish immediately
  as zero-frame tasks.

- **The new lead's first act was to check the handover, and two of its briefs were wrong.** It said the
  review canvas still lacked zoom and told lane C to build it; zoom was delivered and tested on 11-11 by
  #137 - `canvas.js` resizes the stage's real width and never uses a CSS transform, `ZOOM_STEPS` reaches
  400%, and `test_review_canvas.py` runs the real module under Node. Sending that brief would have cost a
  day. It also assigned `P3-15` to lane B; `PLAN.md` assigns it to lane C, and the task spans both - the
  page is C's, the threshold enforcement is in `server/`.
- **`P3-01`'s three acceptance points now have automated evidence through the API, and the task stays
  open because a fourth thing is broken.** `tests/test_batch_acceptance.py` runs a 100-frame task to done,
  polls `GET /api/tasks/{id}` mid-flight, and cuts a run short before restarting it through
  `Worker.start()`. The mid-flight test was shown red first: with the worker's progress write frozen, the
  readings sit at `('running', 0)` and the assertion prints that series.
- **The pool duplicates work, and this was measured rather than reasoned.** Two queued tasks,
  `workers=2`, `asset_count=10` each: both finished with `obj_count=10` and **the same ten `asset_id`s**.
  `_frames_for` selects frames with no `detect_object` row, and two workers read that list before either
  writes. The cost is doubled inference and two task rows claiming the same assets. It needs a claim
  marker - a data-model decision, recorded in `P3-01` rather than patched from outside the lane.
- **`P3-05`'s other half has no task, so one was created.** The rollback needs an API that returns a
  frame's review versions and restores one of them; the review router has only the submit endpoint. The
  material is already stored - `review` writes the full before/after box list into `sys_log`, and
  `detect_object.version_no` marks a hand-drawn box - so `P3-16` is endpoints and tests, not new storage.
- **Housekeeping:** the seven remote branches that had been merged but not deleted are gone; `main` is the
  only branch on the remote.

- **A day of merged work left the status statements behind, and one of them was mine.** `P1-02` said
  "two P0 routes still answer 501" in the same task that said "no route answers 501 by default"; the
  README told a reader detection was not built; the test plan declared the end-to-end chain impossible;
  and the handover listed four things to do that had all been delivered the same morning. `P2-05b`,
  `P2-05a`, `P2-05c` and the AC-10 guard closed them, and the documents that describe the project's
  current ability were the last to find out.
- **The batch route was misdescribed in three documents at once.** `/api/detect/batches` answers 501 only
  when the database holds no frame; with a frame it queues a task the worker consumes, which its tests
  assert with `code == 0`. What is actually missing is `P3-01`'s acceptance - a hundred frames, progress
  while it runs, a restart that resumes - so the endpoint was blamed for a gap in its acceptance.
- **A wrong conclusion was corrected where it was written, not where it was convenient.** A PR claimed
  `requirements-server.txt` does not exist and asked for the plan line to be fixed. It exists at the root
  since #123 (blob `bae8fd82`, one commit, no deletion). The correction is a comment on that PR with the
  three pieces of evidence, so the review record no longer teaches the next reader something false.

- **The traceability matrix was reviewed row by row before it goes to review, and it was behind the code.**
  Seventeen elements still read "in progress" though the server had gained their routes; each was checked on
  the real server today and moved to done: batch detection, cancel and retry; every review-canvas element at
  200% zoom, with the stored boxes matching the page after a reload; hard-sample removal; and account
  disable, restore and password reset, with sign-in refused and then accepted accordingly. Two elements SRS
  §5.2 lists but the pages lack had no row at all, which made P-07 read as finished: recent jobs on P-02 and
  version compare and rollback on P-07 (blocked on lane B). The UT column now says which elements a test
  actually runs. The first history entry claimed 108 rows for version 1.0, which had 106; the history now
  records each version from git.
- **`P3-14` done: the result detail page exports its boxes as CSV.** One row per box listed on the page,
  the server's field names as the header plus a Chinese class name and review status, UTF-8 with a byte-order
  mark and CRLF so Excel reads the Chinese. Escaping is a pure function in `web/static/js/csv.js`, and
  `tests/test_result_csv.py` writes with it under Node and reads back with Python's `csv` module: a comma, a
  quote, a newline and Chinese all survive. An empty result says so and makes no file; the filename carries the
  frame id and a UTC time, and a demo export is marked `-mock`. Checked on the real server: 4 rows, 4 objects
  from the API, ids in the same order. The last criterion, Chinese class names opening correctly in Excel,
  was checked by opening a real-data export in Excel, so `P3-14` is ticked.
- **`P3-05` in part: the review canvas zooms, and every gesture has a defined answer to every event.** Zoom
  (50% to 400%, buttons, keys, Ctrl + wheel at the pointer) changes the stage's real width inside a scrolling
  viewport, never a CSS transform, so one tested function, `toImageCoords`, converts pointer positions at any
  zoom and scroll. `tests/test_review_canvas.py` runs that geometry under Node. Checked in the browser: at 400%
  a dragged box moves exactly with the pointer, a box drawn at 50% matches the dragged rectangle, a box dragged
  off the picture stops at its edge, Esc mid-drag puts the box back, and a press before the picture has loaded
  draws nothing (the first try drew on a 16 px broken-image strip, which is why readiness is now checked).
  Not ticked: two versions and a rollback between them need routes the server does not have (lane B).
- **The task board and the briefs now say the same thing.** `P2-05b` still carried "blocked until the
  weights arrive" a day after the weights were registered and activated, which is exactly how a team loses
  a day waiting for a door that is open. The blocker is cleared in writing, and the checkpoint now has its
  own acceptance: real boxes for the online version, a measured `latency_ms`, the version read from the
  database rather than a path in the code, lazy `torch` imports so the server still serves without the
  training stack, and an error code with a message instead of an empty box list dressed up as a result.
- **`P3-05` and `P3-14` were stated as outcomes nobody could check.** Both now name the work that is
  actually missing: zoom is the one canvas gesture that does not exist, and scaling must move picture and
  boxes together through one tested coordinate function rather than a CSS transform that leaves clicks
  wrong. Export gains the three things that break CSV - comma, quote and newline escaping, an empty result
  that says so instead of downloading an empty file, and a filename that distinguishes two exports.
- **Delegation has a rule in `AGENTS.md` §7, and deliberately no roster.** The rule is the part that holds
  for anyone: split along two axes - the lane says where an agent may write, the task type says how the
  work is done and what finished means - and keep finding separate from fixing, because an agent that
  both audits and repairs has no reason to report what it would rather not touch. **Who the helpers are
  and what they are called is a working detail of one session's setup, not a rule of this repository**, so
  the roster stays out of the file the other members' assistants read. It was written in and then cut
  back out the same morning on the owner's instruction.
- **`P2-05c` checked every `/api/stats/*` figure against the rows `P2-05b` wrote, and the four routes
  the dashboard reads agree with the database.** A batch task on the real weights ran two desk frames
  and two DUO test frames to `done` at progress 100 with `obj_count` 20; rejecting one box through the
  review route moved the reviewed basis to 19 while raw stayed 20, `corrections.rejected` became 1,
  and `quality` and `trend` equalled the frame counts. Each figure was compared with a direct SQL count
  on the same database, and the page reads exactly these four routes (`stats.html` through `api.js`).
  The numbers a person sees are the rows, not a fixture.
- **`P2-02` closes the result loop: one automatic set per frame, and it comes back by `frame_id`.**
  Re-running detection replaces the previous automatic boxes instead of appending a second set — every
  statistic would count a duplicate twice — and keeps the boxes a reviewer drew, which the model
  cannot reproduce. The policy is now stated in `docs/data-model-*.md` §3.5 and pinned by tests:
  detecting twice leaves one set, a hand-drawn box survives the re-run, and
  `GET /api/frames/{frame_id}/objects` returns exactly the rows detection wrote, counts included.
  Checked on the scratch server as well: 20 boxes stored, the query returned the same 20 object ids,
  and a second run left the count at 20 with a new task row.
- **`P2-05b` runs the online weights for real, and the single-frame route no longer answers 501.**
  The model comes from the `model_version` row with `is_online = 1` and is loaded once at start-up; no
  weight path appears in the code. A frame posted through the capture route went through
  `POST /api/detect/frames` end to end: 20 boxes, `model_version` `v8n-E0-exploratory`, a measured
  `latency_ms` of 2816 ms (CPU runtime, a 3840×2160 test image), the rows in `detect_object`, and the
  task row `done` with `obj_count` 20 and the model version that produced it. The boxes equal a
  direct ultralytics run of the same weights on the same image, compared at the precision the columns
  keep — that comparison is now `tests/test_detect_real.py`, which skips with a written reason when
  the database, the weights or torch are absent.
- **The latency is measured, not estimated.** The timer covers what the route does with the image:
  handing it to the model, pre-processing, inference and NMS. Contract §8's capture-to-result
  definition describes the live socket, where the capture is part of the same call; here the frame is
  already on disk, and the difference is written where the call is made.
- **Every way the model can fail to run is a stated refusal.** No online row, two online rows, a
  missing weight file, an unreadable file, torch absent and a class order that disagrees with
  `species_dict`: each produces a sentence the operator can act on, and the route answers 501 with it.
  A frame that never came through capture is 404 in the handler (AC-10), and a runtime failure is 500
  with a `failed` task row carrying the reason. Nothing invents a box — including ultralytics' own
  habit of answering a missing image with an empty result, which the detector refuses instead.
- **The server still starts without torch.** The import lives inside the loading function, so a
  machine without the training stack serves every other route and only detection answers with the
  reason. The class order is verified against `species_dict` at load time (data model §3.6), and a
  mismatch refuses to run rather than mislabelling every box.

## 2026-11-10

- **Three documents were audited against the code and thirty-odd claims were false.** The rig documents
  contradicted the firmware in eighteen places - the state diagram still drew `boot -> Offline` after the
  firmware had started booting into `Ready`, `EVT SCREEN` was documented as reporting every screen change
  while the capture timeout emitted only `EVT TIMEOUT`, and the protocol table was missing `CMD RESULT`'s
  score clamp, the `UNKNOWN` reason token and `EVT INVARIANT`. The API contract documented query parameters
  and request fields the routes do not read; the architecture document said "four concerns" above a table
  of five. All fixed against the source, none against another document.
- **One of those was a protocol hole, and the fix went into the firmware rather than the prose.** The
  capture timeout changed the screen to `RETAKE` without emitting `EVT SCREEN`, so "every screen change is
  reported" was false. `serviceCaptureTimeout` now sends `EVT TIMEOUT` and then `EVT SCREEN RETAKE -1`; the
  documents say so. Documenting an exception would have been cheaper and would have made the protocol
  unlearnable - a client could never tell whether a missing `EVT SCREEN` meant "no change" or "this one
  does not report".
- **`CMD SCAN` exists because the boot scan was the only look at the bus.** The turbidity bring-up went
  three rounds of "rescan and see" that each cost a power cycle and a race against the boot window. One
  command that rescans on demand makes a wiring change testable in a second. It is in both firmware
  READMEs, and it is what made the last two hours of diagnostics possible.
- **The turbidity sensor was not found, and the reason is power, not code.** The I2C scan answers nothing
  at any address: the sensor is a 4.5-5.5 V part, the board has no 5 V output (its `5Vin` is an input), and
  the 12 V module on hand needs a supply nobody has. `readTurbidity` returns -1, the firmware shows `-----`
  and sends no `EVT TURBIDITY`, which is the designed behaviour: a plausible wrong number is worse than a
  visible gap. Next step is a USB charger and a spare cable, not a code change.
- **Two code docstrings were lying about the system they describe.** `detect.py` blamed a missing weight
  file for the 501 when a version is registered and online - the missing piece is the detection path
  (P2-05b) - and `system.py` claimed `PATCH /api/params` answers 501 for want of a parameter table, which
  now exists and which the endpoint writes to. The README said the same stale thing in both languages.
- **`models.py` said "the nine tables" above thirteen, and the capture route filed frames flat.** The
  documented layout is `data/frames/<site>/<YYYYMMDD>/<session>/`; the API writer dropped site and session
  and put thousands of frames from different sessions in one folder. Fixed to match the data model.

- **The PC and the board talked to each other for the first time, and the keepalive lifecycle was
  observed on the panel rather than argued from the source.** On one open port: keepalives held `READY`;
  thirteen seconds of silence produced `EVT SCREEN OFFLINE`; the next keepalive raised `EVT SCREEN READY`
  again. Then the real server, with `AV_RIG_PORT=COM5`, opened the port, logged the rig's `READY`, and on
  a button press took `EVT TRIGGER`, failed to find a camera, stayed silent - and five seconds later the
  rig's own `EVT TIMEOUT` arrived. That is the failure path working as designed: no invented score, the
  silence is answered by the firmware's timeout.
- **Opening the serial port resets the board, and that is now written down in both firmware READMEs.**
  DTR and RTS feed the bridge chip's auto-reset circuit, so every program that opens `COM5` restarts the
  sketch. It looks like a fault the first time - the log begins with the ROM banner - and it changes how
  the keepalive has to be tested: on a port held open, not by reconnecting, because the boot and the
  ten-second link timer start together.
- **A hardware feature whose logs are invisible is a hardware feature nobody can debug.** The server's
  own loggers emitted nothing: uvicorn configures `uvicorn.*` and leaves the root alone, and without a
  root handler every `app.rig` INFO line was dropped. `rig: link configured on COM5`, `rig: port open`,
  `rig: screen READY` and the capture failure now appear in the terminal. One `basicConfig` in
  `create_app`, and the difference between "the link is running" and "the link never started" stopped
  being invisible.

- **A filename is as unportable as a path.** The hardware reference listed the three vendor PDFs by
  filename - `esp32-s3-wroom-1.pdf` and two more - and those files are on the lead's disk, not in the
  repository. A reader who cannot open a document gains nothing from knowing what somebody else called it.
  The table now names the kind of document (manufacturer datasheet, module datasheet, sensor manual rev A3)
  and says what each settled; the paragraph says the copies are held by the hardware lead.
- **`firmware/README.md` has a Chinese counterpart** (`firmware/README-zh.md`), and the pairing is
  enforced: `check-bilingual.py` used to know only about `docs/*-en/zh` and the root README, so a second
  README could drift unpaired forever. It now pairs the firmware one too - and said `MISSING` on the first
  run, because the file it demands did not exist yet. A check that fails before the work is written is the
  only kind worth adding after it.

- **The hardware reference described a folder that exists on one machine only.** It said the three vendor
  PDFs are kept "in the submission folder's `datasheets/` directory", which is a location on the lead's
  disk and meaningless to anyone reading the public repository. It now says the documents are not in the
  repository, why they cannot be, and that the hardware lead provides copies on request - no folder, no
  drive, no machine.
- **`check-paths.py` cannot catch that class of defect, and now that is known rather than assumed.** The
  check matches path *syntax* - a drive letter, a UNC share, a home directory - and `datasheets/` has
  none: character for character it is a relative reference, indistinguishable from `docs/`. The defect is
  reachability, not syntax, so no regex finds it; a reviewer has to ask whether the name resolves inside
  the repository. The older dated entry above still describes the folder, and stays: `PROGRESS.md` is
  append-only, so the correction is this sentence, not an edit to history.
- **`P2-17` is finished rather than merely working.** The two unused helpers in `link.py` are gone; the
  wiring now has an end-to-end test (settings -> link -> trigger -> keepalive -> `CMD RESULT`) instead of
  three modules tested in isolation; and `scripts/test_rig_link.py` is the bench tool an operator runs
  first, in the shape of `test_exposure.py` and `test_rig.py` - it prints every line the board says, pings
  every two seconds, and exits 0 only on a real `EVT PONG`.
- **The wiring test found a setting that lied.** Every field in `config.py` carries an explicit
  `validation_alias`, and with `extra="ignore"` a constructor call by field name - `Settings(rig_port=...)`
  - was accepted and then discarded, leaving the default. The link would silently never start for anyone
  who built settings that way. `populate_by_name=True` makes the name mean what it says; the test that
  caught it stays as the regression.
- **A leftover I created is now cleaned.** Five `pytest-cache-files-*` directories had been left in the
  project root by earlier runs under a sandbox that then refused to read them, and they made
  `ruff format --check .` crash rather than report. Removed, and the check passes again.

- **Hard samples: the quality badge no longer sits on top of the source badge.** The thumbnail rule put
  every badge inside a card in the top-right corner, so the quality badge in the meta line landed on the
  source badge. The rule now applies only to a badge placed directly on the card; the image browser, whose
  quality badge is meant for the corner, is unchanged. Figure 8 of the traceability matrix is recaptured.
- **`P2-18` done: one page, one name.** The menu, every page title and heading, and the traceability matrix
  now use the SRS §5.2 names, and `tests/test_page_names.py` compares the four lists page by page (shown
  failing on five planted mismatches, then passing). `frames.html` and `frame.html` became
  `image-browser.html` and `result-detail.html`, and a test refuses template names one character apart. The
  `P-xx` eyebrow left the page headers; the shell now finds the current page by its menu link. The copy
  review's three open items are closed: the group names and statistics subtitles applied, the current-model
  label applied, and the "today" prefix rejected because two of those cards are not daily figures against the
  real server.
- **The rig link now has its PC half (P2-17), written from a state matrix rather than from intuition.**
  `server/app/rig/` holds the protocol grammar as pure functions, a link that owns the port
  (DOWN / OPENING / OPEN / STOPPING against start, opened, open failed, read failed, write failed stop,
  keepalive tick and line in), and a service that answers a trigger with the same quality gate the rest
  of the product uses. The matrix is §9 of `docs/rig-state-machine-en/zh.md`.
- **The matrix paid for itself on the first run.** The initial link set the *global* stop event when a
  write failed, which ended the reader thread for good: one unlucky write and the rig link never came
  back. The test that caught it is `test_a_failed_write_takes_the_link_down_and_it_recovers`, and the
  fix was to give each connection its own event instead of borrowing the shutdown one.
- **A failed capture sends nothing at all.** No invented score, no error message the rig would have to
  learn - the firmware's five-second timeout turns the silence into `RETAKE / NO REPLY`, which is what
  actually happened. The two halves agree about the verdict because they run the same scoring code.
- **Port, baud and keepalive are settings** (`AV_RIG_PORT`, `AV_RIG_BAUD`, `AV_RIG_KEEPALIVE_SECONDS`),
  and an empty port means no link: a developer's machine, CI and every machine that is not at the rig run
  without a board and are not in a degraded state. `pyserial` is installed by `requirements-server.txt`.
- **The state-matrix rule is now a working principle** (`AGENTS.md` §4, principle 8): hardware behaviour is specified
  as the product of its states and events before it is coded, because the pairs nobody writes down are
  where the demo fails.

- **A decision stopped being true, so it was replaced rather than left standing.** ADR 07 said `pytest`
  stays CI-only until its dependencies install on every workstation without torch. `requirements-server.txt`
  now pins the server and the tests - pytest, httpx, no torch - so the condition is met, and the local
  `pytest -q` that `AGENTS.md`, the pull-request template and the README already demand is now a recorded
  decision instead of a habit running ahead of one. The record is superseded by ADR 11 rather than
  rewritten in place: a suite that only runs in CI is a suite people push past. Cost: one record, two
  table rows and two index lines; the check set and CI keep their roles.
- **A documentation audit against the code found thirty-five claims that were not true, and fifteen of
  them are fixed.** The pattern was the same in every case: a number or a name written once in a document
  and never compared to the thing it described. Two examples worth naming: the stack table promised
  ECharts while `web/static/vendor/` holds only Bootstrap and `charts.js` draws its own SVG; the SRS
  promised a WebSocket endpoint that no router implements. Both are now what the code is, and the plans
  are marked as plans.
- **The layer diagram described a structure that does not exist.** It drew `api/ -> services/ -> repo/`,
  and the code has `routers/` and a flat `app/` with no services or repo packages at all. The diagram now
  shows the real shape and states which part is the target; a diagram of an intended layer that is drawn
  as if it were present makes the reader distrust every other diagram in the document.
- **Four numbers were corrected by asking the file rather than the memory.** The bill of materials had
  nine items and ¥377.42 in its header while its own table summed to eleven and ¥388.32 - and the honest
  repair was not to change one number but to say **when** each item joined the list, because the 11-05
  order really was nine items and the resistors and button came later. Frames are stored under a
  `<site>/<YYYYMMDD>/` level the data model never mentioned. The retention default was 90 days in one
  document, 7 in another and 30 in the code; it is 30 everywhere now.
- **Seven documents outside my lane were left alone and recorded instead.** The API contract documents
  `from=`/`to=` for a route that reads `start`/`end` - a filter written from the contract silently returns
  unfiltered data - and the test plan names a script and a fixture directory that do not exist. That is
  `P2-19`, for the two lanes that own those files: fixing another lane's document inside this diff is the
  habit the handover forbids, and it is also how a reviewable change becomes unreviewable.
- **Correction to the 11-10 entry above**: the state machine lists **nine** events, not ten; the ten was
  the product of five screens and two link states.

- **The repository could not be run from a clean clone, and the README described a workflow that did not
  work.** An audit against the code found four blockers: the FastAPI app mounted routers only, so the
  pages and the API were on different ports and every call from a page answered "interface not found";
  `init_db` seeded species and no account, so a correct database still could not be logged into; the
  SQLite path was relative to the process working directory, so `init_db` from the root and `uvicorn`
  from `server/` built two databases and the health check passed on the empty one; and `requirements.txt`
  pulls torch through `ultralytics` plus a second OpenCV build, which is why CI had silently installed a
  hand-picked list instead.
- **All four are fixed in code, not in prose.** `web/` is mounted on the app with `/` redirecting to the
  sign-in page; `init_db` creates the first account and prints its password once; `app.db.resolve_dsn`
  anchors relative SQLite paths to the repository root; `requirements-server.txt` is the server and test
  set on its own. Four tests in `tests/test_pages_served.py` hold the single origin down.
- **The README is now a walkthrough that was executed, not written from memory** - environment,
  install, database, one start command, three URLs, the test command, and a table of the five failures
  someone actually hits. The configuration section of the architecture document had three wrong variable
  names and one that does not exist, and now matches `config.py`.
- **`check-paths.py` was scanning the root and `docs/` only**, which is how `firmware/README.md` could
  keep a path to a folder outside the repository: the subdirectory READMEs were never read. It now walks
  every Markdown file in the repository, proved by planting a path and watching it fail.

- **One page had three names, and the English had two.** The menu said `Capture control`, SRS §5.2 said
  `Capture control page`, and nine of the thirteen English names disagreed between the SRS and the
  traceability matrix (`Frame browser` against `Image browser`, `Detection tasks` against `Detection
  jobs`, `Administration` against `System administration`). The Chinese scheme was mixed too: object plus
  noun beside noun plus verb, `workbench` used both as a page type and as a modifier, and one name with a
  conjunction in it.
- **SRS V1.11 fixes the scheme**: object plus action, four characters where the language allows, no page
  suffix, no conjunction. The §5.2 table and `docs/traceability-en/zh.md` now carry the new names - 146
  replacements across the two matrices - and §5.2 is the authority the interface has to match.
- **The features keep their own names.** `FR-M4-01` is still the review bench, `/api/hard-samples` is
  still the hard-sample route, and the dataset-export feature is still that: renaming a page is not
  renaming a requirement, a route or a table. Only the four lists that name *pages* move together.
- **The task now asks for the test, not the rename.** Four hand-maintained lists - menu labels, page
  titles, SRS §5.2, the traceability matrix - kept equal by a check are the only reason this stays fixed;
  the rename alone would drift again by Friday.

- **The design pass is now a task with a definition, not an intention.** `P2-18` collects the three things
  that have been waiting for it: the SRS §5.1 palette requirement ("deep-sea blue and teal, never the
  clinical blue-white of a medical console"), the nine copy findings in `docs/copy-review-en/zh.md`, and
  the `P-xx` eyebrow that twelve page headers still carry because it was once the only anchor from a
  screen to SRS §5.2 - an anchor the traceability matrix now provides properly.
- **The measure of "beautified" is a test, not an opinion.** The palette already lives only in
  `tokens.css` (the single hardcoded colour outside it is one line in `app.css`), so a check in the shape
  of `test_api_js.py` makes the rule enforceable: a hex value in a template fails the build. Pages also
  get a screenshot each in `docs/images/ui/`, so the next design argument is a comparison.

- **The boot screen was the last argument: `READY`, not `OFFLINE`.** A panel that announces itself dead
  before anything has had a chance to speak reads as a fault, and the ten-second grace is far longer than
  a connected PC needs to send its first keepalive. So the rig boots `READY` on an optimistic `Alive`, and
  a rig on a bench with no PC software goes `OFFLINE` ten seconds later - which is correct, because there
  is nobody there. The invariant is unchanged: `OFFLINE` if and only if the link is gone, and boot is
  `READY` on a live link.
- **The link model was wrong twice before it was right, and the Cartesian product is what exposed it.**
  First the rig declared itself `OFFLINE` ten seconds after every power-up, because a watchdog on
  incoming commands measures the absence of a PC nobody had promised. Then the fix - a third
  "never connected yet" state - was argued down in one sentence: the PC sends a keepalive every two
  seconds, so `OFFLINE` plus a keepalive *is* `READY`, and the window between power-up and the first
  message is honestly `OFFLINE`. Two link states, booting on the second one.
- **The product of screens and link states turned a rule into a machine-checked invariant.** Five
  screens times two link states is ten combinations; five of them must never exist, and all five are
  excluded by one sentence: `OFFLINE` if and only if the link is gone, everything else needs a live PC.
  `rig::invariantHolds` encodes it and the main loop checks it every pass, reporting `EVT INVARIANT` if
  it is ever broken. It has not fired.
- **The product also found dead code.** The button handler carried a branch for "pressed while the PC is
  gone -> show OFFLINE", which by the invariant was unreachable: the screen was already `OFFLINE`.
  Deleted, along with the third link state that had made the earlier fix look necessary.

- **OFFLINE was measuring the wrong thing.** The rig declared the PC gone after ten seconds of silence,
  but silence is what a healthy idle system produces: nothing needs to be said between a capture and the
  next button press. The link has no carrier signal - the rig talks UART through a bridge chip and cannot
  see the cable - so liveness has to be a protocol matter: **the PC now owes a `CMD PING` every two
  seconds**, and ten seconds of silence is five missed keepalives, which does mean a real disconnection.
  The obligation is written into `firmware/README.md` and rule 6 of the state machine.
- **Writing that rule exposed a task nobody owned.** The architecture draws `MCU -. serial .-> CAP`, and
  no task in `PLAN.md` implemented the PC half of it: opening the port, keeping it alive, turning a
  trigger into a capture, answering with a verdict, and logging the rig's own events. That is now `P2-17`,
  in the capture lane.

- **The rig's state machine was written out as a five-by-ten table, and every cell now has an answer.**
  `docs/rig-state-machine-en/zh.md` lists five states against ten events, with the resulting state and
  the code that enforces it. The table found six things the firmware did not handle.
- **Six rules, each from a way the rig would have failed a demo.** A capture in flight ignores the button
  (a second press used to become a second frame); a verdict is accepted only while a capture is in flight
  and otherwise dropped **and reported** as `EVT STRAY RESULT`; a capture with no verdict after five
  seconds becomes a retake with `NO REPLY` and no score (the spinner used to turn forever); a keepalive
  `PING` refreshes the link without touching the screen; losing the PC overrides everything but
  recovering from it only resets `OFFLINE` (a recovered link used to wipe a verdict off the panel); and
  every transition is reported, because before that a wiring fault and a logic fault looked identical
  from the serial port.
- **All of it was verified on the board**, not in the code: two presses produced one `EVT TRIGGER`, a
  press during a verdict started the next capture, the timeout fired exactly 5000 ms after the trigger
  (`EVT TRIGGER 5280` → `EVT TIMEOUT 10280`), a verdict in the wrong state produced `EVT STRAY RESULT`,
  and a keepalive left the PASS screen alone.
- **The floating button wire was itself a finding.** Presses the operator never made showed up as
  `EVT TRIGGER`; a 20 cm jumper hanging off an input is an antenna. The test sequence had to be redesigned
  around it, and the lesson belongs to the assembly: the real switch connects the pin to ground, so it
  does not float.

- **The panel design was rebuilt against the hardware, and the first version lost four arguments to it.**
  Shape now carries the verdict - a filled banner for PASS, an outline for RETAKE - because at 128x64 the
  words alone were the only difference. The retake reason moved from a second line in the banner (one
  pixel of clearance, which read as a smudge) to the caption slot above the score. The labels went to
  bold 7x13 so they read as captions: measured on the panel, the score font's ascent 19 and the label's
  ascent 9 then put both on the same centre line at 21.5. The footer settled on a single six-pixel
  gutter in both columns, with the value left-aligned after it - right-aligning left a two-pixel gap after
  a five-digit reading and a wide one after a three-digit reading, two gaps in one row.
- **The trend mark is gone, and it was a design defect rather than a taste problem.** The triangle was
  chosen by an absolute threshold of two counts on a reading that spans 700-16000: two counts is noise,
  so the mark flickered between rising, falling and steady. At five digits it also overlapped `FRAMES`.
  The field and its computation were removed with the drawing, because a feature that lies is worse than
  no feature.
- **Every state was exercised on the panel, and the walk found two real bugs.** `protocol::poll` returns
  whether a command arrived, and the caller discarded it, so the link timer only ever started at boot
  and the rig declared OFFLINE ten seconds later however much it was talking to the PC. And the screen
  state became observable at all only after adding `EVT SCREEN <name> <score>` - before that, a wiring
  question and a logic question looked identical from the serial port.
- **A temporary `CMD TURB` command injected readings for the demo and was removed before the commit.**
  A rig that accepts invented sensor values is exactly what this project must not ship.

- **The rig's electrical half started, and the first module works.** The OLED was wired directly to the
  ESP32 - `3V3`, `GND`, `GPIO8`, `GPIO9` - because it is a 3.3 V part and needs no level shifter. The
  boot scan reports `EVT I2C 3C`, the splash draws, and `CMD PING` answers `EVT PONG`: the I2C bus, the
  display and the PC-to-board command path are all confirmed at once, with a serial port and no button.
- **The five screens were driven from the serial port**, which is what makes a buttonless bring-up
  possible: `CMD RESULT` with PASS, and with LOWLIGHT, COLORCAST and UNKNOWN reasons, plus `OFFLINE`
  by staying silent past the ten-second timeout. The LED pulses could not be observed - the 330 ohm
  resistors had not arrived - so the two LEDs remain unverified while the logic behind them is not.
- **The board has two USB connectors, and they do different things.** The sketch writes to UART0, which
  reaches the PC only through the CH343 bridge on the `UART`-marked connector; the `USB`-marked one
  exposes the S3's native USB and shows ROM boot messages only. Plugged into the wrong one, a working
  board looks mute.

- **The datasheets arrived and one of them changed the wiring.** The ME2100A-IIC manual (rev A3,
  2025-02-27) states 4.5-5.5 V, and its revision history shows A3 *removed* the 3.3 V specification
  that earlier revisions carried. The interface tolerates up to 5.5 V; the ESP32 does not. **The level
  shifter is now required**, where the assembly plan had called it skippable, and the part is already on
  the procurement list.
- **Two guesses were settled and one was not.** The address `0x49` and the two-byte width are confirmed;
  the turquoise channel reads high in clear water and low in turbid water, as the code assumed. What the
  manual never states is **which register holds the measurement** — it documents the read transaction but
  omits the register map — so `readTurbidity()`'s bare read remains unverified in that one respect, and
  the README says how to settle it by measurement.
- **The datasheets are kept outside the repository on purpose.** The turbidity manual forbids disclosure
  to third parties without written consent, and the repository is public. The facts are recorded in
  `firmware/README.md`; the PDFs live in the submission folder beside a note explaining why.
- **The board's blinking was the vendor's RGB demo**, and the `SHA-256 comparison failed` warning it
  printed disappeared with the first real firmware write.

- **The board arrived and the first firmware assumption was wrong.** `ARDUINO_USB_CDC_ON_BOOT=1` sent
  `Serial` to the S3's native USB port, so the CH343 UART bridge showed ROM boot messages and nothing
  from the sketch: a board that looks dead while it is running fine. Measured, then set to 0 — the
  sketch now talks on UART0, one cable flashes and monitors, and no BOOT button is involved.
  `EVT HELLO 1.1` arrives, and the factory image's `SHA-256 comparison failed` warning disappeared with
  the first write of a real firmware.
- **The I2C bus is now reported at boot.** `setup()` scans addresses 1-126 and prints one
  `EVT I2C <addr>` line per device that answers, so an unplugged display or sensor is visible in the
  serial log rather than only as a blank screen. With nothing wired it correctly reports nothing.
- **The blinking the board arrived with was a factory RGB demo**, not a fault: `RGB Demo / 50%R /
  50%G / 50%B` on the serial port.

- **`P2-04` done: the review loop persists delete, add and relabel with one submit.** Every edit is
  local until the reviewer submits the whole set (the server's contract), delete asks first, and after
  the submit the page reloads the boxes from the server: new boxes get their ids there, rejected boxes
  stay out of the working set, and the count is the server's `object_count`. Checked on the real server
  with boxes seeded into a scratch database (detection had not written boxes yet): one delete,
  one drawn box and one relabel submitted with the count going from 3 to 3; the stored rows match the page, and the page
  shows the same rows after a reload.
- **`P2-16` done: `live.js` follows contract §7.** The token now travels as the first `auth` message and never in
  the URL; the client waits for `auth_ok` before sending `start`; a 4401 close sends the user to sign in,
  and a 4408 close is reported as a stall. `tests/test_live_socket.py` fails when the client uses a message
  type or a field §7 does not define (checked by planting a mismatch). Checked against a scratch socket
  server that speaks §7: auth then start, boxes drawn, and a refused token returns to sign-in.
  `/ws/capture` is still not on `main`, so P2-08 stays open.
- **`P2-03` done: the capture and review pages hold no mock data.** Neither page imports the mock; the only
  route to it is the explicit `?mock=1` switch, which stays. Capture reads sessions and frames from the API and
  shows the empty state when there are none; review reads the newest frame (or the one named) and submits to the
  real route (`P2-04`). Checked against the real server: sessions and posted frames render, the review page
  loads boxes and submits. The capture page's live boxes still depend on `/ws/capture` (`P2-08`).
- **`P3-02` in part: the species chart follows the counting basis, and its caption follows with it.** The
  chart reads `/api/stats/species?basis=…`, and the caption names the basis; the other three charts say they do
  not depend on it. Checked on the real server: reviewed gives 6 boxes and raw gives 8, both matching the API.
  Not ticked: the route has no site dimension, so the "empty site" criterion cannot be met, and the quality chart
  needs per-day figures the server does not return. `P3-14` (CSV) is blocked on lane B; see the PR description.

- **The rig's three numbers became a script, so the tank can be judged without an opinion.**
  `scripts/test_rig.py` measures lighting uniformity, the width of a 5 cm target at 640 px, and the
  brightness drift between the first and last frame of a run; `server/app/vision/rig.py` holds the
  measurement and `tests/test_rig_measure.py` covers it on generated frames. Ten tests, all of which
  state a number from the procurement document rather than a shape of code.
- **The first version passed a desk photo as a good rig.** It reported a 346 px target by finding the
  bright window, and its 60th-percentile threshold swallowed the whole frame once the target occupied
  only a few percent of it. Otsu's threshold plus a fill-ratio and an upper width bound fixed both:
  the desk photo now reports 0 px, and a 318 px square at 1080p is measured as exactly 106 px at 640 —
  the number it should be. A check that can be fooled by the scene is worse than no check.

- **`P3-15` partly done: thresholds are viewable and editable on P-12, unknown codes are refused, and the
  page says the truth about scope.** The batch route takes its own `conf_thr` (default 0.50) and never reads
  the species dictionary, so a saved threshold does not change detection yet. The caption says so; the
  task stays open until the route reads the dictionary (lane B). Checked on the real server: 0.55 saved
  and kept after a reload; 1.2 refused in the browser; an unknown code in the scratch database shown as
  a refusal, not a row.

- **The contract settled, so the client owes it two changes (§7).** The socket used to carry the token
  in the query string because nothing better had been decided; §7 now requires it as the first `auth`
  message and adds `auth_ok`, `4401` and `4408`. `P2-16` is the new task: move the client onto the
  agreed protocol and add the test that fails when the two drift, mirroring `tests/test_api_js.py` for
  the REST surface.
- **The camera now produces real frames**, which changes what the backend lane can test: detection no
  longer has to wait for synthetic images, and a capture session from this morning is on disk at 1080p.

- **One footer cost an afternoon of history rewriting.** The squash-merged `P2-15` commit carried
  `Co-authored-by: Claude Code`, which GitHub counts as a second contributor. It happened because a
  squash merge copies the single local commit's message onto `main` verbatim, so a line written on
  someone's machine becomes permanent history.
- **The suggested repair would have damaged a different commit.** By the time it was proposed, two more
  commits had merged on top; `git commit --amend` rewrites only the tip, so it would have replaced the
  message of the camera work and left the offending commit untouched. The repair has to be a rebase of
  the three affected commits.
- **`main` was rewritten to `c279872`**, message-only: `90ad154` → `83850dd`, `d0b68af` → `f5c77c5`,
  `eef7a82` → `c279872`. The tree before and after is identical (`9a2ba2e`), which is the check that
  proves only the message moved; a copy of the old branch is kept as `backup/pre-trailer-rewrite` until
  the team has reset.
- **The gate was proved in CI, not just locally.** A throwaway branch carried one empty commit whose
  message ended with the forbidden footer. Pull request #100: the `check` job failed, `mergeable_state`
  read `blocked`, and the branch changed no files — so lint and format could not be the cause. The same
  command on the same commit reproduces the refusal locally. That also confirmed branch protection is
  back: a failing required check stops the merge, which is the state that had to hold after the rewrite.
- **The rule now lives where it can be enforced.** `CONTRIBUTING.md` §2 forbids attribution footers,
  `scripts/check-commit-messages.py` fails on one, CI runs it on every pull request, and `AGENTS.md` §6
  lists it. The check was proved to fail against the old commit and pass against the rewritten history
  before being trusted.

- **The camera arrived and the device half of `P1-03` is closed.** `scripts/test_exposure.py --index 1`
  exits 0 on the real unit: 1080p, exposure controllable and lockable to a 0.5 % frame-to-frame spread,
  5 fps. Twenty frames went through the pipeline, which closed by confirming on disk that the file,
  the quality score and the frame id all agree.
- **Four defects were found by using it, not by reading the code.** The capture CLI had no way to set
  exposure at all, though manual exposure is an SRS requirement; gain was read and never fixed, though
  the SRS says "shutter and gain fixed"; the lock measured the sensor settling and reported a 224 %
  drift on a locked exposure; and forcing manual white balance turned every frame green (cast score 0
  against 83 for automatic) because this driver echoes the temperature back without acting on it.
- **The unit has one broken mode and one hard ceiling.** 720p stalls at 1 fps; 1080p runs at 5 fps,
  which is the USB 2.0 bandwidth for uncompressed video; 640×480 gives 30 fps. MJPEG is ignored. The
  rig captures stills, so 1080p at 5 fps is enough — but nothing may use 720p.
- **Image quality has not passed, and should not have.** With a good exposure the frames score 49–50:
  brightness 72, cast 83–86, **sharpness 21** — a desk with no tank, no fill light and no target has
  nothing sharp in it. The gate is right to reject them; `P1-06`'s rig numbers wait for assembly.

- **Correction: the dataset was never missing.** The entry above says the prerequisite for `P2-06` was
  not on this machine. True, and irrelevant — it is on the training machine, as the owner of that lane
  pointed out within the hour: 6671 + 1111 raw images and a 5671 / 1000 / 1111 split, both present.
  Checking one machine and reporting its absence as a blocker for someone else's work is how a
  scheduling problem gets invented.
- **The training split is 85:15, and the `7:2:1` in that task was wrong.** Two different splits share
  the word "split": the training split, where `docs/test-plan-en.md` §2 asks for 10–15 % validation and a
  frozen test set of 500+, and the dataset-export feature (FR-M4-04), where 7:2:1 is the ratio the
  application writes at run time. The task copied the second onto the first. The existing 5671 / 1000 /
  1111 is therefore correct as it stands; what it lacks is a seed and a manifest, not a new ratio.
- **The path rule was enforced where it could be checked, and forgotten where it travels furthest.**
  `check-paths.py` reads the repository's documents; it cannot see a task brief handed to someone to
  forward. A brief went out carrying a path from this machine, and it had to be pointed out twice.
  `AGENTS.md` §6 now says the rule is wider than the check's reach.
- **`P1-02` could not have been closed as written.** Its "done when" required every P0 route to return
  real data, and one of them — `POST /api/compare/frames/{id}` — needs two registered model versions
  loaded at once, which cannot exist before P4. The task would have stayed open for another month for a
  reason that has nothing to do with the work in it. `compare` is now `P4-10`; `P1-02` closes on the two
  detection routes and the reviewed statistics, which is `P2-05`.
- **What keeps `P1-02` open is exactly two routes**, both waiting on weights: `POST /api/detect/frames`
  (FR-M3-01) and `POST /api/detect/batches` (FR-M3-02).
- **The backend lane has produced nothing since 11-08, and part of that is a scheduling fault of mine.**
  `P2-05` and `P2-06` were assigned as parallel tasks, but detection needs weights and weights come from
  the baseline — they are strictly sequential. Worse, the prerequisite is not on this machine:
  `scripts/prepare_dataset.py` reads `data/raw/DUO/DUO`, and `data/` does not exist here. A task whose
  first step is impossible should say so on the first day.
- **Both tasks are now checkpoints rather than black boxes.** `P2-05` is 05a (queue consumer on
  synthetic rows, unblocked), 05b (detection, waiting on weights) and 05c (statistics verified). `P2-06`
  is 06a (split), 06b (baseline), 06c (weights). Three merges each, so progress is visible without
  asking.
- **`P2-15` added: the three contract §7 questions**, which block the frontend's live capture page and
  cost a paragraph to answer. They are cheap work sitting in front of expensive work.
- **The frontend lane delivered five of six tasks, and left the sixth open on purpose.** `P2-09`,
  `P2-10`, `P2-11`, `P2-12` and `P2-14` are ticked and verified here; `P2-08` is built but not ticked,
  because the server has no `/ws/capture`, nothing posts frames to the API, and detection still returns
  501 — a live detection cannot be shown, so it is not called done. That judgement is the review's most
  useful result: the box was left open rather than closed on faith.
- **Both of the new tests were shown to fail before being trusted.** Renaming a route in `api.js` turns
  `test_every_exported_function_maps_to_a_contract_route` red; adding the word "provisional" back turns
  the other one red. A test that has never failed is a decoration.
- **The traceability matrix is real work, not a table.** 106 rows per language, one row per UI control,
  13 annotated screenshots with numbered callouts, every cited requirement id checked against SRS
  Table 3-1, and a status column that admits 27 elements are in progress and 4 are not started.
- **Three contract gaps came back from the frontend, and are now in the backend lane's list**: a binary
  frame carries no `frame_id` for §8's correlation, `detect` carries no quality score for the ring, and
  the socket's authentication is unspecified — the client currently puts the token in the query string,
  which leaks it into logs and referrers.
- **`P2-15` answered those three questions before the route exists.** The socket authenticates with a
  first `auth` message, never a query-string token; each binary JPEG follows a `frame` message that
  carries `frame_id`, `captured_at` and `quality`; and results correlate to frames by `frame_id`, not
  by order. This unblocks `P2-08`: `web/static/js/live.js` still sends the token in the query string
  and must move to first-message authentication. The `/ws/capture` route itself does not exist yet.
- **`P2-07` closed the payload-shape gap on every P0 route.** The skeleton test covered the envelope,
  the guards and the 501s; it did not check what each route actually returns. A new section now
  asserts status, `code`, and the documented fields and types for all 21 P0 routes, seeding tasks,
  boxes, models, experiments and species through the SQLite fixture. The failing reference was
  demonstrated once: removing `task_code` from `serializers.task` turns the batch-task test red.
- **`P2-05a` gave the queue a consumer.** `server/app/worker.py` claims a queued `detect_task`, walks
  the frames that have no detection rows, advances `progress` per frame, and stops when the row is
  cancelled. A failure writes its reason; retry deletes the partial result and runs the same frames
  again; rows left running by a crash are requeued at start-up. The detector is injected: P2-05a
  passes none, so a task fails with "model weights are not registered" instead of inventing boxes;
  P2-05b supplies the real one. The app starts a `max_concurrency` pool in its lifespan; tests disable
  it.
- **`P2-06a` put the split under a seed and the test set under a manifest.** `prepare_dataset.py` now
  takes `--seed` (42) and `--manifest`; the split test uses the real group sizes (6455 singles, 106
  pairs, one four) and asserts 5671 / 1000, same seed same split, and 7782 total. `test-manifest.txt`
  is committed with 1111 `filename md5` lines, generated from the frozen official test set; the
  images stay out of git. The split already on disk was not regenerated — the lead confirmed it is
  correct; the seed governs a fresh run.
- **`P2-06b` ran the exploratory baseline end to end.** A separate `aquavision-train` environment
  (torch 2.12.1+cu126, ultralytics 8.4.202) trained YOLOv8n on 1800 train / 200 val for 30 epochs
  (seed 42, batch 16, 640). On the frozen 1111-image test set: mAP@0.5 **0.770**, mAP@0.5:0.95
  **0.561**, mean recall **0.692**, 499 fps, 3.14 M parameters; `train_experiment` row 1 has every
  metric column filled. mAP@0.5 clears the 0.75 target; mean recall does not (0.692 vs 0.75) —
  the class imbalance (sea urchin is about 24x scallop) and the 1800-image subset are the first
  hypotheses. The official E0–E4 stay at P4. The run was interrupted at epoch 20 and resumed from
  `last.pt`; the final row is a continuous 30-epoch run with a dataloader restart.
- **`P2-06c` registered and activated the baseline weights.** `scripts/register_model.py` turned
  `metrics.json` into `model_version` row 1 (`v8n-E0-exploratory`, mAP@0.5 0.7703, mAP@0.5:0.95
  0.5614, recall 0.6919, 499 fps, 3.14 M parameters) and made it the only online row. The app loaded
  it at start-up from `runs/detect/data/models/baseline-e0/weights/best.pt`; a captured frame went
  through `POST /api/detect/frames`, returned the model version, and its `detect_task` points at
  model 1. A manual run of the same weights on the same stored image matched the API boxes. The
  camera's A3 1080p frames were not on this machine (`data/frames/A3/20261110` is absent and camera
  index 1 is unavailable), so the proof used the laptop camera; the real A3 frame acceptance stays
  with P2-05b. The CPU runtime's first inference took 6.6 s; the 499 fps figure is the training GPU.

## 2026-11-09

- **Nine tasks assigned for P2, split by lane, each with a criterion a stranger can run.** Backend and
  model: finish `P1-02` (detection, the queue consumer, reviewed statistics), prepare the DUO split and
  run one exploratory baseline, and add contract tests for every P0 route. Interface: `api.js` stops
  claiming routes are provisional, sign-in calls the real endpoint, every page renders loading, empty
  and failure, the capture page streams real frames, and the dataset export page loses its mocks.
- **The baseline moved out of `P4` into `P2-06`, deliberately.** Training is wall-clock work with
  iteration in it; leaving all of it in the final phase means discovering model problems with no time
  left to answer them. The phase boundary is stated in the task so the official E0–E4 runs at `P4`
  are not mistaken for the same work done twice.
- **P3 and P4 were too coarse to start on, and one number in them was stale.** Six P3 tasks covered 29
  requirements — a whole module per task, which cannot be a pull request — and P4 asked for "nine
  metrics" while SRS Table 6-1 has seven since V1.3 deleted two. Both phases were rewritten so a task is
  one PR-sized slice that names the acceptance items it closes.
- **Writing the acceptance ids down exposed three capabilities that had no task at all**: scheduled
  capture (AC-06), CSV export of results (AC-14) and the species dictionary editor (AC-26). None of
  them was in the plan in any form, and the first two do not exist in the code either.
- **All 36 acceptance items are now claimed by exactly one task.** That is what makes the P3 gate
  ("every item traceable to the task that closed it") a check rather than a wish — and it is verified by
  reading `PLAN.md`, not by memory.
- **A traceability matrix joins the frontend lane (`P2-14`).** The course wants one built from the SRS
  and the UI prototype, covering every screen. The template it follows is five sheets — cover, change
  history, matrix, and one annotated screenshot per screen — and its unit is **one UI element per row**,
  not one screen per row: a title, an input, a button, each described by how it looks and what it does,
  and each pointing at a numbered callout on the picture. The template workbook was read for its
  structure and then deleted; the structure is recorded in `docs/handover-en.md` §3.6 so it does not
  have to be found again.
- **`docs/handover-en.md` was rewritten as the acceptance list rather than a note.** It opens by naming
  what already exists — the cheapest mistake on a Monday is rebuilding a skeleton that is already
  there — and every remaining item is paired with the check that settles it.
- **`P2-10` done: `api.js` no longer calls any route provisional.** All 37 exported functions map to a
  route in `api-contract` §6, and `tests/test_api_js.py` now fails if the word returns or a function
  names a route the contract lacks. Five contract routes have no browser caller yet (`auth/login`,
  `auth/me`, `tasks/{id}`, `detect/frames`, `compare/frames`); none was invented to fill the gap.
- **The mock is older than the contract and it shows.** Its field names for tasks, datasets, reports and
  the review reply differ from the server's serializers, and the frames page sends `session_id`,
  `verdict`, `from`, `to` where the server reads `session`, `quality`, `start`, `end`. The comments now
  say so instead of calling the routes provisional; the fields get aligned page by page under `P2-12`.
- **`P2-11` done: sign-in calls `POST /api/auth/login`.** The token and user are stored, every request
  carries the bearer header, a refusal shows the server's own sentence (attempts left, then the
  lockout and its remaining seconds), and a 401 anywhere except the login call clears the session and
  returns to the form with the page to come back to. The captcha field is gone: the endpoint never
  took one, and a field nothing checks is decoration. FR-M1-01 still asks for a captcha.
- **The mock became opt-in per tab.** `?mock=1` runs a tab on the mock, `?mock=0` leaves it; without
  the flag every page talks to the real API. A hard-coded switch could not serve both the demo laptop
  and the integrated system.
- **Two gaps found while testing against the real server, both lane B.** The FastAPI app does not
  serve `web/`, so the pages and the API share no origin without a separate mount or proxy; and
  nothing creates the first account — `init_db` seeds species only. Testing used a scratch runner that
  mounts `web/` and adds a test account; neither is committed.
- **`P2-12` part 1: loading, empty and failure on the task, frame and hard-sample pages.** One helper,
  `loadInto`, draws all three; after five seconds the loading line says the server is slow, so a slow
  answer never reads as an empty one, and a failure says why and offers a retry. Each page and its mock
  route now use the server's shape — status words, progress as a percentage, the server's filter names
  and source codes — so real rows render instead of `NaN`.
- **Three more contract questions surfaced, all lane B:** `POST /detect/batches` takes a frame count,
  not the selected frames; `GET /tasks` and `GET /hard-samples` have no keyword filter, which SRS §5.1
  asks of every list page; and no route serves a frame's picture, so real thumbnails stay placeholders.
- **For lane A: the quality score rejects underwater colour.** Two DUO frames posted to the real
  server scored 40 and 31 with colour cast 0 — blue-green water reads as a colour defect, so as tuned
  the gate would turn every underwater frame away.
- **`P2-12` part 2: the model and administration pages.** Same three states, per tab, and the same
  move to the server's shapes. Two were outright broken against the real server: resetting a password
  sent no password (the route requires one of at least eight characters), and the parameter form wrote
  `max_workers` and `default_conf`, keys the server does not have. Monitoring now shows what the
  server measures — queue, stored frames, disk, concurrency — instead of a GPU figure nothing reports.
- **`P2-12` done with part 3: home, statistics, reports, frame detail and review.** Every page that calls
  the API now draws loading, empty and failure. The home cards no longer show fixture numbers against a
  real server: they read the trend, quality and model routes, and "pending review" says no route
  counts it. Frames from the server have no picture, so the stage draws a labelled placeholder and the
  boxes on it rather than a broken image.
- **Two of screen 6's charts cannot be fed by the contract.** Interception per day and corrections per
  class are drawn from arrays; the server returns totals. Against the server those two cards state the
  totals in words and say what breakdown is missing — lane B's call whether the contract grows.
- **`P2-14` done: requirements traceability matrix.** `docs/traceability-en.md` and `-zh.md`, 13
  screens, 106 element rows, each pointing at a numbered callout on a per-screen screenshot in
  `docs/images/traceability/` (compressed to 1.2 MB). The generator refuses to write unless every
  requirement cited is in SRS table 3-1, every screen has its image and every template has a section.
  Status is stated as it is: mock-only elements are "in progress", and the UT column is "not started"
  throughout because no per-element test exists yet. FR-M2-05 and FR-M3-03 have no screen element and
  say why. The menu's role filtering is recorded as in progress, not done.
- **`P2-08`: the capture page's client is built, the box stays open.** `web/static/js/live.js` feeds the
  page from one stream — the mock under `?mock=1`, `/ws/capture` as contract §7 describes it, or a
  one-second poll of the session's newest frame when the socket will not open — and every figure on the
  page comes from that stream. The poll was verified against the real server with frames posted into
  the open session; the socket path against a scratch endpoint speaking §7, including a stale result
  that was correctly dropped. The box is not ticked: the server has no `/ws/capture`, nothing posts the
  camera's frames to the API yet, and detection still returns 501, so no live detection can be shown.
- **Contract §7 leaves a client three questions, sent to lane B.** A binary frame carries no
  `frame_id`, so §8's "correlate by frame id" has nothing to correlate; `detect` carries no quality
  score for the ring; and the socket's authentication is unspecified. The client accepts an optional
  `{ type: "frame", frame_id, captured_at, quality }` header before each JPEG and a `quality` field on
  `detect` if the contract adds them, and works without them.
- **`P2-09` done: the dataset page exports against the real route.** It sends what the server takes — a
  `DS-` name, the ratio as tenths (`7:2:1`), a seed, reviewed-only — where it had sent percentages and an
  `include_hard` flag the server never had. Counts on the page are the server's; a snapshot whose splits
  do not add up to its frame count is marked on the row as a defect rather than smoothed over. Two
  exports of the same four frames with seed 42 split identically, which is the determinism AC-18 asks for.
- **The mock's saved state is now versioned.** A tab that had run the old mock restored its old-shaped
  records over the new data and drew `undefined`; the storage key carries a version so a shape change
  starts clean.

# Progress

> Owner: whoever did the work · Revisit when: continuously, append only

Current phase: **P1 — skeleton**
Gate: `uvicorn` starts, `/api/health` answers, 13 tables exist, 13 pages render

One entry per day, newest first. A day's work goes in that day's entry; do not open a second one when
the afternoon brings more. The heading is the date and nothing else — no “evening”, no “later”.
**Why** a task moved lives here; **whether** it is done lives in `PLAN.md`.

Length is not capped. A long day is a long day, and forcing it shorter only invites compressing the
truth or splitting one day across two dates. What matters is one bullet per decision or per change of
state, not a parade of every commit — the commits are already in git. If a day grows past a screen,
the usual cause is a decision sitting in the log that belongs in an ADR.

## 2026-11-07

- **The decision table in the architecture document stopped at 07.** Three ADRs were added today and
  the table was missed every time, while the README and the folder both said ten. The table now lists
  08, 09 and 10 — with 09 marked superseded, since it is the one ADR that a later one replaced.
- **`scripts/check-adr-index.py` exists so the next one cannot be missed.** It checks both directions
  in both languages (a record missing from the table, a table row pointing at nothing) and the
  `adr/01-NN` range in the documentation index. Demonstrated failing by removing a row, then passing
  again once restored.


- **`firmware/main/src/` split into five files so the lead can change the rig without reading all of
  it**: `config.h` (pins, timings), `rig_state.h` (what the rig knows), `screen.cpp` (the layout),
  `protocol.cpp` (the serial grammar), `main.cpp` (wiring). Adding a screen state is three edits, none
  of them in `main.cpp`.
- **CI now compiles the firmware.** A second job caches the ESP32 toolchain on `platformio.ini` and
  runs `pio run`, so a syntax error surfaces on a pull request instead of on the bench.
- **The firmware still has not compiled, and now we know why.** PlatformIO cannot unpack
  `framework-arduinoespressif32-esp32s3-libs` on this machine: the package contains paths longer than
  Windows' 260-character limit, and the unpack fails with `WinError 3`. That is a platform limit, not a
  permission one — 5.7 GB of toolchain was downloaded and then removed. CI runs on Linux, where the
  limit does not exist, so the first compile will happen there.


- **The rig has a screen, and it says something.** A 0.96" OLED from the STM32 kit shows connection
  state, turbidity, the quality score and the verdict; two LEDs pulse green for a pass and yellow for a
  retake. Everything on it is ASCII — a Chinese font would cost one to two megabytes of flash for the
  fourteen words the screen needs.
- **A retake shows its reason, not just its score.** `LOW LIGHT`, `BLUR`, `COLOR CAST` come from the
  three components the quality score already computes. A number without a cause gives the operator
  nothing to fix.
- **The firmware exists and has never been compiled.** `firmware/main/` holds a PlatformIO project and
  a state machine, written without a toolchain on the machine. That is recorded in
  `firmware/README.md` rather than discovered on the rig — the first build will produce errors, and
  pretending otherwise would cost an afternoon.
- **The turbidity read is a guess and is labelled as one.** Two bytes, big-endian, address 0x49; the
  ME2100A-IIC datasheet has not been checked against it. A plausible but wrong reading is worse than a
  blank one, so the screen shows `--` until a value arrives.


- **The fill light is now something the program can actually control.** The architecture diagram and the
  parts list had said the MCU handles dimming since the beginning; the procurement document then chose
  two desk lamps, and the two statements could not both be true. A 12 V LED board, an IRF520 module and
  its own supply replace them — about ¥55, no mains switching next to a water tank. The reason it
  matters is not tidiness: the quality score reads brightness, so a light that moves between runs makes
  the score look broken.
- **Superseded the same day: the lamp on hand is already a DC source.** ADR 09 bought a 12 V strip
  because a mains lamp cannot be controlled and would flicker. The lead's Midea MT-10T4 is USB-powered,
  4000 K, 10 W and advertised as flicker-free — a DC source, so the flicker argument never applied. The
  strip, MOSFET, adapter and lead are withdrawn (ADR 10), the parts list returns to ¥377.42, and the
  architecture diagram stops claiming the MCU drives the light. Two rules carry the decision instead of
  hardware: run the lamp on USB rather than its battery, and tape over the dimmer once it is set.
- **Two acceptance checks added to the rig, both cheap to run**: PWM from 30 % to 80 % must raise
  brightness monotonically, and the light board, MOSFET and ESP32 grounds must show continuity. A
  floating ground gives a gate signal that switches only sometimes, which is the kind of fault that
  survives a rehearsal and fails on the day.
- **The assembly order now says to skip the level shifter if the sensor accepts 3.3 V.** One module and
  eight wires fewer is one less intermittent joint, and the sensor's supply has not been measured yet.

## 2026-11-06

- **Prototype screen 2 delivered** (`web/templates/home.html`): four KPI cards, a hand-drawn 7-day
  SVG trend, and the recent-session list. No chart library, deliberately: ECharts is not vendored and
  screen 6 needs a team decision before two people pull it in different ways.
- **Two stale fields found in lane A and fixed.** `fixtures.js` and `capture.html` still carried
  `water_temp_c` and `turbidity_ntu`, both removed in SRS V1.4. The change map in `docs/INDEX-en.md`
  §4 lists "field name → mock data" exactly for this; nobody had run it.
- **P1-03 capture module written**: `server/app/vision/quality.py` scores a frame, `capture.py` owns
  the device, ids, paths and manifest, and the CLI verifies its own output. 18 tests.
- **That verification found a real defect.** Scores were computed on the in-memory frame, so JPEG
  smoothing changed the stored file's score — 25 against 29 on low-sharpness frames. The score is now
  taken from the encoded bytes, and a borderline-frame regression test fails without the fix.
- **The camera half is unverified here.** This environment has no usable device: DirectShow cannot
  open by index and FFmpeg lacks libavdevice. The error path behaves correctly, so the device and
  exposure-lock steps still need a machine with the camera — the lead's laptop, or P1-06.
- **Page self-check added** (`tests/test_pages.py`, 19 cases): dead links, script-requested ids that
  the markup never defines, duplicate ids, pages that skip the shared shell, and menu entries that
  point nowhere. Proven by planting all three faults in one template and watching them fail.
- **`scripts/make_samples.py` added**: deterministic synthetic frames for running the capture pipeline
  where no camera exists. Five of them ran the whole path end to end and the manifest verified.
- **`python scripts/test_exposure.py` now exists.** The procurement document had told people to run it
  for weeks; the file never did. It answers three questions in order: does the device open, does the
  picture actually change when the exposure property moves, and do 20 pinned frames stay inside the
  10 % spread. Exit codes separate "no camera" (2) from "camera fails the check" (1), so nobody
  mistakes an unplugged cable for a broken module.
- **Branch deletion moved to a repository setting.** `gh pr merge --auto --delete-branch` does not
  work — the flag is read when the merge is *requested*, and with auto-merge the merge happens
  minutes later. A `pull_request: closed` workaround was tried and did not fire either: GitHub does
  not cascade workflow runs from events raised by `GITHUB_TOKEN`, and the bot is what merges. The
  setting *Settings → General → Automatically delete head branches* applies regardless of who
  merges, so the workaround is deleted rather than left looking useful.
- **Copy pass over the thirteen pages.** The mechanical layer was already clean — no doubled
  characters, no half-width punctuation inside Chinese, no missing spaces around Latin text — so the
  edits were about meaning, all in the interface language, which is Chinese by requirement:
  - the drawn box is now a *target* box, not a *detection* box: the pipeline does detection, the
    artefact on the image is a target, and the data table is named for the target;
  - an out-of-range field now says it will be marked and refused, rather than "marked red on the
    spot", which is developer shorthand for a validation pattern;
  - the seed hint and the hard-example caption were split into two sentences each, because a colon
    list of three conditions inside one line reads as homework;
  - the capture button reads "end capture" instead of a bare "stop", which could equally mean
    pausing the preview.
- **Deferred: the `P-xx` eyebrow above each page title.** It is development scaffolding, and the
  request is to remove it at design polish. It stays until then because it is the only anchor tying a
  screen to its row in SRS §5.2, and reviewers are still tracing screens to requirements.
- **Contract closed from 18 to 42 routes.** The frontend was calling 24 routes that the contract never
  named; a route the contract does not describe is a route the backend cannot build against. Each
  route now carries the requirement it serves and inherits that requirement's priority from SRS
  Table 3-1, so scope is read from the SRS instead of counted in the contract.
- **`P1-02` redefined the same way.** Its "18 routes" was a snapshot of the old table; it now says
  every contract route is mounted, P0 ones return real data, the rest return 501 in the envelope.
  The count is gone from `PLAN.md` — today's lesson about brittle numbers, applied before it bit.
- **Three box fields and the review body are now in the contract**: `object_id`, `is_manual`,
  `review_status` already existed in the data model, and a reviewer cannot edit a box without a
  stable handle. The review POST carries the whole corrected set rather than a diff, because the
  canvas is the authority and a diff would have to merge against a version that may have moved.
- **Role mapping settled in the glossary**: the contract's `observer` is the SRS collector role. Renaming the
  code would touch the seed, the contract and the frontend for no functional gain.
- **The camera device path now has tests, written against a fake `VideoCapture`.** Everything tested
  before went through the image-folder source; `open`, `lock_exposure` and `read` had never run under
  a test. Ten cases cover backend fallback, the "tried all three" message, a lock that holds, a lock
  that drifts (and says so), a read that returns nothing, and a driver with no exposure control. Two
  deliberate mutations — forcing the lock verdict to true, swapping the backend order — each turned a
  test red, so the suite is not passing vacuously. Tomorrow's arrival now has one unknown left: does
  the device open at all.
- **P1-05 delivered: 49 cases over the 36 acceptance items.** Written before the features, not after:
  a case that cannot run yet still fixes what "done" means, which is the only moment anyone can argue
  about it cheaply. Twelve items carried more than one case, because they hid two independent claims —
  a lockout has a duration and a storage format, a capture source has an absence and an idempotence
  rule. Every case states precondition, steps, expected and `not implemented`, and each names the
  acceptance item it serves, so a failure lands on a case id rather than on a memory.
- **P1-02 started and most of it landed, by hand, because the lane owner is away until Monday.** The
  skeleton is real: settings, the response envelope and its error codes, JWT with server-side role
  guards, the database session per request, and all 42 contract routes mounted. Twenty-one of them
  answer with data read from the nine tables — accounts, sessions, frames, tasks, review, hard
  examples, statistics, models, experiments, species, messages, the audit log.
- **What answers 501, and why it is 501 rather than fake data.** Single-frame detection, batch
  execution and the same-frame comparison need a weight file that does not exist yet. Datasets and
  reports need something worse than effort: **the data model has no table for either**, and PATCH
  params has nowhere to persist. Four routes therefore say what is missing instead of pretending.
- **The contract test is the one that will age well.** It parses `docs/api-contract-en.md` and fails
  when a route in the document is not mounted, so the contract stays the list of routes rather than a
  description of last week. It also asserts the count is 42 — a deliberate tripwire for the next
  person who edits one side only.
- **Two drifts found and reported rather than fixed** (lane B): the data model has no `dataset`,
  `report` or `param` table although the contract has four routes and a PATCH for them; and the
  contract's frame object implies persisted quality *components* while `media_asset` stores only the
  score and the flag. Capture returns the components it just measured and stores the score; the
  storage question is the data model owner's.
- **Four tables added, and the nine-table decision revised rather than quietly worked around.** SRS
  V1.5 records it and ADR 08 explains why: a snapshot exported before any experiment has nowhere to
  live, a report history cannot be filtered out of a directory, and a parameter change has to persist
  and stay audited. `dataset`, `dataset_item`, `report` and `sys_param` now exist, `EXPECTED_COLUMNS`
  has thirteen entries, and the schema check caught the first defect of its own making — a declared
  column count that did not match the model.
- **Exports and reports are real.** A snapshot splits deterministically by seeded group, and the group
  never straddles two splits, so two exports of the same frames with the same seed produce the same
  assignment — that is AC-18, tested rather than asserted. A report writes a Markdown document from
  the same queries the dashboard uses, and keeps the period, template, basis and model version in a
  row the history can be filtered by.
- **One uncertainty left standing, stated rather than hidden:** SRS §7 asks for Word or PDF and the
  app writes Markdown, because neither format is reachable without a rendering dependency. The row
  shape already carries everything a later export step needs.
- **Two permission holes in the skeleton, closed the same day.** `PATCH /api/params` had no role guard,
  so any signed-in account could change the retention period; `POST /api/review/frames/{id}` was open
  to the collector role, which owns the camera and not the judgement. Both now require the roles SRS
  FR-M1-02 names, and the role test covers three guarded surfaces instead of one — a happy path never
  finds the surface somebody forgot to guard.
- **A nightly run on `main`, because the post-merge run was silently skipped.** A push made with
  `GITHUB_TOKEN` does not start a workflow, and every merge is performed by the auto-merge bot holding
  exactly that token. The two events therefore never ran, and a pull request that passed on its own
  branch but broke an earlier one would have gone unnoticed. A schedule needs no secret and cannot
  expire, which is why it was chosen over a personal token.
- **`docs/handover-en.md` now carries the work that changed hands**, with acceptance written as
  checks rather than adjectives. The `P1-02` section opens by listing what already exists, because the
  most expensive mistake available on Monday is rebuilding it; the frontend section turns three
  opinions into two mechanical tests and one page change. Items are deleted when accepted — a handover
  document that lists finished work stops being read.
- **The report is Markdown, and SRS V1.6 says so.** Scenario 5, FR-M5-04 and §7 described Word or PDF
  output that this project was never going to produce; the repository keeps Markdown and converts
  nothing. §7 now records that the Word, PDF and Excel column is a conversion target, not a second copy.
- **CI moved to a daily 12:00 run** rather than a nightly one, so a red build is seen during the day
  it happened rather than after a night of silence.
- **The five blocked directories are gone**, by asking for the access instead of designing around it.
  The temporary ruff exclude is removed; the principle is now `AGENTS.md` §4.7.
- **Prototype screen 6 done:** stats page with four hand-rolled SVG charts (species donut, daily
  trend line, interception bars, correction stack), report/export buttons answering with a toast,
  and both demo-data notices (header badge, footer note). No chart library — ADR 05 keeps front-end
  assets local.
- **Mock:** `STILLS` uses DUO ground-truth boxes normalised onto four 1280x720 test frames, so every
  box sits on a real target; one deliberate 0.42-confidence false positive (rock read as a sea
  cucumber) drives the review demo. Stats fixtures are hand-set and share the dashboard figures
  (`DASHBOARD.daily` is `STATS_TREND`, `rejected_today` is today's intercepted count), so screens
  2 and 6 cannot disagree. `/stats/species` and `/stats/quality` follow the contract; trend and
  corrections are provisional.
- **Flagged for later, not fixed here:** the prototype badge lives in `stats.html` only — the other
  pages need it from the shared shell; and `.av-page-actions` stretches non-button children, so a
  badge's text sits high unless it centres itself.
- **Prototype screens 3-5 delivered** (#43 shared layer, #44 capture, #45 review, detail in the PR
  that adds this line). The walk-through clicks end to end: start capture, open a frame from the
  strip, see the 0.42 box flagged, go to review, drag and relabel it, submit, and the detail page
  shows the change. Box overlay, class colours and the low-confidence style live in one module,
  `web/static/js/boxes.js`, so the three screens cannot drift apart.
- **The badge item above is resolved**: the shell now puts "prototype · mock data" on every page.
- **Page ids now follow SRS §5.2.** Screen 6 had taken P-06, which the SRS gives to the
  detection-result page (screen 4); statistics is P-10. The seven pages the prototype skips stay in
  the menu, greyed and tagged P2, as prototype §1 asks.
- **The mock holds a walk-through together.** Every page load restarts it, so captured frames and
  submitted reviews are kept in `sessionStorage`. Live frames follow a fixed quality script
  (86, 82, 87, 79, then 49) instead of the seeded dice, which had opened the demo on a retake.
- **Open for lane B:** fields the screens need that the contract does not list yet — `image_url` on a
  frame; `object_id`, `is_manual`, `review_status` on a box (all in the data model); the review body
  `{ objects }` and its `{ count_before, count_after }` reply.
- **Unverified here:** the "try the laptop camera" button. The Browser pane blocks camera access, so
  only the failure path (a toast, the samples stay) was seen; the real camera needs a check in Chrome.
- **Data model completed before P1-01.** data-model carried only the 3 core tables while SRS 4.2
  held the full dictionary — with stale names (`asset_code`/`species_code`/`x_center`) that
  disagreed with api-contract and the mocks. data-model now defines all 9 tables field by field
  (media_asset 18, detect_object 19); the SRS core tables were synced to it: `frame_id`,
  `captured_at`, `class_code`, `x`/`y`/`w`/`h`, `map50`/`map50_95`. `detect_task.class_filter`
  stores a JSON array — the one documented exception to the no-lists rule.
- **P1-04 done: all 13 pages open on mock data** (#48 tasks, #49 hard samples, #50 dataset export,
  #51 reports, #52 models, and system administration in the PR that ticks the box). No menu entry is
  greyed any more. Checked page by page: each opens, the menu highlights the right entry, nothing
  scrolls sideways at 1280 or 1920, and all 31 links the pages render resolve.
- **Mock data for those pages lives in `web/static/mock/catalog.js`**, apart from `fixtures.js`.
  Figures are tied to what already exists: DS-V2 is the P0-01 split, E0 and E3 are the SRS scenario-4
  numbers, the report preview reads the same stats calls as screen 6, monitoring counts the task list.
- **Open for lane B:** every collection route these pages call is provisional and marked in
  `api.js` — tasks, hard samples, datasets, reports, experiments, species, users, parameters,
  monitoring, logs, messages. Roles use the contract codes; `observer` is read as the SRS capture
  operator, which nobody has confirmed.
- **Known limitation:** after a rollback on P-12, the dashboard and report footer still say v8n-E3 for
  that tab; their figure is fixed in the fixtures.
- **The screen 6 review answered** (`fix/stats-review`): the P-10 menu label now matches the SRS page
  list — statistics dashboard, not statistics-and-reports; the report side stays with P-11 (the id
  itself was already corrected in #43). `.av-page-actions` centres its children, so no badge needs
  inline styles. The four Chinese species names live once in `web/static/js/species.js`, imported by
  the charts and the box overlay (`boxes.js` re-exports it as `CLASSES` for the five pages that
  already import from there). The overlay now clamps each box to the frame at draw time, so an
  annotation that pokes past the image edge can never render outside it. Two other review items
  were already resolved by #43-#46 (P-10 id, badge in the shell).
- **P1-01 delivered** (`feat/init-db`): the nine tables exist as SQLAlchemy models in
  `server/app/models.py`, transcribed column by column from the dictionary, and
  `scripts/init_db.py` creates them and seeds the four species on an empty database. The DSN
  order is `--dsn`, then `$DB_DSN`, then a gitignored SQLite default — no path lives in code
  (architecture §8). `EXPECTED_COLUMNS` mirrors the dictionary's column counts and the script
  fails loudly if model and dictionary ever drift apart. Tests run on SQLite (CI stays
  database-server-free) and once as a subprocess, because PLAN words the acceptance as "the
  script runs". Seed categories follow SRS §3.5.1: three economic species, starfish as the pest.

## 2026-11-05

- **Rig design settled (P0-06).** A desk lamp instead of purchased LED bars: one lamp above and 45°
  forward, tracing paper as a diffuser, a white card reflector on the dark side. It removes a whole
  5 V power domain — the rig now runs off one USB cable.
- **Single lamp first, a second only if it fails.** Criterion is the left/right brightness ratio: at
  0.7 or above keep one lamp, between 0.5 and 0.7 adjust the reflector or move the lamp, below 0.5 add
  the second — same colour temperature, or the wall goes two-tone.
- **Rig acceptance moved to P1-06**, because none of it can be measured before the parts arrive:
  ratio ≥ 0.7, a 5 cm target ≥ 45 px at 640 input, no flicker filmed by a phone, 20-frame mean
  brightness spread < 10 %.
- **Order placed, nine items, ¥377.42**: JD eight (camera, glass tank, polarising sheet, ESP32-S3,
  level shifter, jumpers, 1660-hole breadboard, GH1.25-to-Dupont cable) and LCSC one (turbidity
  module). `P0-03` ticked; the list is frozen in `docs/procurement-en.md`.
- **Three items came off the draft at checkout.** The 405-hole breadboard, because the ESP32 and the
  shifter do not fit on it; the button, because a through-hole push button is already on hand; the
  tinned single-ended GH1.25 cable, because a tinned end has nothing to plug into. The draft had
  sixteen items and ¥382.42.
- **Camera exposure confirmed lockable by the seller.** The fixed-lighting fallback is off the table
  and SRS 2.4.3 stands as written. `test_exposure.py` still runs on arrival, now as evidence rather
  than as a gate.
- **SRS V1.4 closes the field question.** `water_temp_c` deleted; `turbidity_ntu` renamed
  `turbidity_rel` (0–100, 0 clear) because the sensor reports a reflectance index, not NTU. Table 2-3
  rebuilt against the actual rig, api-contract and data-model follow in both languages.
- **P0 closed.** The review is recorded as the four internal rounds that happened, not an external
  one: the calendar is not fixed and the team drives the schedule, so waiting would have stalled
  coding for nothing. Annex B now carries the approver for V1.1 to V1.4.
- **Review bar adopted.** An item passes when a stranger holding only the document can decide whether
  it holds; anything that leaves the decision to the author is a must-fix. A round is capped at 90
  minutes and does not start above 15 must-fix items — that is debugging, not review.
- **Demo format fixed.** Live rig first, screen recording always prepared. The recording is not
  optional: a live demo that dies has nothing behind it.
- **Documentation set rebuilt.** An index, owner lines with revisit triggers, a change map in the PR
  template, ADR 07 on local-first verification, and a CI check for Chinese in English documents.
- Lighting is recorded here and later in `dataset-stats.json`, deliberately **not** in `site`, which
  is a monitoring location — appending `-L1` would split the stats.

## 2026-11-04

- P0-04 done: design tokens, shared shell, three pages navigate (#7). P0-02 environment lock (#11).
- P1-04 started ahead of GATE P0: lane C does not depend on the server; lead to confirm.
- P1-04 so far: `api.js` and contract-shaped mocks (#8), capture and frame pages (#9), visual language
  (#10); 4 of 13 pages.
- Open: provisional endpoints in #8 for lane B; SRS vs contract on login token, captcha and frame rate
  for lanes A/B.
- Next: the remaining nine pages, one PR per domain; the last one ticks P1-04.
- P0-02 merged: dependencies pinned for Python 3.11 (#11).
- P0-01: DUO in place — 7782 images cleaned, split and counted; test set is 1111.
- DUO carries no video ids and already de-duplicates frames, so "split by video" is implemented as
  perceptual-hash grouping (dhash64, hamming <= 3, largest group 4).
- Open issues: echinus has 24x the boxes of chlamys; debris class has no images yet.
- Next: find a debris source, finish the three-machine install check.
- Scope change, later on 11-04: **marine debris is dropped**. The line above is superseded — the class
  has no public dataset, and the self-collected route cost two days for the one class that could not
  be defended in the metric table. SRS V1.3 records it in annex B; lane C still has to remove it from
  the frontend.

## 2026-11-03

- Repository created: conventions, CI, branch protection (#1, #2).
- `PLAN.md` in place: five phases, 27 tasks, five gates (#3).
- SRS reached V1.2: five classes, hardware list, per-class metrics.
- Blocked: P0-01 — dataset download links are dead, mirrors under review.
- Next: P0-02 environment lock, P0-03 hardware order.
