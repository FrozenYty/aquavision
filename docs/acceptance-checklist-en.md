# Acceptance checklist

> Chinese version: [acceptance-checklist-zh.md](acceptance-checklist-zh.md). This file is the source of truth.
> Owner: @IkeaFyj · Revisit when: an acceptance item changes, or its evidence moves

One row per acceptance item in SRS Table 8-1, sorted by id, with the evidence that exists today and a state a reviewer can act on. The SRS is the authority for what must hold; `docs/test-cases-en.md` is how a person runs it; this page adds the evidence and the verdict, not a second description of the steps. A row without evidence is a defect, not an argument — that is `PLAN.md` P4-16's rule, and section 4 is where the three such rows are written down.

## 1. What this page is for

The question after a defence is not "did it work" but "which item has what behind it". This page answers that for all 36 items: what the SRS says, which case serves it, the file or minute that proves it, and whether a reviewer may treat it as closed. It does not re-run anything, and it does not edit the cases — where the two disagree, section 5 says why and names the task that moved.

## 2. How to read a row

| Field | Meaning |
|---|---|
| AC | The acceptance id from SRS Table 8-1 (`docs/srs-en.md` §8.1); the table is sorted by it |
| SRS criterion | The item's sentence, compressed to one line; the SRS is still the authority |
| Case | The case or cases in `docs/test-cases-en.md` that serve the item |
| Evidence | The test file, document section or demo minute that proves it today |
| State | `closed` when the evidence is automated; `manual` when a person, the deployment machine or the rig must still run it; `open` when a clause has no evidence at all |

A case's own `Not asserted` note stays in the case and is not repeated here; the state follows the case's verdict, except where a later task delivered the missing evidence (section 5). An `open` row is a defect with an owner, never a promise.

## 3. The checklist

