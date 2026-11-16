import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { runInNewContext } from "node:vm";

const timers = new Map();
let timerId = 0;
globalThis.setTimeout = (fn, ms) => { timers.set(++timerId, { fn, ms }); return timerId; };
globalThis.clearTimeout = (id) => timers.delete(id);
const storage = () => ({ getItem: () => null, setItem() {}, removeItem() {} });
globalThis.sessionStorage = storage();
globalThis.localStorage = storage();
globalThis.location = { search: "", pathname: "/templates/home.html" };

class Element {
  constructor(id = "") {
    this.id = id; this.innerHTML = ""; this.textContent = ""; this.value = "";
    this.tagName = "DIV"; this.dataset = {}; this.style = {}; this.handlers = {};
    this.children = []; this.hidden = false;
    this.classList = { add() {}, remove() {}, toggle() {} };
  }
  addEventListener(type, handler) { this.handlers[type] = handler; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  closest() { return null; }
  setAttribute() {}
  append(child) { this.children.push(child); }
  focus() {}
  checkValidity() { return true; }
}

// Explicit (page, fault, expected state) inventory; each case executes that page's actual script,
// real api.js and real UI loader. Only DOM, network and the navigation shell are replaced.
const pages = ["login", "home", "capture", "image-browser", "tasks", "result-detail", "review",
  "hard-samples", "dataset-export", "stats", "reports", "models", "admin"];
const faults = [
  { name: "500", code: 50001, message: "Internal error", expected: /重试|管理员/ },
  { name: "timeout", expected: /超时.*重试/ },
  { name: "401", code: 40101, message: "Session expired", expected: /登录/ },
];
assert.equal(readdirSync(new URL("../web/templates/", import.meta.url)).filter((p) => p.endsWith(".html")).length, pages.length);

for (const page of pages) for (const fault of faults) {
  timers.clear();
  const elements = new Map();
  const get = (id) => { if (!elements.has(id)) elements.set(id, new Element(id)); return elements.get(id); };
  const body = new Element("body");
  const document = { getElementById: get, body, createElement: () => new Element(),
    querySelector: () => null, querySelectorAll: () => [], addEventListener() {} };
  globalThis.document = document;
  globalThis.location = { search: "", pathname: `/templates/${page}.html`, href: "" };
  let requests = 0;
  globalThis.fetch = async (_url, { signal } = {}) => {
    requests++;
    if (fault.name === "timeout") return new Promise((_resolve, reject) => {
      signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    });
    return { status: Number(fault.name), json: async () => ({ code: fault.code, message: fault.message, request_id: "req-test" }) };
  };
  const html = readFileSync(new URL(`../web/templates/${page}.html`, import.meta.url), "utf8");
  let source = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
  const bindings = { document, location, Element, URLSearchParams, AbortController,
    structuredClone, setTimeout, clearTimeout, setInterval() {}, window: { confirm: () => true },
    FormData: class { *[Symbol.iterator]() {} }, renderShell() {} };
  const pending = [];
  const imports = [...source.matchAll(/import\s+([\s\S]*?)\s+from\s+"([^"]+)";/g)];
  for (const [statement, names, url] of imports) {
    source = source.replace(statement, "");
    if (url.endsWith("layout.js")) continue;
    const module = await import(new URL(url, new URL(`../web/templates/${page}.html`, import.meta.url)));
    if (names.trim().startsWith("*")) bindings[names.trim().split(/\s+/).at(-1)] = module;
    else for (const name of names.replace(/[{}]/g, "").split(",").map((x) => x.trim()).filter(Boolean)) {
      bindings[name] = name === "loadInto" ? (...args) => { const p = module.loadInto(...args); pending.push(p); return p; } : module[name];
    }
  }
  runInNewContext(source, bindings, { filename: `${page}.html` });
  if (page === "login") pending.push(get("login-form").handlers.submit({ preventDefault() {} }));
  await Promise.resolve();
  if (fault.name === "timeout") {
    for (const timer of [...timers.values()]) if (timer.ms === 15000) timer.fn();
  }
  // A broken request deadline must fail instead of leaving this test pending forever.
  await Promise.race([Promise.all(pending), new Promise((_resolve, reject) => {
    process.nextTick(() => { if (fault.name === "timeout" && ![...timers.values()].some((t) => t.ms === 15000)) reject(new Error("request has no timeout")); });
  })]);
  await Promise.resolve();
  const text = [...elements.values(), ...body.children.flatMap((el) => el.children)].map((el) => el.innerHTML + el.textContent).join("\n");
  assert.ok(requests > 0, `${page}: fault must reach an actual request`);
  assert.match(text, fault.expected, `${page}/${fault.name}: actionable message`);
  assert.ok(!text.includes("spinner-border"), `${page}/${fault.name}: no spinner remains`);
  if (page === "login") assert.equal(get("btn-login").disabled, false);
  else if (fault.name === "401") assert.match(location.href, /^login\.html\?next=/);
}
console.log("13 pages x 3 faults: actionable messages, cleared spinners and 401 recovery passed");
