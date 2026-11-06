# Test cases

> Chinese version: [test-cases-zh.md](test-cases-zh.md). This file is the source of truth.
> Owner: @IkeaFyj · Revisit when: an acceptance item changes, or a case is executed

Draft cases for the 36 acceptance items in SRS Table 8-1. **Nothing here has been executed**: every
case is marked `not implemented`, which is the point of the draft — it says what will be checked, so
implementation can be built against it rather than tested afterwards.

## 1. Purpose and scope

One case per acceptance item, and a second case wherever one item hides two independent claims. The
SRS is the authority for what must hold; a case says only how a person proves it.

Deliberately not covered: unit and integration tests. Those live beside the code and run in CI. This
document covers the checks that need a running system, a database, a trained model or a person
looking at a screen.

## 2. How a case is written

| Field | Meaning |
|---|---|
| Case | Stable identifier, `TC-<AREA>-<serial>` |
| AC | The acceptance item it serves, from SRS Table 8-1 |
| Precondition | What must be true before the first step; if it is not, the result is not a failure |
| Steps | The shortest path that exercises the claim |
| Expected | What is observed when the item holds — stated so a stranger can decide |
| State | `not implemented` until the feature exists; then `pass` or the defect id |

## 3. Cases

### 3.1 Account and permissions

**TC-AUTH-01** — AC-01 · sign-in lockout · not implemented
- Precondition: one enabled account, known password.
- Steps: submit a wrong password five times; then submit the correct password.
- Expected: the fifth failure returns a lockout message with the remaining seconds; the correct
  password during the lock is refused with the same remaining time.

**TC-AUTH-02** — AC-01 · password storage · not implemented
- Precondition: the account from TC-AUTH-01 has signed in at least once.
- Steps: read the `password_hash` and `salt` columns in the database.
- Expected: neither contains the password; the hash differs for two accounts with the same password.

**TC-PERM-01** — AC-02 · role boundary · not implemented
- Precondition: signed in as the collector role; one registered model version exists.
- Steps: call `POST /api/models/{id}/activate` with the collector's token.
- Expected: 403 in the standard envelope; a rejection row appears in the operation log.

**TC-PERM-02** — AC-02 · unauthenticated access · not implemented
- Precondition: no token.
- Steps: call `POST /api/capture/sessions/{id}/frames`.
- Expected: 401 in the standard envelope; no frame is written.

**TC-ACC-01** — AC-03 · disable an account · not implemented
- Precondition: an account with detection history; an administrator session.
- Steps: disable the account; sign in with it; query its historical results as the administrator.
- Expected: the sign-in is refused; the history is still returned.

**TC-ACC-02** — AC-03 · duplicate phone · not implemented
- Precondition: one account already uses a phone number.
- Steps: create a second account with the same number.
- Expected: refused with a message naming the conflict; no new row appears.

**TC-AUD-01** — AC-04 · audit values · not implemented
- Precondition: one frame with a review pending.
- Steps: delete one box and submit the review; query the operation log for that frame.
- Expected: an entry carrying the operator, the time and the before/after values of the change.

**TC-AUD-02** — AC-04 · no deletion path · not implemented
- Precondition: at least one log row exists.
- Steps: exercise every endpoint in the contract that could plausibly remove data.
- Expected: no route deletes a log row; the row count never decreases outside retention.

### 3.2 Capture

**TC-CAP-01** — AC-05 · no source without a camera · not implemented
- Precondition: the capture device is disconnected.
- Steps: start the system; look for any path that would put an image into the detection queue.
- Expected: none exists; the interface reports the device as unavailable and produces no record.

**TC-CAP-02** — AC-05 · timestamp tolerance · not implemented
- Precondition: the capture device connected.
- Steps: submit a frame whose capture time is six seconds behind the server clock.
- Expected: refused with the reason recorded; no row is written.

**TC-CAP-03** — AC-05 · idempotent frames · not implemented
- Precondition: one session open.
- Steps: submit the same frame twice with the same identifier.
- Expected: one row; the second call reports success without creating a duplicate.

**TC-CAP-04** — AC-06 · scheduled capture · not implemented
- Precondition: a schedule of six captures at ten-minute intervals.
- Steps: advance the clock through the schedule; count the batches.
- Expected: six batches, each with the planned frame count.

**TC-CAP-05** — AC-06 · failed run · not implemented
- Precondition: a schedule whose device becomes unavailable before the third trigger.
- Steps: let the schedule run to completion.
- Expected: the third run is marked failed with a reason; the earlier batches are untouched.

**TC-CAP-06** — AC-07 · quality gate · not implemented
- Precondition: the device can be defocused on demand.
- Steps: capture one defocused frame; capture one sharp frame.
- Expected: the defocused frame scores below 60, is stored, is marked needs-retake and does not enter
  the detection queue; the sharp one does.

