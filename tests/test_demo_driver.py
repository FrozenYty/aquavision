"""The demo driver runs the slice for real (P4-12).

`scripts/demo.py` is the one command a rehearsal uses, so the test runs it as a subprocess against the
throwaway database it creates and checks the numbers it printed against the rows the API actually
wrote. A driver that stops running a step, or prints a number the database disagrees with, fails here.

The driver is run with the checkout-local inference interpreter when the checkout has one:
`ultralytics` and torch are not in the server environment. Where there is none, the driver states that
box counts are absent, and the test asserts that statement rather than a count.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
DRIVER = ROOT / "scripts" / "demo.py"
INFER_PYTHON = ROOT / ".venv-infer" / "Scripts" / "python.exe"
DEV_DATABASE = ROOT / "data" / "app.db"
DELIVERED_FILES = ("best.pt", "labels.txt", "metrics.json")

SUMMARY = re.compile(r"^demo summary: (\{.*\})\s*$", re.MULTILINE)
FRAMES_CAPTURED = re.compile(r"^frames captured (\d+)$", re.MULTILINE)
BOXES_DRAWN = re.compile(r"^boxes drawn (\d+)$", re.MULTILINE)


def driver_python() -> Path:
    """The inference interpreter when this checkout has one, the test runner's otherwise."""
    return INFER_PYTHON if INFER_PYTHON.is_file() else Path(sys.executable)


def can_detect(python: Path) -> bool:
    """Whether that interpreter can load a model; checked without importing torch here."""
    probe = subprocess.run(
        [
            str(python),
            "-c",
            "import importlib.util, sys; "
            "sys.exit(0 if importlib.util.find_spec('ultralytics') else 1)",
        ],
        capture_output=True,
    )
    return probe.returncode == 0


def delivered_versions() -> list[str]:
    models = ROOT / "models"
    return sorted(
        entry.name
        for entry in models.iterdir()
        if entry.is_dir() and all((entry / name).is_file() for name in DELIVERED_FILES)
    )


def number(pattern: re.Pattern[str], text: str, what: str) -> int:
    match = pattern.search(text)
    assert match is not None, f"the driver did not print {what}:\n{text}"
    return int(match.group(1))


def rows(summary: dict, query: str, parameters: tuple = ()):
    database = sqlite3.connect(ROOT / summary["database"])
    try:
        return database.execute(query, parameters).fetchall()
    finally:
        database.close()


@pytest.fixture(scope="module")
def run():
    """One driver run for the module: loading the weights is the expensive part of it."""
    python = driver_python()
    inference = can_detect(python)
    before = (
        DEV_DATABASE.exists(),
        DEV_DATABASE.stat().st_mtime_ns if DEV_DATABASE.exists() else None,
    )

    result = subprocess.run(
        [str(python), str(DRIVER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )

    match = SUMMARY.search(result.stdout)
    if match is None:
        pytest.fail(
            f"scripts/demo.py printed no summary line (exit {result.returncode}):\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )
    summary = json.loads(match.group(1))
    yield SimpleNamespace(result=result, summary=summary, inference=inference, dev_before=before)
    shutil.rmtree(ROOT / summary["scratch"], ignore_errors=True)


def test_the_slice_runs_and_the_printed_numbers_match_the_database(run):
    assert run.result.returncode == 0, run.result.stdout + run.result.stderr
    summary, stdout = run.summary, run.result.stdout

    captured = number(FRAMES_CAPTURED, stdout, "frames captured")
    assert captured == summary["frames"] == 1
    assert rows(summary, "select count(*) from media_asset")[0][0] == captured
    assert rows(summary, "select frame_id from media_asset") == [(summary["frame_id"],)]

    boxes = rows(summary, "select count(*) from detect_object")[0][0]
    per_class = dict(rows(summary, "select class_code, count(*) from detect_object group by 1"))
    assert per_class == summary["class_counts"]
    assert boxes == (summary["boxes"] or 0)
    # The report and the dashboard are read from the same rows, so the figure the statistics route
    # answers with must be the number of boxes the detection wrote.
    assert summary["stats_total"] == boxes

    if run.inference:
        assert summary["detection"] == "ok"
        assert boxes == number(BOXES_DRAWN, stdout, "boxes drawn")
        assert summary["model_version"] in delivered_versions()
    else:
        # No inference dependency: the driver says the counts are absent and writes no box.
        assert summary["boxes"] is None
        assert summary["detection"].startswith("unavailable")
        assert "box counts will be absent" in stdout
        assert "boxes drawn absent" in stdout

    report = rows(
        summary, "select status from report where report_code = ?", (summary["report_code"],)
    )
    assert report == [(1,)], "the report row is not ready"
    assert (ROOT / summary["report_file"]).is_file()


def test_the_run_owns_its_database_and_says_where_the_frame_came_from(run):
    summary, stdout = run.summary, run.result.stdout

    assert (ROOT / summary["scratch"]).is_dir()
    assert summary["database"].startswith(summary["scratch"] + "/")
    assert summary["database"] != "data/app.db"
    after = (
        DEV_DATABASE.exists(),
        DEV_DATABASE.stat().st_mtime_ns if DEV_DATABASE.exists() else None,
    )
    assert after == run.dev_before, "the driver wrote to the development database"

    assert f"frame source: {summary['frame_source']}" in stdout
    kind = summary["frame_source_kind"]
    if kind == "recorded":
        recorded = ROOT / summary["frame_source"].removeprefix("recorded frame ")
        assert recorded.is_file() and recorded.suffix == ".jpg"
    elif kind == "camera":
        assert "live grab" in summary["frame_source"]
    else:
        assert kind == "generated"
        assert "no camera answered" in summary["frame_source"]

    # The frame the driver supplied went through the capture route: the row names a file, and that
    # file is under the throwaway data root, not the development one.
    stored = rows(
        summary, "select file_path from media_asset where frame_id = ?", (summary["frame_id"],)
    )
    assert stored, "the capture route stored no row for the frame it answered with"
    assert (ROOT / summary["scratch"] / "data" / stored[0][0]).is_file()
