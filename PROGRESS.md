# Progress

Current phase: **P0 — foundation**
Gate: dataset ≥ 3000 split · three environments identical · purchase list final · rig design final

Dated log, newest first, five lines per entry. **Why** a task moved lives here; **whether** it is
done lives in `PLAN.md`.

## 2026-11-05

- **Rig design settled (P0-06 done).** Lighting is a desk lamp, not purchased LED bars: the tank is
  lit from a single lamp above and 45° forward, with tracing paper as a diffuser and a white card
  reflector on the dark side. It removes a whole 5V power domain — the rig now runs off one USB cable.
- **Single lamp first, second lamp only if it fails.** Criterion: left/right half brightness ratio
  ≥ 0.7. 0.5–0.7 means adjust the reflector or move the lamp; below 0.5 add the second lamp. Two
  lamps must be the same colour temperature — a warm and a cool lamp give a two-tone wall, which is
  worse than one lamp.
- **Acceptance numbers for the rig**: left/right ratio ≥ 0.7, a 5 cm target ≥ 45 px at 640 input, no
  flicker when filmed by a phone, 20-frame mean brightness spread < 10%. These live in P1-06 now,
  because they can only be measured once the parts arrive.
- **Purchase list frozen at 16 items, ¥382.42**, across three channels: Taobao (camera module, tank,
  models, scenery, polarising film), JD (ESP32-S3 with pre-soldered headers), LCSC (turbidity module
  C55121807, level shifter, GH1.25 cable, DS18B20 probe C22360667, wire, switch, terminals).
- Lighting in use is recorded in `PROGRESS.md` and, later, in `dataset-stats.json`. It is deliberately
  **not** written into `site`, which is a monitoring location — appending `-L1` would split the stats.

## 2026-11-04

- P0-04 done: design tokens, shared shell, three pages navigate (#7). P0-02 environment lock (#11).
- P1-04 started ahead of GATE P0: lane C does not depend on the server; lead to confirm.
- P1-04 so far: `api.js` and contract-shaped mocks (#8), capture and frame pages (#9), visual language (#10); 4 of 13 pages.
- Open: provisional endpoints in #8 for lane B; SRS vs contract on login token, captcha and frame rate for lanes A/B.
- Next: the remaining nine pages, one PR per domain; the last one ticks P1-04.
- P0-02 merged: dependencies pinned for Python 3.11 (#11).
- P0-01: DUO in place — 7782 images cleaned, split and counted; test set is 1111.
- DUO carries no video ids and already de-duplicates frames, so "split by video" is
  implemented as perceptual-hash grouping (dhash64, hamming <= 3, largest group 4).
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

