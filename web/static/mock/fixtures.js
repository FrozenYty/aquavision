// Deterministic demo data shaped like docs/api-contract-en.md §6. Same output on every load.

let seed = 42;
function rand() {
  seed = (seed * 16807) % 2147483647;
  return seed / 2147483647;
}
const int = (lo, hi) => lo + Math.floor(rand() * (hi - lo + 1));
const pad = (n, w = 2) => String(n).padStart(w, "0");

export const CAMERAS = [
  { index: 0, name: "USB 1080P Camera", width: 1920, height: 1080, available: true },
];

// Session fields beyond session_id are provisional (no session object in the contract yet).
export const SESSIONS = [
  ["s-a3-001", "A3", "2026-11-03T09:10:00+08:00", "closed", null],
  ["s-a3-002", "A3", "2026-11-03T14:30:00+08:00", "closed", null],
  ["s-b1-001", "B1", "2026-11-03T19:30:00+08:00", "closed", null],
  ["s-b1-002", "B1", "2026-11-04T08:45:00+08:00", "failed", "摄像头不可用，请检查 USB 连接"],
].map(([session_id, site, started_at, status, fail_reason]) => ({
  session_id,
  site,
  started_at,
  status,
  fail_reason,
  frame_count: 0,
  retake_count: 0,
}));

function makeFrame(session, i) {
  const t = new Date(new Date(session.started_at).getTime() + i * 1000);
  const local = new Date(t.getTime() + 8 * 3600e3); // render the ID in +08:00
  const stamp =
    `${local.getUTCFullYear()}${pad(local.getUTCMonth() + 1)}${pad(local.getUTCDate())}T` +
    `${pad(local.getUTCHours())}${pad(local.getUTCMinutes())}${pad(local.getUTCSeconds())}`;
  const sharpness = int(35, 92);
  const brightness = int(40, 90);
  const colorcast = int(40, 85);
  const score = Math.round(sharpness * 0.5 + brightness * 0.3 + colorcast * 0.2);
  return {
    frame_id: `${stamp}-${pad(i + 1, 4)}`,
    session_id: session.session_id,
    captured_at: `${local.toISOString().slice(0, 23)}+08:00`,
    quality: { sharpness, brightness, colorcast, score, verdict: score >= 60 ? "ok" : "retake" },
    env: { turbidity_rel: int(4, 28) },
    width: 1920,
    height: 1080,
    site: session.site, // provisional: the contract filters by site but the frame has no site field
  };
}

export const FRAMES = SESSIONS.filter((s) => s.status !== "failed").flatMap((s) => {
  const frames = Array.from({ length: int(14, 22) }, (_, i) => makeFrame(s, i));
  s.frame_count = frames.length;
  s.retake_count = frames.filter((f) => f.quality.verdict === "retake").length;
  return frames;
});

export const newFrame = makeFrame;
// Dashboard figures. Fixed rather than random: a demo that changes on every reload looks broken.
// today is the last element; the array runs oldest to newest.
export const DASHBOARD = {
  frames_today: 412,
  rejected_today: 49,
  to_review: 7,
  model_version: "v8n-E3",
  model_map50: 0.83,
  daily: [318, 402, 377, 441, 389, 356, 412],
};