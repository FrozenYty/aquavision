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
- **The five blocked directories are gone**, by asking for the access instead of designing around it.
  The temporary ruff exclude is removed; the principle is now `AGENTS.md` §4.7.

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
