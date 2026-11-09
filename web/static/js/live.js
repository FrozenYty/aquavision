// The capture page's live feed. One interface, three sources, and every figure on the page — picture,
// boxes, quality, strip, latency — comes from the same stream of updates, never a second source:
//
//   mock     the prototype: grab a frame from the mock every few seconds (?mock=1);
//   socket   /ws/capture as api-contract §7 describes it;
//   polling  the newest frame of the session over REST, when the socket cannot open.
//
// An update is { frame_id, captured_at, image_url, quality, components, boxes, latency_ms, age_ms };
// any field may be missing, and the page draws what arrives.

import * as api from "./api.js";

const SOCKET_TIMEOUT_MS = 3000;
const POLL_MS = 1000;
const MOCK_GRAB_MS = 3000; // one frame every three seconds reads as live without rushing the demo
const MOCK_LATENCY_MS = 2000; // the prototype's latency figure moves every two seconds (prototype §3)

function socketUrl() {
  const scheme = location.protocol === "https:" ? "wss:" : "ws:";
  // Browsers cannot set headers on a WebSocket; the contract does not say how it authenticates yet,
  // so the token rides as a query parameter for when it does.
  const token = encodeURIComponent(localStorage.getItem("av_token") ?? "");
  return `${scheme}//${location.host}/ws/capture?token=${token}`;
}

// Frame ids start with the capture time (YYYYMMDDTHHMMSS-…), so they order as strings.
const newer = (a, b) => !b || a > b;

function mockFeed(sessionId, onUpdate) {
  const grab = async () => {
    const frame = await api.grabFrame(sessionId);
    const { items } = await api.getObjects(frame.frame_id);
    onUpdate({
      frame_id: frame.frame_id,
      captured_at: frame.captured_at,
      image_url: frame.image_url,
      quality: frame.quality,
      components: frame.quality_components ?? frame.quality,
      boxes: items,
    });
  };
  const latency = () => onUpdate({ latency_ms: 110 + Math.floor(Math.random() * 50) });
  latency();
  const timers = [setInterval(grab, MOCK_GRAB_MS), setInterval(latency, MOCK_LATENCY_MS)];
  grab();
  return () => timers.forEach(clearInterval);
}

function pollingFeed(sessionId, onUpdate, onError) {
  let shown = null;
  let stopped = false;
  let timer = null;
  const tick = async () => {
    try {
      const { items } = await api.listFrames({ session: sessionId, page: 1, size: 1 });
      const frame = items[0];
      if (frame && frame.frame_id !== shown) {
        shown = frame.frame_id;
        const { items: boxes } = await api.getObjects(frame.frame_id);
        onUpdate({
          frame_id: frame.frame_id,
          captured_at: frame.captured_at,
          image_url: frame.image_url ?? null,
          quality: frame.quality,
          boxes,
        });
      }
      // Polling carries no server latency; the page shows how old the newest frame is instead.
      if (frame) onUpdate({ age_ms: Date.now() - Date.parse(frame.captured_at) });
    } catch (err) {
      onError(err);
    }
    if (!stopped) timer = setTimeout(tick, POLL_MS);
  };
  tick();
  return () => {
    stopped = true;
    clearTimeout(timer);
  };
}

// Resolves to a stop function once the socket is open, or rejects when it cannot open in time.
function socketFeed(sessionId, onUpdate, onState) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(socketUrl());
    ws.binaryType = "blob";
    let header = null; // optional { type: "frame", frame_id, captured_at, quality } before a JPEG
    let shownFrame = null;
    let lastUrl = null;
    let opened = false;
    let stopping = false;
    const timeout = setTimeout(() => {
      ws.close();
      reject(new Error("socket timeout"));
    }, SOCKET_TIMEOUT_MS);

    ws.onopen = () => {
      opened = true;
      clearTimeout(timeout);
      ws.send(JSON.stringify({ type: "start", session_id: sessionId, fps: 10, detect_interval_ms: 300 }));
      resolve(() => {
        stopping = true;
        if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "stop" }));
        ws.close();
        if (lastUrl) URL.revokeObjectURL(lastUrl);
      });
    };
    ws.onerror = () => {
      clearTimeout(timeout);
      reject(new Error("socket error"));
    };
    // A socket that never opened has already handed over to polling; only a dropped one is news.
    ws.onclose = () => {
      if (opened && !stopping) onState("closed");
    };

    ws.onmessage = (event) => {
      if (event.data instanceof Blob) {
        if (lastUrl) URL.revokeObjectURL(lastUrl);
        lastUrl = URL.createObjectURL(event.data);
        shownFrame = header?.frame_id ?? shownFrame;
        onUpdate({ image_url: lastUrl, frame_id: header?.frame_id, captured_at: header?.captured_at, quality: header?.quality, boxes: [] });
        header = null;
        return;
      }
      const msg = JSON.parse(event.data);
      if (msg.type === "frame") header = msg;
      // §8: a result for a frame older than the one on screen is dropped, never queued.
      if (msg.type === "detect" && !newer(shownFrame ?? "", msg.frame_id)) {
        onUpdate({ frame_id: msg.frame_id, boxes: msg.boxes, latency_ms: msg.latency_ms, quality: msg.quality });
      }
      if (msg.type === "status") onState("status", msg);
    };
  });
}

// Starts the right feed for the session. onState(kind, detail) reports "mock", "socket", "polling",
// "status" and "closed"; the returned promise resolves to a function that stops the feed.
export async function openFeed(sessionId, onUpdate, onState, onError) {
  if (api.USE_MOCK) {
    onState("mock");
    return mockFeed(sessionId, onUpdate);
  }
  try {
    const stop = await socketFeed(sessionId, onUpdate, onState);
    onState("socket");
    return stop;
  } catch {
    onState("polling");
    return pollingFeed(sessionId, onUpdate, onError);
  }
}
