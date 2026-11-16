import assert from "node:assert/strict";
import { fmtTime, reportPeriod } from "../web/static/js/time.js";

assert.equal(fmtTime("2026-11-02T15:59:59.000+00:00"), "2026-11-02 15:59:59.000 +00:00");
assert.equal(fmtTime("2026-11-02T23:59:59.000+08:00"), "2026-11-02 23:59:59.000 +08:00");
assert.equal(fmtTime("2026-11-02T23:59:59.418-05:00"), "2026-11-02 23:59:59.418 -05:00");
assert.equal(fmtTime(null), "—");
assert.equal(fmtTime("bad"), "—");
assert.deepEqual(reportPeriod("2026-11-02", "week"), { label: "本周", from: "2026-11-02", to: "2026-11-02" });
assert.equal(reportPeriod("2026-11-01", "week").from, "2026-10-26");
assert.equal(reportPeriod("2026-11-02", "month").from, "2026-11-01");
assert.equal(reportPeriod("", "week"), null);
assert.equal(reportPeriod("2026-11-02", "custom", "2026-11-03", "2026-11-02"), null);
console.log("Operating time: offsets, milliseconds and calendar periods passed");
