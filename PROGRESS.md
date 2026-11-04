# Progress

Current phase: **P0 — foundation**
Gate: dataset ≥ 3000 split · three environments identical · camera outputs frames

Dated log, newest first, five lines per entry. **Why** a task moved lives here; **whether** it is
done lives in `PLAN.md`.

## 2026-11-04

- P0-04 done: design tokens, shared shell, three pages navigate (#7). P0-02 environment lock (#11).
- P1-04 started ahead of GATE P0: lane C does not depend on the server; lead to confirm.
- P1-04 so far: `api.js` and contract-shaped mocks (#8), capture and frame pages (#9), visual language (#10); 4 of 13 pages.
- Open: provisional endpoints in #8 for lane B; SRS vs contract on login token, captcha and frame rate for lanes A/B.
- Next: the remaining nine pages, one PR per domain; the last one ticks P1-04.

## 2026-11-03

- Repository created: conventions, CI, branch protection (#1, #2).
- `PLAN.md` in place: five phases, 27 tasks, five gates (#3).
- SRS reached V1.2: five classes, hardware list, per-class metrics.
- Blocked: P0-01 — dataset download links are dead, mirrors under review.
- Next: P0-02 environment lock, P0-03 hardware order.

## 2026-11-04

- P0-02 merged: dependencies pinned for Python 3.11 (#11).
- P0-01: DUO in place — 7782 images cleaned, split and counted; test set is 1111.
- DUO carries no video ids and already de-duplicates frames, so "split by video" is
  implemented as perceptual-hash grouping (dhash64, hamming <= 3, largest group 4).
- Open issues: echinus has 24x the boxes of chlamys; debris class has no images yet.
- Next: find a debris source, finish the three-machine install check.
