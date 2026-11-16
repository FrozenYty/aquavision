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
