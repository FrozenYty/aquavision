// Mock data for the pages beyond the prototype walk-through (P-05, P-08, P-09, P-11, P-12, P-13).
// Hand-set and fixed, like fixtures.js: a demo that changes on every reload looks broken.
// Every route these pages call is in docs/api-contract-en.md §6. The field names below are older
// than the contract and do not all match the server's; each page aligns them when it moves to real
// data, which is when a mismatch would actually show.

// detect_task, in the shape serializers.task returns: status is a word, progress a percentage.
export const TASKS = [
  { task_id: 46, task_code: "DT261106-0046", type: "batch", status: "running", progress: 35, asset_count: 20, obj_count: 41, model_version_id: 4, error_msg: null, created_at: "2026-11-06T02:42:00+00:00", finished_at: null },
  { task_id: 47, task_code: "DT261106-0047", type: "batch", status: "queued", progress: 0, asset_count: 15, obj_count: 0, model_version_id: 4, error_msg: null, created_at: "2026-11-06T02:44:00+00:00", finished_at: null },
  { task_id: 48, task_code: "DT261106-0048", type: "live", status: "queued", progress: 0, asset_count: 1, obj_count: 0, model_version_id: 4, error_msg: null, created_at: "2026-11-06T02:45:00+00:00", finished_at: null },
  { task_id: 45, task_code: "DT261106-0045", type: "batch", status: "done", progress: 100, asset_count: 14, obj_count: 37, model_version_id: 4, error_msg: null, created_at: "2026-11-06T01:20:00+00:00", finished_at: "2026-11-06T01:21:10+00:00" },
  { task_id: 44, task_code: "DT261106-0044", type: "batch", status: "failed", progress: 64, asset_count: 14, obj_count: 22, model_version_id: 4, error_msg: "推理超时：单帧超过 5 秒", created_at: "2026-11-06T01:05:00+00:00", finished_at: "2026-11-06T01:06:02+00:00" },
  { task_id: 43, task_code: "DT261105-0043", type: "live", status: "done", progress: 100, asset_count: 1, obj_count: 3, model_version_id: 3, error_msg: null, created_at: "2026-11-05T08:12:00+00:00", finished_at: "2026-11-05T08:12:01+00:00" },
  { task_id: 42, task_code: "DT261105-0042", type: "batch", status: "cancelled", progress: 40, asset_count: 20, obj_count: 15, model_version_id: 3, error_msg: null, created_at: "2026-11-05T07:30:00+00:00", finished_at: "2026-11-05T07:31:00+00:00" },
];

// Hard-sample pool (FR-M4-03). One entry per seeded sample, using the server's source codes:
// low_conf (low confidence), modified (changed in review), inconsistent (models disagree).
export const HARD_SOURCES = ["low_conf", "inconsistent", "low_conf", "modified", "inconsistent", "low_conf", "modified"];

// Dataset snapshots (FR-M4-04). DS-V2 is the cleaned DUO set from P0-01: 7782 images, test 1111,
// split by perceptual-hash group. Mock field names; the contract's snapshot is in §6.
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

// Inspection reports (FR-M5-04). Mock field names; the contract's report is in §6.
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

// model_version, train_experiment and species_dict. Figures follow SRS scenario 4 (baseline
// mAP@0.5 0.76 at 42 FPS, improved 0.83 at 39 FPS) and the dashboard's online model v8n-E3.
export const MODELS = [
  { model_id: 4, version_name: "v8n-E3", dataset: "DS-V2", map50: 0.83, map5095: 0.55, recall: 0.77, fps: 39, params_m: 3.4, is_online: 1, registered_at: "2026-11-05T18:00:00+08:00" },
  { model_id: 3, version_name: "v8n-E2", dataset: "DS-V2", map50: 0.81, map5095: 0.53, recall: 0.75, fps: 40, params_m: 3.4, is_online: 0, registered_at: "2026-11-05T11:20:00+08:00" },
  { model_id: 2, version_name: "v8n-E1", dataset: "DS-V2", map50: 0.79, map5095: 0.51, recall: 0.73, fps: 41, params_m: 3.2, is_online: 0, registered_at: "2026-11-04T21:40:00+08:00" },
  { model_id: 1, version_name: "v8n-E0", dataset: "DS-V2", map50: 0.76, map5095: 0.49, recall: 0.71, fps: 42, params_m: 3.2, is_online: 0, registered_at: "2026-11-04T15:10:00+08:00" },
];

