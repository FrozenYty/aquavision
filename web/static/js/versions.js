// The review page's version panel: what a timeline entry reads as, whether the restore button may
// act, and what a finished rollback means for the canvas. No DOM and no fetch here, so
// tests/test_review_versions_page.py can run these under Node the way canvas.js is run.
//
// A refused rollback is a normal outcome, not an exception: the reviewer picked a version that is
// already the current set, or an entry that belongs to another frame. The server answers 409, the
// canvas must stay exactly as it was, and the reviewer is told why.

export const ACTION_LABELS = { submit: "提交", rollback: "回滚" };

export function actionLabel(action) {
  return ACTION_LABELS[action] ?? String(action);
}

// Bootstrap badge colour: a rollback is informational, a submission neutral.
export function actionTone(action) {
  return action === "rollback" ? "info" : "secondary";
}

// One timeline entry's main line: what happened, and the box count before → after.
export function versionText(item) {
  return `${actionLabel(item.action)} · ${item.before_count} → ${item.after_count}`;
}

// The API sends the display name, null for a row an automated action wrote.
export function authorText(item) {
  return item.author ?? "系统";
}

// What the restore button may do in the current state, and the short line beside it.
export function restoreState({ selectedLogId = null, restoring = false, versionCount = 0 } = {}) {
  if (restoring) return { enabled: false, hint: "正在恢复…" };
  if (!versionCount) return { enabled: false, hint: "没有可回滚的版本" };
  if (selectedLogId == null) return { enabled: false, hint: "先选择一个版本" };
  return { enabled: true, hint: "恢复会用该版的目标覆盖当前画布" };
}

// The sentence the reviewer sees after a refusal. The server's message says which rule stopped it;
// the client only decides how to show it and how serious it is. 409 is a warning, not a failure:
// nothing was written and the canvas was not touched.
export function refusalNotice(error) {
  const code = error?.code;
  const message = error?.message ? String(error.message) : "未知错误";
  if (code === 40901) return { kind: "warning", text: `未回滚：${message}。画面未改动。` };
  if (code === 40401) {
    return { kind: "danger", text: "回滚失败：这条版本记录已不存在，请刷新版本列表后重试。" };
  }
  return { kind: "danger", text: `回滚失败：${message}` };
}

// What a finished rollback may do to the page: reload the canvas only when the server applied it.
// A refusal reloads nothing, so the reviewer's work stays exactly as it was.
export function rollbackPlan(error) {
  if (!error) return { reload: true, notice: null };
  return { reload: false, notice: refusalNotice(error) };
}

// The success message: the new version number and what the restore changed.
export function restoreText(result) {
  return (
    `已恢复到第 ${result.version_no} 版：目标 ${result.object_count} 个，` +
    `新增 ${result.added}，驳回 ${result.rejected}`
  );
}
