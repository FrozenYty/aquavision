# Demo environment kit card

> Chinese version: [demo-kit-card-zh.md](demo-kit-card-zh.md). This file is the source of truth.

> Owner: @FrozenYty · Revisit when: a kit item, a check or the room layout changes

One printed page, ticked with a pen. If a line cannot be ticked, the card is wrong too: fix the card
the same day, not the memory of it.

## 1. Before you leave

- [ ] **Laptop** — charged, with the demo checkout on it.
- [ ] **Offline database copy** — the `VACUUM INTO` copy from runbook §5, with its frames directory.
- [ ] **Camera at index 1** — the USB camera, not the laptop's built-in one.
- [ ] **Lamp** — Midea MT-10T4, USB-powered, one dimming level taped over.
- [ ] **Polariser** — both pieces cut from the one sheet.
- [ ] **Rig** — ESP32-S3, panel, button, on its breadboard.
- [ ] **Spare USB cable** — a data cable, not a charge-only one.
- [ ] **Power** — laptop charger, the lamp's USB supply, one free wall socket.

## 2. The order you lay it out

1. Wall socket and power strip first.
2. Table, with the tank in the middle.
3. Lamp aimed across the tank; one polariser taped flat on the lamp head.
4. Camera in front of the tank, the lens-side polariser on it.
5. Rig to the left of the tank, its button facing the presenter, its USB cable in reach.
6. Laptop to the right, the camera cable running to it.
7. Spare USB cable taped to the table edge, not left in a bag.
8. Offline database copy on the laptop, restored before the first frame.

## 3. On arrival

- [ ] Camera opens at index 1: `python scripts/test_exposure.py --index 1` exits 0.
- [ ] Offline database copy is runbook §5's `VACUUM INTO` copy, frames beside it: `/api/health` answers, one frame opens.
- [ ] Power: the lamp is on USB, not on its battery; every plug is in the strip, one socket free.
- [ ] Cable: the camera cable is seated, not strained; the rig's cable and the spare are in reach.
- [ ] This card is on the table, printed on one page — not on a phone.

## 4. The first rehearsal

- [ ] The first rehearsal is run from this card alone — no memory, no second list, no asking.
- [ ] Each line is ticked as it happens; a line that cannot be ticked is the day's first defect.
- [ ] The card is signed and dated at the end; a signed card is the evidence that P4-18 is done.

## 5. What this card does not own

- Browser profile, radio off, 100 % zoom, demo resolution — `P4-19`.
- The three rehearsals, the eight-minute limit, the injected failure — `P4-07`.
- The backup and restore drill — `P4-17`; this card only asks that today's copy is the §5 kind.