| AC | SRS criterion | Case | Evidence | State |
|---|---|---|---|---|
| AC-01 | Five failures lock the account with the remaining time; passwords are hashes; a correct password is refused while locked. | TC-AUTH-01, TC-AUTH-02 | `tests/test_api_skeleton.py::test_wrong_password_counts_down_then_locks`; the password columns and the remaining-seconds sentence are read by hand (TC-AUTH-01, TC-AUTH-02) | manual |
| AC-02 | A collector is refused the activation route and the refusal is logged; an unauthenticated capture call is refused. | TC-PERM-01, TC-PERM-02 | `tests/test_forbidden_is_logged.py::test_a_route_level_guard_logs_the_attempt_too`; `tests/test_capture_local_only.py::test_a_remote_call_without_a_token_is_still_a_401`; `tests/test_permission_matrix.py::test_the_matrix_is_honoured_in_both_directions` | closed |
| AC-03 | A disabled account cannot sign in and its history stays searchable; duplicate phone numbers are refused. | TC-ACC-01, TC-ACC-02 | `tests/test_accounts.py::test_a_duplicate_identifier_is_refused_with_the_message`; disabling, signing in and reading the history back is manual (TC-ACC-01) | manual |
| AC-04 | A review traces to operator, time and before/after values; no endpoint deletes a log entry. | TC-AUD-01, TC-AUD-02 | `tests/test_review_versions.py::test_two_submissions_appear_newest_first_with_their_counts_and_authors`; walking the contract for a deleting route is manual (TC-AUD-02) | manual |
| AC-05 | With capture stopped there is no source; a clock skew over 5 s is refused; a duplicate frame stores once. | TC-CAP-01, TC-CAP-02, TC-CAP-03 | `tests/test_ws_capture.py::test_a_server_without_a_camera_closes_with_1011`; `tests/test_api_skeleton.py::test_detect_frame_rejects_a_frame_that_never_came_through_capture`, `::test_a_frame_with_a_skewed_clock_is_refused`, `::test_capture_scores_the_frame_and_is_idempotent` | closed |
| AC-06 | Six captures ten minutes apart produce six batches; a failed capture marks its run failed. | TC-CAP-04, TC-CAP-05 | none: there is no schedule route, table or timer in `server/` (`PLAN.md` P3-13 is open) | open |
| AC-07 | A defocused frame scores below 60 and stays out of the queue; retake frames are marked as their own record. | TC-CAP-06, TC-CAP-07 | queue half: `tests/test_batch_quality.py`, `tests/test_capture.py::test_flat_frame_is_a_retake`, `tests/test_params_live.py::test_the_capture_verdict_uses_the_threshold_in_force`; retake marking has no writer: `server/app/routers/capture.py` stores `is_retake=0` | open |
| AC-08 | Four filters combine; a batch drills into its frames; ticked frames become the job. | TC-CAP-08 | `tests/test_frames_filters.py::test_the_four_filters_combine_as_an_intersection`, `::test_the_total_counts_the_filtered_set_not_the_page`; `tests/test_batch_selection.py` (the case's `Not implemented` clause, closed in P4-05) | closed |
| AC-09 | Cleanup nulls the references and frees disk; originals survive under the default policy. | TC-CAP-09 | `scripts/cleanup_retention.py`; `tests/test_cleanup_retention.py` (delivered after the cases were written) | closed |
| AC-10 | Trigger to box within 3 s; an image that never came through capture is refused. | TC-DET-01, TC-DET-02 | `tests/test_api_skeleton.py::test_detect_frame_rejects_a_frame_that_never_came_through_capture`; `tests/test_detect_real.py` (skips without torch and the development database); the 3 s half is a stopwatch on the deployment machine (TC-DET-01) | manual |
| AC-11 | A 100-frame job updates live; a cancel takes effect within 5 s; a failed frame retries. | TC-DET-03 | `tests/test_worker.py::test_queue_runs_100_frames_to_done`, `::test_cancel_at_frame_40_stops_within_five_seconds`, `::test_failure_is_retryable`; `tests/test_batch_acceptance.py::test_progress_is_queryable_while_a_batch_task_runs` | closed |
| AC-12 | Changing a threshold changes the result count; a job's parameters cannot be edited afterwards. | TC-DET-04, TC-DET-05 | none automated: two thresholds on one frame and the immutability walk are manual (TC-DET-04, TC-DET-05) | manual |
| AC-13 | Per-class counts equal the list rows; the class filter moves counts and chart together. | TC-DET-06 | `tests/test_api_skeleton.py::test_boxes_come_back_by_frame_id`; the single-class filter and the chart are named `Not asserted` in the case (TC-DET-06) | closed |
| AC-14 | CSV rows equal the page rows; Excel opens the file with Chinese intact. | TC-DET-07 | `tests/test_result_csv.py::test_comma_quote_newline_and_chinese_survive_a_round_trip`, `::test_the_bytes_are_utf8_so_chinese_opens_in_excel`, `::test_the_header_is_the_servers_field_names` | closed |
| AC-15 | Deleting a box lowers the count and drawing one raises it; the automatic result stays viewable. | TC-REV-01 | `tests/test_api_skeleton.py::test_review_submission_returns_the_documented_result`; `tests/test_review_versions.py::test_rollback_marks_removed_boxes_rejected_instead_of_deleting_them` | closed |
| AC-16 | Two reviews produce two versions; after rollback the result matches the target version. | TC-REV-02 | `tests/test_review_versions.py::test_two_submissions_appear_newest_first_with_their_counts_and_authors`, `::test_rollback_restores_the_target_box_set_as_a_new_version` | closed |
| AC-17 | Every corrected frame enters the hard-example pool with its origin; a removed entry disappears. | TC-REV-03 | `tests/test_hard_samples.py::test_a_review_correction_enters_the_pool_with_its_origin`, `::test_the_pool_lists_each_frame_once_and_keeps_the_origins_filterable`, `::test_removal_empties_the_pool_entry_and_keeps_the_evidence` | closed |
| AC-18 | One seed gives identical file lists; unreviewed samples are refused. | TC-REV-04 | `tests/test_api_skeleton.py::test_dataset_export_is_deterministic_and_keeps_groups_together`, `::test_export_without_reviewed_frames_is_refused`; `tests/test_datasets.py::test_a_snapshot_keeps_a_burst_out_of_two_splits` | closed |
| AC-19 | Switching the basis changes the figures and the label together; shares total 100 %. | TC-STA-01 | `tests/test_api_skeleton.py::test_stats_figures_follow_the_rows_detection_and_review_wrote`; demo 4:40 | closed |
| AC-20 | Heat map and site ranking agree; an empty site shows an empty state, not a blank chart. | TC-STA-02 | none: no heat map and no site-distribution figure in the pages or the contract (`docs/test-cases-en.md` TC-STA-02; `docs/traceability-en.md` TM-089) | open |
| AC-21 | Rates reconcile by hand; a missing baseline shows a dash. | TC-STA-03 | `tests/test_stats_view.py`, which runs `tests/stats_view.mjs`: the day-over-day rate, the dash and the one-day case (delivered after the cases were written); demo 4:40 | closed |
| AC-22 | Report figures equal the dashboard's; the footer carries the model version and the basis. | TC-STA-04 | `tests/test_report_dashboard_agree.py`; footer labels: `tests/test_api_skeleton.py::test_report_is_generated_from_the_same_figures_as_the_dashboard`; demo 5:25 | closed |
| AC-23 | A version without metrics cannot go online; a version name has exactly one row. | TC-MOD-01 | `tests/test_model_activation.py::test_a_version_without_metrics_cannot_go_online`; `tests/test_register_model.py::test_registration_is_idempotent_and_can_stay_candidate` | closed |
| AC-24 | New jobs record the version in force; a rollback restores the earlier one. | TC-MOD-02 | `tests/test_model_activation.py::test_a_task_records_the_version_that_was_online_when_it_was_created` | closed |
| AC-25 | Baseline and improved runs compare in one table; two identical runs differ by less than 1 %. | TC-MOD-03 | experiment table: `tests/test_api_skeleton.py::test_experiments_list_reports_metrics_and_baseline`; the two-run reproducibility half is manual (TC-MOD-03) | manual |
| AC-26 | A class code the labels contradict is refused; a new class threshold binds new jobs. | TC-MOD-04 | `tests/test_class_thresholds.py` (both sentences and the labels refusal, delivered in P3-15); `tests/test_detect_real.py::test_the_loader_refuses_a_model_whose_class_order_disagrees` | closed |
| AC-27 | A new concurrency limit constrains later jobs, with before and after values logged. | TC-SYS-01 | `tests/test_params_live.py::test_a_limit_changed_at_the_page_binds_the_claims_that_follow` | closed |
| AC-28 | A large batch visibly moves the queue figure; disk usage past its threshold turns red with a note. | TC-SYS-02 | `tests/test_monitoring.py::test_a_large_batch_moves_the_queue_figure`, `::test_disk_past_its_threshold_turns_the_item_red_with_a_note` (delivered in P3-09) | closed |
| AC-29 | One unread message per offline event; repeats within the hour add nothing. | TC-SYS-03 | `tests/test_messages.py::test_repeated_failures_within_the_hour_add_nothing` | closed |
| AC-30 | mAP@0.5 at least 0.75 and mAP@0.5:0.95 at least 0.45 on the fixed test set. | TC-ALG-01 | none automated: the fixed-set evaluation is manual (`PLAN.md` P4-01 and P4-04 are open) | manual |
| AC-31 | Recall at least 0.75 and precision at least 0.70 for all four classes. | TC-ALG-02 | none automated: the per-class table is read from the same manual evaluation (P4-04) | manual |
| AC-32 | At least +0.03 mAP@0.5 over the baseline and at least 90 % of its FPS. | TC-ALG-03 | none automated: two runs and their comparison are manual (P4-02, P4-03) | manual |
| AC-33 | De-duplicated counts deviate from a hand count by at most 15 %. | TC-ALG-04 | none automated: the hand count is manual (TC-ALG-04) | manual |
| AC-34 | Single frame end to end within 1.5 s on GPU; list endpoints P90 within 2 s. | TC-PERF-01, TC-PERF-02 | `python scripts/measure_performance.py --detect-only` and `--list-only` print the numbers on the deployment machine; `tests/test_measure_performance.py` holds the script's arithmetic, not the machine's speed | manual |
| AC-35 | The matrix covers all 29 requirements, each with an acceptance item; the documents are complete. | TC-DOC-01, TC-DOC-02 | `scripts/check-ac-coverage.py` (ownership and a named test); the matrix walk and the SRS §7.3 walk are manual (TC-DOC-01, TC-DOC-02) | manual |
| AC-36 | The capture-to-report chain runs live without interruption; the iteration loop can be described and its key steps shown. | TC-DEMO-01, TC-DEMO-02 | `docs/demo-script-en.md` §4 (0:50–6:50) and its closing paragraph on the iteration loop; the three rehearsals (`PLAN.md` P4-07) | manual |

## 4. Open rows

These are listed as defects, not argued away, following `PLAN.md` P4-16.

- **AC-06 — scheduled capture.** No route, table or timer exists in `server/`, so six scheduled batches and a failed-run record cannot be shown. Owned by `PLAN.md` P3-13.
- **AC-07 — retake marking.** `media_asset.is_retake` is written as 0 on every capture and no route ever sets it, so a retake is not its own record. The quality-gate half is proven by the tests in the row. Owned by the capture module's next task.
- **AC-20 — site distribution.** There is no heat map, no ranking and no site-distribution figure in the pages or the contract; `docs/traceability-en.md` TM-089 records the missing element. Owned by `PLAN.md` P3-02.

## 5. Where the cases and this page disagree

The case verdicts were established on 2026-11-12 by reading the tests. Six rows have evidence that arrived afterwards; this page uses the evidence and keeps the cases untouched, so their owner can re-run the cases rather than trust this table. None of these is an invented claim: each names the test that now asserts the sentence.

| AC | Case verdict on 11-12 | Evidence today | Delivered by |
|---|---|---|---|
| `AC-08` | automated, with `Not implemented: carrying a frame selection into job creation` | `tests/test_batch_selection.py` | P4-05, 11-28 |
| `AC-09` | uncovered | `scripts/cleanup_retention.py`, `tests/test_cleanup_retention.py` | P3-08, 11-27 |
| `AC-21` | uncovered | `tests/stats_view.mjs`, run by `tests/test_stats_view.py` | P3-02's statistics work |
| `AC-22` | manual | `tests/test_report_dashboard_agree.py` | P3-07, 11-28 |
| `AC-26` | manual | `tests/test_class_thresholds.py` | P3-15, 11-16 |
| `AC-28` | manual | `tests/test_monitoring.py` | P3-09, 11-12 |

## 6. How this page is checked

- `python scripts/check-ac-coverage.py` exits 0: every one of the 36 items is owned by a task and every task that claims one names a test that exists.
- Each id appears exactly once as a row: `grep -cE '^\| AC-[0-9]{2} \|' docs/acceptance-checklist-en.md` prints 36, and the same command on the Chinese file prints 36.
- Every test path named in the Evidence column exists in `tests/`; the demo minutes named in section 3 are marks in `docs/demo-script-en.md` §4.
- The pair passes `python scripts/check-bilingual.py`, and both files are listed in `docs/INDEX-en.md` and `docs/INDEX-zh.md`.

## 7. What this page does not do

It does not run the cases, own them, or replace the rehearsal. It does not claim a state for the metric rows that `PLAN.md` P4-04 has not recorded; those stay `manual` until the numbers and their dates exist. It is the evidence index behind `PLAN.md` P4-06, and the demo's minutes are the ones in `docs/demo-script-en.md`.
