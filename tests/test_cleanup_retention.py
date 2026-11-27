"""Retention cleanup against a temporary data root (P3-08, FR-M2-05, AC-09).

Every test builds its own data root and SQLite database under `tmp_path`; no real frame is touched and
no camera is needed. The assertions are the acceptance sentence itself: after cleanup the references
are null and disk usage falls, while originals survive.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from app.db import Base, engine_from_dsn
from app.models import MediaAsset
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cleanup_retention.py"
SHANGHAI = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=SHANGHAI)
RETENTION_DAYS = 30
ORIGINAL = "frames/A3/20260901/s-a3/frame.jpg"
THUMB = "frames/A3/20260901/s-a3/frame-thumb.jpg"


def load_script():
    """The cleanup command as a module; it is a script, not an installed package."""
    spec = importlib.util.spec_from_file_location("cleanup_retention", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # `dataclass` looks its module up in `sys.modules` while the decorator runs; without this the
    # module is not importable enough for the class bodies.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cleanup_retention = load_script()


@pytest.fixture
def store(tmp_path):
    """A temporary data root, the schema and a session factory over a SQLite file in `tmp_path`."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'app.db').as_posix()}")
    Base.metadata.create_all(engine)
    yield data_root, sessionmaker(bind=engine)
    engine.dispose()


def write_file(root: Path, relative: str, *, age_days: int, now: datetime = NOW) -> Path:
    """Write one file and back-date its mtime, so age is the only variable a test changes."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * 2048)
    stamp = (now - timedelta(days=age_days)).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def add_asset(factory, *, frame_id: str = "20260901T120000-0001", thumb: str | None = THUMB):
    with factory() as session:
        session.add(
            MediaAsset(
                frame_id=frame_id,
                session_id="s-a3",
                point_code="A3",
                file_path=ORIGINAL,
                thumb_path=thumb,
                file_size=2048,
                file_hash=(frame_id + "0" * 64)[:64],
                captured_at=datetime(2026, 9, 1, 4, 0),
                width=640,
                height=480,
                quality_score=80,
                quality_flag=0,
                is_retake=0,
            )
        )
        session.commit()


def stored_thumb(factory) -> str | None:
    with factory() as session:
        return session.scalar(select(MediaAsset.thumb_path))


def run(store, *, apply: bool):
    root, factory = store
    return cleanup_retention.cleanup(root, factory, RETENTION_DAYS, apply=apply, now=NOW)


def test_a_dry_run_reports_the_list_and_changes_nothing(store):
    root, factory = store
    add_asset(factory)
    thumb = write_file(root, THUMB, age_days=40)

    report = run(store, apply=False)

    assert report.dry_run
    assert [relative for relative, _size in report.deleted] == [THUMB]
    assert THUMB in report.nulled
    assert report.freed_bytes == 2048
    assert thumb.is_file(), "a dry run must not delete"
    assert stored_thumb(factory) == THUMB, "a dry run must not null a reference"


def test_apply_deletes_the_thumbnail_and_nulls_the_reference(store):
    root, factory = store
    add_asset(factory)
    write_file(root, ORIGINAL, age_days=40)
    thumb = write_file(root, THUMB, age_days=40)

    report = run(store, apply=True)

    assert not report.dry_run
    assert not thumb.exists()
    assert stored_thumb(factory) is None
    assert (root / ORIGINAL).is_file(), "an original frame is never a cleanup candidate"
    assert report.freed_bytes == 2048


def test_an_intermediate_younger_than_the_retention_period_is_kept(store):
    root, factory = store
    add_asset(factory)
    thumb = write_file(root, THUMB, age_days=2)

    report = run(store, apply=True)

    assert THUMB in report.kept
    assert thumb.is_file()
    assert stored_thumb(factory) == THUMB


def test_a_missing_thumbnail_only_loses_its_reference(store):
    add_asset(store[1])

    report = run(store, apply=True)

    assert report.deleted == []
    assert THUMB in report.nulled
    assert stored_thumb(store[1]) is None


def test_a_reference_outside_the_data_root_is_skipped(store):
    root, factory = store
    add_asset(factory, thumb="../outside.jpg")
    outside = root.parent / "outside.jpg"
    outside.write_bytes(b"x")

    report = run(store, apply=True)

    assert report.skipped
    assert outside.is_file()
    assert stored_thumb(factory) == "../outside.jpg"


def test_live_scratch_is_intermediate_but_a_site_frame_is_not(store):
    root, _factory = store
    scratch = write_file(root, "frames/live/20260901T120000-0001-abcd.jpg", age_days=40)
    site_frame = write_file(root, ORIGINAL, age_days=40)

    report = run(store, apply=True)

    assert not scratch.exists()
    assert site_frame.is_file(), "a frame under a site is an original, not a cleanup candidate"
    assert any(relative.startswith("frames/live/") for relative, _size in report.deleted)


def test_the_command_is_a_dry_run_unless_apply_is_passed(store, monkeypatch, capsys):
    root, factory = store
    add_asset(factory)
    now = datetime.now(SHANGHAI)
    thumb = write_file(root, THUMB, age_days=40, now=now)

    monkeypatch.setenv("DB_DSN", f"sqlite:///{(root.parent / 'app.db').as_posix()}")
    monkeypatch.setenv("AV_DATA_DIR", str(root))
    monkeypatch.setenv("AV_RETENTION_DAYS", str(RETENTION_DAYS))
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        assert cleanup_retention.main(["--retention-days", str(RETENTION_DAYS)]) == 0
        printed = capsys.readouterr().out
        assert "dry run" in printed
        assert "would delete" in printed
        assert thumb.is_file()

        assert cleanup_retention.main(["--apply", "--retention-days", str(RETENTION_DAYS)]) == 0
        assert not thumb.exists()
        assert stored_thumb(factory) is None
    finally:
        get_settings.cache_clear()
