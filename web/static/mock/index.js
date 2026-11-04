// Mock server for api.js. Answers with the contract envelope and error codes (§2, §3).

import { CAMERAS, FRAMES, SESSIONS, newFrame } from "./fixtures.js";

class Fail extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

let nextTaskId = 1001;

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
    session.frame_count += 1;
    if (frame.quality.verdict === "retake") session.retake_count += 1;
    FRAMES.unshift(frame);
    return frame;
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
    return paginate(items, query);
  },

  "POST /detect/batches": ({ body }) => {
    if (!body?.frame_ids?.length) throw new Fail(40001, "请至少选择一帧");
    return { task_id: nextTaskId++, status: 0, total: body.frame_ids.length };
  },
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
