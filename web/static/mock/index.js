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
  HARD_SEEDS,
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
const STORE = "av-mock-state";
const saved = (() => {
  try {
    return JSON.parse(sessionStorage.getItem(STORE)) ?? {};
  } catch {
    return {};
  }
})();
const captured = saved.frames ?? [];
const REVIEWS = saved.reviews ?? {};
FRAMES.unshift(...captured);
if (saved.tasks) TASKS.splice(0, TASKS.length, ...saved.tasks);
const removedHard = new Set(saved.removed_hard ?? []);
if (saved.datasets) DATASETS.splice(0, DATASETS.length, ...saved.datasets);
if (saved.reports) REPORTS.splice(0, REPORTS.length, ...saved.reports);
if (saved.models) MODELS.splice(0, MODELS.length, ...saved.models);
if (saved.species) SPECIES.splice(0, SPECIES.length, ...saved.species);

function persist() {
  try {
    sessionStorage.setItem(STORE, JSON.stringify({
        frames: captured,
        reviews: REVIEWS,
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

// Each read moves the running task one frame on, so a page that polls shows real progress. When it
// finishes, the oldest queued task starts (two workers in the design, one here keeps it readable).
function advanceTasks() {
  let running = TASKS.find((t) => t.status === 1);
  if (running) {
    running.done = Math.min(running.total, running.done + 1);
    if (running.done === running.total) running.status = 2;
  }
  if (!TASKS.some((t) => t.status === 1)) {
    running = TASKS.filter((t) => t.status === 0).sort((a, b) => a.task_id - b.task_id)[0];
    if (running) running.status = 1;
  }
  persist();
}

function withQueue(tasks) {
  const queued = TASKS.filter((t) => t.status === 0).sort((a, b) => a.task_id - b.task_id);
  return tasks.map((t) => ({ ...t, queue_pos: t.status === 0 ? queued.indexOf(t) + 1 : null }));
}

// The pool: seeded samples on real frames, plus every frame corrected on the review page (FR-M4-03
// says a modified frame enters the pool automatically). Source and reason are mock field names.
function hardSamples() {
  const ok = FRAMES.filter((f) => f.quality.verdict === "ok" && !captured.includes(f));
  const seeded = HARD_SEEDS.map((seed, i) => ({ ...seed, frame: ok[i * 2] })).filter((h) => h.frame);
  const corrected = Object.entries(REVIEWS).map(([id, boxes]) => ({
    source: "corrected",
    class_code: boxes.find((b) => b.review_status === 2)?.class_code ?? boxes[0]?.class_code,
    confidence: null,
    reason: "复核时修改过框或类别",
    frame: FRAMES.find((f) => f.frame_id === id),
  }));
  return [...corrected, ...seeded]
    .filter((h) => h.frame && !removedHard.has(h.frame.frame_id))
    .filter((h, i, all) => all.findIndex((o) => o.frame === h.frame) === i)
    .map(({ frame, ...h }) => ({ ...h, frame_id: frame.frame_id, image_url: withImage(frame).image_url, added_at: frame.captured_at }));
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

const ROUTES = {
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

  "GET /frames": ({ query }) => {
    const items = FRAMES.filter(
      (f) =>
        (!query.site || f.site === query.site) &&
        (!query.session_id || f.session_id.includes(query.session_id)) &&
        (!query.verdict || f.quality.verdict === query.verdict) &&
        (!query.from || f.captured_at.slice(0, 10) >= query.from) &&
        (!query.to || f.captured_at.slice(0, 10) <= query.to),
    );
    const result = paginate(items, query);
    return { ...result, items: result.items.map(withImage) };
  },

  "GET /frames/{id}": ({ id }) => withImage(findFrame(id)),

  "GET /frames/{id}/objects": ({ id }) => REVIEWS[id] ?? detectedObjects(findFrame(id)),

  // Body { objects: [...] }: the full box list after review (api-contract §6). The reply is the
  // mock's own; the contract's is { version_no, object_count, hard_sample }.
  "POST /review/frames/{id}": ({ id, body }) => {
    if (!Array.isArray(body?.objects)) throw new Fail(40001, "缺少复核结果");
    const before = (REVIEWS[id] ?? detectedObjects(findFrame(id))).length;
    REVIEWS[id] = body.objects;
    persist();
    return { frame_id: id, count_before: before, count_after: body.objects.length };
  },

  "POST /detect/batches": ({ body }) => {
    if (!body?.frame_ids?.length) throw new Fail(40001, "请至少选择一帧");
    const task = {
      task_id: Math.max(...TASKS.map((t) => t.task_id)) + 1,
      kind: "batch",
      source: `${body.frame_ids.length} 帧（影像浏览）`,
      total: body.frame_ids.length,
      done: 0,
      status: 0,
      model_version: "v8n-E3",
      created_at: new Date().toISOString(),
      error: null,
    };
    TASKS.push(task);
    persist();
    return task;
  },

  // System administration (api-contract §6).
  "GET /users": () => USERS,

  "POST /users/{id}/status": ({ id, body }) => {
    const user = USERS.find((u) => u.user_id === Number(id));
    if (!user) throw new Fail(40401, "账号不存在");
    if (user.role === "admin" && !body.status) throw new Fail(40301, "不能停用管理员账号");
    user.status = body.status ? 1 : 0;
    return user;
  },

  "POST /users/{id}/reset-password": ({ id }) => {
    if (!USERS.some((u) => u.user_id === Number(id))) throw new Fail(40401, "账号不存在");
    return { reset: true };
  },

  "GET /params": () => PARAMS,

  "PATCH /params": ({ body }) => {
    if (!(body.quality_threshold >= 0 && body.quality_threshold <= 100)) throw new Fail(40001, "质量阈值须在 0 到 100 之间");
    return Object.assign(PARAMS, body);
  },

  // Monitoring figures: queue and failure rate from the task list, the rest fixed.
  "GET /monitor": () => {
    const finished = TASKS.filter((t) => t.status >= 2);
    return {
      queue: TASKS.filter((t) => t.status === 0).length,
      running: TASKS.filter((t) => t.status === 1).length,
      failure_rate: finished.length ? TASKS.filter((t) => t.status === 3).length / finished.length : 0,
      gpu_mem_gb: 3.8,
      gpu_mem_total_gb: 8,
      disk_used_pct: 41,
      checked_at: new Date().toISOString(),
    };
  },

  "GET /logs": ({ query }) => {
    const q = (query.q ?? "").toLowerCase();
    return LOGS.filter((l) => !q || `${l.account}${l.action}${l.before}${l.after}`.toLowerCase().includes(q));
  },

  "GET /messages": () => MESSAGES,

  "POST /messages/{id}/read": ({ id }) => {
    const msg = MESSAGES.find((m) => m.msg_id === Number(id));
    if (!msg) throw new Fail(40401, "消息不存在");
    msg.is_read = 1;
    return msg;
  },

  // Model versions: both routes are in the contract. Exactly one model is online (P3-03).
  "GET /models": () => MODELS,

  "POST /models/{id}/activate": ({ id }) => {
    const model = MODELS.find((m) => m.model_id === Number(id));
    if (!model) throw new Fail(40401, "模型版本不存在");
    if (model.is_online) throw new Fail(40901, "该版本已在线");
    MODELS.forEach((m) => { m.is_online = m === model ? 1 : 0; });
    persist();
    return model;
  },

  // Experiments and the species dictionary (api-contract §6).
  "GET /experiments": () => EXPERIMENTS,

  "GET /species": () => SPECIES,

  "PATCH /species/{id}": ({ id, body }) => {
    const row = SPECIES.find((s) => s.class_code === id);
    if (!row) throw new Fail(40401, "类别不存在");
    if (!(body.conf_thr >= 0.05 && body.conf_thr <= 0.95)) throw new Fail(40001, "阈值须在 0.05 到 0.95 之间");
    Object.assign(row, { conf_thr: body.conf_thr, in_stat: body.in_stat });
    persist();
    return row;
  },

  // Inspection reports. Generation runs over a few reads, like the dataset export.
  "GET /reports": () => {
    for (const r of REPORTS.filter((x) => x.status === "running")) {
      r.progress = Math.min(100, r.progress + 34);
      if (r.progress === 100) r.status = "done";
    }
    persist();
    return REPORTS;
  },

  "POST /reports": ({ body }) => {
    if (!body?.period) throw new Fail(40001, "请选择统计周期");
    const report = {
      report_id: Math.max(...REPORTS.map((r) => r.report_id)) + 1,
      title: `${body.label}巡检报告`,
      period: body.period,
      template: body.template,
      basis: body.basis,
      model_version: "v8n-E3",
      created_at: new Date().toISOString(),
      status: "running",
      progress: 0,
    };
    REPORTS.unshift(report);
    persist();
    return report;
  },

  // Dataset export. An export runs over a few reads, like a background job would.
  "GET /datasets": () => {
    for (const ds of DATASETS.filter((d) => d.status === "running")) {
      ds.progress = Math.min(100, ds.progress + 25);
      if (ds.progress === 100) ds.status = "done";
    }
    persist();
    return DATASETS;
  },

  "POST /datasets": ({ body }) => {
    const { train, val, test } = body?.ratio ?? {};
    if (train + val + test !== 100) throw new Fail(40001, "划分比例之和必须为 100");
    if (DATASETS.some((d) => d.status === "running")) throw new Fail(40901, "已有导出任务在进行中");
    const images = 7782 + (body.include_hard ? hardSamples().length : 0) + Object.keys(REVIEWS).length;
    const valCount = Math.round((images * val) / 100);
    const testCount = Math.round((images * test) / 100);
    const ds = {
      version: `DS-V${DATASETS.length + 1}`,
      created_at: new Date().toISOString(),
      images,
      split: { train: images - valCount - testCount, val: valCount, test: testCount },
      seed: body.seed,
      scope: [body.reviewed_only ? "仅复核后结果" : "全部结果", body.include_hard ? "含难例" : "不含难例"].join("，"),
      status: "running",
      progress: 0,
    };
    DATASETS.unshift(ds);
    persist();
    return ds;
  },

  // Hard-sample pool.
  "GET /hard-samples": ({ query }) => {
    const q = (query.q ?? "").toLowerCase();
    const items = hardSamples().filter(
      (h) => (!query.source || h.source === query.source) && (!q || h.frame_id.toLowerCase().includes(q)),
    );
    return paginate(items, query);
  },

  "DELETE /hard-samples/{id}": ({ id }) => {
    if (!hardSamples().some((h) => h.frame_id === id)) throw new Fail(40401, "难例不存在");
    removedHard.add(id);
    persist();
    return { frame_id: id };
  },

  // Task list, cancel and retry; every route here is in api-contract §6.
  "GET /tasks": ({ query }) => {
    advanceTasks();
    const q = (query.q ?? "").toLowerCase();
    const items = TASKS.filter(
      (t) =>
        (query.status === undefined || t.status === Number(query.status)) &&
        (!q || String(t.task_id).includes(q) || t.source.toLowerCase().includes(q)),
    ).sort((a, b) => b.task_id - a.task_id);
    const result = paginate(items, query);
    return { ...result, items: withQueue(result.items) };
  },

  "GET /tasks/{id}": ({ id }) => withQueue([findTask(id)])[0],

  "POST /tasks/{id}/cancel": ({ id }) => {
    const task = findTask(id);
    if (task.status > 1) throw new Fail(40901, "任务已结束，不能取消");
    Object.assign(task, { status: 3, error: "已取消" });
    persist();
    return task;
  },

  "POST /tasks/{id}/retry": ({ id }) => {
    const task = findTask(id);
    if (task.status !== 3) throw new Fail(40901, "只有失败的任务可以重试");
    Object.assign(task, { status: 0, done: 0, error: null });
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
