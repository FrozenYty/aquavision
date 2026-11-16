import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import * as ui from "../web/static/js/ui.js";
import * as view from "../web/static/js/report-preview.js";
import * as time from "../web/static/js/time.js";

const elements = new Map();
const get = (id) => {
  if (!elements.has(id)) elements.set(id, { value: "", innerHTML: "", handlers: {},
    addEventListener(type, handler) { this.handlers[type] = handler; },
    classList: { toggle() {} }, querySelector: () => null });
  return elements.get(id);
};
const document = { getElementById: get };
globalThis.document = document;
get("period").value = "custom";
get("from").value = "2026-11-02";
get("to").value = "2026-11-02";
get("basis").value = "raw";
get("template").value = "standard";
const requests = [], generated = [];
let finishGeneration;
const api = {
  statsTrend: async () => ({ items: [{ date: "2026-11-02" }] }),
  listReports: async () => ({ items: [] }),
  previewReport: (query) => new Promise((resolve, reject) => requests.push({ query, resolve, reject })),
  createReport: async (body) => { generated.push(body); return new Promise((resolve) => { finishGeneration = resolve; }); },
};
const pending = [];
const source = readFileSync(new URL("../web/templates/reports.html", import.meta.url), "utf8")
  .match(/<script type="module">([\s\S]*?)<\/script>/)[1].replace(/import[\s\S]*?from\s+"[^"\n]+";/g, "");
runInNewContext(source, { ...ui, ...view, ...time, api, document, renderShell() {}, toast() {},
  loadInto: (...args) => { const p = ui.loadInto(...args); pending.push(p); return p; } });
await Promise.all(pending);
assert.equal(requests.length, 1);
assert.equal(get("btn-generate").disabled, true);
get("from").value = "2026-11-03";
get("to").value = "2026-11-03";
get("from").handlers.change();
assert.equal(requests.length, 2);
const response = (query, frames) => ({ ...query, model_version: "v8n-test", figures: {
  frames, rejected: 1, rate: .5, species: [{ name: "Sea cucumber", count: 4, share: 1 }],
} });
requests[0].resolve(response(requests[0].query, 7));
await new Promise(setImmediate);
assert.equal(get("btn-generate").disabled, true, "stale success cannot enable generation");
requests[1].resolve(response(requests[1].query, 2));
await new Promise(setImmediate);
assert.match(get("preview").innerHTML, /2 帧/);
assert.ok(!get("preview").innerHTML.includes("7 帧"));
assert.equal(get("btn-generate").disabled, false);
const submission = get("report-form").handlers.submit({ preventDefault() {} });
await new Promise(setImmediate);
assert.equal(generated[0].period_start, "2026-11-03");
assert.equal(generated[0].basis, "raw");
get("basis").value = "reviewed";
get("basis").handlers.change();
requests[2].resolve(response(requests[2].query, 3));
await new Promise(setImmediate);
assert.equal(get("btn-generate").disabled, true, "a new preview cannot unlock an in-flight generation");
finishGeneration({ report_code: "RP-1" });
await submission;
assert.equal(get("btn-generate").disabled, false);
get("basis").value = "raw";
get("basis").handlers.change();
requests[3].reject(new Error("preview unavailable; retry"));
await new Promise(setImmediate);
assert.equal(get("btn-generate").disabled, true);
assert.match(get("preview").innerHTML, /preview unavailable/);
assert.ok(!get("preview").innerHTML.includes("spinner-border"));
console.log("Report page: selected period, stale responses, generation gate and failure passed");

const { handle } = await import("../web/static/mock/index.js");
const historyBefore = (await handle("GET", "/reports", { query: {} })).data.total;
const emptyPreview = await handle("GET", "/reports/preview", { query: {
  period_start: "1970-01-01", period_end: "1970-01-01", basis: "raw",
} });
assert.equal(emptyPreview.code, 0);
assert.equal(emptyPreview.data.figures.frames, 0);
assert.deepEqual(emptyPreview.data.figures.species, []);
assert.equal((await handle("GET", "/reports", { query: {} })).data.total, historyBefore);
