// Bounding boxes drawn over a frame. Coordinates are normalised to 0..1 with the origin at the
// top-left corner (api-contract §6), so the overlay scales with the image at any size.

import { esc } from "./ui.js";

// Glossary §4, in class-code order.
export const CLASSES = {
  holothurian: "海参",
  strongylocentrotus: "海胆",
  chlamys: "扇贝",
  asterias: "海星",
};

// Below this a box still awaiting review gets a translucent fill and a review tag, not just a
// different colour (SRS §5.1). Once a reviewer has touched it, it is drawn like any other box.
export const LOW_CONFIDENCE = 0.5;

const pct = (v) => `${(v * 100).toFixed(2)}%`;

export function boxLabel(box) {
  const score = box.is_manual ? "人工" : box.confidence.toFixed(2);
  return `${CLASSES[box.class_code] ?? esc(box.class_code)} ${score}`;
}

// i staggers the fade-in, so boxes arrive one after another as if detection were running.
export function boxHtml(box, i = 0) {
  const classes = [
    "av-box",
    `av-class-${box.class_code}`,
    !box.review_status && !box.is_manual && box.confidence < LOW_CONFIDENCE ? "is-low" : "",
    box.y < 0.06 ? "is-top" : "",
  ].join(" ");
  return (
    `<div class="${classes}" data-id="${box.object_id ?? i}" style="left: ${pct(box.x)}; ` +
    `top: ${pct(box.y)}; width: ${pct(box.w)}; height: ${pct(box.h)}; --i: ${i}">` +
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
  return `<span class="badge text-bg-${REVIEW_KIND[box.review_status]}">${REVIEW[box.review_status]}</span>`;
}

export function countByClass(boxes) {
  const counts = Object.fromEntries(Object.keys(CLASSES).map((code) => [code, 0]));
  for (const box of boxes) counts[box.class_code] = (counts[box.class_code] ?? 0) + 1;
  return counts;
}
