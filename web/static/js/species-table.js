import { SPECIES } from "./species.js";
import { esc } from "./ui.js";

export function speciesPatch(code, value, inStat) {
  if (!Object.hasOwn(SPECIES, code)) return { valid: false, error: "类别码不在约定的四类中，请核对 labels.txt。" };
  const number = Number(value);
  if (String(value).trim() === "" || !Number.isFinite(number) || number < 0 || number > 1 ||
      Math.abs(number * 100 - Math.round(number * 100)) > 1e-8) {
    return { valid: false, error: "阈值须在 0 到 1 之间，最多两位小数。" };
  }
  return { valid: true, body: { conf_thr: number, in_stat: Boolean(inStat) } };
}

export function speciesTable(items) {
  const codes = Object.keys(SPECIES);
  const known = items.filter((row) => Object.hasOwn(SPECIES, row.class_code))
    .sort((a, b) => codes.indexOf(a.class_code) - codes.indexOf(b.class_code));
  const unknown = items.filter((row) => !Object.hasOwn(SPECIES, row.class_code)).map((row) => row.class_code);
  const missing = codes.filter((code) => !known.some((row) => row.class_code === code));
  const category = { 1: "经济种", 2: "敌害种", 3: "环境物" };
  const warning = [unknown.length ? `已拒绝显示类别码 ${unknown.join("、")}` : "",
    missing.length ? `缺少类别 ${missing.join("、")}` : ""].filter(Boolean).join("；");
  return {
    warning: warning ? `${warning}；请核对模型 labels.txt 与物种字典。` : "",
    html: known.map((row) => `<tr data-code="${row.class_code}">
      <td class="av-mono">${row.class_code}</td><td><span class="av-class av-class-${row.class_code}">${esc(row.cn_name)}</span></td>
      <td>${esc(category[row.category] ?? row.category)}</td>
      <td><input class="form-control form-control-sm w-auto" type="number" step="0.01" min="0" max="1" value="${esc(row.conf_thr)}" aria-label="${esc(row.cn_name)}阈值">
        <div class="invalid-feedback">阈值须在 0 到 1 之间，最多两位小数。</div></td>
      <td><input class="form-check-input" type="checkbox" ${row.in_stat ? "checked" : ""} aria-label="${esc(row.cn_name)}计入统计"></td>
      <td><button class="btn btn-sm btn-outline-primary" data-save type="button">保存</button></td></tr>`).join(""),
  };
}
