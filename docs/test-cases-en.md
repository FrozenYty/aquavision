# Test cases

> Chinese version: [test-cases-zh.md](test-cases-zh.md). This file is the source of truth.
> Owner: @IkeaFyj · Revisit when: an acceptance item changes, or a case is executed

Cases for the 36 acceptance items in SRS Table 8-1, with the evidence that exists for each one today.
**Every case carries a verdict**: `automated` when a test in `tests/` asserts it, `manual` when a person
has to run the steps, `uncovered` when neither a test nor the feature exists. The verdicts were
established on 2026-11-12 by reading the tests, not by trusting a case's title: a test that exists but
does not assert the claim was not counted as coverage, and whatever it leaves to a person is named on
the case's `Where` line.

## 1. Purpose and scope

One case per acceptance item, and a second case wherever one item hides two independent claims. The
SRS is the authority for what must hold; a case says only how a person proves it.

The cases are the checks that need a running system, a database, a trained model or a person looking at
a screen; a case is not a restatement of a unit test. The `Where` line does point at the test that
covers a case, because that is where the evidence lives and a reviewer has to be able to open it.

## 2. How a case is written

| Field | Meaning |
|---|---|
| Case | Stable identifier, `TC-<AREA>-<serial>` |
| AC | The acceptance item it serves, from SRS Table 8-1 |
| Precondition | What must be true before the first step; if it is not, the result is not a failure |
| Steps | The shortest path that exercises the claim |
| Expected | What is observed when the item holds — stated so a stranger can decide |
| State | `automated` when a test asserts the claim; `manual` when a person must run it; `uncovered` when neither the test nor the feature exists |
| Where | The evidence: the test as `file::function`, or the manual step, or what is missing |

An `automated` verdict is only as good as the test it names. The test must exist, must drive the claim
through the real code, and must fail when the behaviour regresses. A clause the named test does not
assert is written after `Not asserted:` on the same line; a clause with no implementation at all is
written after `Not implemented:`. Both stay visible rather than being promoted into a claim nobody
checked.

## 3. Cases

### 3.1 Account and permissions

**TC-AUTH-01** — AC-01 · sign-in lockout · automated
- Precondition: one enabled account, known password.
- Steps: submit a wrong password five times; then submit the correct password.
- Expected: the fifth failure returns a lockout message with the remaining seconds; the correct
  password during the lock is refused with the same remaining time.
- Where: `tests/test_api_skeleton.py::test_wrong_password_counts_down_then_locks` — the countdown, the
  lock code, and the correct password refused while locked. Not asserted: the remaining-seconds
  sentence a later attempt receives; the lock itself reports its duration in minutes.

**TC-AUTH-02** — AC-01 · password storage · manual
- Precondition: the account from TC-AUTH-01 has signed in at least once.
- Steps: read the `password_hash` and `salt` columns in the database.
- Expected: neither contains the password; the hash differs for two accounts with the same password.
- Where: manual — step 2, against a seeded database. No test reads either column, and the fixtures hash
  the same password many times without comparing two results.

**TC-PERM-01** — AC-02 · role boundary · automated
- Precondition: signed in as the collector role; one registered model version exists.
- Steps: call `POST /api/models/{id}/activate` with the collector's token.
- Expected: 403 in the standard envelope; a rejection row appears in the operation log.
- Where: `tests/test_forbidden_is_logged.py::test_a_route_level_guard_logs_the_attempt_too` — the 403
  and one `forbidden` row naming the user and the route. The wider matrix is
  `tests/test_permission_matrix.py::test_the_matrix_is_honoured_in_both_directions`.

**TC-PERM-02** — AC-02 · unauthenticated access · automated
- Precondition: no token.
- Steps: call `POST /api/capture/sessions/{id}/frames`.
- Expected: 401 in the standard envelope; no frame is written.
- Where: `tests/test_capture_local_only.py::test_a_remote_call_without_a_token_is_still_a_401` — the 401
  and its envelope code, answered before the locality guard. Not asserted: "no frame is written" —
  the refusal is checked, and the frame list is never read back.

