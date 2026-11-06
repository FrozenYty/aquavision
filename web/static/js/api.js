// The only module that talks HTTP. Pages call the named functions below, never fetch().
// While USE_MOCK is true, requests are answered by ../mock/ in the same envelope as the server.
//
// Paths marked "provisional" are not in docs/api-contract-en.md yet; lane B confirms them.

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
export const listSessions = (query) => request("GET", "/capture/sessions", { query }); // provisional
export const openSession = (body) => request("POST", "/capture/sessions", { body });
export const grabFrame = (sessionId) => request("POST", `/capture/sessions/${sessionId}/frames`);
export const closeSession = (sessionId) => request("POST", `/capture/sessions/${sessionId}/close`);

// ---- Frames and detection ----
// Contract filters: page, size, site, from, to. Provisional: session_id, verdict.
export const listFrames = (query) => request("GET", "/frames", { query });
// Body shape is provisional; the contract names the route only.
export const startBatch = (frameIds) =>
  request("POST", "/detect/batches", { body: { frame_ids: frameIds } });
export const listTasks = (query) => request("GET", "/tasks", { query }); // provisional
export const cancelTask = (id) => request("POST", `/tasks/${id}/cancel`); // provisional
export const retryTask = (id) => request("POST", `/tasks/${id}/retry`); // provisional
export const listHardSamples = (query) => request("GET", "/hard-samples", { query }); // provisional
export const removeHardSample = (frameId) => request("DELETE", `/hard-samples/${frameId}`); // provisional
export const listDatasets = () => request("GET", "/datasets"); // provisional
export const exportDataset = (body) => request("POST", "/datasets", { body }); // provisional
export const listReports = () => request("GET", "/reports"); // provisional
export const createReport = (body) => request("POST", "/reports", { body }); // provisional
export const getFrame = (frameId) => request("GET", `/frames/${frameId}`);
export const getObjects = (frameId) => request("GET", `/frames/${frameId}/objects`);

// ---- Review ----
// Body shape is provisional: the full box list after review.
export const submitReview = (frameId, objects) =>
  request("POST", `/review/frames/${frameId}`, { body: { objects } });

// ---- Stats (screen 6) ----
export const statsSpecies = () => request("GET", "/stats/species");
export const statsQuality = () => request("GET", "/stats/quality");
export const statsTrend = () => request("GET", "/stats/trend"); // provisional
export const statsCorrections = () => request("GET", "/stats/corrections"); // provisional
