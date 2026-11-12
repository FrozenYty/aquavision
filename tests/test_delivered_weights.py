"""The delivered model is in the repository, and a clean clone can register it (ADR 13).

ADR 13 puts a delivered version in `models/<version_name>/` — `best.pt`, `labels.txt` and
`metrics.json`, tracked — so that a clone can register the version and run detection. This file is
the half of that acceptance which needs no torch and no camera: it reads the directory git would
hand a clone, it runs the real `scripts/init_db.py` against an empty database, and it checks what a
fresh installation ends up pointing at. The other half — that the weights actually load and produce
the same boxes as a manual run — is `tests/test_detect_real.py`, which needs ultralytics.

The class order is checked here without running the model, against the seed the dictionary is built
from: one position out of order mislabels every box, and that is worth catching on a machine that
cannot load a `.pt` at all.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from app.db import engine_from_dsn
from app.detector import resolve_weight_path
from app.models import ModelVersion
from app.seed import SPECIES_SEED
from sqlalchemy import select
from sqlalchemy.orm import Session

REPO = Path(__file__).resolve().parent.parent
MODELS = REPO / "models"
DEV_DB = REPO / "data" / "app.db"
#: The three files SRS section 4 delivers together and ADR 13 tracks. Nothing else belongs here.
DELIVERED_FILES = ("best.pt", "labels.txt", "metrics.json")


def _versions() -> list[Path]:
    return sorted(entry for entry in MODELS.iterdir() if entry.is_dir()) if MODELS.is_dir() else []


def _tracked(prefix: str) -> set[str]:
    """What git has under `prefix` — the same answer a fresh clone gets."""
    result = subprocess.run(
        ["git", "ls-files", "-z", prefix],
        cwd=REPO,
        capture_output=True,
        check=True,
    )
    return {name for name in result.stdout.decode("utf-8").split("\0") if name}


def _relative(version: Path, name: str) -> str:
    return f"models/{version.name}/{name}"


def test_the_delivered_version_holds_exactly_three_tracked_files() -> None:
    versions = _versions()
    assert versions, "models/ holds no delivered version, so a clean clone has nothing to register"

    tracked = _tracked("models")
    for version in versions:
        names = sorted(entry.name for entry in version.iterdir())
        assert names == sorted(DELIVERED_FILES), (
            f"{version.name} holds {names}; ADR 13 tracks exactly {sorted(DELIVERED_FILES)}"
        )
        for name in DELIVERED_FILES:
            assert (version / name).stat().st_size > 0, f"{_relative(version, name)} is empty"
            assert _relative(version, name) in tracked, (
                f"{_relative(version, name)} is not tracked, so a clone does not have it"
            )


def test_the_labels_follow_the_species_dictionary_order() -> None:
    """Data model §3.6: the codes and their order are a contract with `species_dict`."""
    expected = [str(row["class_code"]) for row in SPECIES_SEED]
    for version in _versions():
        lines = [
            line.strip()
            for line in (version / "labels.txt").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert lines == expected, f"{version.name}/labels.txt is {lines}, expected {expected}"


def test_the_metrics_name_the_delivered_weight_and_carry_the_report_columns() -> None:
    columns = ("map50", "map50_95", "recall_avg", "fps", "params_m")
    for version in _versions():
        metrics = json.loads((version / "metrics.json").read_text(encoding="utf-8"))
        # A path with this machine's drive letter in it is the defect that made the old registration
        # describe one laptop; the delivered file names the delivered weight, relative to the root.
        assert metrics["weights"] == _relative(version, "best.pt")
        for column in columns:
            assert isinstance(metrics[column], (int, float)), f"{column} is not a number"


def test_a_fresh_database_registers_the_delivered_version_with_a_portable_path(
    tmp_path: Path,
) -> None:
    """The acceptance, run the way a clean clone runs it: the script, an empty database, nothing else."""
    versions = _versions()
    assert versions, "models/ holds no delivered version, so a clean clone has nothing to register"

    db = tmp_path / "clean.db"
    dsn = f"sqlite:///{db.as_posix()}"
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "init_db.py"),
            "--dsn",
            dsn,
            "--admin-password",
            "clean-clone",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    engine = engine_from_dsn(dsn)
    try:
        with Session(engine) as session:
            online = list(session.scalars(select(ModelVersion).where(ModelVersion.is_online == 1)))
            assert len(online) == 1, f"a fresh database has {len(online)} online versions"
            row = online[0]
            assert row.weight_path == f"models/{row.version_name}/best.pt"
            assert row.labels_path == f"models/{row.version_name}/labels.txt"
            # Activation refuses a row without metrics (P3-03); a delivered one has all of them.
            for column in ("map50", "map50_95", "recall_avg", "fps", "params_m"):
                assert getattr(row, column) is not None, f"{column} is empty on an online version"
    finally:
        engine.dispose()

    # The stored path must survive the move to another machine: the app resolves it against the
    # repository root, and what it resolves to is a file git carries.
    resolved = resolve_weight_path(row.weight_path)
    assert resolved.is_relative_to(REPO)
    assert resolved.is_file(), f"{row.weight_path} does not resolve to a file: {resolved}"
    assert row.weight_path in _tracked("models")


def test_the_development_database_online_version_points_at_the_delivered_weight() -> None:
    """The row this machine serves from. It is local — `data/` is the gitignored runtime root."""
    if not DEV_DB.is_file():
        pytest.skip(f"the development database is not on this machine: {DEV_DB.name} is missing")

    engine = engine_from_dsn(f"sqlite:///{DEV_DB.as_posix()}")
    try:
        with Session(engine) as session:
            online = list(session.scalars(select(ModelVersion).where(ModelVersion.is_online == 1)))
    finally:
        engine.dispose()

    assert len(online) <= 1, f"{DEV_DB.name} has {len(online)} online versions; only one may be"
    if not online:
        # A machine state, not a defect: `data/` is the local runtime root, and a database created
        # before the weights existed has no row naming them. The clean-clone acceptance is proven by
        # test_a_fresh_database_registers_the_delivered_version_with_a_portable_path, which needs no
        # local database at all - so this one says what to run rather than failing the suite for
        # everyone whose dev database predates the delivery.
        pytest.skip(
            f"{DEV_DB.name} serves no model: no version is online. "
            "Register the delivered one with `python scripts/register_model.py`."
        )
    row = online[0]
    assert not Path(row.weight_path).is_absolute(), (
        f"the online version is registered with a machine-specific path: {row.weight_path}"
    )
    assert resolve_weight_path(row.weight_path).is_file()
    assert row.weight_path in _tracked("models")
