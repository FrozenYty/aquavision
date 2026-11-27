import assert from "node:assert/strict";
import { correctionsView, qualityView, speciesView, trendView } from "../web/static/js/stats.js";
import { renderSpeciesDonut, renderTotalBars } from "../web/static/js/charts.js";

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
