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

// Prototype stills for screens 3-5. Images are DUO test frames resized to 1280x720;
// every box below is the dataset annotation for that frame, normalised to 0..1.
// Never generate these at random - a box that misses its target reads as a fake demo.
export const STILLS = [
  {
    image: "samples/sample-01.jpg",
    width: 1280,
    height: 720,
    boxes: [
      { class_code: "asterias", confidence: 0.71, x: 0.3284, y: 0.1097, w: 0.0508, h: 0.0606 },
      { class_code: "strongylocentrotus", confidence: 0.94, x: 0.5656, y: 0.2653, w: 0.2326, h: 0.4500 },
      { class_code: "strongylocentrotus", confidence: 0.68, x: 0.3089, y: 0.8060, w: 0.0708, h: 0.1625 },
    ],
  },
  {
    image: "samples/sample-02.jpg",
    width: 1280,
    height: 720,
    boxes: [
      { class_code: "strongylocentrotus", confidence: 0.91, x: 0.1076, y: 0.2282, w: 0.1135, h: 0.1444 },
      { class_code: "strongylocentrotus", confidence: 0.88, x: 0.3560, y: 0.5634, w: 0.0896, h: 0.1560 },
      { class_code: "strongylocentrotus", confidence: 0.83, x: 0.5227, y: 0.3236, w: 0.0560, h: 0.1315 },
      { class_code: "strongylocentrotus", confidence: 0.79, x: 0.7164, y: 0.0981, w: 0.0284, h: 0.0569 },
      { class_code: "strongylocentrotus", confidence: 0.74, x: 0.7099, y: 0.2333, w: 0.0461, h: 0.0407 },
      { class_code: "strongylocentrotus", confidence: 0.72, x: 0.7401, y: 0.4824, w: 0.0383, h: 0.0579 },
      { class_code: "strongylocentrotus", confidence: 0.69, x: 0.7557, y: 0.2523, w: 0.0214, h: 0.0653 },
      { class_code: "strongylocentrotus", confidence: 0.66, x: 0.6086, y: 0.8565, w: 0.0615, h: 0.1144 },
      { class_code: "strongylocentrotus", confidence: 0.63, x: 0.7734, y: 0.5634, w: 0.0354, h: 0.0634 },
      { class_code: "strongylocentrotus", confidence: 0.61, x: 0.3927, y: 0.9014, w: 0.0760, h: 0.0991 },
      { class_code: "strongylocentrotus", confidence: 0.58, x: 0.9049, y: 0.6176, w: 0.0354, h: 0.0556 },
    ],
  },
  {
    image: "samples/sample-03.jpg",
    width: 1280,
    height: 720,
    boxes: [
      { class_code: "holothurian", confidence: 0.86, x: 0.2135, y: 0.5083, w: 0.1904, h: 0.4870 },
      { class_code: "holothurian", confidence: 0.72, x: 0.6734, y: 0.2213, w: 0.0964, h: 0.1713 },
      { class_code: "asterias", confidence: 0.65, x: 0.3732, y: 0.0065, w: 0.0534, h: 0.0931 },
      { class_code: "strongylocentrotus", confidence: 0.77, x: 0.1823, y: 0.0019, w: 0.0953, h: 0.1597 },
    ],
  },
  {
    image: "samples/sample-04.jpg",
    width: 1280,
    height: 720,
    boxes: [
      { class_code: "asterias", confidence: 0.84, x: 0.2659, y: 0.7204, w: 0.4198, h: 0.2745 },
      { class_code: "asterias", confidence: 0.73, x: 0.4167, y: 0.4148, w: 0.1333, h: 0.1375 },
      { class_code: "asterias", confidence: 0.62, x: 0.6453, y: 0.5060, w: 0.0674, h: 0.0778 },
      { class_code: "chlamys", confidence: 0.81, x: 0.3604, y: 0.4806, w: 0.0599, h: 0.0787 },
      { class_code: "chlamys", confidence: 0.76, x: 0.7865, y: 0.6870, w: 0.0628, h: 0.0769 },
      { class_code: "chlamys", confidence: 0.64, x: 0.8130, y: 0.5773, w: 0.0383, h: 0.0662 },
      { class_code: "holothurian", confidence: 0.70, x: 0.0815, y: 0.2856, w: 0.0823, h: 0.0713 },
    ],
  },
];

// One extra frame detail: the wrong box the demo points at (a rock read as a sea cucumber).
export const FALSE_POSITIVE = {
  image: "samples/sample-01.jpg",
  width: 1280,
  height: 720,
  boxes: [
    { class_code: "holothurian", confidence: 0.42, x: 0.0750, y: 0.6600, w: 0.1300, h: 0.1200 },
  ],
};

// Screen 6 mock data. /stats/species and /stats/quality match the contract route
// table; trend and corrections are provisional (not in docs/api-contract-en.md yet).
// Totals are DASHBOARD.daily element for element and today's intercepted count is
// DASHBOARD.rejected_today, so screens 2 and 6 cannot disagree when compared.

export const STATS_SPECIES = [
  { class_code: "strongylocentrotus", frame_count: 187, box_count: 312 },
  { class_code: "holothurian", frame_count: 118, box_count: 164 },
  { class_code: "asterias", frame_count: 64, box_count: 92 },
  { class_code: "chlamys", frame_count: 41, box_count: 57 },
];

export const STATS_QUALITY = [
  { date: "2026-10-31", total: 318, intercepted: 38 },
  { date: "2026-11-01", total: 402, intercepted: 51 },
  { date: "2026-11-02", total: 377, intercepted: 44 },
  { date: "2026-11-03", total: 441, intercepted: 56 },
  { date: "2026-11-04", total: 389, intercepted: 47 },
  { date: "2026-11-05", total: 356, intercepted: 33 },
  { date: "2026-11-06", total: 412, intercepted: 49 },
];

// Provisional: frames captured per day, for the trend line.
export const STATS_TREND = STATS_QUALITY.map(({ date, total }) => ({ date, frames: total }));

// Provisional: review corrections per class (relabel / added / removed boxes).
export const STATS_CORRECTIONS = [
  { class_code: "strongylocentrotus", relabel: 9, added: 4, removed: 2 },
  { class_code: "holothurian", relabel: 12, added: 3, removed: 5 },
  { class_code: "asterias", relabel: 6, added: 2, removed: 1 },
  { class_code: "chlamys", relabel: 8, added: 5, removed: 0 },
];
