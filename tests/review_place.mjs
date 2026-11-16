import assert from "node:assert/strict";
import { serializePlace, restorePlace, placeStore } from "../web/static/js/place.js";

const place = { frameId: "frame-40", selected: 8, zoom: 3, page: 4 };
const saved = serializePlace(place);
assert.deepEqual(restorePlace(saved, { frameId: "frame-40", objectIds: [8, 9] }), place);
assert.equal(restorePlace(saved, { frameId: "other", objectIds: [8] }).selected, null);
assert.equal(restorePlace(saved, { frameId: "other" }).zoom, 1);
assert.equal(restorePlace(saved, { objectIds: [9] }).selected, null);
assert.deepEqual(restorePlace("not JSON"), { frameId: null, selected: null, zoom: 1, page: 1 });
assert.equal(restorePlace('{"version":1,"page":-2,"zoom":999}').page, 1);
assert.equal(restorePlace('{"version":1,"zoom":999}').zoom, 1);
assert.equal(restorePlace('{"version":2,"frameId":"old"}').frameId, null);
console.log("Review place: round trip, frame isolation, removed selection and corrupt data passed");

let notices = 0;
globalThis.sessionStorage = { getItem() { throw new Error("denied"); }, setItem() { throw new Error("denied"); } };
const store = placeStore("review", () => notices++);
assert.equal(store.read(), null);
store.write(place);
assert.equal(notices, 1, "storage failures are reported once instead of swallowed");
