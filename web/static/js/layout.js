// Shared shell: top bar, left menu and footer. Every page except login calls renderShell(pageId).
// Menu groups follow the business domains of SRS §5.1; page IDs follow the SRS page list (§5.2).

import { USE_MOCK } from "./api.js";

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
    group: "统计",
    items: [{ id: "P-06", label: "统计与报告", href: "stats.html" }],
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
      ${USE_MOCK ? '<span class="av-status" title="页面数据来自本地模拟">MOCK</span>' : ""}
      <span class="av-clock" aria-hidden="true"></span>
      <a href="#" title="站内消息">消息 <span class="badge rounded-pill text-bg-info">0</span></a>
      <span class="av-topbar-user"><span class="av-avatar" aria-hidden="true">演</span> 演示账号</span>
      <a href="login.html">退出</a>
    </div>`;
}

function sidebarHtml(pageId) {
  return MENU.map(
    ({ group, items }, i) => `
    <details class="av-menu-group" open>
      <summary><span class="av-mono">${String(i + 1).padStart(2, "0")}</span>${group}</summary>
      ${items
        .map(
          (item) =>
            `<a class="av-menu-link${item.id === pageId ? " active" : ""}" href="${item.href}"` +
            `${item.id === pageId ? ' aria-current="page"' : ""}>` +
            `${item.label}<span class="av-mono">${item.id}</span></a>`,
        )
        .join("")}
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
