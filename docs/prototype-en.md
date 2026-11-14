# Prototype plan

> Chinese version: [prototype-zh.md](prototype-zh.md). This file is the source of truth.
> Owner: @chemflowers · Revisit when: the prototype is replaced by P2 work
> Valid until: the walkthrough replaced by the real slice. After that this file is history.

Goal: a person clicks through the main line in three minutes and believes this is a working system.
Not feature complete — **credibly shaped**.

## 1. Scope: six screens, one line

| # | Screen | State | This round |
|---|---|---|---|
| 1 | Login | exists | keep, minor polish |
| 2 | Overview | exists, thin | **rework**: four metric cards + one trend chart |
| 3 | Capture and live detection | exists, no boxes | **rework**: frame + boxes + quality gauge + filmstrip |
| 4 | Frame detail | none | **new**: large frame, boxes, object list, “go to review” |
| 5 | Review workbench | none | **new**: canvas, drag a box, relabel |
| 6 | Statistics and report | none | **new**: four charts, export button |

The other seven screens stay out of scope. Grey them in the sidebar and label `P2` — that reads as
sequencing, not as missing work.

## 2. Walkthrough

```
login → overview (412 frames today, 7 to review) → start capture
      → boxes appear, quality 86, latency 128 ms
      → open a frame → one box is wrong (a rock read as a sea cucumber)
      → review → drag a box, relabel → count 10 → 11
      → statistics → generate report → export
```

**Every arrow must be clickable.** A dead end reads as unfinished.

## 3. Key elements per screen

**Overview** — four cards (frames today, to review, rejection rate, online model), numbers ≥ 28 px,
one seven-day line chart below, a short session list at the bottom.

**Capture** — this is the screen that sells the system.
- live frame with boxes, each box labelled with class and confidence;
- the four class colours fixed: sea cucumber orange, urchin purple, scallop pink, starfish yellow;
- a latency number in the corner, ticking every two seconds;
- quality gauge, turning amber below 60 with “needs retake”;
- a filmstrip of recent frames along the bottom.

**Frame detail** — large frame, boxes drawn, object list on the right with confidence and status, one
button through to review.

**Review** — the screen that earns the most credit.
- canvas with the frame and draggable boxes, selected box showing handles;
- object list on the right: confirm, edit, delete, add;
- toolbar: select, draw, delete, undo; zoom percentage; relabel dropdown; submit.
- **Dragging one box and relabelling once is enough.** No zoom, no undo stack.

**Statistics** — four charts in a 2×2 grid: species composition, capture volume, rejection rate,
correction distribution. Two buttons: generate report, export PDF. A toast is enough; no real file.

## 4. The capture end has no hardware yet

Three ways to show it, in descending honesty:

| Option | Source | Real | Cost |
|---|---|---|---|
| **A browser opens the laptop camera** | `getUserMedia()` | image real, boxes fake | twenty lines |
| **B real frames from the dataset** | DUO samples | data real, live fake | none |
| C placeholder | a grey box | all fake, declared | none |

**Use B as the default**: pick three to five frames from the 7782 DUO images, place the boxes by hand,
and fade them in one after another — closer to detection than all at once.

**Add A as a button.** “Try this machine's camera” switches the pane to the laptop feed. When someone
asks where the image comes from, open it live. Do not draw boxes in this mode: the laptop is pointing
at a desk, and boxes over a desk look wrong.

Three labels are mandatory:

1. page header: `Prototype · simulated data`
2. capture footnote: `Frames from the DUO public dataset; the release build streams from a USB camera`
3. statistics footnote: `Demonstration figures, not real run results`

**A judge accepts simulated data. A judge does not accept being misled.**

## 5. Mock data

Keep it in `web/static/mock/fixtures.js`, shaped like `api-contract`:

```js
{ frame_id: "20261105T193012-0042", session_id: "s-a3-007",
  captured_at: "2026-11-05T19:30:12+08:00",
  quality: { sharpness: 78, brightness: 91, colorcast: 85, score: 86, verdict: "ok" },
  width: 1920, height: 1080 }

{ class_code: "holothurian", confidence: 0.87, x: 0.41, y: 0.52, w: 0.12, h: 0.09 }
```

**Place the boxes by hand**, eight to twelve of them, on real object positions. Generated boxes float
over empty water and give the whole thing away.

## 6. Acceptance

- [ ] six screens open, the sidebar highlights the current one
- [ ] no dead links between them, a way back from every screen
- [ ] capture shows a frame, boxes, a quality score and a latency number
- [ ] review can drag one box and relabel once
- [ ] statistics shows four charts with data; export gives feedback
- [ ] one type scale, one radius, one spacing rhythm — only tokens from `tokens.css`
- [ ] the three labels are present
- [ ] the “try this machine's camera” button opens a real feed
- [ ] no Lorem ipsum, no TODO
- [ ] no horizontal scroll at 1280×800 or 1920×1080

## 7. Division

| Person | Task | Delivery |
|---|---|---|
| Sun Jianheng | screens 3, 4, 5 | frames with boxes, detail, canvas review |
| Gao Tianxiang | screen 6, mock data | four charts, plausible box positions |
| Fu Yijia | demo script, six screenshots, one page of notes | script and images |
| Yao Tianyu | screen 2, visual consistency, walkthrough | the line runs end to end |

## 8. Timebox

Morning: screens 3, 4, 5 — the main line. Afternoon: screens 2 and 6, navigation. Evening: walk the
line, take screenshots, kill every dead link.

**If it will not finish, drop screen 6.** Statistics can be described out loud; a broken main line
cannot be recovered.

## 9. Explicitly out of scope

No real backend. No permissions, no multi-user, no real export. No mobile. Not all thirteen screens —
**a missing screen beats a half-built one.**