// Ablation order: each experiment adds one improvement to the one before (README stack).
export const EXPERIMENTS = [
  { exp_id: "E0", model_id: 1, change: "基线 YOLOv8n", seed: 42, baseline: true },
  { exp_id: "E1", model_id: 2, change: "+ 水下色彩校正", seed: 42 },
  { exp_id: "E2", model_id: 3, change: "+ EMA 注意力", seed: 42 },
  { exp_id: "E3", model_id: 4, change: "+ WIoU v3 损失", seed: 42 },
];

// category: 1 economic, 2 pest (glossary §4).
export const SPECIES = [
  { class_code: "holothurian", cn_name: "海参", category: 1, conf_thr: 0.5, in_stat: 1 },
  { class_code: "strongylocentrotus", cn_name: "海胆", category: 1, conf_thr: 0.5, in_stat: 1 },
  { class_code: "chlamys", cn_name: "扇贝", category: 1, conf_thr: 0.45, in_stat: 1 },
  { class_code: "asterias", cn_name: "海星", category: 2, conf_thr: 0.5, in_stat: 1 },
];

// sys_user, system parameters, sys_log and sys_message. Roles use the contract's codes
// (api-contract §4); reading observer as the SRS capture operator is an assumption to confirm.
export const USERS = [
  { user_id: 1, account: "admin@aquavision.test", role: "admin", status: 1, last_login: "2026-11-06T08:55:00+08:00" },
  { user_id: 2, account: "analyst@aquavision.test", role: "analyst", status: 1, last_login: "2026-11-06T09:40:00+08:00" },
  { user_id: 3, account: "algo@aquavision.test", role: "algo", status: 1, last_login: "2026-11-05T21:10:00+08:00" },
  { user_id: 4, account: "capture@aquavision.test", role: "observer", status: 1, last_login: "2026-11-06T10:42:00+08:00" },
  { user_id: 5, account: "intern@aquavision.test", role: "observer", status: 0, last_login: "2026-10-28T14:00:00+08:00" },
];

// Defaults from architecture §8 and the SRS: two workers, 300 ms detection interval, score 60.
export const PARAMS = { retention_days: 90, max_workers: 2, default_conf: 0.5, quality_threshold: 60, detect_interval_ms: 300 };

export const LOGS = [
  { time: "2026-11-06T10:58:00+08:00", account: "analyst@aquavision.test", action: "提交复核", before: "4 个目标", after: "5 个目标" },
  { time: "2026-11-06T09:30:00+08:00", account: "admin@aquavision.test", action: "修改参数", before: "质量阈值 55", after: "质量阈值 60" },
  { time: "2026-11-05T18:02:00+08:00", account: "algo@aquavision.test", action: "模型上线", before: "v8n-E2", after: "v8n-E3" },
  { time: "2026-11-05T09:15:00+08:00", account: "admin@aquavision.test", action: "停用账号", before: "intern@aquavision.test 启用", after: "停用" },
  { time: "2026-11-04T16:21:00+08:00", account: "algo@aquavision.test", action: "导出数据集", before: "DS-V1", after: "DS-V2" },
  { time: "2026-11-04T08:50:00+08:00", account: "capture@aquavision.test", action: "登录", before: "", after: "" },
];

// msg_type: capture_fail, task_fail, report_done (FR-M8-02).
export const MESSAGES = [
  { msg_id: 3, msg_type: "task_fail", text: "识别任务 #2044 失败：推理超时，单帧超过 5 秒", created_at: "2026-11-06T09:06:00+08:00", is_read: 0 },
  { msg_id: 2, msg_type: "report_done", text: "11 月第 1 周巡检报告已生成，可在巡检报告页下载", created_at: "2026-11-06T09:00:00+08:00", is_read: 0 },
  { msg_id: 1, msg_type: "capture_fail", text: "会话 s-b1-002 采集失败：摄像头不可用，请检查 USB 连接", created_at: "2026-11-04T08:45:00+08:00", is_read: 1 },
];
