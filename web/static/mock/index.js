// Mock server for api.js. Answers with the contract envelope and error codes (§2, §3).

import {
  CAMERAS,
  FALSE_POSITIVE,
  FRAMES,
  SESSIONS,
  STILLS,
  newFrame,
  STATS_SPECIES,
  STATS_QUALITY,
  STATS_TREND,
  STATS_CORRECTIONS,
} from "./fixtures.js";
import {
  DATASETS,
  EXPERIMENTS,
  HARD_SOURCES,
  LOGS,
  MESSAGES,
  MODELS,
  PARAMS,
  REPORTS,
  SPECIES,
  TASKS,
  USERS,
} from "./catalog.js";

class Fail extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}


// Every page load starts the mock afresh, but screens 3-5 hand a frame from page to page. Frames
// captured and reviews submitted are kept for the browser tab so the walk-through holds together.
// Versioned: state saved by an older mock, in older shapes, must not be restored over the new data.
const STORE = "av-mock-state-v2";
const saved = (() => {
  try {
    return JSON.parse(sessionStorage.getItem(STORE)) ?? {};
  } catch {
    return {};
  }
})();
// A demo reset is a state of its own: the tab has deleted its business data and must not restore it
// - or the seeded demo rows - on the next page load. Accounts, species, model versions and parameters
// stay, exactly as the contract's reset promises.
let demoResetApplied = saved.demo_reset === true;
const captured = demoResetApplied ? [] : (saved.frames ?? []);
const REVIEWS = demoResetApplied ? {} : (saved.reviews ?? {});
const VERSIONS = demoResetApplied ? {} : (saved.versions ?? {});
// One entry per submit or rollback this tab made, per frame; the version panel reads it (api-contract §6).
const TIMELINE = demoResetApplied ? {} : (saved.timeline ?? {});
FRAMES.unshift(...captured);
if (demoResetApplied) {
  FRAMES.length = 0;
  TASKS.length = 0;
  REPORTS.length = 0;
  DATASETS.length = 0;
  EXPERIMENTS.length = 0;
  MESSAGES.length = 0;
  LOGS.length = 0;
} else {
  if (saved.tasks) TASKS.splice(0, TASKS.length, ...saved.tasks);
  if (saved.datasets) DATASETS.splice(0, DATASETS.length, ...saved.datasets);
  if (saved.reports) REPORTS.splice(0, REPORTS.length, ...saved.reports);
}
const removedHard = new Set(demoResetApplied ? [] : (saved.removed_hard ?? []));
if (saved.models) MODELS.splice(0, MODELS.length, ...saved.models);
if (saved.species) SPECIES.splice(0, SPECIES.length, ...saved.species);

function persist() {
  try {
    sessionStorage.setItem(STORE, JSON.stringify({
        frames: captured,
        reviews: REVIEWS,
        versions: VERSIONS,
        timeline: TIMELINE,
        demo_reset: demoResetApplied,
        tasks: TASKS,
        removed_hard: [...removedHard],
        datasets: DATASETS,
        reports: REPORTS,
        models: MODELS,
        species: SPECIES,
      }));
  } catch {
    // Storage unavailable: the walk-through still works within one page.
  }
}

// Each frame shows one DUO still, picked by its sequence number, so the first frame of a session is
// always sample-01 - the one carrying the deliberate false positive.
function stillOf(frame) {
  return STILLS[(Number(frame.frame_id.slice(-4)) - 1) % STILLS.length];
}

// image_url is mock-only: the contract's frame object does not say where the picture is served.
const withImage = (frame) => ({ ...frame, image_url: new URL(stillOf(frame).image, import.meta.url).href });

// Live frames follow a script instead of the dice: four good frames, then one below the threshold,
// so the walk-through always opens on a detected frame and still shows an interception.
const LIVE_QUALITY = [
  { sharpness: 84, brightness: 91, colorcast: 83, score: 86, verdict: "ok" },
  { sharpness: 79, brightness: 88, colorcast: 80, score: 82, verdict: "ok" },
  { sharpness: 88, brightness: 86, colorcast: 85, score: 87, verdict: "ok" },
  { sharpness: 76, brightness: 83, colorcast: 78, score: 79, verdict: "ok" },
  { sharpness: 38, brightness: 64, colorcast: 55, score: 49, verdict: "retake" },
];

function findTask(id) {
  const task = TASKS.find((t) => t.task_id === Number(id));
  if (!task) throw new Fail(40401, "识别任务不存在");
  return task;
}

