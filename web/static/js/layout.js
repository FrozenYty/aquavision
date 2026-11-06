// Shared shell: top bar, left menu and footer. Every page except login calls renderShell(pageId).
// Menu groups follow the business domains of SRS §5.1; page IDs follow the SRS page list (§5.2).

import { USE_MOCK } from "./api.js";

// Page ids follow SRS §5.2. Entries without href are not built in the prototype: they stay in the
// menu, greyed and tagged P2, so the full system reads as a schedule rather than as missing pages.
const MENU = [
  { group: "概览", items: [{ id: "P-02", label: "工作台", href: "home.html" }] },
  {
    group: "采集",
    items: [
      { id: "P-03", label: "采集控制", href: "capture.html" },
      { id: "P-04", label: "影像浏览", href: "frames.html" },
    ],
  },
  {
    group: "识别",
    items: [
      { id: "P-05", label: "识别任务", href: "tasks.html" },
      { id: "P-06", label: "识别结果", href: "frame.html" },
    ],
  },
  {
    group: "复核与回流",
    items: [
      { id: "P-07", label: "复核工作台", href: "review.html" },
      { id: "P-08", label: "难例池", href: "hard-samples.html" },
      { id: "P-09", label: "数据集导出", href: "dataset-export.html" },
    ],
  },
  {
    group: "统计与报告",
    items: [
      { id: "P-10", label: "统计与报告", href: "stats.html" },
      { id: "P-11", label: "巡检报告", href: "reports.html" },
    ],
  },
  {
    group: "模型与系统",
    items: [
      { id: "P-12", label: "模型与实验", href: "models.html" },
      { id: "P-13", label: "系统管理" },
    ],
  },
];

const DATA_SOURCE = "数据来源：公开水下数据集与教学演示水箱影像，不含真实海域位置信息。";

function topbarHtml() {
  return `
    <button class="av-menu-toggle" type="button" aria-label="展开菜单">☰</button>
    <a class="av-brand" href="home.html">
      <span class="av-brand-mark" aria-hidden="true"></span>
      <span class="av-brand-name">AQUAVISION</span>
      <small>水下物种识别与监测</small>
    </a>
    <div class="av-topbar-actions">
      <span class="av-clock" aria-hidden="true"></span>
      <a href="#" title="站内消息">消息 <span class="badge rounded-pill text-bg-info">0</span></a>
      <span class="av-topbar-user"><span class="av-avatar" aria-hidden="true">演</span> 演示账号</span>
      <a href="login.html">退出</a>
    </div>`;
}

function menuLinkHtml(item, pageId) {
  if (!item.href) {
    return (
      `<span class="av-menu-link is-planned" aria-disabled="true" title="${item.id} 排在 P2 阶段">` +
      `${item.label}<span class="av-mono">P2</span></span>`
    );
  }
  const active = item.id === pageId;
  return (
    `<a class="av-menu-link${active ? " active" : ""}" href="${item.href}"` +
    `${active ? ' aria-current="page"' : ""}>${item.label}<span class="av-mono">${item.id}</span></a>`
  );
}

function sidebarHtml(pageId) {
  return MENU.map(
    ({ group, items }, i) => `
    <details class="av-menu-group" open>
      <summary><span class="av-mono">${String(i + 1).padStart(2, "0")}</span>${group}</summary>
      ${items.map((item) => menuLinkHtml(item, pageId)).join("")}
    </details>`,
  ).join("");
}

// "P-03 / 采集" above the page title, taken from the menu so it never drifts.
function addEyebrow(pageId) {
  const h1 = document.querySelector(".av-page-header h1");
  const group = MENU.find(({ items }) => items.some((item) => item.id === pageId));
  if (!h1 || !group) return;
  const eyebrow = document.createElement("span");
  eyebrow.className = "av-eyebrow";
  eyebrow.textContent = `${pageId} / ${group.group}`;
  h1.prepend(eyebrow);
}

// Every page says plainly that its numbers are not real while the mock is on (prototype §4).
function addPrototypeBadge() {
  const h1 = document.querySelector(".av-page-header h1");
  if (!USE_MOCK || !h1) return;
  const badge = document.createElement("span");
  badge.className = "av-proto-badge";
  badge.title = "原型阶段，页面数据来自模拟";
  badge.textContent = "原型演示 · 模拟数据";
  h1.after(badge);
}

function startClock(el) {
  const tick = () => {
    el.textContent = new Date().toLocaleString("zh-CN", { hour12: false });
  };
  tick();
  setInterval(tick, 1000);
}

export function renderShell(pageId) {
  const topbar = document.createElement("header");
  topbar.className = "av-topbar";
  topbar.innerHTML = topbarHtml();

  const sidebar = document.createElement("nav");
  sidebar.className = "av-sidebar";
  sidebar.setAttribute("aria-label", "主菜单");
  sidebar.innerHTML = sidebarHtml(pageId);

  document.body.prepend(topbar, sidebar);

  const content = document.querySelector(".av-content");
  const footer = document.createElement("footer");
  footer.className = "av-footer";
  footer.textContent = DATA_SOURCE;
  content.append(footer);

  addEyebrow(pageId);
  addPrototypeBadge();
  startClock(topbar.querySelector(".av-clock"));

  // Stagger the page blocks (and each card inside a grid row) on first paint.
  let i = 0;
  for (const block of content.children) {
    const cards = block.matches(".row") ? block.querySelectorAll(":scope > *") : [block];
    for (const el of cards) {
      el.classList.add("av-reveal");
      el.style.setProperty("--i", i++);
    }
  }

  topbar.querySelector(".av-menu-toggle").addEventListener("click", () => {
    document.body.classList.toggle("av-menu-open");
  });
}
