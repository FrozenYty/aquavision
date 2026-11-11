// The only module that talks HTTP. Pages call the named functions below, never fetch().
// While USE_MOCK is true, requests are answered by ../mock/ in the same envelope as the server.
//
// Every function maps to a route in docs/api-contract-en.md §6; tests/test_api_js.py holds both
// that claim and the absence of any "not in the contract yet" marker. API calls are arrow functions
// that call request(); session helpers are plain function declarations, so the test can tell them apart.

const MOCK_KEY = "av_mock";
const TOKEN_KEY = "av_token";
const USER_KEY = "av_user";
const AUTH_CODES = [40101, 40102]; // token expired, not signed in (api-contract §3)

// The mock is opt-in per tab: open any page with ?mock=1 to run the prototype without a backend,
// ?mock=0 to leave it. Without the flag every page talks to the real API.
function readMockFlag() {
  try {
    const flag = new URLSearchParams(location.search).get("mock");
    if (flag === "1") sessionStorage.setItem(MOCK_KEY, "1");
    if (flag === "0") sessionStorage.removeItem(MOCK_KEY);
    return sessionStorage.getItem(MOCK_KEY) === "1";
  } catch {
    return false;
  }
}

export const USE_MOCK = readMockFlag();

export function saveSession({ token, user }) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function currentUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY));
  } catch {
    return null;
  }
}

export function hasSession() {
  return USE_MOCK || Boolean(localStorage.getItem(TOKEN_KEY));
}

// Back to the form, remembering where the user was. Only a bare page name is kept, so the login page
// can never be turned into a redirect to somewhere else.
export function toLogin() {
  const page = location.pathname.split("/").pop();
  location.href = `login.html?next=${encodeURIComponent(page + location.search)}`;
}

export class ApiError extends Error {
  constructor(code, message, requestId) {
    super(message);
    this.code = code;
    this.requestId = requestId;
  }
}

async function request(method, path, { query, body } = {}) {
  const qs = query ? `?${new URLSearchParams(clean(query))}` : "";
  let envelope;
  if (USE_MOCK) {
    const { handle } = await import("../mock/index.js");
    envelope = await handle(method, path, { query: clean(query ?? {}), body });
  } else {
    const token = localStorage.getItem(TOKEN_KEY);
    let res;
    try {
      res = await fetch(`/api${path}${qs}`, {
        method,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(0, "无法连接服务器，请确认服务已启动后刷新页面");
    }
    envelope = await res.json().catch(() => null);
    // Not JSON: usually a plain static server with no API behind it.
    if (!envelope) {
      throw new ApiError(res.status, `没有找到接口服务（HTTP ${res.status}）。只想看原型，请在地址后加 ?mock=1`);
    }
  }
  if (envelope.code !== 0) {
    // The login call answers a wrong password with the same code; there it is a message, not a redirect.
    if (AUTH_CODES.includes(envelope.code) && path !== "/auth/login") {
      clearSession();
      toLogin();
    }
    throw new ApiError(envelope.code, envelope.message, envelope.request_id);
  }
  return envelope.data;
}

// Drop empty filters so they are not sent as "?site=".
function clean(params) {
  return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v != null));
}

// ---- Auth ----
export const login = (username, password) =>
  request("POST", "/auth/login", { body: { username, password } });

// ---- Capture ----
export const listCameras = () => request("GET", "/cameras");
export const listSessions = (query) => request("GET", "/capture/sessions", { query });
export const openSession = (body) => request("POST", "/capture/sessions", { body });
export const grabFrame = (sessionId) => request("POST", `/capture/sessions/${sessionId}/frames`);
export const closeSession = (sessionId) => request("POST", `/capture/sessions/${sessionId}/close`);

// ---- Frames and detection ----
export const listFrames = (query) => request("GET", "/frames", { query });
// The server counts frames (asset_count); which frames is not part of the contract yet, so the ids
// travel along for when it is.
export const startBatch = (frameIds) =>
  request("POST", "/detect/batches", { body: { asset_count: frameIds.length, frame_ids: frameIds } });
export const listTasks = (query) => request("GET", "/tasks", { query });
export const cancelTask = (id) => request("POST", `/tasks/${id}/cancel`);
export const retryTask = (id) => request("POST", `/tasks/${id}/retry`);
export const listHardSamples = (query) => request("GET", "/hard-samples", { query });
export const removeHardSample = (frameId) => request("DELETE", `/hard-samples/${frameId}`);
export const listDatasets = () => request("GET", "/datasets");
export const exportDataset = (body) => request("POST", "/datasets", { body });
export const listReports = () => request("GET", "/reports");
export const createReport = (body) => request("POST", "/reports", { body });
export const listModels = () => request("GET", "/models");
export const activateModel = (id) => request("POST", `/models/${id}/activate`);
export const listExperiments = () => request("GET", "/experiments");
export const listSpecies = () => request("GET", "/species");
export const updateSpecies = (code, body) => request("PATCH", `/species/${code}`, { body });
// ---- System administration ----
export const listUsers = () => request("GET", "/users");
export const setUserStatus = (id, status) => request("POST", `/users/${id}/status`, { body: { status } });
export const resetPassword = (id, password) =>
  request("POST", `/users/${id}/reset-password`, { body: { password } });
export const getParams = () => request("GET", "/params");
export const updateParams = (body) => request("PATCH", "/params", { body });
export const getMonitor = () => request("GET", "/monitor");
export const listLogs = (query) => request("GET", "/logs", { query });
export const listMessages = () => request("GET", "/messages");
export const markRead = (id) => request("POST", `/messages/${id}/read`);
export const getFrame = (frameId) => request("GET", `/frames/${frameId}`);
export const getObjects = (frameId) => request("GET", `/frames/${frameId}/objects`);

// ---- Review ----
// The full corrected box list, not a diff (api-contract §6, review submission).
export const submitReview = (frameId, objects) =>
  request("POST", `/review/frames/${frameId}`, { body: { objects } });
// The version timeline, newest first, and the rollback that restores one entry as a new version
// (api-contract §6, review versions and rollback).
export const listReviewVersions = (frameId) =>
  request("GET", `/review/frames/${frameId}/versions`);
export const rollbackReview = (frameId, logId) =>
  request("POST", `/review/frames/${frameId}/rollback`, { body: { log_id: logId } });

// ---- Stats (screen 6) ----
export const statsSpecies = (query) => request("GET", "/stats/species", { query });
export const statsQuality = () => request("GET", "/stats/quality");
export const statsTrend = () => request("GET", "/stats/trend");
export const statsCorrections = () => request("GET", "/stats/corrections");
