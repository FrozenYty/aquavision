"""Result export, run for real: web/static/js/csv.js under Node, read back with Python's csv module.

The writer is JavaScript and the reader is Python's standard library, so a round trip proves the file is
valid CSV to an independent parser, not merely that the code agrees with itself (PLAN P3-14).
"""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CSV_JS = ROOT / "web" / "static" / "js" / "csv.js"
DETAIL = ROOT / "web" / "templates" / "result-detail.html"

NODE = shutil.which("node")
# Locally a missing Node skips; in CI it fails, so the checks can never pass by being skipped there.
if NODE is None and os.environ.get("CI"):
    pytest.fail("Node is required in CI to run tests/test_result_csv.py", pytrace=False)
needs_node = pytest.mark.skipif(NODE is None, reason="Node is not installed")


def run(expression: str):
    script = (
        f"import * as m from {json.dumps(CSV_JS.as_uri())};"
        f"process.stdout.write(JSON.stringify({expression}));"
    )
    out = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    return json.loads(out.stdout)


FRAME = {
    "frame_id": "20261103T091000-0001",
    "session_id": "s-a3-001",
    "point_code": "A3",
    "captured_at": "2026-11-03T01:10:00+00:00",
}
TRICKY = [
    'a, comma',
    'a "quote"',
    "a\nnewline",
    "a\r\nCRLF",
    "海参, 刺参",
    ' leading space',
    "",
]


@needs_node
def test_plain_fields_are_left_alone_and_risky_ones_are_quoted():
    fields = ["plain", "海胆", 0.94, 3, None, *TRICKY]
    got = run(f"{json.dumps(fields)}.map(m.csvField)")
    assert got == [
        "plain",
        "海胆",
        "0.94",
        "3",
        "",
        '"a, comma"',
        '"a ""quote"""',
        '"a\nnewline"',
        '"a\r\nCRLF"',
        '"海参, 刺参"',
        '" leading space"',
        "",
    ]


@needs_node
def test_comma_quote_newline_and_chinese_survive_a_round_trip():
    boxes = [
        {"object_id": i + 1, "class_code": "holothurian", "confidence": 0.5, "x": 0.1, "y": 0.2,
         "w": 0.3, "h": 0.4, "is_manual": 0, "review_status": 0}
        for i in range(len(TRICKY))
    ]  # fmt: skip
    # Each box gets one tricky class name, so every escaping case passes through the whole file.
    names = {f"c{i}": name for i, name in enumerate(TRICKY)}
    for i, box in enumerate(boxes):
        box["class_code"] = f"c{i}"
    text = run(
        f"m.toCsv(m.RESULT_COLUMNS, m.resultRows({json.dumps(FRAME)}, {json.dumps(boxes)}, "
        f"{json.dumps(names)}, ['待复核']))"
    )
    assert text.startswith("﻿"), "the file must start with a UTF-8 byte-order mark for Excel"
    assert text.endswith("\r\n")
    rows = list(csv.DictReader(io.StringIO(text.removeprefix("﻿"), newline="")))
    assert len(rows) == len(boxes), "one row per box, no more and no fewer"
    assert [row["class_name"] for row in rows] == TRICKY
    assert {row["frame_id"] for row in rows} == {FRAME["frame_id"]}
    assert rows[0]["review_status_name"] == "待复核"
    assert rows[0]["confidence"] == "0.5"


@needs_node
def test_the_header_is_the_servers_field_names():
    columns = run("m.RESULT_COLUMNS")
    box_fields = ["object_id", "class_code", "confidence", "x", "y", "w", "h", "is_manual", "review_status"]
    frame_fields = ["frame_id", "session_id", "point_code", "captured_at"]
    assert all(field in columns for field in box_fields + frame_fields)
    assert [c for c in columns if c not in box_fields + frame_fields] == ["class_name", "review_status_name"]


@needs_node
def test_the_bytes_are_utf8_so_chinese_opens_in_excel():
    text = run("m.toCsv(['class_name'], [{ class_name: '海参' }])")
    data = text.encode("utf-8")
    assert data.startswith(b"\xef\xbb\xbf")
    assert data.decode("utf-8-sig") == "class_name\r\n海参\r\n"


@needs_node
def test_the_filename_carries_the_frame_id_and_the_time():
    when = "new Date('2026-11-11T02:45:07.123Z')"
    assert run(f"m.csvFilename('20261103T091000-0001', {when})") == (
        "aquavision-20261103T091000-0001-20261111T024507Z.csv"
    )
    assert run(f"m.csvFilename('a/b:c', {when})") == "aquavision-a_b_c-20261111T024507Z.csv"
    assert run(f"m.csvFilename('f', {when}, {{ mock: true }})").endswith("-mock.csv")
    later = run("m.csvFilename('f', new Date('2026-11-11T02:45:08Z'))")
    assert later != run(f"m.csvFilename('f', {when})"), "two exports a second apart must differ"


def test_the_page_exports_through_the_module_and_refuses_an_empty_result():
    page = DETAIL.read_text(encoding="utf-8")
    assert "toCsv(" in page and "csvFilename(" in page, "result-detail.html must export through csv.js"
    assert "boxes.length === 0" in page, "an empty result must be refused before any file is made"