**TC-ACC-01** — AC-03 · disable an account · manual
- Precondition: an account with detection history; an administrator session.
- Steps: disable the account; sign in with it; query its historical results as the administrator.
- Expected: the sign-in is refused; the history is still returned.
- Where: manual — the case's three steps. `POST /api/users/{id}/status` exists and flips `status`, but
  no test calls it with `status: 0`, signs in afterwards, or queries the history.

**TC-ACC-02** — AC-03 · duplicate phone · uncovered
- Precondition: one account already uses a phone number.
- Steps: create a second account with the same number.
- Expected: refused with a message naming the conflict; no new row appears.
- Where: uncovered — the contract has no account-creation operation, so there is no route to post a
  second account to and no uniqueness rule to exercise.

**TC-AUD-01** — AC-04 · audit values · automated
- Precondition: one frame with a review pending.
- Steps: delete one box and submit the review; query the operation log for that frame.
- Expected: an entry carrying the operator, the time and the before/after values of the change.
- Where: `tests/test_review_versions.py::test_two_submissions_appear_newest_first_with_their_counts_and_authors`
  — operator, timestamp and the before/after box counts read back from the stored log. Not asserted:
  the same rows through `/api/logs`; the test reads them through the version route.

**TC-AUD-02** — AC-04 · no deletion path · manual
- Precondition: at least one log row exists.
- Steps: exercise every endpoint in the contract that could plausibly remove data.
- Expected: no route deletes a log row; the row count never decreases outside retention.
- Where: manual — walk the 45 operations in `docs/api-contract-en.md`. No test asserts the absence of a
  deleting route, and `/api/demo/reset` does clear `sys_log` by design (a rehearsal, not retention).

### 3.2 Capture

**TC-CAP-01** — AC-05 · no source without a camera · automated
- Precondition: the capture device is disconnected.
- Steps: start the system; look for any path that would put an image into the detection queue.
- Expected: none exists; the interface reports the device as unavailable and produces no record.
- Where: `tests/test_ws_capture.py::test_a_server_without_a_camera_closes_with_1011` — the live socket
  closes and sends no frame, and `tests/test_api_skeleton.py::test_detect_frame_rejects_a_frame_that_never_came_through_capture`
  — detection refuses an image that did not come through capture. Not asserted: the page's own
  unavailable state.

**TC-CAP-02** — AC-05 · timestamp tolerance · automated
- Precondition: the capture device connected.
- Steps: submit a frame whose capture time is six seconds behind the server clock.
- Expected: refused with the reason recorded; no row is written.
- Where: `tests/test_api_skeleton.py::test_a_frame_with_a_skewed_clock_is_refused` — the refusal code and
  the five-second rule in the message. Not asserted: that no row was written (the refusal precedes the
  insert).

**TC-CAP-03** — AC-05 · idempotent frames · automated
- Precondition: one session open.
- Steps: submit the same frame twice with the same identifier.
- Expected: one row; the second call reports success without creating a duplicate.
- Where: `tests/test_api_skeleton.py::test_capture_scores_the_frame_and_is_idempotent` — the same
  `frame_id` twice, then one row in the list.

**TC-CAP-04** — AC-06 · scheduled capture · uncovered
- Precondition: a schedule of six captures at ten-minute intervals.
- Steps: advance the clock through the schedule; count the batches.
- Expected: six batches, each with the planned frame count.
- Where: uncovered — there is no schedule: no route, no table and no timer anywhere in `server/`.

**TC-CAP-05** — AC-06 · failed run · uncovered
- Precondition: a schedule whose device becomes unavailable before the third trigger.
- Steps: let the schedule run to completion.
- Expected: the third run is marked failed with a reason; the earlier batches are untouched.
- Where: uncovered — the same missing schedule. Nothing records a failed trigger.

**TC-CAP-06** — AC-07 · quality gate · manual
- Precondition: the device can be defocused on demand.
- Steps: capture one defocused frame; capture one sharp frame.
- Expected: the defocused frame scores below 60, is stored, is marked needs-retake and does not enter
  the detection queue; the sharp one does.
- Where: manual — the score and the verdict are covered by
  `tests/test_capture.py::test_flat_frame_is_a_retake` and
  `tests/test_params_live.py::test_the_capture_verdict_uses_the_threshold_in_force`, but the queue half
  fails today: `/api/detect/batches` selects every frame not yet detected and never filters
  `quality_flag`, so a needs-retake frame does enter a batch.

