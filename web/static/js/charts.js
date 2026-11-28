// Hand-rolled SVG charts for screen 6 (statistics page). No chart library: the
// repo rule keeps front-end resources local (ADR 05), and four small charts do
// not justify pulling one in. Colours and type come from tokens.css custom
// properties; nothing is hard-coded here.

import { SPECIES } from "./species.js";

const NS = "http://www.w3.org/2000/svg";

function svgEl(width, height) {
  const s = document.createElementNS(NS, "svg");
  s.setAttribute("viewBox", `0 0 ${width} ${height}`);
  s.setAttribute("role", "img");
  s.style.width = "100%";
  s.style.height = "auto";
  s.style.display = "block";
  return s;
}

function node(name, attrs = {}) {
  const n = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) n.setAttribute(key, value);
  return n;
}

function text(
  x,
  y,
  content,
  { size = 11, fill = "var(--av-text-muted)", anchor = "middle", family, weight } = {},
) {
  const t = node("text", { x, y, "text-anchor": anchor, "font-size": size });
  t.setAttribute("fill", fill);
  if (family) t.setAttribute("font-family", family);
  if (weight) t.setAttribute("font-weight", weight);
  t.textContent = content;
  return t;
}

const shortDate = (iso) => iso.slice(5).replace("-", "/");

// Horizontal grid lines with value labels, shared by the three axis charts.
function yAxis(s, { left, top, bottom, height, width, max, step, unit = "" }) {
  for (let v = 0; v <= max; v += step) {
    const y = top + (1 - v / max) * (height - top - bottom);
    const line = node("line", { x1: left, x2: width - 12, y1: y, y2: y });
    line.setAttribute("stroke", v === 0 ? "var(--av-text-muted)" : "var(--av-border)");
    if (v > 0) line.setAttribute("stroke-dasharray", "3 4");
    s.append(line, text(left - 8, y + 4, `${v}${unit}`, { anchor: "end", size: 10 }));
  }
}

// 1-2-5-10 progression, so tick counts stay between 3 and 6.
function niceStep(max) {
  const raw = max / 5;
  const pow = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map((m) => m * pow).find((step) => step >= raw);
}

// Count axes are whole numbers: a maximum of 1 would otherwise step by 0.2 and
// print labels like "0.6000000000000001". A whole step of at least 1 keeps every
// label an integer; the percent axis is untouched.
function countStep(max) {
  return Math.max(1, Math.ceil(niceStep(max)));
}

// ---- Chart 1: species composition donut ----
export function renderSpeciesDonut(container, rows, total) {
  container.replaceChildren();
  const W = 480;
  const H = 236;
  const s = svgEl(W, H);
  const cx = 112;
  const cy = H / 2;
  const r = 76;
  const sw = 30;
  const circ = 2 * Math.PI * r;
  let acc = 0;
  for (const row of rows) {
    const len = Math.max(row.share * circ - 2, 0.5);
    const seg = node("circle", {
      cx,
      cy,
      r,
      fill: "none",
      "stroke-width": sw,
      "stroke-dasharray": `${len} ${circ - len}`,
      "stroke-dashoffset": -acc,
    });
    seg.setAttribute("transform", `rotate(-90 ${cx} ${cy})`);
    seg.style.stroke = `var(--av-class-${row.class_code})`;
    const tip = node("title");
    tip.textContent = `${SPECIES[row.class_code]}：${row.box_count} 框`;
    seg.append(tip);
    s.append(seg);
    acc += len + 2;
  }
  s.append(
    text(cx, cy - 2, String(total), {
      size: 30,
      fill: "var(--av-text)",
      family: "var(--av-font-display)",
      weight: 700,
    }),
    text(cx, cy + 22, "目标框", { size: 12 }),
  );
  rows.forEach((row, i) => {
    const y = 40 + i * 40;
    const swatch = node("rect", { x: 268, y: y - 12, width: 14, height: 14, rx: 3 });
    swatch.style.fill = `var(--av-class-${row.class_code})`;
    const pct = (row.share * 100).toFixed(1);
    s.append(
      swatch,
      text(292, y, `${SPECIES[row.class_code]} · ${row.class_code}`, {
        anchor: "start",
        fill: "var(--av-text)",
        size: 12.5,
      }),
      text(292, y + 16, `${row.box_count} 框 · ${pct}%`, {
        anchor: "start",
        size: 11,
        family: "var(--av-font-mono)",
      }),
    );
  });
  container.append(s);
}

