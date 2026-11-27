// What the statistics page draws, worked out from what /api/stats/* returned. Free of the DOM, so it is
// tested by running it (tests/test_stats_view.py). Each function takes one response and returns the
// figures, the caption and whether the card is empty, all from that one response: a caption and figures
// that come from two places can disagree, and a half-finished basis switch is exactly that.

export const BASIS = {
  reviewed: {
    label: "复核后结果",
    empty: "所选口径下没有目标框。可切换到原始识别结果查看。",
  },
  raw: {
    label: "原始识别结果",
    empty: "还没有识别结果。识别任务完成后，这里会按原始识别结果统计目标框。",
  },
};

const pct = (share) => `${(share * 100).toFixed(1)}%`;

// Species composition. The basis is the one the server says it counted (it echoes the parameter), so
// the caption can never describe a different basis from the numbers under it.
export function speciesView(data, { mock = false } = {}) {
  const basis = BASIS[data.basis] ? data.basis : "reviewed";
  const rows = (data.items ?? []).map((item) => ({
    class_code: item.class_code,
    box_count: item.count,
    share: item.share,
  }));
  const total = data.total;
  return {
    basis,
    caption: `近 ${data.days} 日目标框数 · ${BASIS[basis].label}${mock ? "（演示数据不区分口径）" : ""}`,
    total,
    rows,
    empty: total === 0,
    emptyText: BASIS[basis].empty,
  };
}

// The change from one day to the next, as a fraction; null when there is no baseline to compare with
// (the first day, or a previous day with no frames), which the page shows as a dash (AC-21).
export function dayOverDay(rows) {
  return rows.map((row, i) => {
    const before = i > 0 ? rows[i - 1].frames : 0;
    return before > 0 ? (row.frames - before) / before : null;
  });
}

export function formatChange(change) {
  if (change === null) return "—";
  const sign = change > 0 ? "+" : "";
  return `${sign}${(change * 100).toFixed(1)}%`;
}

// Daily capture. The server pads quiet days with zeros, so the list is never empty; a period with no
// frames at all is the empty state, not a flat line along the axis.
export function trendView(data) {
  const rows = data.items ?? [];
  const total = rows.reduce((sum, row) => sum + row.frames, 0);
  const changes = dayOverDay(rows);
  const last = changes.at(-1) ?? null;
  return {
    rows: rows.map((row, i) => ({ ...row, change: changes[i], changeText: formatChange(changes[i]) })),
    total,
    caption: `近 ${data.days} 日共 ${total} 帧 · 最近一日较前日 ${formatChange(last)}`,
    empty: total === 0,
    emptyText: `近 ${data.days} 日没有采集任何帧`,
  };
}

// Quality rejection: the frames that passed and the frames sent back for a retake.
export function qualityView(data) {
  return {
    bars: [
      { key: "passed", label: "合格", value: data.total - data.rejected, tone: "success" },
      { key: "rejected", label: "需重拍", value: data.rejected, tone: "warning" },
    ],
    total: data.total,
    caption: `近 ${data.days} 日共 ${data.total} 帧 · 拦截率 ${pct(data.rate)}`,
    empty: data.total === 0,
    emptyText: `近 ${data.days} 日没有采集任何帧`,
  };
}

// Review corrections: how reviewers changed the automatic result.
export function correctionsView(data) {
  return {
    bars: [
      { key: "modified", label: "改类别", value: data.modified, tone: "primary" },
      { key: "added", label: "补框", value: data.added, tone: "success" },
      { key: "rejected", label: "删框", value: data.rejected, tone: "danger" },
    ],
    total: data.total,
    caption: `近 ${data.days} 日共 ${data.total} 处人工修正`,
    empty: data.total === 0,
    emptyText: `近 ${data.days} 日还没有人工修正`,
  };
}