**TC-CAP-07** — AC-07 · retake marking · uncovered
- Precondition: one frame marked needs-retake.
- Steps: trigger a retake; open the batch.
- Expected: the retake is its own record in the same batch, flagged as a retake.
- Where: uncovered — no operation triggers a retake. `is_retake` is written as 0 on every capture and
  no route ever sets it.

**TC-CAP-08** — AC-08 · combined search · automated
- Precondition: at least three batches across two sites and three dates.
- Steps: filter by site, date range and quality together; then open a batch.
- Expected: only matching batches return; opening one lists its frames; selecting frames carries the
  selection into job creation.
- Where: `tests/test_frames_filters.py::test_the_four_filters_combine_as_an_intersection` and
  `::test_the_total_counts_the_filtered_set_not_the_page`. Not implemented: carrying a frame selection
  into job creation — a batch is created from a count, not from selected frames.

**TC-CAP-09** — AC-09 · cleanup · uncovered
- Precondition: intermediate files older than the retention period.
- Steps: run the cleanup with and without the original-images option.
- Expected: references to deleted files are nulled and disk usage falls; originals survive under the
  default policy.
- Where: uncovered — there is no cleanup operation. `retention_days` is stored as a parameter and read
  by nothing that deletes a file.

### 3.3 Detection

**TC-DET-01** — AC-10 · immediate detection · manual
- Precondition: one registered frame; the online model loaded.
- Steps: trigger detection and time until boxes are visible.
- Expected: boxes on screen within three seconds; the elapsed time is recorded with the result.
- Where: manual — a stopwatch on the deployment machine for the three-second half. The endpoint and the
  recorded latency are covered by
  `tests/test_detect_real.py::test_one_real_inference_matches_a_manual_run_of_the_same_weights`, which
  needs torch and the development database.

**TC-DET-02** — AC-10 · source enforcement · automated
- Precondition: a local image that never passed through capture.
- Steps: attempt to submit it for detection by any route.
- Expected: refused with a source-mismatch message.
- Where: `tests/test_api_skeleton.py::test_detect_frame_rejects_a_frame_that_never_came_through_capture`
  — an unknown frame id is a 404 and no box is invented.

**TC-DET-03** — AC-11 · batch progress · automated
- Precondition: a batch of 100 frames.
- Steps: start detection; watch progress; cancel at frame 40; retry one failed frame.
- Expected: progress advances frame by frame; the cancel takes effect within five seconds and stops
  adding results; the retry produces a new result for that frame only.
- Where: `tests/test_worker.py::test_queue_runs_100_frames_to_done`,
  `::test_cancel_at_frame_40_stops_within_five_seconds` and `::test_failure_is_retryable`; progress read
  through the API while the task runs is
  `tests/test_batch_acceptance.py::test_progress_is_queryable_while_a_batch_task_runs`.

**TC-DET-04** — AC-12 · threshold effect · manual
- Precondition: one frame with several detections near the threshold.
- Steps: run with confidence 0.5, then 0.2.
- Expected: the second run returns more boxes on the same frame.
- Where: manual — the case's two runs against the loaded model. No test compares two thresholds on one
  frame; `tests/test_worker.py::test_a_task_runs_with_its_own_inference_parameters` only shows the
  parameters reach the model.

**TC-DET-05** — AC-12 · frozen parameters · manual
- Precondition: a job that has already run.
- Steps: attempt to change its confidence threshold through every route in the contract.
- Expected: no route allows it; the recorded parameters still match what was used.
- Where: manual — walk the contract. No test asserts the record is immutable. Adding a mutating route
  fails `tests/test_permission_matrix.py::test_the_matrix_covers_every_mounted_route`, but that guards
  the route set, not this claim.

**TC-DET-06** — AC-13 · count consistency · automated
- Precondition: a job with results across all four classes.
- Steps: read the per-class counts; filter by one class.
- Expected: the total equals the number of list rows; filtering updates counts and chart together.
- Where: `tests/test_api_skeleton.py::test_boxes_come_back_by_frame_id` — the counts equal the rows
  returned and the same box set detection wrote. Not asserted: the single-class filter and the chart.

