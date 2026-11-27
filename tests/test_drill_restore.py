"""Restore drill against a temporary SQLite database (P4-17, runbook section 5).

Every test builds its own database under `tmp_path` and calls the command's functions directly. The
assertions are the acceptance sentence itself: the intact copy returns the same totals, a copy that
lost a row is reported as a difference naming the figure, the source is not modified, and an
existing scratch copy is not overwritten without the force flag. No camera, no running service and
no network are involved.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.db import Base, engine_from_dsn
from app.models import DetectObject, DetectTask, MediaAsset, SpeciesDict, SysUser
from sqlalchemy.orm import sessionmaker

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "drill_restore.py"

#: The labels the drill compares, in the order it prints them. A renamed figure fails here too.
ROW_FIGURES = ("sys_user", "detect_object", "detect_task")
STATS_FIGURES = (
    "/api/stats/species total (reviewed)",
    "/api/stats/species total (raw)",
    "/api/stats/quality total",
    "/api/stats/corrections total",
)


def load_script():
    """The drill command as a module; it is a script, not an installed package."""
    spec = importlib.util.spec_from_file_location("drill_restore", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # `dataclass` looks its module up in `sys.modules` while the decorator runs; without this the
    # module is not importable enough for the class bodies.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


drill = load_script()


@pytest.fixture
def database(tmp_path):
    """A source database with rows in every table the drill compares, recent enough for the stats."""
    path = tmp_path / "app.db"
    engine = engine_from_dsn(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    now = datetime.now(UTC).replace(tzinfo=None)
    with factory() as session:
        session.add_all(
            [
                SysUser(
                    username="admin",
                    password_hash="hash",
                    salt="salt",
                    role_code="admin",
                    real_name="Administrator",
                ),
                SysUser(
                    username="analyst",
                    password_hash="hash",
                    salt="salt",
                    role_code="analyst",
                    real_name="Analyst",
                ),
                SpeciesDict(class_code="holothurian", cn_name="Holothurian", category=1),
            ]
        )
        session.flush()

        frames = [
            MediaAsset(
                frame_id=f"20261127T090000-{index:04d}",
                session_id="s-drill",
                point_code="A3",
                file_path=f"frames/drill-{index}.jpg",
                file_size=1024,
                file_hash=f"{index:064d}",
                captured_at=now,
                width=640,
                height=480,
                quality_score=80,
                quality_flag=0,
                is_retake=0,
            )
            for index in range(2)
        ]
        session.add_all(frames)
        session.flush()

        task = DetectTask(task_code="DT261127-0001", task_type=2, asset_count=2)
        session.add(task)
        session.flush()
        session.add_all(
            [
                DetectObject(
                    task_id=task.task_id,
                    asset_id=frames[0].asset_id,
                    frame_id=frames[0].frame_id,
                    class_code="holothurian",
                    confidence=0.9,
                    x=0.1,
                    y=0.1,
                    w=0.2,
                    h=0.2,
                    review_status=1,
                ),
                DetectObject(
                    task_id=task.task_id,
                    asset_id=frames[0].asset_id,
                    frame_id=frames[0].frame_id,
                    class_code="holothurian",
                    confidence=0.8,
                    x=0.3,
                    y=0.3,
                    w=0.2,
                    h=0.2,
                    review_status=1,
                ),
                DetectObject(
                    task_id=task.task_id,
                    asset_id=frames[1].asset_id,
                    frame_id=frames[1].frame_id,
                    class_code="holothurian",
                    confidence=0.7,
                    x=0.5,
                    y=0.5,
                    w=0.2,
                    h=0.2,
                    review_status=3,
                ),
            ]
        )
        session.commit()
    yield path
    engine.dispose()


def backup(database: Path, tmp_path: Path) -> Path:
    """Take the drill's backup into a fresh scratch path and return it."""
    scratch = tmp_path / "drill" / "app-backup.db"
    drill.take_backup(database, scratch)
    return scratch


def figures_of(report) -> dict:
    return {figure.label: figure for figure in report.figures}