**TC-CAP-07** — AC-07 · retake marking · not implemented
- Precondition: one frame marked needs-retake.
- Steps: trigger a retake; open the batch.
- Expected: the retake is its own record in the same batch, flagged as a retake.

**TC-CAP-08** — AC-08 · combined search · not implemented
- Precondition: at least three batches across two sites and three dates.
- Steps: filter by site, date range and quality together; then open a batch.
- Expected: only matching batches return; opening one lists its frames; selecting frames carries the
  selection into job creation.

**TC-CAP-09** — AC-09 · cleanup · not implemented
- Precondition: intermediate files older than the retention period.
- Steps: run the cleanup with and without the original-images option.
- Expected: references to deleted files are nulled and disk usage falls; originals survive under the
  default policy.

### 3.3 Detection

**TC-DET-01** — AC-10 · immediate detection · not implemented
- Precondition: one registered frame; the online model loaded.
- Steps: trigger detection and time until boxes are visible.
- Expected: boxes on screen within three seconds; the elapsed time is recorded with the result.

**TC-DET-02** — AC-10 · source enforcement · not implemented
- Precondition: a local image that never passed through capture.
- Steps: attempt to submit it for detection by any route.
- Expected: refused with a source-mismatch message.

**TC-DET-03** — AC-11 · batch progress · not implemented
- Precondition: a batch of 100 frames.
- Steps: start detection; watch progress; cancel at frame 40; retry one failed frame.
- Expected: progress advances frame by frame; the cancel takes effect within five seconds and stops
  adding results; the retry produces a new result for that frame only.

**TC-DET-04** — AC-12 · threshold effect · not implemented
- Precondition: one frame with several detections near the threshold.
- Steps: run with confidence 0.5, then 0.2.
- Expected: the second run returns more boxes on the same frame.

**TC-DET-05** — AC-12 · frozen parameters · not implemented
- Precondition: a job that has already run.
- Steps: attempt to change its confidence threshold through every route in the contract.
- Expected: no route allows it; the recorded parameters still match what was used.

**TC-DET-06** — AC-13 · count consistency · not implemented
- Precondition: a job with results across all four classes.
- Steps: read the per-class counts; filter by one class.
- Expected: the total equals the number of list rows; filtering updates counts and chart together.

**TC-DET-07** — AC-14 · export · not implemented
- Precondition: a job whose page shows N results.
- Steps: export CSV; open it in Excel.
- Expected: N data rows plus a header; Chinese class names render correctly; coordinates are
  normalised.

### 3.4 Review

**TC-REV-01** — AC-15 · review edits · not implemented
- Precondition: a frame with one false positive and one miss.
- Steps: delete the false box; draw a box for the miss; submit.
- Expected: the count falls by one then rises by one; the automatic result remains viewable.

**TC-REV-02** — AC-16 · versions and rollback · not implemented
- Precondition: the frame from TC-REV-01.
- Steps: submit a second review; roll back to the earlier version.
- Expected: two versions exist; after rollback the result matches the target version exactly and both
  versions remain listed.

**TC-REV-03** — AC-17 · hard-example pool · not implemented
- Precondition: the corrected frame from TC-REV-01.
- Steps: open the pool; remove one entry.
- Expected: the frame is present with source `corrected`; after removal it no longer appears.

**TC-REV-04** — AC-18 · reproducible export · not implemented
- Precondition: a sample range containing one unreviewed frame.
- Steps: export twice with the same seed; then export a range with the unreviewed frame included.
- Expected: the two file lists are identical; the third export is refused and names the unreviewed
  frame.

### 3.5 Statistics

**TC-STA-01** — AC-19 · basis switch · not implemented
- Precondition: results with both automatic and reviewed states.
- Steps: open the composition chart; switch the basis.
- Expected: the figures change and the stated basis changes with them; shares sum to 100 %.

**TC-STA-02** — AC-20 · distribution · not implemented
- Precondition: at least two sites, one with no data.
- Steps: open the heat map; compare it with the ranking table; select the empty site.
- Expected: heat map and ranking agree; the empty site shows an empty state, not a blank chart.

**TC-STA-03** — AC-21 · trend arithmetic · not implemented
- Precondition: two periods of data, the earlier one missing.
- Steps: open the trend; compute one rate by hand.
- Expected: the computed rate matches the displayed one; the missing baseline shows a dash and no
  conclusion is drawn.

**TC-STA-04** — AC-22 · report fidelity · not implemented
- Precondition: a dashboard with non-zero figures.
- Steps: generate a report; compare figures; read the footer.
- Expected: report figures equal the dashboard; the footer states the model version and the basis.

### 3.6 Models

