// Mock data for the pages beyond the prototype walk-through (P-05, P-08, P-09, P-11, P-12, P-13).
// Hand-set and fixed, like fixtures.js: a demo that changes on every reload looks broken.
// Field names follow the data model; collection routes for these pages are provisional (not in
// docs/api-contract-en.md yet) and marked as such in api.js.

// detect_task. status: 0 queued, 1 running, 2 done, 3 failed (glossary §3). kind, source, total,
// done and error are provisional: the data model keeps them on the task row in some form, the
// contract does not list them yet.
export const TASKS = [
  { task_id: 2046, kind: "batch", source: "s-b1-001", total: 20, done: 7, status: 1, model_version: "v8n-E3", created_at: "2026-11-06T10:42:00+08:00", error: null },
  { task_id: 2047, kind: "batch", source: "s-a3-002", total: 15, done: 0, status: 0, model_version: "v8n-E3", created_at: "2026-11-06T10:44:00+08:00", error: null },
  { task_id: 2048, kind: "single", source: "20261103T091003-0004", total: 1, done: 0, status: 0, model_version: "v8n-E3", created_at: "2026-11-06T10:45:00+08:00", error: null },
  { task_id: 2045, kind: "batch", source: "s-a3-001", total: 14, done: 14, status: 2, model_version: "v8n-E3", created_at: "2026-11-06T09:20:00+08:00", error: null },
  { task_id: 2044, kind: "batch", source: "s-a3-001", total: 14, done: 9, status: 3, model_version: "v8n-E3", created_at: "2026-11-06T09:05:00+08:00", error: "推理超时：单帧超过 5 秒" },
  { task_id: 2043, kind: "single", source: "20261103T143000-0001", total: 1, done: 1, status: 2, model_version: "v8n-E2", created_at: "2026-11-05T16:12:00+08:00", error: null },
  { task_id: 2042, kind: "batch", source: "s-b1-001", total: 20, done: 20, status: 2, model_version: "v8n-E2", created_at: "2026-11-05T15:30:00+08:00", error: null },
];

// Hard-sample pool (FR-M4-03). Three sources: low confidence, corrected in review, and models that
// disagree. The mock attaches these to real frames in order; frames corrected on the review page
// join as "corrected" on their own.
export const HARD_SEEDS = [
  { source: "low_conf", class_code: "holothurian", confidence: 0.42, reason: "礁石纹理被判成海参" },
  { source: "disagree", class_code: "chlamys", confidence: 0.55, reason: "基线判扇贝，改进模型判海星" },
  { source: "low_conf", class_code: "asterias", confidence: 0.38, reason: "目标被泥沙半遮挡" },
  { source: "corrected", class_code: "strongylocentrotus", confidence: 0.61, reason: "漏检一只海胆，复核补框" },
  { source: "disagree", class_code: "holothurian", confidence: 0.49, reason: "两模型框位置偏差超过 0.3 IoU" },
  { source: "low_conf", class_code: "strongylocentrotus", confidence: 0.44, reason: "画面边缘，目标只露一半" },
  { source: "corrected", class_code: "asterias", confidence: 0.58, reason: "海星被改为扇贝" },
];

// Dataset snapshots (FR-M4-04). DS-V2 is the cleaned DUO set from P0-01: 7782 images, test 1111,
// split by perceptual-hash group. Fields are provisional.
export const DATASETS = [
  {
    version: "DS-V2", created_at: "2026-11-04T16:20:00+08:00", images: 7782,
    split: { train: 5447, val: 1224, test: 1111 }, seed: 42, scope: "DUO 清洗后全集",
    status: "done", progress: 100,
  },
  {
    version: "DS-V1", created_at: "2026-10-30T10:05:00+08:00", images: 6200,
    split: { train: 4340, val: 1240, test: 620 }, seed: 42, scope: "DUO 首批，未去重",
    status: "done", progress: 100,
  },
];

// Inspection reports (FR-M5-04). Fields are provisional.
export const REPORTS = [
  {
    report_id: 12, title: "11 月第 1 周巡检报告", period: "2026-11-01 ~ 2026-11-06", template: "standard",
    basis: "reviewed", model_version: "v8n-E3", created_at: "2026-11-06T09:00:00+08:00", status: "done", progress: 100,
  },
  {
    report_id: 11, title: "10 月巡检报告", period: "2026-10-01 ~ 2026-10-31", template: "standard",
    basis: "reviewed", model_version: "v8n-E2", created_at: "2026-11-01T08:30:00+08:00", status: "done", progress: 100,
  },
];
