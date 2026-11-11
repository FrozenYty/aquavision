// The demo-reset section on the settings page: the typed confirmation, which per-table counts the
// page shows, and how a finished call reads. No DOM and no fetch here, so tests/test_mock_demo.py
// can run these under Node the way canvas.js and versions.js are run.
//
// This control deletes data. A 404 means demo mode is off and nothing was deleted; it must never read
// like a success, so every refusal view carries no counts at all - the page can only draw a result
// table from a view that actually received one.

export const CONFIRM_TOKEN = "RESET";

// Business tables in the words the operator reads (data model §3). A table the dictionary does not
// know keeps its own name: the page shows what the server reported and invents no row.
export const TABLE_LABELS = {
  media_asset: "采集帧",
  detect_object: "检测框",
  detect_task: "识别任务",
  detect_task_item: "任务条目",
  report: "巡检报告",
  dataset: "数据集快照",
  dataset_item: "快照条目",
  train_experiment: "训练实验",
  sys_message: "站内消息",
  sys_log: "操作日志",
};

// The typed confirmation is the whole gate: there is no dialog to click through, and a wrong token
// keeps the button disabled.
export function resetGate({ token = "", busy = false } = {}) {
  if (busy) return { enabled: false, hint: "正在复位…" };
  if (!token) return { enabled: false, hint: "先输入 RESET 才能启用按钮" };
  if (token !== CONFIRM_TOKEN) return { enabled: false, hint: "确认词不匹配：请输入大写 RESET" };
  return { enabled: true, hint: "将删除采集数据；账号、物种字典、模型版本、参数会保留" };
}

// One row per table the response actually reported, in a stable order (by table name).
export function deletedRows(deleted = {}) {
  return Object.entries(deleted)
    .map(([table, count]) => ({ table, label: TABLE_LABELS[table] ?? table, count }))
    .sort((a, b) => a.table.localeCompare(b.table));
}

// A 404 is demo mode being off, not a failed request; anything else is a failure. Neither carries a
// count, because nothing was reported.
export function resetNotice(error) {
  if (error?.code === 40401) {
    return {
      kind: "off",
      title: "演示模式未开启",
      text:
        "服务端没有删除任何数据。演示模式由环境变量 AV_DEMO_ENABLED 控制：" +
        "设为 1 并重启服务后，这个按钮才会生效。",
    };
  }
  const message = error?.message ? String(error.message) : "未知错误";
  return { kind: "failure", title: "复位失败", text: `服务端没有返回删除结果：${message}` };
}

// The one render model for both outcomes. A refused or failed call has no rows and no model name, so
// the page cannot draw a success table for it.
export function resetView({ result = null, error = null } = {}) {
  if (error) {
    const notice = resetNotice(error);
    return {
      state: notice.kind,
      title: notice.title,
      text: notice.text,
      rows: [],
      model: null,
      files: null,
    };
  }
  const rows = deletedRows(result.deleted);
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  return {
    state: "success",
    title: "演示复位完成",
    text: `已删除 ${total} 行业务记录，移除 ${result.frame_files_removed} 个图像文件。`,
    rows,
    model: result.model_online ?? "没有上线的模型",
    files: result.frame_files_removed,
  };
}
