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
const page = readFileSync(new URL("../web/templates/reports.html", import.meta.url), "utf8");
const source = page.match(/<script type="module">([\s\S]*?)<\/script>/)[1]
  .replace(/import[\s\S]*?from\s+"[^"\n]+";/g, "");
runInNewContext(source, { ...ui, ...view, ...time, api, document, renderShell() {}, toast() {},
  loadInto: (...args) => { const p = ui.loadInto(...args); pending.push(p); return p; } });
await Promise.all(pending);
assert.equal(requests.length, 1);
assert.equal(get("btn-generate").disabled, true);
get("from").value = "2026-11-03";
get("to").value = "2026-11-03";
get("from").handlers.change();
assert.equal(requests.length, 2);
const response = (query, frames) => ({ ...query, preview_token: "test-preview-token", model_version: "v8n-test", figures: {
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
assert.equal(get("generation-status").textContent, "生成中…");
assert.equal(generated[0].period_start, "2026-11-03");
assert.equal(generated[0].basis, "raw");
assert.equal(generated[0].preview_token, "test-preview-token");
get("basis").value = "reviewed";
get("basis").handlers.change();
requests[2].resolve(response(requests[2].query, 3));
await new Promise(setImmediate);
assert.equal(get("btn-generate").disabled, true, "a new preview cannot unlock an in-flight generation");
finishGeneration({ report_code: "RP-1" });
await submission;
assert.match(get("generation-status").textContent, /RP-1.*已生成/);
assert.equal(get("btn-generate").disabled, false);
get("basis").value = "raw";
get("basis").handlers.change();
requests[3].reject(new Error("preview unavailable; retry"));
await new Promise(setImmediate);
assert.equal(get("btn-generate").disabled, true);
assert.match(get("preview").innerHTML, /preview unavailable/);
assert.ok(!get("preview").innerHTML.includes("spinner-border"));
console.log("Report page: selected period, stale responses, generation gate and failure passed");

// A refresh asked for while a scan runs waits for it instead of being dropped.
const scans = [];
api.listReports = () => new Promise((resolve) => { scans.push(resolve); });
const submitHistory = get("history-filters").handlers.submit;
submitHistory({ preventDefault() {} });
await new Promise(setImmediate);
assert.equal(scans.length, 1, "a search starts one scan");
submitHistory({ preventDefault() {} });
await new Promise(setImmediate);
assert.equal(scans.length, 1, "a refresh waits while a scan runs");
scans[0]({ items: [] });
await new Promise(setImmediate);
await new Promise(setImmediate);
assert.equal(scans.length, 2, "the queued refresh runs once, after the running scan");
scans[1]({ items: [] });
await new Promise(setImmediate);
await new Promise(setImmediate);
assert.match(get("history").innerHTML, /还没有生成过报告/, "an empty archive with no filters is a first install");
assert.equal(get("history-search").disabled, false, "the queued refresh frees the search button");
get("history-from").value = "2026-11-01";
submitHistory({ preventDefault() {} });
await new Promise(setImmediate);
scans[2]({ items: [] });
await new Promise(setImmediate);
assert.match(get("history").innerHTML, /没有符合筛选条件的报告/, "an empty result with a filter blames the filters");
get("history-from").value = "";

assert.match(page, /起日<input id="history-from"/);
assert.match(page, /止日<input id="history-to"/);
assert.match(page, /与所选范围有重叠的报告/);
assert.ok(!page.includes("周期开始") && !page.includes("周期结束"), "the filters name an overlap, not period edges");

// Paging follows full pages and dedupes: a report inserted between pages shifts the live list.
{
  const rows = Array.from({ length: 200 }, (_, index) => ({ report_id: 200 - index }));
  let fetches = 0;
  const out = await view.reportHistory(async ({ page: position, size }) => {
    fetches += 1;
    if (fetches === 2) rows.unshift({ report_id: 201 });   // a colleague generates a report mid-scan
    return { total: rows.length, items: rows.slice((position - 1) * size, position * size) };
  }, {});
  const ids = out.items.map((row) => row.report_id);
  assert.equal(ids.length, 200);
  assert.equal(new Set(ids).size, 200, "a shift cannot count one report twice");
  assert.ok(ids.includes(1), "a shift cannot skip the oldest report");
  assert.ok(!ids.includes(201), "a report created mid-scan is not half-read");
}
{
  const fetched = [];
  const out = await view.reportHistory(async ({ page: position }) => {
    fetched.push(position);
    return { total: 1000, items: position === 1 ? [{ report_id: 1 }, { report_id: 2 }] : [] };
  }, {});
  assert.deepEqual(fetched, [1], "a short page ends the scan regardless of total");
  assert.equal(out.items.length, 2);
}
console.log("Report history: queued refresh, empty copy, overlap and paging passed");

const { handle } = await import("../web/static/mock/index.js");
const historyBefore = (await handle("GET", "/reports", { query: {} })).data.total;
const emptyPreview = await handle("GET", "/reports/preview", { query: {
  period_start: "1970-01-01", period_end: "1970-01-01", basis: "raw",
} });
assert.equal(emptyPreview.code, 0);
assert.equal(emptyPreview.data.figures.frames, 0);
assert.deepEqual(emptyPreview.data.figures.species, []);
assert.equal((await handle("GET", "/reports", { query: {} })).data.total, historyBefore);

// The mock rows carry the operating offset, so the day a filter compares is the operating day: a
// report whose period is 10-01..10-31 local belongs to an October filter, not to 11-01.
const mockReports = (await handle("GET", "/reports", { query: {} })).data.items;
assert.ok(mockReports.every((row) =>
  row.period_start.endsWith("+08:00") && row.period_end.endsWith("+08:00")
  && row.created_at.endsWith("+08:00")), "mock report timestamps use the operating offset");
const mockPage = async ({ page: position, size }) => ({
  total: mockReports.length, items: mockReports.slice((position - 1) * size, position * size),
});
const lastOfOctober = await view.reportHistory(mockPage, { from: "2026-10-31", to: "2026-10-31" });
assert.ok(lastOfOctober.items.some((row) => row.report_code === "RP261101-011"),
  "a report ending 10-31 local belongs to a 10-31 filter");
const firstOfNovember = await view.reportHistory(mockPage, { from: "2026-11-01", to: "2026-11-01" });
assert.ok(firstOfNovember.items.some((row) => row.report_code === "RP261106-012"),
  "a report starting 11-01 local belongs to a 11-01 filter");
const seventhOfNovember = await view.reportHistory(mockPage, { from: "2026-11-07", to: "2026-11-07" });
assert.ok(!seventhOfNovember.items.some((row) => row.report_code === "RP261106-012"),
  "a report ending 11-06 local does not reach into 11-07");
// A +08:00 end just after local midnight stays on its operating day.
const boundary = await view.reportHistory(async () => ({ items: [
  { report_id: 9, period_start: "2026-11-02T00:00:00+08:00", period_end: "2026-11-02T00:30:00+08:00" },
] }), { from: "2026-11-02", to: "2026-11-02" });
assert.equal(boundary.items.length, 1);

// The range is an overlap test against the period, not equality: 11-01..11-03 matches 11-02.
const archive = [
  { report_id: 2, period_start: "2026-11-01T00:00:00+08:00", period_end: "2026-11-03T23:59:59+08:00", template: "brief", basis: "raw" },
  { report_id: 1, period_start: "2026-10-01T00:00:00+08:00", period_end: "2026-10-04T23:59:59+08:00", template: "standard", basis: "reviewed" },
];
const search = await view.reportHistory(async () => ({ total: archive.length, items: archive }),
  { from: "2026-11-02", to: "2026-11-02", template: "brief", basis: "raw" });
assert.deepEqual(search.items, [archive[0]]);