// ---- Chart 2: daily frames trend line ----
export function renderTrendLine(container, rows) {
  container.replaceChildren();
  const W = 480;
  const H = 236;
  const L = 46;
  const T = 14;
  const B = 30;
  const s = svgEl(W, H);
  const maxV = Math.max(...rows.map((row) => row.frames));
  const step = countStep(maxV);
  const top = Math.ceil(maxV / step) * step;
  yAxis(s, { left: L, top: T, bottom: B, height: H, width: W, max: top, step });

  const xs = rows.map((_, i) => L + (i * (W - L - 14)) / (rows.length - 1));
  const ys = rows.map((row) => T + (1 - row.frames / top) * (H - T - B));

  const area = node("path", {
    d:
      `M ${xs[0]} ${H - B} ${xs.map((x, i) => `L ${x} ${ys[i]}`).join(" ")} ` +
      `L ${xs[xs.length - 1]} ${H - B} Z`,
    fill: "var(--av-primary)",
    opacity: 0.07,
  });
  s.append(area);

  const points = xs.map((x, i) => `${x},${ys[i]}`).join(" ");
  const line = node("polyline", { points, fill: "none" });
  line.setAttribute("stroke", "var(--av-primary)");
  line.setAttribute("stroke-width", 2);
  s.append(line);

  rows.forEach((row, i) => {
    const dot = node("circle", { cx: xs[i], cy: ys[i], r: 3.5, fill: "var(--av-surface)" });
    dot.setAttribute("stroke", "var(--av-primary)");
    dot.setAttribute("stroke-width", 2);
    const tip = node("title");
    tip.textContent = `${row.date}：${row.frames} 帧${row.changeText ? `（较前日 ${row.changeText}）` : ""}`;
    dot.append(tip);
    s.append(dot, text(xs[i], H - B + 18, shortDate(row.date), { size: 10 }));
  });

  const last = rows[rows.length - 1];
  s.append(
    text(xs[xs.length - 1] - 4, ys[ys.length - 1] - 10, String(last.frames), {
      size: 12,
      fill: "var(--av-primary)",
      family: "var(--av-font-mono)",
      weight: 600,
    }),
  );
  container.append(s);
}

// ---- Charts 3 and 4: totals as bars (quality rejection, review corrections) ----
// The server answers both routes with totals for the period, not a daily or per-class breakdown, so they
// are drawn as one bar per total. Each bar's height is its value over the axis maximum.
export function renderTotalBars(container, bars) {
  container.replaceChildren();
  const W = 480;
  const H = 236;
  const L = 46;
  const T = 24;
  const B = 30;
  const s = svgEl(W, H);
  const maxV = Math.max(...bars.map((bar) => bar.value), 1);
  const step = countStep(maxV);
  const top = Math.ceil(maxV / step) * step;
  yAxis(s, { left: L, top: T, bottom: B, height: H, width: W, max: top, step });

  const total = bars.reduce((sum, bar) => sum + bar.value, 0);
  const slot = (W - L - 14) / bars.length;
  const bw = Math.min(slot * 0.5, 64);
  bars.forEach((bar, i) => {
    const x = L + slot * i + (slot - bw) / 2;
    const height = (bar.value / top) * (H - T - B);
    const rect = node("rect", { x, y: H - B - height, width: bw, height, rx: 3, "data-key": bar.key });
    rect.style.fill = `var(--av-${bar.tone})`;
    const share = total ? ` · ${((bar.value / total) * 100).toFixed(1)}%` : "";
    const tip = node("title");
    tip.textContent = `${bar.label}：${bar.value}${share}`;
    rect.append(tip);
    s.append(
      rect,
      text(x + bw / 2, H - B - height - 6, String(bar.value), {
        size: 11,
        fill: "var(--av-text)",
        family: "var(--av-font-mono)",
      }),
      text(x + bw / 2, H - B + 18, bar.label, { size: 11, fill: "var(--av-text)" }),
    );
  });
  container.append(s);
}
