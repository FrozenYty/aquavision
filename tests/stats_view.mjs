import assert from "node:assert/strict";
import { correctionsView, qualityView, speciesView, trendView } from "../web/static/js/stats.js";
import {
  renderSpeciesDonut,
  renderTotalBars,
  renderTrendLine,
} from "../web/static/js/charts.js";

class Element {
  constructor(tag) { this.tag = tag; this.attrs = {}; this.style = {}; this.children = []; }
  setAttribute(key, value) { this.attrs[key] = value; }
  append(...children) { this.children.push(...children); }
  replaceChildren() { this.children = []; }
}
globalThis.document = { createElementNS: (_, tag) => new Element(tag) };
const data = (basis, total, count, share) => ({ basis, total, days: 7,
  items: [{ class_code: "holothurian", count, share }] });
const reviewed = speciesView(data("reviewed", 6, 4, .6667));
const raw = speciesView(data("raw", 8, 5, .625));
assert.deepEqual([reviewed.total, raw.total], [6, 8]);
assert.match(reviewed.caption, /复核后结果/);
assert.match(raw.caption, /原始识别结果/);
const root = new Element("div");
renderSpeciesDonut(root, reviewed.rows, reviewed.total);
assert.ok(root.children[0].children.some((e) => e.textContent === "6"));
assert.ok(root.children[0].children.some((e) => e.textContent?.includes("66.7%")));
const trend = trendView({ days: 4, items: [0, 40, 50, 0].map((frames) => ({ frames })) });
assert.deepEqual(trend.rows.map((row) => row.changeText), ["—", "—", "+25.0%", "-100.0%"]);
const corrections = correctionsView({ total: 9, modified: 6, added: 2, rejected: 1 });
renderTotalBars(root, corrections.bars);
const bars = root.children[0].children.filter((e) => e.attrs["data-key"]);
assert.equal(bars.length, 3);
assert.equal(bars[0].attrs.height / bars[1].attrs.height, 3);
assert.match(qualityView({ total: 10, rejected: 2, rate: .123 }).caption, /12.3%/);
assert.ok([
  speciesView({ basis: "raw", total: 0, items: [] }),
  trendView({ items: [{ frames: 0 }] }),
  qualityView({ total: 0, rejected: 0, rate: 0 }),
  correctionsView({ total: 0, modified: 0, added: 0, rejected: 0 }),
].every((view) => view.empty));

// Count axes are whole numbers: a maximum of 1 stepped by 0.2 and printed labels
// like "0.6000000000000001". Both count charts must label with integers.
const axisLabels = (root) =>
  root.children[0].children
    .filter((element) => element.tag === "text" && element.attrs["text-anchor"] === "end")
    .map((element) => element.textContent);
renderTotalBars(root, qualityView({ total: 1, rejected: 0, rate: 0 }).bars);
let countLabels = axisLabels(root);
assert.ok(countLabels.length >= 2, `count axis drew ${countLabels.length} labels`);
assert.ok(
  countLabels.every((label) => /^\d+$/.test(label)),
  `fractional count axis: ${countLabels}`,
);

renderTrendLine(root, [
  { date: "2026-11-01", frames: 1 },
  { date: "2026-11-02", frames: 1 },
]);
countLabels = axisLabels(root);
assert.ok(
  countLabels.every((label) => /^\d+$/.test(label)),
  `fractional trend axis: ${countLabels}`,
);

// Fewer than two days cannot be drawn: the line divides by rows.length - 1, which
// was NaN for a one-day response.
const oneDay = trendView({ days: 1, items: [{ date: "2026-11-01", frames: 5 }] });
assert.equal(oneDay.empty, true);
assert.match(oneDay.emptyText, /数据不足两天，画不出趋势/);
const quietOneDay = trendView({ days: 1, items: [{ date: "2026-11-01", frames: 0 }] });
assert.equal(quietOneDay.empty, true);
assert.match(quietOneDay.emptyText, /没有采集任何帧/, "a zero-frame period keeps its no-capture message");

// Every empty state names a next step, as the other pages do.
assert.match(qualityView({ total: 0, rejected: 0, rate: 0 }).emptyText, /href="capture\.html"/);
assert.match(trendView({ days: 7, items: [] }).emptyText, /href="capture\.html"/);
assert.match(
  correctionsView({ total: 0, modified: 0, added: 0, rejected: 0 }).emptyText,
  /href="review\.html"/,
);
assert.match(
  speciesView({ basis: "reviewed", total: 0, items: [], days: 7 }).emptyText,
  /原始识别结果/,
  "the species card keeps its basis hint",
);

// The mock answers in the routers' shapes: days is echoed and applied, and cn_name
// comes from the mock's species catalog instead of repeating the class code.
globalThis.sessionStorage = { getItem: () => null, setItem() {} };
const mock = await import("../web/static/mock/index.js");
const mockGet = async (path, query) => (await mock.handle("GET", path, { query })).data;
const mockSpecies = await mockGet("/stats/species", { days: 3 });
assert.equal(mockSpecies.days, 3);
assert.equal(
  mockSpecies.items.find((item) => item.class_code === "holothurian").cn_name,
  "海参",
);
assert.equal((await mockGet("/stats/quality", { days: 3 })).days, 3);
assert.equal((await mockGet("/stats/corrections", { days: 3 })).days, 3);
const mockTrend = await mockGet("/stats/trend", { days: 3 });
assert.equal(mockTrend.days, 3);
assert.equal(mockTrend.items.length, 3, "the trend item count follows days");
