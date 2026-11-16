import { ZOOM_STEPS } from "./canvas.js";

const empty = () => ({ frameId: null, selected: null, zoom: 1, page: 1 });

// A saved place is navigation state, never an annotation draft or a substitute for server boxes.
export function restorePlace(serialized, { frameId, objectIds } = {}) {
  let data;
  try { data = JSON.parse(serialized); } catch { return empty(); }
  if (!data || data.version !== 1) return empty();
  const savedFrame = typeof data.frameId === "string" ? data.frameId : null;
  if (frameId && savedFrame !== frameId) return { ...empty(), frameId };
  const selected = Number.isSafeInteger(data.selected) && data.selected > 0 &&
    (!objectIds || objectIds.includes(data.selected)) ? data.selected : null;
  return {
    frameId: savedFrame, selected,
    zoom: ZOOM_STEPS.includes(data.zoom) ? data.zoom : 1,
    page: Number.isSafeInteger(data.page) && data.page > 0 ? data.page : 1,
  };
}

export function serializePlace(place) {
  return JSON.stringify({ version: 1, ...restorePlace(JSON.stringify({ ...place, version: 1 })) });
}

export function placeStore(key, onError) {
  let warned = false;
  const failed = (error) => { if (!warned) { warned = true; onError(error); } };
  return {
    read() {
      try { return globalThis.sessionStorage.getItem(key); }
      catch (error) { failed(error); return null; }
    },
    write(place) {
      try { globalThis.sessionStorage.setItem(key, serializePlace(place)); }
      catch (error) { failed(error); }
    },
  };
}
