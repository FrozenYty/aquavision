import assert from "node:assert/strict";
import { rememberEdit, undoEdit } from "../web/static/js/history.js";

const original = [{ object_id: 1, x: 0.1, class_code: "holothurian" }];
const moved = [{ ...original[0], x: 0.2 }];
const drawn = [...moved, { object_id: 2, x: 0.4 }];
let history = [];
history = rememberEdit(history, original, 1);
history = rememberEdit(history, moved, 1);
history = rememberEdit(history, drawn, 2);
let step = undoEdit(history);
assert.deepEqual(step.objects, drawn, "undo delete restores the drawn box");
assert.equal(step.selected, 2);
step = undoEdit(step.history);
assert.deepEqual(step.objects, moved, "undo draw leaves the moved box");
step = undoEdit(step.history);
assert.deepEqual(step.objects, original, "undo drag restores the initial geometry");
assert.equal(undoEdit(step.history), null, "empty history is a no-op");
assert.equal(history.length, 3, "undo never mutates its input");
original[0].x = 0.9;
assert.equal(history[0].objects[0].x, 0.1, "snapshots do not share mutable boxes");
step.objects[0].x = 0.8;
assert.equal(history[0].objects[0].x, 0.1, "restored boxes do not mutate history");
console.log("Review history: drag, draw, delete, selection and isolation passed");

// Run the page's real handlers with a minimal DOM; geometry and history stay real modules.
const { readFileSync } = await import("node:fs");
const { runInNewContext } = await import("node:vm");
const geometry = await import("../web/static/js/canvas.js");
const historyFns = await import("../web/static/js/history.js");
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    value: "holothurian", dataset: {}, style: {}, handlers: {}, disabled: false,
    classList: { toggle() {}, add() {} },
    addEventListener(type, handler) { this.handlers[type] = handler; },
    querySelector() { return null; }, setPointerCapture() {},
    getBoundingClientRect() { return { left: 0, top: 0, width: 1000, height: 500 }; },
    click() { if (!this.disabled) return this.onclick?.(); },
  });
  return elements.get(id);
}
const document = { getElementById: element, addEventListener(type, fn) { this[type] = fn; } };
const context = { ...geometry, ...historyFns, document, structuredClone, Element: class {},
  renderShell() {}, CLASSES: { holothurian: "Sea cucumber" },
  boxHtml: () => "", statusBadge: () => "", confirmAction: () => true,
  loadInto() {}, api: { getObjects: async () => ({ items: [] }) },
};
const html = readFileSync(new URL("../web/templates/review.html", import.meta.url), "utf8");
const source = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1]
  .replace(/import[\s\S]*?from\s+"[^"\n]+";/g, "");
runInNewContext(source + `
  globalThis.reviewTest = {
    init() { imageWidth = 1280; imageHeight = 720; frameId = "frame-1"; objects = [{ object_id: 1, x: .1, y: .1, w: .2, h: .2,
      class_code: "holothurian", confidence: .5, review_status: 0 }]; selected = 1; },
    state() { return structuredClone({ objects, selected, steps: history.length }); },
    reloadBoxes,
  };
`, context);
const page = context.reviewTest;
page.init();
const viewport = element("viewport");
const boxTarget = { dataset: {}, closest: (selector) => selector === ".av-box" ? { dataset: { id: "1" } } : {} };
const pointer = (x, y, target = boxTarget) => ({ button: 0, pointerId: 1, clientX: x, clientY: y, target });
const move = () => {
  viewport.handlers.pointerdown(pointer(150, 100));
  viewport.handlers.pointermove(pointer(250, 100));
  viewport.handlers.pointerup();
};
move();
assert.equal(page.state().steps, 1);
viewport.handlers.pointerdown(pointer(250, 100));
viewport.handlers.pointermove(pointer(350, 100));
viewport.handlers.pointercancel();
assert.equal(page.state().steps, 1, "cancel preserves earlier history");
assert.equal(page.state().objects[0].x, .2);
viewport.handlers.pointerdown(pointer(250, 100));
viewport.handlers.pointerup();
assert.equal(page.state().steps, 1, "selection alone does not consume undo");
element("tool-draw").click();
viewport.handlers.pointerdown(pointer(500, 250));
viewport.handlers.pointermove(pointer(700, 350));
viewport.handlers.pointerup();
assert.equal(page.state().objects.length, 2);
element("tool-delete").click();
assert.equal(page.state().objects.length, 1);
element("tool-undo").click();
assert.equal(page.state().objects.length, 2);
element("tool-undo").click();
assert.equal(page.state().objects.length, 1);
let prevented = false;
document.keydown({ key: "z", ctrlKey: true, preventDefault() { prevented = true; } });
assert.equal(prevented, true);
assert.equal(page.state().objects[0].x, .1);
assert.equal(element("tool-undo").disabled, true);
element("class-select").value = "echinus";
element("class-select").handlers.change();
assert.equal(page.state().objects[0].class_code, "echinus");
element("tool-undo").click();
assert.equal(page.state().objects[0].class_code, "holothurian");
assert.equal(element("class-select").value, "holothurian", "undo updates the class chooser");
element("tool-draw").click();
viewport.handlers.pointerdown(pointer(500, 250));
viewport.handlers.pointerup();
assert.equal(page.state().objects.length, 1, "a tiny draw is discarded");
assert.equal(page.state().steps, 0);
move();
const key = (name, shiftKey = false) => document.keydown({ key: name, shiftKey, preventDefault() {} });
const xBefore = page.state().objects[0].x;
key("ArrowRight");
assert.equal(page.state().objects[0].x, xBefore + 1 / 1280);
key("z");
element("tool-undo").click();
assert.equal(page.state().objects[0].x, xBefore);
const widthBefore = page.state().objects[0].w;
key("ArrowRight", true);
assert.equal(page.state().objects[0].w, widthBefore + 1 / 1280);
element("tool-undo").click();
key("n");
assert.equal(page.state().selected, 1);
key("Delete");
assert.equal(page.state().objects.length, 0);
element("tool-undo").click();
assert.equal(page.state().objects.length, 1);
const getObjects = context.api.getObjects;
context.api.getObjects = async () => { throw new Error("offline"); };
await assert.rejects(page.reloadBoxes(), /offline/);
assert.equal(page.state().steps, 1, "failed reload preserves local undo");
context.api.getObjects = getObjects;
await page.reloadBoxes();
assert.equal(page.state().steps, 0, "server reload clears pre-submit history");
console.log("Review page handlers: undo chain, cancelled drag, click and reload passed");
