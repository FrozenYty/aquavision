// Geometry for the review canvas, kept free of the DOM so it can be tested by running it
// (tests/test_review_canvas.py). Boxes are normalised to 0..1 from the top-left corner (api-contract §6).
//
// Zoom changes the stage's real width inside a scrolling viewport; it is never a CSS transform. So the
// stage's bounding rectangle is always the picture as drawn, and one conversion is enough at any zoom
// level and any scroll position: screen -> stage rectangle -> normalised image coordinates.

export const ZOOM_STEPS = [0.5, 0.75, 1, 1.5, 2, 3, 4];
export const MIN_BOX = 0.01; // a drawn box smaller than this on either side was a click, not a drag

const clamp01 = (v) => Math.min(1, Math.max(0, v));

// rect is the stage's bounding rectangle in client coordinates ({ left, top, width, height }).
// Returns null while the stage has no size yet (the picture has not loaded), so a click then is ignored
// instead of producing NaN coordinates.
export function toImageCoords(clientX, clientY, rect) {
  if (!rect || !(rect.width > 0) || !(rect.height > 0)) return null;
  return {
    x: clamp01((clientX - rect.left) / rect.width),
    y: clamp01((clientY - rect.top) / rect.height),
  };
}

// The next zoom step up (dir > 0) or down (dir < 0); stays put at either end.
export function nextZoom(current, dir) {
  const i = ZOOM_STEPS.findIndex((step) => step >= current - 1e-9);
  const at = i === -1 ? ZOOM_STEPS.length - 1 : i;
  const exact = Math.abs(ZOOM_STEPS[at] - current) < 1e-9;
  if (dir > 0) return ZOOM_STEPS[Math.min(ZOOM_STEPS.length - 1, exact ? at + 1 : at)];
  return ZOOM_STEPS[Math.max(0, at - 1)];
}

// A box being drawn, from where the pointer went down to where it is now.
export function drawBox(start, p) {
  return {
    x: Math.min(start.x, p.x),
    y: Math.min(start.y, p.y),
    w: Math.abs(p.x - start.x),
    h: Math.abs(p.y - start.y),
  };
}

// A box moved by (dx, dy): it keeps its size and stops at the picture's edge rather than leaving it.
export function moveBox(from, dx, dy) {
  return {
    x: Math.min(Math.max(0, from.x + dx), 1 - from.w),
    y: Math.min(Math.max(0, from.y + dy), 1 - from.h),
    w: from.w,
    h: from.h,
  };
}

// A box resized from one corner ("nw", "ne", "sw", "se"): the opposite corner stays put, every edge is
// clamped to the picture, and dragging past the opposite corner flips the box instead of inverting it.
export function resizeBox(from, handle, dx, dy) {
  let left = from.x;
  let right = from.x + from.w;
  let top = from.y;
  let bottom = from.y + from.h;
  if (handle.endsWith("w")) left = clamp01(left + dx);
  if (handle.endsWith("e")) right = clamp01(right + dx);
  if (handle.startsWith("n")) top = clamp01(top + dy);
  if (handle.startsWith("s")) bottom = clamp01(bottom + dy);
  return {
    x: Math.min(left, right),
    y: Math.min(top, bottom),
    w: Math.abs(right - left),
    h: Math.abs(bottom - top),
  };
}

// Where to scroll so the image point under the pointer stays under it after a zoom. before and after
// are the stage rectangles; returns how far to scroll the viewport, in pixels.
export function anchorScroll(clientX, clientY, before, after) {
  const p = toImageCoords(clientX, clientY, before);
  if (!p || !after) return { dx: 0, dy: 0 };
  return {
    dx: after.left + p.x * after.width - clientX,
    dy: after.top + p.y * after.height - clientY,
  };
}
