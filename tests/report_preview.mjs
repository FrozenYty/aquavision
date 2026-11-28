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

// A refresh asked for while a request runs waits for it instead of being dropped.
const scans = [];
api.listReports = (query) => new Promise((resolve) => { scans.push({ query, resolve }); });
const submitHistory = get("history-filters").handlers.submit;
submitHistory({ preventDefault() {} });
await new Promise(setImmediate);
assert.equal(scans.length, 1, "a search starts one request");
submitHistory({ preventDefault() {} });
await new Promise(setImmediate);
assert.equal(scans.length, 1, "a refresh waits while a request runs");
assert.deepEqual(scans[0].query, { page: 1, size: 24 }, "no filter is page 1 of the whole archive");
scans[0].resolve({ items: [], total: 0, page: 1, size: 24 });
await new Promise(setImmediate);
await new Promise(setImmediate);
assert.equal(scans.length, 2, "the queued refresh runs once, after the running request");
scans[1].resolve({ items: [], total: 0, page: 1, size: 24 });
await new Promise(setImmediate);
await new Promise(setImmediate);
assert.match(get("history").innerHTML, /还没有生成过报告/, "an empty archive with no filters is a first install");
assert.equal(get("history-search").disabled, false, "the queued refresh frees the search button");
get("history-from").value = "2026-11-01";
get("history-template").value = "brief";
submitHistory({ preventDefault() {} });
await new Promise(setImmediate);
assert.deepEqual(scans[2].query, { page: 1, size: 24, from: "2026-11-01", template: "brief" },
  "the operator's filters travel to the server");
scans[2].resolve({ items: [], total: 0, page: 1, size: 24 });
await new Promise(setImmediate);
assert.match(get("history").innerHTML, /没有符合筛选条件的报告/, "an empty result with a filter blames the filters");
get("history-from").value = "";
get("history-template").value = "";

assert.match(page, /起日<input id="history-from"/);
assert.match(page, /止日<input id="history-to"/);
assert.match(page, /与所选范围有重叠的报告/);
assert.ok(!page.includes("周期开始") && !page.includes("周期结束"), "the filters name an overlap, not period edges");
console.log("Report history: queued refresh, empty copy and server-side filters passed");

// The server filters and pages the archive; the page renders the page it receives and offers the
// filtered total to the pager. Nothing is re-filtered in the browser any more.
assert.deepEqual(view.reportHistoryQuery({
  from: "2026-11-02", to: "2026-11-02", template: "brief", basis: "raw",
}, 2, 24), { page: 2, size: 24, from: "2026-11-02", to: "2026-11-02", template: "brief", basis: "raw" });
assert.deepEqual(view.reportHistoryQuery({ from: "", to: "", template: "", basis: "" }),
  { page: 1, size: 24 }, "a blank filter is left out, not sent empty");
const sent = [];
const pageAnswer = { items: [{ report_id: 2 }], total: 42, page: 3, size: 24 };
const answered = await view.reportHistory(async (query) => { sent.push(query); return pageAnswer; },
  { from: "2026-11-02", to: "2026-11-02" }, 3);
assert.deepEqual(sent, [{ page: 3, size: 24, from: "2026-11-02", to: "2026-11-02" }]);
assert.equal(answered.total, 42, "the total is the server's filtered count, not the rows on this page");
assert.equal(answered.items.length, 1, "the server's page is shown as it arrived");

// The download control exists only where a document does: a ready row with a recorded file.
assert.match(view.reportDownloadControl({ report_code: "RP1", status: "ready", file_path: "reports/RP1.md" }),
  /data-download="RP1"/);
assert.equal(view.reportDownloadControl({ report_code: "RP2", status: "generating", file_path: null }), "");
assert.equal(view.reportDownloadControl({ report_code: "RP3", status: "failed", path: null }), "");
assert.equal(view.reportDownloadControl({ report_code: "RP4", status: "ready", file_path: null }), "");
assert.match(page, /<th>下载<\/th>/, "the history table has the download column");
assert.match(page, /id="pager"/, "the archive is paged by the server, so the table needs a pager");
console.log("Report history: one server page, filtered total and the download control passed");

const { handle } = await import("../web/static/mock/index.js");
const historyBefore = (await handle("GET", "/reports", { query: {} })).data.total;
const emptyPreview = await handle("GET", "/reports/preview", { query: {
  period_start: "1970-01-01", period_end: "1970-01-01", basis: "raw",
} });
assert.equal(emptyPreview.code, 0);
assert.equal(emptyPreview.data.figures.frames, 0);
assert.deepEqual(emptyPreview.data.figures.species, []);
assert.equal((await handle("GET", "/reports", { query: {} })).data.total, historyBefore);

// The mock honours the same filters: the overlap is decided on the operating day, then the page.
const allReports = (await handle("GET", "/reports", { query: {} })).data;
assert.ok(allReports.items.length >= 2);
assert.ok(allReports.items.every((row) =>
  row.period_start.endsWith("+08:00") && row.period_end.endsWith("+08:00")
  && row.created_at.endsWith("+08:00")), "mock report timestamps use the operating offset");
const codes = async (query) => (await handle("GET", "/reports", { query })).data;
assert.deepEqual((await codes({ from: "2026-10-31", to: "2026-10-31" })).items.map((row) => row.report_code),
  ["RP261101-011"], "a report ending 10-31 local belongs to a 10-31 filter");
assert.deepEqual((await codes({ from: "2026-11-01", to: "2026-11-01" })).items.map((row) => row.report_code),
  ["RP261106-012"], "a report starting 11-01 local belongs to a 11-01 filter");
assert.equal((await codes({ from: "2026-11-07", to: "2026-11-07" })).total, 0,
  "a report ending 11-06 local does not reach into 11-07");
assert.equal((await codes({ template: "brief" })).total, 0, "the template filter narrows the mock too");
assert.equal((await codes({ basis: "raw" })).total, 0, "the basis filter narrows the mock too");
const oneWeek = await codes({ template: "standard", size: 1 });
assert.deepEqual([oneWeek.total, oneWeek.items.length, oneWeek.page, oneWeek.size], [2, 1, 1, 1],
  "paging applies to the filtered set");
assert.equal((await handle("GET", "/reports", { query: { from: "2026-11-02", to: "2026-11-01" } })).code, 40002);

// The mock answers the file route with the two parts api.downloadReport() presents.
const file = await handle("GET", "/reports/RP261106-012/file", { query: {} });
assert.equal(file.code, 0);
assert.equal(file.data.filename, "RP261106-012.md");
assert.match(file.data.text, /^# 巡检报告 RP261106-012/);
assert.equal((await handle("GET", "/reports/RP000000-000/file", { query: {} })).code, 40401);
console.log("Report mock: server-side filters, paging and the file route passed");
