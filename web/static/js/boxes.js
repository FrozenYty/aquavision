// Bounding boxes drawn over a frame. Coordinates are normalised to 0..1 with the origin at the
// top-left corner (api-contract §6), so the overlay scales with the image at any size.

import { esc } from "./ui.js";
import { SPECIES } from "./species.js";

// Glossary §4, in class-code order. Re-exported under the old name for the five pages that
// already import CLASSES from here; new code should import SPECIES from species.js directly.
export const CLASSES = SPECIES;

// Below this a box still awaiting review gets a translucent fill and a review tag, not just a
// different colour (SRS §5.1). Once a reviewer has touched it, it is drawn like any other box.
export const LOW_CONFIDENCE = 0.5;

const pct = (v) => `${(v * 100).toFixed(2)}%`;

// A ground-truth label may quote a box that pokes past the frame edge; the overlay is drawn from
// the clamped rect so nothing ever renders outside the image. The data itself stays as measured —
// clamping at draw time instead of moving the numbers keeps every box on its target (PR #42
// review, item 2).
function clampBox(box) {
  const x = Math.max(0, box.x);
  const y = Math.max(0, box.y);
  return { ...box, x, y, w: Math.min(box.w, 1 - x), h: Math.min(box.h, 1 - y) };
}

export function boxLabel(box) {
  const score = box.is_manual ? "人工" : box.confidence.toFixed(2);
  return `${CLASSES[box.class_code] ?? esc(box.class_code)} ${score}`;
}

// i staggers the fade-in, so boxes arrive one after another as if detection were running.
export function boxHtml(box, i = 0) {
  const b = clampBox(box);
  const classes = [
    "av-box",
    `av-class-${box.class_code}`,
    !box.review_status && !box.is_manual && box.confidence < LOW_CONFIDENCE ? "is-low" : "",
    b.y < 0.06 ? "is-top" : "",
  ].join(" ");
  return (
    `<div class="${classes}" data-id="${box.object_id ?? i}" style="left: ${pct(b.x)}; ` +
    `top: ${pct(b.y)}; width: ${pct(b.w)}; height: ${pct(b.h)}; --i: ${i}">` +
    `<span class="av-box-label">${boxLabel(box)}</span></div>`
  );
}

export function stageHtml(imageUrl, boxes) {
  return (
    `<div class="av-stage"><img src="${esc(imageUrl)}" alt="帧画面" draggable="false">` +
    `${boxes.map(boxHtml).join("")}</div>`
  );
}

// review_status values from the data model; low confidence is called out while still pending.
const REVIEW = ["待复核", "已确认", "已修改", "已驳回"];
const REVIEW_KIND = ["secondary", "success", "info", "danger"];

export function statusBadge(box) {
  if (box.review_status === 0 && !box.is_manual && box.confidence < LOW_CONFIDENCE) {
    return '<span class="badge text-bg-warning">低置信 · 待复核</span>';
  }
  return (
    `<span class="badge text-bg-${REVIEW_KIND[box.review_status]}">` +
    `${REVIEW[box.review_status]}</span>`
  );
}

export function countByClass(boxes) {
  const counts = Object.fromEntries(Object.keys(CLASSES).map((code) => [code, 0]));
  for (const box of boxes) counts[box.class_code] = (counts[box.class_code] ?? 0) + 1;
  return counts;
}
