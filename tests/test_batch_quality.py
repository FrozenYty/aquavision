"""A frame the quality gate refused stays out of a detection batch (AC-07, P4-05).

AC-07's second half is a queue rule, not a display rule: a defocused frame scores below the pass mark
and `quality_flag` is set, and the batch selection must not then pick it up. Before this test the
selection filtered only "already detected" and "already owned by a task", so a refused frame was queued
anyway — the gate's verdict was recorded and ignored.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.db import Base, engine_from_dsn
from app.models import DetectTaskItem, MediaAsset
from app.routers.tasks import BatchBody, create_batch
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker


def frame(index: int, quality_flag: int, now: datetime) -> MediaAsset:
    """One captured frame; a refused one carries the quality gate's own marks."""
    return MediaAsset(
        frame_id=f"20261127T0900{index:02d}-{index:04d}",
        session_id="s-quality",
        point_code="A3",
        file_path=f"frames/quality-{index}.jpg",
        file_size=1024,
        file_hash=f"{index:064d}",
        captured_at=now,
        width=640,
        height=480,
        quality_score=30 if quality_flag else 85,
        quality_flag=quality_flag,
        is_retake=quality_flag,
    )


def test_a_refused_frame_stays_out_of_the_batch(tmp_path):
    """The queue holds the accepted frames only; a batch does not fill itself from retakes."""
    dsn = f"sqlite:///{(tmp_path / 'batch.db').as_posix()}"
    engine = engine_from_dsn(dsn)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    now = datetime.now(UTC).replace(tzinfo=None)
    try:
        with factory() as db:
            accepted = [frame(index, 0, now) for index in range(3)]
            refused = [frame(10 + index, 1, now) for index in range(2)]
            db.add_all(accepted + refused)
            db.commit()

            task = create_batch(db, BatchBody(asset_count=10))

            assigned = set(db.scalars(select(DetectTaskItem.asset_id)).all())
            assert task.asset_count == 10, "the request size is recorded as asked"
            assert assigned == {row.asset_id for row in accepted}, (
                "a batch took frames the quality gate refused"
            )
            assert not assigned & {row.asset_id for row in refused}
    finally:
        engine.dispose()


def test_the_refusal_is_still_marked_after_the_batch(tmp_path):
    """Staying out of the queue does not rewrite the gate's verdict: the frame keeps its marks."""
    dsn = f"sqlite:///{(tmp_path / 'batch.db').as_posix()}"
    engine = engine_from_dsn(dsn)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    now = datetime.now(UTC).replace(tzinfo=None)
    try:
        with factory() as db:
            refused = frame(10, 1, now)
            db.add(refused)
            db.commit()
            keep = refused.asset_id

            create_batch(db, BatchBody(asset_count=10))
            db.expire_all()
            row = db.get(MediaAsset, keep)
            assert row is not None
            assert (row.quality_flag, row.is_retake) == (1, 1)
            assert db.scalar(select(DetectTaskItem.asset_id)) is None
    finally:
        engine.dispose()
