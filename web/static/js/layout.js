// Shared shell: top bar, left menu and footer. Every page except login calls renderShell(pageId).
// Menu groups follow the business domains of SRS §5.1; page IDs follow the SRS page list (§5.2).

const MENU = [
  { group: "概览", items: [{ id: "P-02", label: "工作台", href: "home.html" }] },
  { group: "采集", items: [{ id: "P-03", label: "采集控制", href: "capture.html" }] },
];

const DATA_SOURCE = "数据来源：公开水下数据集与教学演示水箱影像，不含真实海域位置信息。";

function topbarHtml() {
  return `
    <button class="av-menu-toggle" type="button" aria-label="展开菜单">☰</button>
    <a class="av-brand" href="home.html">
      <span class="av-brand-mark" aria-hidden="true"></span>
      AquaVision <small>水下物种识别与监测</small>
    </a>
    <div class="av-topbar-actions">
      <a href="#" title="站内消息">消息 <span class="badge rounded-pill text-bg-info">0</span></a>
      <span class="av-topbar-user">演示账号</span>
      <a href="login.html">退出</a>
    </div>`;
}

function sidebarHtml(pageId) {
  return MENU.map(
    ({ group, items }) => `
    <details class="av-menu-group" open>
      <summary>${group}</summary>
      ${items
        .map(
          (item) =>
            `<a class="av-menu-link${item.id === pageId ? " active" : ""}" href="${item.href}"` +
            `${item.id === pageId ? ' aria-current="page"' : ""}>${item.label}</a>`,
        )
        .join("")}
    </details>`,
  ).join("");
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

  const footer = document.createElement("footer");
  footer.className = "av-footer";
  footer.textContent = DATA_SOURCE;
  document.querySelector(".av-content").append(footer);

  topbar.querySelector(".av-menu-toggle").addEventListener("click", () => {
    document.body.classList.toggle("av-menu-open");
  });
}
