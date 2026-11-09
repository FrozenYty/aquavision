// Small rendering helpers shared by pages. No state lives here.

export const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

// Timestamps arrive as ISO 8601 with offset; render in the browser's local zone.
export function fmtTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

// Retake is marked by text as well as colour (SRS §5.1).
export function qualityBadge(quality) {
  return quality.verdict === "ok"
    ? `<span class="badge text-bg-success">质量 ${quality.score}</span>`
    : `<span class="badge text-bg-warning">需重拍 · ${quality.score}</span>`;
}

export function toast(message, kind = "info") {
  let box = document.querySelector(".av-toasts");
  if (!box) {
    box = document.createElement("div");
    box.className = "av-toasts";
    document.body.append(box);
  }
  const item = document.createElement("div");
  item.className = `alert alert-${kind} shadow-sm py-2 mb-2`;
  item.setAttribute("role", "status");
  item.textContent = message;
  box.append(item);
  setTimeout(() => item.remove(), 3500);
}

// ---- Loading, empty and failure (handover §3.3) ----
// Mock data never fails, so until P2 no page had drawn a failure. Every region that waits on the API
// goes through loadInto(): a slow answer shows its own words and must never look like an empty one.

const SLOW_MS = 5000;

// A table body takes its message as one full-width row; anything else takes a plain block.
function stateBlock(el, html) {
  if (el.tagName === "TBODY") {
    const cols = el.closest("table")?.querySelectorAll("thead th").length || 1;
    el.innerHTML = `<tr><td colspan="${cols}">${html}</td></tr>`;
  } else {
    el.innerHTML = html;
  }
}

export function showLoading(el, text = "正在加载…") {
  stateBlock(el, `<div class="av-state" role="status"><span class="spinner-border spinner-border-sm"></span>
    <span class="av-state-text">${text}</span></div>`);
}

export function showEmpty(el, html) {
  stateBlock(el, `<div class="av-empty">${html}</div>`);
}

export function showError(el, err, retry) {
  stateBlock(el, `<div class="av-state is-error" role="alert">加载失败：${esc(err.message)}
    ${retry ? '<button class="btn btn-sm btn-outline-danger ms-2" type="button" data-retry>重试</button>' : ""}</div>`);
  el.querySelector("[data-retry]")?.addEventListener("click", retry);
}

// Runs fetcher, then render(data) or the empty state. quiet: true skips the spinner, for a refresh of
// a list already on screen. Returns the data, or undefined when the call failed.
export async function loadInto(el, fetcher, { render, isEmpty, empty, quiet = false }) {
  if (!quiet) showLoading(el);
  const slow = setTimeout(() => {
    const text = el.querySelector(".av-state-text");
    if (text) text.textContent = "服务器响应较慢，仍在等待…";
  }, SLOW_MS);
  try {
    const data = await fetcher();
    if (isEmpty(data)) showEmpty(el, empty);
    else render(data);
    return data;
  } catch (err) {
    showError(el, err, () => loadInto(el, fetcher, { render, isEmpty, empty }));
    return undefined;
  } finally {
    clearTimeout(slow);
  }
}

// Destructive actions (cancel, remove, roll back, disable) ask twice (SRS §5.1).
export const confirmAction = (message) => window.confirm(message);

// Tabs without Bootstrap's script: buttons carry data-tab, panels carry data-panel.
export function bindTabs(root) {
  root.addEventListener("click", (event) => {
    const tab = event.target.closest("[data-tab]")?.dataset.tab;
    if (!tab) return;
    root.querySelectorAll("[data-tab]").forEach((el) => el.classList.toggle("active", el.dataset.tab === tab));
    root.querySelectorAll("[data-panel]").forEach((el) => { el.hidden = el.dataset.panel !== tab; });
  });
}

// Bootstrap pagination for a {total, page, size} block; calls onPage(n) on click.
export function renderPager(el, { total, page, size }, onPage) {
  const pages = Math.max(1, Math.ceil(total / size));
  const item = (n, label, disabled, active) =>
    `<li class="page-item${disabled ? " disabled" : ""}${active ? " active" : ""}">` +
    `<button class="page-link" type="button" data-page="${n}">${label}</button></li>`;
  const numbers = Array.from({ length: pages }, (_, i) => item(i + 1, i + 1, false, i + 1 === page));
  el.innerHTML =
    `<span class="text-secondary small me-auto">共 ${total} 条</span>` +
    `<ul class="pagination pagination-sm mb-0">` +
    `${item(page - 1, "上一页", page <= 1)}${numbers.join("")}${item(page + 1, "下一页", page >= pages)}</ul>`;
  el.onclick = (event) => {
    const n = Number(event.target.dataset.page);
    if (n && n !== page) onPage(n);
  };
}
