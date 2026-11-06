# Progress

> Owner: whoever did the work · Revisit when: continuously, append only

Current phase: **P1 — skeleton**
Gate: `uvicorn` starts, `/api/health` answers, 9 tables exist, 13 pages render

One entry per day, newest first. A day's work goes in that day's entry; do not open a second one when
the afternoon brings more. The heading is the date and nothing else — no “evening”, no “later”.
**Why** a task moved lives here; **whether** it is done lives in `PLAN.md`.

Length is not capped. A long day is a long day, and forcing it shorter only invites compressing the
truth or splitting one day across two dates. What matters is one bullet per decision or per change of
state, not a parade of every commit — the commits are already in git. If a day grows past a screen,
the usual cause is a decision sitting in the log that belongs in an ADR.

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
- **Merged branches now delete themselves.** `gh pr merge --auto --delete-branch` does not work: the
  flag is read when the merge is *requested*, and with auto-merge the merge happens later. Twelve
  branches had piled up. A `pull_request: closed` job deletes the head branch instead, after checking
  the PR actually merged and that the branch belongs to this repository.
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