def test_an_intact_copy_returns_the_same_tables_and_stats(database, tmp_path):
    scratch = backup(database, tmp_path)

    report = drill.compare(database, scratch)

    assert report.ok
    figures = figures_of(report)
    assert tuple(figures) == ROW_FIGURES + STATS_FIGURES
    assert (figures["sys_user"].source, figures["sys_user"].restored) == (2, 2)
    assert (figures["detect_object"].source, figures["detect_object"].restored) == (3, 3)
    assert (figures["detect_task"].source, figures["detect_task"].restored) == (1, 1)
    assert figures[STATS_FIGURES[0]].source == 2
    assert figures[STATS_FIGURES[1]].source == 3
    assert figures[STATS_FIGURES[2]].source == 2
    assert figures[STATS_FIGURES[3]].source == 1
    assert all(figure.restored == figure.source for figure in report.figures)


def test_a_restored_copy_missing_a_row_fails_naming_the_table(database, tmp_path, capsys):
    scratch = backup(database, tmp_path)
    with sqlite3.connect(scratch) as connection:
        connection.execute("DELETE FROM sys_user WHERE username = 'analyst'")
        connection.commit()

    report = drill.compare(database, scratch)
    drill.print_report(report)

    printed = capsys.readouterr().out
    assert not report.ok
    assert [figure.label for figure in report.differences] == ["sys_user"]
    assert (figures_of(report)["sys_user"].source, figures_of(report)["sys_user"].restored) == (
        2,
        1,
    )
    assert "FAIL" in printed
    assert "sys_user: source 2 != restored 1" in printed


def test_a_changed_review_state_fails_the_stats_even_with_the_same_row_counts(database, tmp_path):
    scratch = backup(database, tmp_path)
    with sqlite3.connect(scratch) as connection:
        connection.execute("UPDATE detect_object SET review_status = 3 WHERE object_id = 1")
        connection.commit()

    report = drill.compare(database, scratch)

    assert not report.ok
    figures = figures_of(report)
    assert figures["detect_object"].same, "the row count is unchanged; only the API total moves"
    reviewed = figures["/api/stats/species total (reviewed)"]
    assert (reviewed.source, reviewed.restored) == (2, 1)
    assert not reviewed.same
    assert figures["/api/stats/species total (raw)"].same, "raw still counts every box"
    assert (
        figures["/api/stats/corrections total"].source,
        figures["/api/stats/corrections total"].restored,
    ) == (1, 2)


def test_the_drill_does_not_modify_the_source(database, tmp_path):
    before_hash = hashlib.sha256(database.read_bytes()).hexdigest()
    before_mtime = database.stat().st_mtime_ns

    scratch = backup(database, tmp_path)
    drill.compare(database, scratch)

    assert hashlib.sha256(database.read_bytes()).hexdigest() == before_hash
    assert database.stat().st_mtime_ns == before_mtime


def test_the_configured_sqlite_dsn_and_data_root_are_used_by_default(
    database, tmp_path, monkeypatch
):
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("DB_DSN", f"sqlite:///{database.as_posix()}")
    monkeypatch.setenv("AV_DATA_DIR", str(data_root))
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        assert drill.main([]) == 0
    finally:
        get_settings.cache_clear()

    assert (data_root / "drill" / "app-backup.db").is_file()


def test_a_postgresql_deployment_is_reported_as_not_covered(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("DB_DSN", "postgresql://user:secret@db.example/aquavision")

    code = drill.main(["--scratch", str(tmp_path / "scratch.db")])

    assert code == 3
    printed = capsys.readouterr()
    assert "not covered" in printed.err
    assert "PostgreSQL" in printed.err
    assert "secret" not in printed.err, "the configured DSN can carry a password; never echo it"
    assert "PASS" not in printed.out
    assert not (tmp_path / "scratch.db").exists()


def test_an_existing_scratch_copy_is_refused_without_the_force_flag(database, tmp_path, capsys):
    scratch = tmp_path / "drill" / "app-backup.db"
    scratch.parent.mkdir(parents=True)
    scratch.write_bytes(b"occupied")

    refused = drill.main(["--source", str(database), "--scratch", str(scratch)])
    assert refused == 2
    assert "already exists" in capsys.readouterr().err
    assert scratch.read_bytes() == b"occupied"

    accepted = drill.main(["--source", str(database), "--scratch", str(scratch), "--force"])
    printed = capsys.readouterr()
    assert accepted == 0
    assert "PASS" in printed.out
    assert scratch.read_bytes() != b"occupied"
