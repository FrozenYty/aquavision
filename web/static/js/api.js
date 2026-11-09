// The only module that talks HTTP. Pages call the named functions below, never fetch().
// While USE_MOCK is true, requests are answered by ../mock/ in the same envelope as the server.
//
// Every function maps to a route in docs/api-contract-en.md §6; tests/test_api_js.py holds both
// that claim and the absence of any "not in the contract yet" marker.

export const USE_MOCK = true;

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
    const token = localStorage.getItem("av_token");
    const res = await fetch(`/api${path}${qs}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    envelope = await res.json();
  }
  if (envelope.code !== 0) throw new ApiError(envelope.code, envelope.message, envelope.request_id);
  return envelope.data;
}

// Drop empty filters so they are not sent as "?site=".
function clean(params) {
  return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v != null));
}

// ---- Capture ----
export const listCameras = () => request("GET", "/cameras");
export const listSessions = (query) => request("GET", "/capture/sessions", { query });
export const openSession = (body) => request("POST", "/capture/sessions", { body });
export const grabFrame = (sessionId) => request("POST", `/capture/sessions/${sessionId}/frames`);
export const closeSession = (sessionId) => request("POST", `/capture/sessions/${sessionId}/close`);

// ---- Frames and detection ----
export const listFrames = (query) => request("GET", "/frames", { query });
export const startBatch = (frameIds) =>
  request("POST", "/detect/batches", { body: { frame_ids: frameIds } });
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
export const resetPassword = (id) => request("POST", `/users/${id}/reset-password`);
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

// ---- Stats (screen 6) ----
export const statsSpecies = () => request("GET", "/stats/species");
export const statsQuality = () => request("GET", "/stats/quality");
export const statsTrend = () => request("GET", "/stats/trend");
export const statsCorrections = () => request("GET", "/stats/corrections");