**TC-MOD-01** — AC-23 · registration guards · not implemented
- Precondition: one registered version.
- Steps: register a second version without metrics; then register one with an existing name.
- Expected: both refused, each naming the missing or conflicting field.

**TC-MOD-02** — AC-24 · activation and rollback · not implemented
- Precondition: two registered versions, one online.
- Steps: activate the other; create a job; roll back; create another job.
- Expected: both jobs record the version in force at their creation, and the rollback restores the
  earlier one.

**TC-MOD-03** — AC-25 · experiment comparison · not implemented
- Precondition: baseline and improved runs on the same dataset.
- Steps: open the comparison; run the improved configuration twice with the same seed.
- Expected: both runs appear in one table with relative deltas; the two identical runs differ by less
  than 1 %.

**TC-MOD-04** — AC-26 · dictionary guards · not implemented
- Precondition: a `labels.txt` with four class codes.
- Steps: add a species whose code is absent from it; then change one threshold and start a new job.
- Expected: the add is refused with the differing entries listed; the new job uses the new threshold.

### 3.7 System

**TC-SYS-01** — AC-27 · parameter effect · not implemented
- Precondition: one parameter change, for example the concurrency limit.
- Steps: change it; start jobs until the limit binds; read the log.
- Expected: no more than the configured number run at once; the log holds before and after values.

**TC-SYS-02** — AC-28 · monitoring · not implemented
- Precondition: a queue that can be filled.
- Steps: submit a large batch; watch the panel; fill the disk past the threshold.
- Expected: queue length rises visibly within one refresh; the disk item turns red with a note.

**TC-SYS-03** — AC-29 · message deduplication · not implemented
- Precondition: a capture failure can be triggered on demand.
- Steps: trigger it twice within an hour.
- Expected: one unread message, one increment, and the second failure adds nothing.

### 3.8 Algorithm

**TC-ALG-01** — AC-30 · overall accuracy · not implemented
- Precondition: the fixed test set and the deployed weights.
- Steps: evaluate and record mAP@0.5 and mAP@0.5:0.95.
- Expected: at least 0.75 and 0.45 respectively.

**TC-ALG-02** — AC-31 · per-class accuracy · not implemented
- Precondition: as TC-ALG-01.
- Steps: produce the per-class recall and precision table.
- Expected: recall at least 0.75 and precision at least 0.70 for all four classes.

**TC-ALG-03** — AC-32 · improvement · not implemented
- Precondition: baseline and improved runs sharing data, epochs and seed.
- Steps: compare mAP@0.5 and FPS.
- Expected: at least +0.03 mAP@0.5 and at least 90 % of baseline FPS.

**TC-ALG-04** — AC-33 · count deviation · not implemented
- Precondition: one clip counted by hand.
- Steps: compare the de-duplicated count with the human count.
- Expected: deviation at most 15 %.

### 3.9 Performance

**TC-PERF-01** — AC-34 · single-frame latency · not implemented
- Precondition: the deployment machine with its GPU.
- Steps: time 100 single-frame detections; take median and P90.
- Expected: median at most 1.5 s end to end.

**TC-PERF-02** — AC-34 · list latency · not implemented
- Precondition: a database at design capacity.
- Steps: run a load test against the list endpoints; take P90.
- Expected: P90 at most 2 s.

### 3.10 Delivery and demonstration

**TC-DOC-01** — AC-35 · traceability · not implemented
- Precondition: the current SRS and the traceability matrix.
- Steps: read every row of Table A-1; check each requirement has a use case and an acceptance item.
- Expected: all 29 requirements are covered; no row is empty.

**TC-DOC-02** — AC-35 · document set · not implemented
- Precondition: the repository at the closing commit.
- Steps: walk the deliverable list in SRS §7.3.
- Expected: every entry either exists or has a recorded reason for its absence.

**TC-DEMO-01** — AC-36 · live chain · not implemented
- Precondition: the assembled rig, a charged battery of targets, a fresh database.
- Steps: run capture → detection → review → statistics → report without a reload or a restart.
- Expected: the chain completes with no blocking step and no console error.

**TC-DEMO-02** — AC-36 · iteration narrative · not implemented
- Precondition: the same rig, one reviewed frame.
- Steps: export a dataset, train nothing, but show the experiment table and the activation.
- Expected: the hard-example set, the dataset snapshot, the experiment record and the activation can
  each be shown and their order explained.

## 4. Running them

Cases that need a person are run against a seeded database, by hand, in the order given: an earlier
case often produces the state a later one needs. The two performance cases need the deployment
machine and a database at design capacity, which do not exist yet.

When a case fails, the defect is recorded against the case id, so a later run can tell a fixed defect
from a new one.

## 5. Status

All 49 cases are `not implemented`. This draft exists so the features are built against it: a case
that cannot be run yet is still useful, because it states what "done" means before anyone argues
about it.
