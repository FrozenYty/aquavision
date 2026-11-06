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

// ---- Chart 1: species composition donut ----
export function renderSpeciesDonut(container, rows) {
  container.replaceChildren();
  const total = rows.reduce((sum, row) => sum + row.box_count, 0);
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
    const len = Math.max((row.box_count / total) * circ - 2, 0.5);
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
    const pct = ((row.box_count / total) * 100).toFixed(1);
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
  const step = niceStep(maxV);
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
    tip.textContent = `${row.date}：${row.frames} 帧`;
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

// ---- Chart 3: quality interception rate bars ----
export function renderInterceptBars(container, rows) {
  container.replaceChildren();
  const W = 480;
  const H = 236;
  const L = 46;
  const T = 18;
  const B = 30;
  const s = svgEl(W, H);
  const rates = rows.map((row) => ({ ...row, rate: (row.intercepted / row.total) * 100 }));
  const maxRate = Math.max(...rates.map((row) => row.rate));
  const step = niceStep(maxRate);
  const top = Math.ceil(maxRate / step) * step;
  yAxis(s, { left: L, top: T, bottom: B, height: H, width: W, max: top, step, unit: "%" });

  const slot = (W - L - 14) / rows.length;
  const bw = Math.min(slot * 0.56, 40);
  rates.forEach((row, i) => {
    const x = L + slot * i + (slot - bw) / 2;
    const y = T + (1 - row.rate / top) * (H - T - B);
    const bar = node("rect", { x, y, width: bw, height: H - B - y, rx: 3 });
    bar.style.fill = "var(--av-warning)";
    bar.setAttribute("opacity", i === rows.length - 1 ? 1 : 0.75);
    const tip = node("title");
    tip.textContent = `${row.date}：拦截 ${row.intercepted}/${row.total} 帧（${row.rate.toFixed(1)}%）`;
    bar.append(tip);
    s.append(
      bar,
      text(x + bw / 2, y - 6, `${row.rate.toFixed(1)}%`, {
        size: 10,
        fill: "var(--av-text)",
        family: "var(--av-font-mono)",
      }),
      text(x + bw / 2, H - B + 18, shortDate(row.date), { size: 10 }),
    );
  });
  container.append(s);
}

// ---- Chart 4: review corrections stacked bars ----
export function renderCorrectionStack(container, rows) {
  container.replaceChildren();
  const W = 480;
  const H = 236;
  const L = 46;
  const T = 30;
  const B = 30;
  const s = svgEl(W, H);
  const series = [
    ["relabel", "改类别", "var(--av-primary)"],
    ["added", "补框", "var(--av-success)"],
    ["removed", "删框", "var(--av-danger)"],
  ];
  const totals = rows.map((row) => series.reduce((sum, [key]) => sum + row[key], 0));
  const maxV = Math.max(...totals);
  const step = niceStep(maxV);
  const top = Math.ceil(maxV / step) * step;
  yAxis(s, { left: L, top: T, bottom: B, height: H, width: W, max: top, step });

  const slot = (W - L - 14) / rows.length;
  const bw = Math.min(slot * 0.5, 44);
  rows.forEach((row, i) => {
    const x = L + slot * i + (slot - bw) / 2;
    let yCursor = H - B;
    for (const [key, name, color] of series) {
      const hgt = (row[key] / top) * (H - T - B);
      yCursor -= hgt;
      if (hgt > 0) {
        const seg = node("rect", { x, y: yCursor, width: bw, height: hgt });
        seg.style.fill = color;
        const tip = node("title");
        tip.textContent = `${SPECIES[row.class_code]} · ${name} ${row[key]} 次`;
        seg.append(tip);
        s.append(seg);
      }
    }
    s.append(
      text(x + bw / 2, H - B + 18, SPECIES[row.class_code], { size: 11, fill: "var(--av-text)" }),
    );
  });

  series.forEach(([, name, color], i) => {
    const x = 60 + i * 110;
    const swatch = node("rect", { x, y: 6, width: 12, height: 12, rx: 2 });
    swatch.style.fill = color;
    s.append(swatch, text(x + 18, 17, name, { anchor: "start", size: 11 }));
  });
  container.append(s);
}