// Each read moves the running task on by a tenth, so a page that polls shows real progress. When it
// finishes, the oldest queued task starts (two workers in the design, one here keeps it readable).
function advanceTasks() {
  let running = TASKS.find((t) => t.status === "running");
  if (running) {
    running.progress = Math.min(100, running.progress + 10);
    if (running.progress === 100) Object.assign(running, { status: "done", finished_at: new Date().toISOString() });
  }
  if (!TASKS.some((t) => t.status === "running")) {
    running = TASKS.filter((t) => t.status === "queued").sort((a, b) => a.task_id - b.task_id)[0];
    if (running) running.status = "running";
  }
  persist();
}

// The pool, in the server's shape: the frame object plus its source. Seeded samples sit on real
// frames, and every frame submitted on the review page joins as "modified" (FR-M4-03).
function hardSamples() {
  const ok = FRAMES.filter((f) => f.quality.verdict === "ok" && !captured.includes(f));
  const seeded = HARD_SOURCES.map((source, i) => ({ source, frame: ok[i * 2] })).filter((h) => h.frame);
  const reviewed = Object.keys(REVIEWS).map((id) => ({ source: "modified", frame: FRAMES.find((f) => f.frame_id === id) }));
  return [...reviewed, ...seeded]
    .filter((h) => h.frame && !removedHard.has(h.frame.frame_id))
    .filter((h, i, all) => all.findIndex((o) => o.frame === h.frame) === i)
    .map(({ frame, source }) => ({ ...withImage(frame), source }));
}

function findFrame(id) {
  const frame = FRAMES.find((f) => f.frame_id === id);
  if (!frame) throw new Fail(40401, "帧不存在");
  return frame;
}

// object_id, is_manual and review_status follow the detection box in api-contract §6.
function detectedObjects(frame) {
  if (frame.quality.verdict !== "ok") return []; // needs retake: stored, never detected
  const still = stillOf(frame);
  const extra = still.image === FALSE_POSITIVE.image ? FALSE_POSITIVE.boxes : [];
  return [...still.boxes, ...extra].map((box, i) => ({
    object_id: i + 1,
    ...box,
    is_manual: 0,
    review_status: 0,
  }));
}

function paginate(items, query) {
  const page = Number(query.page ?? 1);
  const size = Math.min(Number(query.size ?? 24), 100);
  return { items: items.slice((page - 1) * size, page * size), total: items.length, page, size };
}

function findSession(id) {
  const session = SESSIONS.find((s) => s.session_id === id);
  if (!session) throw new Fail(40401, "采集会话不存在");
  return session;
}

// ---- Review timeline and demo reset: the tab's own record, never a fixture -----------------------

let logSequence = Math.max(
  0,
  ...LOGS.map((row) => row.log_id),
  ...Object.values(TIMELINE).flat().map((entry) => entry.log_id),
);

// One recorded review, with the box lists it was recorded from. Nothing is invented: the GET route
// lists only what a review or rollback on this tab actually wrote, so an untouched tab stays empty.
function recordReview(frameId, action, before, after) {
  logSequence += 1;
  (TIMELINE[frameId] ??= []).push({
    log_id: logSequence,
    frame_id: frameId,
    action,
    created_at: new Date().toISOString(),
    author: "演示账号",
    before: structuredClone(before),
    after: structuredClone(after),
  });
}

// The same set of boxes, order and object ids aside, at the precision the columns store - the rule
// the server applies when it refuses a rollback to the set the frame already has.
const boxSignature = (box) =>
  [box.class_code, box.confidence, box.x, box.y, box.w, box.h]
    .map((value, i) => (i === 0 ? String(value) : Number(value).toFixed(5)))
    .join("|");

function sameBoxes(a, b) {
  const keys = (boxes) => boxes.map(boxSignature).sort();
  return JSON.stringify(keys(a)) === JSON.stringify(keys(b));
}

// Every box the tab currently stores: reviewed sets, plus the detected boxes of frames not reviewed yet.
function objectCount() {
  return FRAMES.reduce(
    (sum, frame) => sum + (REVIEWS[frame.frame_id] ?? detectedObjects(frame)).length,
    0,
  );
}

