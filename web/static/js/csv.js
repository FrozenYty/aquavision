// Result export as CSV, kept free of the DOM so it can be tested by running it (tests/test_result_csv.py).
//
// Encoding is the part that usually breaks: Excel reads a CSV as the system code page unless the file starts
// with a UTF-8 byte-order mark, and then every Chinese class name turns to mojibake. So the text starts with
// U+FEFF, and lines end in CRLF, which is what Excel writes and reads.

const BOM = "﻿";
const EOL = "\r\n";

// The header is the server's own field names (api-contract §6), so a script reads the file the way it
// reads the API. The two *_name columns are added for people: the Chinese class name and review status.
export const RESULT_COLUMNS = [
  "frame_id",
  "session_id",
  "point_code",
  "captured_at",
  "object_id",
  "class_code",
  "class_name",
  "confidence",
  "x",
  "y",
  "w",
  "h",
  "is_manual",
  "review_status",
  "review_status_name",
];

// One field. Quoted when it holds a comma, a double quote, a line break, or leading or trailing space;
// a double quote inside is doubled (RFC 4180). Missing values are empty fields, never "null".
export function csvField(value) {
  if (value === null || value === undefined) return "";
  const text = String(value);
  return /[",\r\n]|^\s|\s$/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function csvLine(values) {
  return values.map(csvField).join(",");
}

// The whole file: byte-order mark, header, one line per row, and a final line ending.
export function toCsv(columns, rows) {
  return BOM + [columns, ...rows.map((row) => columns.map((key) => row[key]))].map(csvLine).join(EOL) + EOL;
}

// One row per box, in the order the page lists them; the frame's fields repeat on every row so each line
// stands on its own once the file is filtered or sorted.
export function resultRows(frame, boxes, classNames = {}, statusNames = []) {
  return boxes.map((box) => ({
    frame_id: frame.frame_id,
    session_id: frame.session_id,
    point_code: frame.point_code,
    captured_at: frame.captured_at,
    object_id: box.object_id,
    class_code: box.class_code,
    class_name: classNames[box.class_code] ?? "",
    confidence: box.confidence,
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    is_manual: box.is_manual,
    review_status: box.review_status,
    review_status_name: statusNames[box.review_status] ?? "",
  }));
}

// aquavision-<frame id>-<UTC time>.csv. The time is passed in, so the same frame and moment always give the
// same name, and two exports of one frame are told apart by their time. Characters a file system may refuse
// are replaced; a demo export says so in its name, so it cannot pass for real data.
export function csvFilename(frameId, when, { mock = false } = {}) {
  const safe = String(frameId).replace(/[^A-Za-z0-9_-]/g, "_");
  const stamp = when.toISOString().replace(/\.\d{3}Z$/, "Z").replace(/[-:]/g, "");
  return `aquavision-${safe}-${stamp}${mock ? "-mock" : ""}.csv`;
}