**TC-DET-07** — AC-14 · export · automated
- Precondition: a job whose page shows N results.
- Steps: export CSV; open it in Excel.
- Expected: N data rows plus a header; Chinese class names render correctly; coordinates are
  normalised.
- Where: `tests/test_result_csv.py::test_comma_quote_newline_and_chinese_survive_a_round_trip`,
  `::test_the_bytes_are_utf8_so_chinese_opens_in_excel` and `::test_the_header_is_the_servers_field_names`.
  Not asserted: "coordinates are normalised" — the columns are copied from the box unchanged.

### 3.4 Review

**TC-REV-01** — AC-15 · review edits · automated
- Precondition: a frame with one false positive and one miss.
- Steps: delete the false box; draw a box for the miss; submit.
- Expected: the count falls by one then rises by one; the automatic result remains viewable.
- Where: `tests/test_api_skeleton.py::test_review_submission_returns_the_documented_result` — the added
  counter; `tests/test_review_versions.py::test_rollback_marks_removed_boxes_rejected_instead_of_deleting_them`
  — a dropped box stays a queryable row. Not asserted: one submission that both deletes and draws, with
  both counters checked.

**TC-REV-02** — AC-16 · versions and rollback · automated
- Precondition: the frame from TC-REV-01.
- Steps: submit a second review; roll back to the earlier version.
- Expected: two versions exist; after rollback the result matches the target version exactly and both
  versions remain listed.
- Where: `tests/test_review_versions.py::test_two_submissions_appear_newest_first_with_their_counts_and_authors`
  and `::test_rollback_restores_the_target_box_set_as_a_new_version` — the restored set is compared box
  by box, class and coordinates.

**TC-REV-03** — AC-17 · hard-example pool · automated
- Precondition: the corrected frame from TC-REV-01.
- Steps: open the pool; remove one entry.
- Expected: the frame is present with source `corrected`; after removal it no longer appears.
- Where: `tests/test_hard_samples.py::test_a_review_correction_enters_the_pool_with_its_origin`,
  `::test_the_pool_lists_each_frame_once_and_keeps_the_origins_filterable` and
  `::test_removal_empties_the_pool_entry_and_keeps_the_evidence`.

**TC-REV-04** — AC-18 · reproducible export · automated
- Precondition: a sample range containing one unreviewed frame.
- Steps: export twice with the same seed; then export a range with the unreviewed frame included.
- Expected: the two file lists are identical; the third export is refused and names the unreviewed
  frame.
- Where: `tests/test_api_skeleton.py::test_dataset_export_is_deterministic_and_keeps_groups_together` and
  `::test_export_without_reviewed_frames_is_refused`; the burst rule is
  `tests/test_datasets.py::test_a_snapshot_keeps_a_burst_out_of_two_splits`. Not asserted: the refusal
  names the condition, not the offending frame.

### 3.5 Statistics

**TC-STA-01** — AC-19 · basis switch · automated
- Precondition: results with both automatic and reviewed states.
- Steps: open the composition chart; switch the basis.
- Expected: the figures change and the stated basis changes with them; shares sum to 100 %.
- Where: `tests/test_api_skeleton.py::test_stats_figures_follow_the_rows_detection_and_review_wrote` —
  both bases, the figures moving with the basis, and the shares summing to one.

**TC-STA-02** — AC-20 · distribution · uncovered
- Precondition: at least two sites, one with no data.
- Steps: open the heat map; compare it with the ranking table; select the empty site.
- Expected: heat map and ranking agree; the empty site shows an empty state, not a blank chart.
- Where: uncovered — there is no heat map and no site-distribution figure in the pages or the contract;
  a site appears only as a filter column.

**TC-STA-03** — AC-21 · trend arithmetic · uncovered
- Precondition: two periods of data, the earlier one missing.
- Steps: open the trend; compute one rate by hand.
- Expected: the computed rate matches the displayed one; the missing baseline shows a dash and no
  conclusion is drawn.
- Where: uncovered — the trend chart is daily capture volume. Nothing compares two periods and no rate
  is computed, so there is no arithmetic to check.