// Wipe the tab's business data and remember that it is wiped, so a reload does not restore it.
function resetDemo() {
  for (const key of Object.keys(REVIEWS)) delete REVIEWS[key];
  for (const key of Object.keys(VERSIONS)) delete VERSIONS[key];
  for (const key of Object.keys(TIMELINE)) delete TIMELINE[key];
  captured.length = 0;
  FRAMES.length = 0;
  TASKS.length = 0;
  REPORTS.length = 0;
  DATASETS.length = 0;
  EXPERIMENTS.length = 0;
  MESSAGES.length = 0;
  LOGS.length = 0;
  removedHard.clear();
  demoResetApplied = true;
  persist();
}

const ROUTES = {
  // Demo mode accepts any non-empty account; the real lockout and audit live on the server.
  "POST /auth/login": ({ body }) => {
    if (!body?.username || !body?.password) throw new Fail(40001, "请输入账号和密码");
    return {
      token: "mock-token",
      expires_at: new Date(Date.now() + 8 * 3600e3).toISOString(),
      user: { user_id: 1, username: body.username, real_name: "演示账号", role: "admin" },
    };
  },

  "GET /cameras": () => CAMERAS,

  "GET /capture/sessions": ({ query }) =>
    paginate([...SESSIONS].sort((a, b) => Date.parse(b.started_at) - Date.parse(a.started_at)), query),

  "POST /capture/sessions": ({ body }) => {
    if (!body?.site) throw new Fail(40001, "请选择点位");
    if (SESSIONS.some((s) => s.status === "open")) throw new Fail(40901, "已有采集会话在进行中");
    const n = SESSIONS.filter((s) => s.site === body.site).length + 1;
    const session = {
      session_id: `s-${body.site.toLowerCase()}-${String(n).padStart(3, "0")}`,
      site: body.site,
      started_at: new Date().toISOString(),
      status: "open",
      fail_reason: null,
      frame_count: 0,
      retake_count: 0,
    };
    SESSIONS.push(session);
    return session;
  },

  "POST /capture/sessions/{id}/frames": ({ id }) => {
    const session = findSession(id);
    if (session.status !== "open") throw new Fail(40901, "采集会话已关闭");
    const frame = newFrame(
      { ...session, started_at: new Date().toISOString() },
      session.frame_count,
    );
    frame.quality = LIVE_QUALITY[session.frame_count % LIVE_QUALITY.length];
    session.frame_count += 1;
    if (frame.quality.verdict === "retake") session.retake_count += 1;
    FRAMES.unshift(frame);
    captured.unshift(frame);
    persist();
    return withImage(frame);
  },

  "POST /capture/sessions/{id}/close": ({ id }) => {
    const session = findSession(id);
    session.status = "closed";
    return session;
  },

  // Filters as the server reads them: session, site, quality (ok | retake), start, end.
  "GET /frames": ({ query }) => {
    const items = FRAMES.filter(
      (f) =>
        (!query.site || f.site === query.site) &&
        (!query.session || f.session_id === query.session) &&
        (!query.quality || f.quality.verdict === query.quality) &&
        (!query.start || f.captured_at.slice(0, 10) >= query.start) &&
        (!query.end || f.captured_at.slice(0, 10) <= query.end),
    );
    const result = paginate(items, query);
    return { ...result, items: result.items.map(withImage) };
  },

  "GET /frames/{id}": ({ id }) => withImage(findFrame(id)),

  // As the server answers: the boxes plus a per-class count.
  "GET /frames/{id}/objects": ({ id }) => {
    const items = REVIEWS[id] ?? detectedObjects(findFrame(id));
    const counts = {};
    for (const box of items) counts[box.class_code] = (counts[box.class_code] ?? 0) + 1;
    return { items, counts };
  },

  // Body { objects, note }: the full box list after review (api-contract §6); the reply is the contract's.
  // The submission also records the timeline entry the review page's version panel reads.
  "POST /review/frames/{id}": ({ id, body }) => {
    if (!Array.isArray(body?.objects)) throw new Fail(40001, "缺少复核结果");
    const before = REVIEWS[id] ?? detectedObjects(findFrame(id));
    const kept = new Set(body.objects.map((b) => b.object_id));
    const after = structuredClone(body.objects);
    REVIEWS[id] = after;
    VERSIONS[id] = (VERSIONS[id] ?? 1) + 1;
    recordReview(id, "submit", before, after);
    persist();
    return {
      frame_id: id,
      version_no: VERSIONS[id],
      object_count: after.length,
      hard_sample: true,
      rejected: before.filter((b) => !kept.has(b.object_id)).length,
      added: after.filter((b) => b.is_manual).length,
      note: body.note ?? null,
    };
  },

  // The frame's review timeline from this tab's own recorded reviews, newest first. A frame with no
  // review answers an empty list; the counts come from the stored lists, not from today's boxes.
  "GET /review/frames/{id}/versions": ({ id }) => {
    findFrame(id);
    const items = [...(TIMELINE[id] ?? [])]
      .sort((a, b) => b.log_id - a.log_id)
      .map((entry) => ({
        log_id: entry.log_id,
        action: entry.action,
        created_at: entry.created_at,
        author: entry.author,
        before_count: entry.before.length,
        after_count: entry.after.length,
      }));
    return { frame_id: id, items };
  },

  // Restore one recorded set as a new version; the timeline is appended to, never rewritten. A target
  // equal to the current set is refused as a no-op, and another frame's entry is refused, like the server.
  "POST /review/frames/{id}/rollback": ({ id, body }) => {
    const frame = findFrame(id);
    const logId = Number(body?.log_id);
    const entry = Object.values(TIMELINE).flat().find((row) => row.log_id === logId);
    if (!entry) throw new Fail(40401, "复核记录不存在");
    if (entry.frame_id !== id) throw new Fail(40901, "该复核记录属于另一帧，不能用于回滚");
    const current = REVIEWS[id] ?? detectedObjects(frame);
    if (sameBoxes(entry.after, current)) throw new Fail(40901, "该版本与当前结果相同，无需回滚");
    const rejected = current.filter(
      (box) => !entry.after.some((target) => target.object_id === box.object_id),
    ).length;
    const added = entry.after.filter(
      (box) => !current.some((now) => now.object_id === box.object_id),
    ).length;
    const restored = structuredClone(entry.after);
    REVIEWS[id] = restored;
    VERSIONS[id] = (VERSIONS[id] ?? 1) + 1;
    recordReview(id, "rollback", current, restored);
    persist();
    return {
      log_id: logId,
      frame_id: id,
      version_no: VERSIONS[id],
      object_count: restored.length,
      hard_sample: true,
      rejected,
      added,
    };
  },

  // The server takes { asset_count, conf_thr, ... }; frame_ids is sent too and ignored there.
  "POST /detect/batches": ({ body }) => {
    if (!(body?.asset_count >= 1)) throw new Fail(40001, "请至少选择一帧");
    const id = Math.max(0, ...TASKS.map((t) => t.task_id)) + 1;
    const task = {
      task_id: id,
      task_code: `DT${new Date().toISOString().slice(2, 10).replaceAll("-", "")}-${String(id).padStart(4, "0")}`,
      type: "batch",
      status: "queued",
      progress: 0,
      asset_count: body.asset_count,
      obj_count: 0,
      model_version_id: 4,
      error_msg: null,
      created_at: new Date().toISOString(),
      finished_at: null,
    };
    TASKS.push(task);
    persist();
    return task;
  },

  // System administration, in the server's shapes (api-contract §6).
  "GET /users": () => ({ items: USERS, total: USERS.length }),

  "POST /users/{id}/status": ({ id, body }) => {
    const user = USERS.find((u) => u.user_id === Number(id));
    if (!user) throw new Fail(40401, "账号不存在");
    if (user.role === "admin" && !body.status) throw new Fail(40301, "不能停用管理员账号");
    user.status = body.status ? 1 : 0;
    return user;
  },

  "POST /users/{id}/reset-password": ({ id, body }) => {
    if (!USERS.some((u) => u.user_id === Number(id))) throw new Fail(40401, "账号不存在");
    if (!(body?.password?.length >= 8)) throw new Fail(40002, "新密码至少 8 位");
    return { user_id: Number(id), reset: true };
  },

  "GET /params": () => PARAMS,

  // PATCH takes any subset and answers with the full set plus what changed.
  "PATCH /params": ({ body }) => {
    if (body.quality_threshold !== undefined && !(body.quality_threshold >= 0 && body.quality_threshold <= 100)) {
      throw new Fail(40002, "质量阈值须在 0 到 100 之间");
    }
    const changed = Object.fromEntries(
      Object.entries(body).filter(([k, v]) => PARAMS[k] !== v).map(([k, v]) => [k, { before: PARAMS[k], after: v }]),
    );
    Object.assign(PARAMS, body);
    return { params: PARAMS, changed };
  },

  // Demo reset for the prototype tab: the business rows and the seeded demo rows go, while accounts,
  // species, model versions and parameters stay. The counts are what was actually removed; the online
  // model's name is read before the wipe.
  "POST /demo/reset": () => {
    const deleted = {
      media_asset: FRAMES.length,
      detect_object: objectCount(),
      detect_task: TASKS.length,
      report: REPORTS.length,
      dataset: DATASETS.length,
      train_experiment: EXPERIMENTS.length,
      sys_message: MESSAGES.length,
      sys_log: LOGS.length,
    };
    const frameFilesRemoved = FRAMES.length;
    const modelOnline = MODELS.find((model) => model.is_online)?.version_name ?? null;
    resetDemo();
    return { deleted, frame_files_removed: frameFilesRemoved, model_online: modelOnline };
  },

  // Monitoring: queue counts from the task list, the rest fixed (the server measures the disk).
  "GET /monitor": () => ({
    queue: {
      queued: TASKS.filter((t) => t.status === "queued").length,
      running: TASKS.filter((t) => t.status === "running").length,
    },
    frames: FRAMES.length,
    disk: { used_gb: 182.4, total_gb: 476.3, percent: 38.3, level: "ok" },
    max_concurrency: PARAMS.max_concurrency,
    at: new Date().toISOString(),
  }),

  // Filters as the server reads them: module and action, no keyword.
  "GET /logs": ({ query }) =>
    paginate(LOGS.filter((l) => (!query.module || l.module === query.module) && (!query.action || l.action === query.action)), query),

  "GET /messages": ({ query }) => ({
    ...paginate(MESSAGES, query),
    unread: MESSAGES.filter((m) => !m.is_read).length,
  }),

  "POST /messages/{id}/read": ({ id }) => {
    const msg = MESSAGES.find((m) => m.msg_id === Number(id));
    if (!msg) throw new Fail(40401, "消息不存在");
    msg.is_read = true;
    return { msg_id: msg.msg_id, is_read: true };
  },

  // Model versions: both routes are in the contract. Exactly one model is online (P3-03).
  "GET /models": () => ({
    items: MODELS,
    online_model_id: MODELS.find((m) => m.is_online)?.model_id ?? null,
    total: MODELS.length,
  }),

  "POST /models/{id}/activate": ({ id }) => {
    const model = MODELS.find((m) => m.model_id === Number(id));
    if (!model) throw new Fail(40401, "模型版本不存在");
    if (model.is_online) throw new Fail(40901, "该版本已在线");
    MODELS.forEach((m) => { m.is_online = m === model; });
    persist();
    return model;
  },

  // Experiments and the species dictionary (api-contract §6).
  "GET /experiments": () => ({
    items: EXPERIMENTS,
    baseline: EXPERIMENTS.find((e) => e.is_baseline)?.exp_name ?? null,
    total: EXPERIMENTS.length,
  }),

  "GET /species": () => ({ items: SPECIES, total: SPECIES.length }),

  "PATCH /species/{id}": ({ id, body }) => {
    const row = SPECIES.find((s) => s.class_code === id);
    if (!row) throw new Fail(40401, "类别不存在");
    if (body.conf_thr !== undefined && !(body.conf_thr >= 0 && body.conf_thr <= 1)) throw new Fail(40002, "阈值须在 0 到 1 之间");
    for (const key of ["conf_thr", "in_stat", "cn_name"]) if (body[key] !== undefined) row[key] = body[key];
    persist();
    return row;
  },

  // Reports, as the server answers: generated synchronously, ready when the call returns.
  "GET /reports": ({ query }) => paginate(REPORTS, query),

  "POST /reports": ({ body }) => {
    if (!body?.period_start || !body?.period_end) throw new Fail(40001, "请选择统计周期");
    if (body.period_end < body.period_start) throw new Fail(40002, "结束日期不能早于开始日期");
    const id = Math.max(0, ...REPORTS.map((r) => r.report_id)) + 1;
    const code = `RP${new Date().toISOString().slice(2, 10).replaceAll("-", "")}-${String(id).padStart(3, "0")}`;
    const report = {
      report_id: id,
      report_code: code,
      period_start: body.period_start,
      period_end: body.period_end,
      template: body.template,
      basis: body.basis,
      model_version_id: MODELS.find((m) => m.is_online)?.model_id ?? null,
      status: "ready",
      error_msg: null,
      file_path: `reports/${code}.md`,
      created_at: new Date().toISOString(),
    };
    REPORTS.unshift(report);
    persist();
    return report;
  },

  // Dataset snapshots, as the server answers them: export is synchronous and ready on return.
  "GET /datasets": () => ({ items: DATASETS, total: DATASETS.length }),

  "POST /datasets": ({ body }) => {
    if (!/^DS-[A-Za-z0-9_-]+$/.test(body?.snapshot_name ?? "")) throw new Fail(40002, "快照名须以 DS- 开头");
    if (DATASETS.some((d) => d.snapshot_name === body.snapshot_name)) throw new Fail(40901, "该快照名已存在");
    const ratios = (body.split_ratio ?? "7:2:1").split(":").map(Number);
    if (ratios.reduce((a, b) => a + b, 0) !== 10) throw new Fail(40002, "划分比例之和应为 10，例如 7:2:1");
    const frames = body.only_reviewed === false ? FRAMES.length : Object.keys(REVIEWS).length;
    if (!frames) throw new Fail(40002, "没有符合条件的帧，无法导出");
    const val = Math.round((frames * ratios[1]) / 10);
    const test = Math.round((frames * ratios[2]) / 10);
    const ds = {
      dataset_id: Math.max(0, ...DATASETS.map((d) => d.dataset_id)) + 1,
      snapshot_name: body.snapshot_name,
      split_ratio: body.split_ratio,
      seed: body.seed,
      frame_count: frames,
      splits: { train: frames - val - test, val, test },
      groups: Math.ceil(frames / 3),
      manifest_path: `data/datasets/${body.snapshot_name}/manifest.json`,
      status: "ready",
      created_at: new Date().toISOString(),
    };
    DATASETS.unshift(ds);
    persist();
    return ds;
  },

  // Hard-sample pool, filtered by source like the server (no keyword filter there).
  "GET /hard-samples": ({ query }) =>
    paginate(hardSamples().filter((h) => !query.source || h.source === query.source), query),

  "DELETE /hard-samples/{id}": ({ id }) => {
    if (!hardSamples().some((h) => h.frame_id === id)) throw new Fail(40401, "难例不存在");
    removedHard.add(id);
    persist();
    return { frame_id: id, removed: 1 };
  },

  // Task list, cancel and retry, as the server answers them (status filter only, no keyword).
  "GET /tasks": ({ query }) => {
    advanceTasks();
    const items = TASKS.filter((t) => !query.status || t.status === query.status).sort(
      (a, b) => b.task_id - a.task_id,
    );
    return paginate(items, query);
  },

  "GET /tasks/{id}": ({ id }) => findTask(id),

  "POST /tasks/{id}/cancel": ({ id }) => {
    const task = findTask(id);
    if (!["queued", "running"].includes(task.status)) throw new Fail(40901, "任务已结束，不能取消");
    Object.assign(task, { status: "cancelled", finished_at: new Date().toISOString() });
    persist();
    return task;
  },

  "POST /tasks/{id}/retry": ({ id }) => {
    const task = findTask(id);
    if (task.status !== "failed") throw new Fail(40901, "只有失败的任务可以重试");
    Object.assign(task, { status: "queued", progress: 0, error_msg: null, finished_at: null });
    persist();
    return task;
  },

  // Screen 6 statistics. species and quality are contract routes; trend and
  // corrections are contract routes too (api-contract §6).
  "GET /stats/species": () => STATS_SPECIES,
  "GET /stats/quality": () => STATS_QUALITY,
  "GET /stats/trend": () => STATS_TREND,
  "GET /stats/corrections": () => STATS_CORRECTIONS,
};

function match(method, path) {
  for (const [key, handler] of Object.entries(ROUTES)) {
    const [m, pattern] = key.split(" ");
    const re = new RegExp(`^${pattern.replace(/\{id\}/g, "([^/]+)")}$`);
    const hit = m === method && path.match(re);
    if (hit) return { handler, id: hit[1] && decodeURIComponent(hit[1]) };
  }
  return null;
}

export async function handle(method, path, { query, body }) {
  await new Promise((r) => setTimeout(r, 150)); // feel like a network call
  const request_id = `req-${Math.random().toString(16).slice(2, 6)}`;
  const route = match(method, path);
  try {
    if (!route) throw new Fail(40401, `接口不存在：${method} ${path}`);
    // Clone so pages never share objects with the mock store, as with real JSON.
    const data = structuredClone(route.handler({ id: route.id, query, body }));
    return { code: 0, message: "ok", data, request_id };
  } catch (err) {
    if (!(err instanceof Fail)) console.error(err);
    const code = err instanceof Fail ? err.code : 50001;
    const message = err instanceof Fail ? err.message : "服务器内部错误";
    return { code, message, data: null, request_id };
  }
}
