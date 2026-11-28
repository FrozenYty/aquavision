import { esc } from "./ui.js";

export function reportQuery(period, basis) {
  return period ? { period_start: period.from, period_end: period.to, basis } : null;
}

// All numbers and the caption come from the same server response used for file generation.
export function reportPreviewHtml(data, mock = false) {
  const figures = data.figures;
  const rows = figures.species.map((row) => `<tr><td>${esc(row.name)}</td><td>${row.count}</td><td>${(row.share * 100).toFixed(2)}%</td></tr>`).join("") ||
    '<tr><td colspan="3">所选周期和口径下没有识别结果</td></tr>';
  return `<h3>巡检报告预览</h3>
    <p>统计周期：${esc(data.period_start.slice(0, 10))} 至 ${esc(data.period_end.slice(0, 10))}</p>
    <h4>采集与质量</h4><p>采集成像：${figures.frames} 帧；质量拦截：${figures.rejected} 帧，拦截率 ${(figures.rate * 100).toFixed(2)}%</p>
    <h4>物种组成</h4><table class="table table-sm small"><thead><tr><th>物种</th><th>目标数</th><th>占比</th></tr></thead><tbody>${rows}</tbody></table>
    <footer>模型版本：${esc(data.model_version ?? "未上线")} · 统计口径：${data.basis === "raw" ? "原始识别结果" : "复核后结果"}${mock ? " · 演示数据" : ""}</footer>`;
}

// The server filters and pages the archive, so the page sends what the operator chose and renders the
// page that comes back: no fetch-all, and `total` is the size of the filtered set. A blank field is
// left out, so "no filter" is "every report" (GET /api/reports, api-contract §6).
export function reportHistoryQuery({ from, to, template, basis } = {}, page = 1, size = 24) {
  const query = { page, size };
  if (from) query.from = from;
  if (to) query.to = to;
  if (template) query.template = template;
  if (basis) query.basis = basis;
  return query;
}

export function reportHistory(fetchPage, filters, page = 1, size = 24) {
  return fetchPage(reportHistoryQuery(filters, page, size));
}

// The archive's download control: only a ready report has a stored document to fetch (FR-M5-04).
// The page owns the click and the save; this names the row's control and nothing else.
export function reportDownloadControl(row) {
  if (row.status !== "ready" || !row.file_path) return "";
  return `<button class="btn btn-outline-secondary btn-sm" type="button" data-download="${esc(row.report_code)}">下载</button>`;
}
