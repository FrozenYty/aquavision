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

// model_version, train_experiment and species_dict, in the shapes serializers.model_version, the
// experiments route and serializers.species return. Figures follow SRS scenario 4 (baseline mAP@0.5
// 0.76 at 42 FPS, improved 0.83 at 39 FPS) and the dashboard's online model v8n-E3.
export const MODELS = [
  { model_id: 4, version_name: "v8n-E3", dataset_ref: "DS-V2", map50: 0.83, map50_95: 0.55, recall_avg: 0.77, fps: 39, params_m: 3.4, is_online: true, status: 1, created_at: "2026-11-05T10:00:00+00:00" },
  { model_id: 3, version_name: "v8n-E2", dataset_ref: "DS-V2", map50: 0.81, map50_95: 0.53, recall_avg: 0.75, fps: 40, params_m: 3.4, is_online: false, status: 1, created_at: "2026-11-05T03:20:00+00:00" },
  { model_id: 2, version_name: "v8n-E1", dataset_ref: "DS-V2", map50: 0.79, map50_95: 0.51, recall_avg: 0.73, fps: 41, params_m: 3.2, is_online: false, status: 1, created_at: "2026-11-04T13:40:00+00:00" },
  { model_id: 1, version_name: "v8n-E0", dataset_ref: "DS-V2", map50: 0.76, map50_95: 0.49, recall_avg: 0.71, fps: 42, params_m: 3.2, is_online: false, status: 1, created_at: "2026-11-04T07:10:00+00:00" },
];

// Ablation order: each experiment adds one improvement to the one before (README stack).
export const EXPERIMENTS = [
  { exp_id: 1, exp_name: "E0 基线 YOLOv8n", dataset_snapshot: "DS-V2", split_ratio: "7:2:1", seed: 42, epochs: 100, map50: 0.76, map50_95: 0.49, recall_avg: 0.71, fps: 42, is_baseline: true, delta_map50: null, created_at: "2026-11-04T07:00:00+00:00" },
  { exp_id: 2, exp_name: "E1 + 水下色彩校正", dataset_snapshot: "DS-V2", split_ratio: "7:2:1", seed: 42, epochs: 100, map50: 0.79, map50_95: 0.51, recall_avg: 0.73, fps: 41, is_baseline: false, delta_map50: 0.03, created_at: "2026-11-04T13:30:00+00:00" },
  { exp_id: 3, exp_name: "E2 + EMA 注意力", dataset_snapshot: "DS-V2", split_ratio: "7:2:1", seed: 42, epochs: 100, map50: 0.81, map50_95: 0.53, recall_avg: 0.75, fps: 40, is_baseline: false, delta_map50: 0.05, created_at: "2026-11-05T03:10:00+00:00" },
  { exp_id: 4, exp_name: "E3 + WIoU v3 损失", dataset_snapshot: "DS-V2", split_ratio: "7:2:1", seed: 42, epochs: 100, map50: 0.83, map50_95: 0.55, recall_avg: 0.77, fps: 39, is_baseline: false, delta_map50: 0.07, created_at: "2026-11-05T09:50:00+00:00" },
];

// category: 1 economic, 2 pest, 3 environment (data model §3.6).
export const SPECIES = [
  { class_code: "holothurian", cn_name: "海参", latin_name: "Holothuroidea", category: 1, conf_thr: 0.5, in_stat: true, status: 1 },
  { class_code: "strongylocentrotus", cn_name: "海胆", latin_name: "Strongylocentrotus", category: 1, conf_thr: 0.5, in_stat: true, status: 1 },
  { class_code: "chlamys", cn_name: "扇贝", latin_name: "Chlamys", category: 1, conf_thr: 0.45, in_stat: true, status: 1 },
  { class_code: "asterias", cn_name: "海星", latin_name: "Asterias", category: 2, conf_thr: 0.5, in_stat: true, status: 1 },
];

// sys_user, system parameters, sys_log and sys_message, in the server's shapes. Roles use the
// contract's codes (api-contract §4); reading observer as the SRS capture operator is unconfirmed.
export const USERS = [
  { user_id: 1, username: "admin", real_name: "系统管理员", role: "admin", status: 1, last_login_at: "2026-11-06T00:55:00+00:00" },
  { user_id: 2, username: "analyst", real_name: "分析员一", role: "analyst", status: 1, last_login_at: "2026-11-06T01:40:00+00:00" },
  { user_id: 3, username: "algo", real_name: "算法员一", role: "algo", status: 1, last_login_at: "2026-11-05T13:10:00+00:00" },
  { user_id: 4, username: "capture", real_name: "采集员一", role: "observer", status: 1, last_login_at: "2026-11-06T02:42:00+00:00" },
  { user_id: 5, username: "intern", real_name: "实习采集员", role: "observer", status: 0, last_login_at: "2026-10-28T06:00:00+00:00" },
];

// The server's parameter set and defaults (config.py, api-contract §6 Parameters).
export const PARAMS = { retention_days: 30, max_concurrency: 2, detect_interval_ms: 300, quality_threshold: 60, camera_index: 0 };

export const LOGS = [
  { log_id: 6, user_id: 2, module: "review", action: "submit", target_type: "media_asset", target_id: "20261103T091000-0001", before_value: "4", after_value: "5", created_at: "2026-11-06T02:58:00+00:00" },
  { log_id: 5, user_id: 1, module: "system", action: "param", target_type: "sys_param", target_id: "quality_threshold", before_value: "55", after_value: "60", created_at: "2026-11-06T01:30:00+00:00" },
  { log_id: 4, user_id: 3, module: "model", action: "activate", target_type: "model_version", target_id: "4", before_value: "v8n-E2", after_value: "v8n-E3", created_at: "2026-11-05T10:02:00+00:00" },
  { log_id: 3, user_id: 1, module: "user", action: "status", target_type: "sys_user", target_id: "5", before_value: "1", after_value: "0", created_at: "2026-11-05T01:15:00+00:00" },
  { log_id: 2, user_id: 3, module: "dataset", action: "export", target_type: "dataset_snapshot", target_id: "DS-V2", before_value: null, after_value: "7782", created_at: "2026-11-04T08:21:00+00:00" },
  { log_id: 1, user_id: 4, module: "auth", action: "login", target_type: "sys_user", target_id: "4", before_value: null, after_value: null, created_at: "2026-11-04T00:50:00+00:00" },
];

// type: capture_fail, task_fail, report_done (FR-M8-02).
export const MESSAGES = [
  { msg_id: 3, type: "task_fail", level: "warn", title: "识别任务失败", content: "DT261106-0044 推理超时：单帧超过 5 秒", is_read: false, created_at: "2026-11-06T01:06:00+00:00" },
  { msg_id: 2, type: "report_done", level: "info", title: "巡检报告已生成", content: "11 月第 1 周巡检报告，可在巡检报告页下载", is_read: false, created_at: "2026-11-06T01:00:00+00:00" },
  { msg_id: 1, type: "capture_fail", level: "error", title: "采集失败", content: "会话 s-b1-002：摄像头不可用，请检查 USB 连接", is_read: true, created_at: "2026-11-04T00:45:00+00:00" },
];
