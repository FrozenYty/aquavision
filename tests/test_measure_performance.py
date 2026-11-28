"""The performance-measurement script runs, reports, and can go red (P3-10, AC-34).

`scripts/measure_performance.py` is the committed measurement behind AC-34. These tests keep it
honest rather than duplicating it: a small throwaway run proves it seeds a database, prints the
tables and exits 0 against the requirements' own budgets, and its single-frame half runs through the
real route whenever torch and the delivered weights are here (otherwise that half is skipped with a
reason - the number belongs to the deployment machine, docs/test-cases-en.md TC-PERF-01). A
deliberately tiny budget proves the check can fail, which is the only way a PASS means anything. The
percentile function is pinned directly so the reported P90 is the nearest-rank value the script
documents, not an interpolation nobody defined.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "measure_performance.py"
MODELS = REPO / "models"


def load_script():
    """Load the script by path: it is a program, not an importable package."""
    spec = importlib.util.spec_from_file_location("measure_performance", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_script(tmp_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the script on a throwaway tree; the caller's database settings never reach it."""
    env = {**os.environ, "PYTHONUTF8": "1"}
    # The script owns its DB_DSN and AV_DATA_DIR. Removing them here proves it does, and keeps a
    # developer's real database out of the measurement tree.
    env.pop("DB_DSN", None)
    env.pop("AV_DATA_DIR", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--scratch", str(tmp_path / "measure"), *arguments],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=300,
    )


def detector_available() -> bool:
    """Whether this checkout can build the online detector: torch/ultralytics and a weight."""
    if importlib.util.find_spec("ultralytics") is None:
        return False
    if not MODELS.is_dir():
        return False
    return any((path / "best.pt").is_file() for path in MODELS.glob("*") if path.is_dir())


def test_percentile_is_the_nearest_rank_and_monotonic():
    module = load_script()
    values = [float(value) for value in range(1, 101)]
    assert module.percentile(values, 0.0) == 1
    assert module.percentile(values, 0.5) == 50
    assert module.p90(values) == 90
    assert module.percentile(values, 1.0) == 100
    increasing = [module.percentile(values, step / 20) for step in range(21)]
    assert increasing == sorted(increasing)
    assert module.percentile([7.0], 0.9) == 7.0
    with pytest.raises(ValueError):
        module.percentile([], 0.9)


def test_a_small_run_seeds_prints_the_table_and_passes(tmp_path):
    measured = detector_available()
    arguments = ["--frames", "60", "--objects", "60", "--requests", "2", "--timings", "2"]
    if not measured:
        arguments.append("--list-only")
    completed = run_script(tmp_path, *arguments)
    output = completed.stdout
    assert completed.returncode == 0, output + completed.stderr

    assert "design capacity" in output
    assert "seeded 60 media_asset, 60 detect_object" in output
    for route in ("/api/frames", "/api/tasks", "/api/hard-samples", "/api/reports"):
        assert route in output
    assert "p90" in output
    assert "PASS  list p90" in output
    assert "/api/datasets" in output and "skipped" in output
    assert '"exit_code": 0' in output

    if measured:
        assert "POST /api/detect/frames/" in output
        assert "torch.cuda.is_available():" in output
        assert "PASS  single-frame median" in output
        assert "PASS  single-frame p90" in output
        assert '"device":' in output
    else:
        assert "single-frame latency: not requested" in output


def test_a_budget_that_cannot_be_met_fails(tmp_path):
    completed = run_script(
        tmp_path,
        "--frames",
        "40",
        "--objects",
        "40",
        "--requests",
        "2",
        "--list-only",
        "--list-budget-ms",
        "0.001",
    )
    output = completed.stdout
    assert completed.returncode == 1, output + completed.stderr
    assert "FAIL  list p90" in output
    assert "summary: some measured budgets did not pass" in output
    assert '"exit_code": 1' in output