**TC-STA-04** — AC-22 · report fidelity · manual
- Precondition: a dashboard with non-zero figures.
- Steps: generate a report; compare figures; read the footer.
- Expected: report figures equal the dashboard; the footer states the model version and the basis.
- Where: manual — the comparison in step 2. `tests/test_api_skeleton.py::test_report_is_generated_from_the_same_figures_as_the_dashboard`
  asserts the footer labels and the file's title, not that a figure equals the dashboard's.

### 3.6 Models

**TC-MOD-01** — AC-23 · registration guards · automated
- Precondition: one registered version.
- Steps: register a second version without metrics; then register one with an existing name.
- Expected: both refused, each naming the missing or conflicting field.
- Where: `tests/test_model_activation.py::test_a_version_without_metrics_cannot_go_online` for the
  missing metrics and `tests/test_register_model.py::test_registration_is_idempotent_and_can_stay_candidate`
  for the repeated name. Not asserted: a refusal for the name — AC-23 words it as one row updated in
  place, and that is what the test checks.

**TC-MOD-02** — AC-24 · activation and rollback · automated
- Precondition: two registered versions, one online.
- Steps: activate the other; create a job; roll back; create another job.
- Expected: both jobs record the version in force at their creation, and the rollback restores the
  earlier one.
- Where: `tests/test_model_activation.py::test_a_task_records_the_version_that_was_online_when_it_was_created`
  — each job's recorded version, and the rollback as an activation of the earlier one.

**TC-MOD-03** — AC-25 · experiment comparison · manual
- Precondition: baseline and improved runs on the same dataset.
- Steps: open the comparison; run the improved configuration twice with the same seed.
- Expected: both runs appear in one table with relative deltas; the two identical runs differ by less
  than 1 %.
- Where: manual — the reproducibility half needs two real training runs. The table and its deltas are
  covered for one row by `tests/test_api_skeleton.py::test_experiments_list_reports_metrics_and_baseline`;
  the per-frame comparison route still answers 501.

**TC-MOD-04** — AC-26 · dictionary guards · manual
- Precondition: a `labels.txt` with four class codes.
- Steps: add a species whose code is absent from it; then change one threshold and start a new job.
- Expected: the add is refused with the differing entries listed; the new job uses the new threshold.
- Where: manual — the class-order guard is
  `tests/test_detect_real.py::test_the_loader_refuses_a_model_whose_class_order_disagrees`, which skips
  without torch and a copied database. The threshold half cannot hold yet: `species_dict.conf_thr` is
  stored and patched, and no detection path reads it.

### 3.7 System

**TC-SYS-01** — AC-27 · parameter effect · automated
- Precondition: one parameter change, for example the concurrency limit.
- Steps: change it; start jobs until the limit binds; read the log.
- Expected: no more than the configured number run at once; the log holds before and after values.
- Where: `tests/test_params_live.py::test_a_limit_changed_at_the_page_binds_the_claims_that_follow` —
  one task at a time under a limit of one, and the audit row holding both values.

**TC-SYS-02** — AC-28 · monitoring · manual
- Precondition: a queue that can be filled.
- Steps: submit a large batch; watch the panel; fill the disk past the threshold.
- Expected: queue length rises visibly within one refresh; the disk item turns red with a note.
- Where: manual — the disk half is a person filling a disk. The queue figures are covered by
  `tests/test_failure_messages.py::test_a_dead_worker_is_reported_with_the_tasks_it_is_not_advancing`.

**TC-SYS-03** — AC-29 · message deduplication · uncovered
- Precondition: a capture failure can be triggered on demand.
- Steps: trigger it twice within an hour.
- Expected: one unread message, one increment, and the second failure adds nothing.
- Where: uncovered — nothing creates a `sys_message` row. The routes list and mark messages read, but
  there is no capture-failure event and no deduplication rule.

### 3.8 Algorithm

**TC-ALG-01** — AC-30 · overall accuracy · manual
- Precondition: the fixed test set and the deployed weights.
- Steps: evaluate and record mAP@0.5 and mAP@0.5:0.95.
- Expected: at least 0.75 and 0.45 respectively.
- Where: manual — the evaluation run. No test asserts a metric threshold; the delivered `metrics.json`
  is checked for having numbers, not for being good enough.

