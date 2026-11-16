import assert from "node:assert/strict";
import { speciesPatch, speciesTable } from "../web/static/js/species-table.js";
import { SPECIES } from "../web/static/js/species.js";

for (const code of Object.keys(SPECIES)) {
  assert.deepEqual(speciesPatch(code, "0.37", true).body, { conf_thr: .37, in_stat: true });
}
for (const value of ["", " ", "NaN", "Infinity", "-0.01", "1.01", "0.333"]) {
  assert.equal(speciesPatch("holothurian", value, true).valid, false, value);
}
assert.equal(speciesPatch("holothurian", "0", false).valid, true);
assert.equal(speciesPatch("holothurian", "1", false).valid, true);
assert.equal(speciesPatch("constructor", ".5", true).valid, false);
assert.equal(speciesPatch("unknown", ".5", true).valid, false);
const rows = Object.entries(SPECIES).map(([class_code, cn_name]) => ({ class_code, cn_name, conf_thr: .5, category: 1, in_stat: true }));
const table = speciesTable([...rows].reverse());
assert.equal((table.html.match(/data-save/g) ?? []).length, 4);
assert.ok(table.html.indexOf("holothurian") < table.html.indexOf("strongylocentrotus"));
assert.equal(table.warning, "");
const refused = speciesTable([...rows, { class_code: "constructor" }]);
assert.equal((refused.html.match(/data-save/g) ?? []).length, 4);
assert.match(refused.warning, /labels.txt/);
assert.ok(!refused.html.includes("constructor"));
assert.match(speciesTable(rows.slice(1)).warning, /holothurian/);
console.log("Species UI: four classes, order, bounds, precision and unknown codes passed");

const { readFileSync } = await import("node:fs");
const { runInNewContext } = await import("node:vm");
const ui = await import("../web/static/js/ui.js");
const functions = await import("../web/static/js/species-table.js");
const elements = new Map();
const get = (id) => {
  if (!elements.has(id)) elements.set(id, { innerHTML: "", handlers: {},
    addEventListener(type, fn) { this.handlers[type] = fn; } });
  return elements.get(id);
};
const requests = [], notices = [];
let refusal = false;
const api = {
  listModels: async () => ({ items: [] }), listExperiments: async () => ({ items: [] }),
  listSpecies: async () => ({ items: rows }),
  updateSpecies: async (code, body) => {
    requests.push({ code, body });
    if (refusal) throw new Error("server refused the class");
  },
};
const source = readFileSync(new URL("../web/templates/models.html", import.meta.url), "utf8")
  .match(/<script type="module">([\s\S]*?)<\/script>/)[1].replace(/import[\s\S]*?from\s+"[^"\n]+";/g, "");
runInNewContext(source, { ...ui, ...functions, api, CLASSES: SPECIES,
  document: { getElementById: get }, renderShell() {}, bindTabs() {},
  toast: (message, kind) => notices.push({ message, kind }),
  loadInto: async (el, fetcher, options) => { const data = await fetcher(); options.render(data); return data; },
});
await new Promise(setImmediate);
const input = { value: ".333", classList: { toggle() {} } };
const button = { disabled: false };
const row = { dataset: { code: "holothurian" }, querySelector: (selector) => selector.includes("number") ? input : { checked: true } };
const target = { closest: (selector) => selector === "tr" ? row : button };
await get("species").handlers.click({ target });
assert.equal(requests.length, 0, "invalid precision never reaches the API");
input.value = ".37";
await get("species").handlers.click({ target });
assert.equal(requests[0].body.conf_thr, .37);
assert.equal(requests[0].code, "holothurian");
assert.equal(button.disabled, false);
refusal = true;
input.value = ".41";
await get("species").handlers.click({ target });
assert.equal(input.value, ".41", "a refused save retains the operator's value");
assert.equal(notices.at(-1).kind, "danger");
assert.equal(button.disabled, false);
