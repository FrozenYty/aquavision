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

// Destructive actions (cancel, remove, roll back, disable) ask twice (SRS §5.1).
export const confirmAction = (message) => window.confirm(message);

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