**TC-ALG-02** — AC-31 · per-class accuracy · manual
- Precondition: as TC-ALG-01.
- Steps: produce the per-class recall and precision table.
- Expected: recall at least 0.75 and precision at least 0.70 for all four classes.
- Where: manual — the same evaluation, read per class.

**TC-ALG-03** — AC-32 · improvement · manual
- Precondition: baseline and improved runs sharing data, epochs and seed.
- Steps: compare mAP@0.5 and FPS.
- Expected: at least +0.03 mAP@0.5 and at least 90 % of baseline FPS.
- Where: manual — two runs and a comparison nobody has automated.

**TC-ALG-04** — AC-33 · count deviation · manual
- Precondition: one clip counted by hand.
- Steps: compare the de-duplicated count with the human count.
- Expected: deviation at most 15 %.
- Where: manual — a hand count against the pipeline's count.

### 3.9 Performance

**TC-PERF-01** — AC-34 · single-frame latency · manual
- Precondition: the deployment machine with its GPU.
- Steps: time 100 single-frame detections; take median and P90.
- Expected: median at most 1.5 s end to end.
- Where: manual — the deployment machine. No test times 100 detections or takes a median.

**TC-PERF-02** — AC-34 · list latency · manual
- Precondition: a database at design capacity.
- Steps: run a load test against the list endpoints; take P90.
- Expected: P90 at most 2 s.
- Where: manual — a load test at design capacity, which no environment here has.

### 3.10 Delivery and demonstration

**TC-DOC-01** — AC-35 · traceability · manual
- Precondition: the current SRS and the traceability matrix.
- Steps: read every row of Table A-1; check each requirement has a use case and an acceptance item.
- Expected: all 29 requirements are covered; no row is empty.
- Where: manual — read `docs/traceability-en.md`. `scripts/check-ac-coverage.py` checks that every
  acceptance item is owned and that a closed one names an existing test; it does not read the matrix.

**TC-DOC-02** — AC-35 · document set · manual
- Precondition: the repository at the closing commit.
- Steps: walk the deliverable list in SRS §7.3.
- Expected: every entry either exists or has a recorded reason for its absence.
- Where: manual — walk SRS §7.3. The bilingual pair check is the only part automated
  (`tests/test_bilingual_structure.py::test_the_repository_pairs_are_in_sync`).

**TC-DEMO-01** — AC-36 · live chain · manual
- Precondition: the assembled rig, a charged battery of targets, a fresh database.
- Steps: run capture → detection → review → statistics → report without a reload or a restart.
- Expected: the chain completes with no blocking step and no console error.
- Where: manual — the live run on the rig. No test drives the five stages in one session.

**TC-DEMO-02** — AC-36 · iteration narrative · manual
- Precondition: the same rig, one reviewed frame.
- Steps: export a dataset, train nothing, but show the experiment table and the activation.
- Expected: the hard-example set, the dataset snapshot, the experiment record and the activation can
  each be shown and their order explained.
- Where: manual — the same rig, told as a story. Each step has a route; nothing asserts they run in
  that order.

## 4. Running them

`automated` cases need nothing from a person: `pytest -q` runs the named test, and CI runs it on every
pull request. A green run is not proof that all of them executed — the files that need torch, a copied
database or Node skip with a reason, and the skip line says which one did not run.

`manual` cases are run against a seeded database, by hand, in the order given: an earlier case often
produces the state a later one needs. The algorithm cases need the fixed test set and the deployment
machine; the performance cases need the deployment machine and a database at design capacity; the
demonstration cases need the assembled rig.

`uncovered` cases are not run at all. They stay in this document as the list of what a reviewer cannot
check yet, and they are the first thing to revisit when the feature behind one of them lands.

When a case fails, the defect is recorded against the case id, so a later run can tell a fixed defect
from a new one.

## 5. Status

49 cases: 20 `automated`, 21 `manual`, 8 `uncovered`. The eight uncovered ones are the gap this document
now shows instead of hiding — scheduled capture and its failed run, retake marking, cleanup, duplicate
phone numbers, the site distribution, the period comparison and message deduplication have nothing to
check.

Six of the 21 manual cases name a test that covers part of the claim (the quality gate, immediate
detection, the report figures, the experiment table, the dictionary guard, the monitoring panel); the
rest wait on a person, the deployment machine, a training run or the rig.
