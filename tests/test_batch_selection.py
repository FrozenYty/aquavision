"""A batch built from the frames the image browser ticked (FR-M3-02, AC-08, P4-05).

AC-08's drill-down ends where the operator's selection must become a job: the image browser sends
`frame_ids`, but the batch body had nowhere to put them, so Pydantic dropped the list and
`create_batch` took the first N eligible frames instead of the ticked ones. The route now reads the
selection, applies the same queue rules the automatic form applies, and refuses the whole request
when one ticked frame cannot be queued - a silently shrunk selection would run a different job than
the operator confirmed.

Sessions are opened directly, as in `tests/test_batch_quality.py`: the point is the selection, not
the HTTP envelope. The fixture gives each test its own throwaway database.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.db import Base, engine_from_dsn
from app.envelope import BAD_PARAM, ApiError
from app.models import DetectObject, DetectTask, DetectTaskItem, MediaAsset
from app.routers.tasks import BatchBody, create_batch
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def session_factory(tmp_path):
    """A throwaway database, disposed when the test ends."""
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'selection.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


def frame(index: int, quality_flag: int, now: datetime) -> MediaAsset:
    """One captured frame; a refused one carries the quality gate's own marks."""
    return MediaAsset(
        frame_id=f"20261127T0900{index:02d}-{index:04d}",
        session_id="s-selection",
        point_code="A3",
        file_path=f"frames/selection-{index}.jpg",
        file_size=1024,
        file_hash=f"{index:064d}",
        captured_at=now,
        width=640,
        height=480,
        quality_score=30 if quality_flag else 85,
        quality_flag=quality_flag,
        is_retake=quality_flag,
    )


def work_list(db, task_id: int) -> list[int]:
    """The task's frames in the order a worker claims them (`item_id`, ADR 12)."""
    return list(
        db.scalars(
            select(DetectTaskItem.asset_id)
            .where(DetectTaskItem.task_id == task_id)
            .order_by(DetectTaskItem.item_id)
        ).all()
    )


def queue_counts(db) -> tuple[int, int]:
    """How many tasks and items the database holds, for "nothing was written" assertions."""
    tasks = db.scalar(select(func.count(DetectTask.task_id))) or 0
    items = db.scalar(select(func.count(DetectTaskItem.item_id))) or 0
    return tasks, items


def earlier_task(db) -> int:
    """A task row for the item or box a test needs to look owned or already detected."""
    row = DetectTask(task_code="DT261127-900", task_type=2, asset_count=1, status=0)
    db.add(row)
    db.flush()
    return row.task_id


def test_the_ticked_frames_become_the_task_work_list(session_factory):
    """The browser sends `frame_ids`; the job must hold exactly those frames, in their order."""
    now = datetime.now(UTC).replace(tzinfo=None)
    with session_factory() as db:
        frames = [frame(index, 0, now) for index in range(5)]
        db.add_all(frames)
        db.commit()

        ticked = [frames[2], frames[4]]
        # api.js sends both keys: asset_count is the count, frame_ids is the selection.
        task = create_batch(
            db, BatchBody(asset_count=2, frame_ids=[row.frame_id for row in ticked])
        )

        assert task.asset_count == len(ticked), "the recorded count is the number assigned"
        assert work_list(db, task.task_id) == [row.asset_id for row in ticked], (
            "the batch took frames other than the ticked ones"
        )


def test_a_selection_does_not_need_asset_count(session_factory):
    """The list alone is a complete request: the recorded count follows from it."""
    now = datetime.now(UTC).replace(tzinfo=None)
    with session_factory() as db:
        frames = [frame(index, 0, now) for index in range(5)]
        db.add_all(frames)
        db.commit()

        ticked = [frames[3], frames[1]]
        task = create_batch(db, BatchBody(frame_ids=[row.frame_id for row in ticked]))

        assert task.asset_count == 2
        assert work_list(db, task.task_id) == [row.asset_id for row in ticked], (
            "the work list did not follow the ticked order"
        )


def test_an_empty_selection_is_refused(session_factory):
    """An empty list is a request with nothing in it, not an automatic batch."""
    now = datetime.now(UTC).replace(tzinfo=None)
    with session_factory() as db:
        db.add(frame(0, 0, now))
        db.commit()

        with pytest.raises(ApiError) as caught:
            create_batch(db, BatchBody(frame_ids=[]))

        assert caught.value.code == BAD_PARAM
        assert "至少" in caught.value.message
        assert queue_counts(db) == (0, 0), "a refused request created a task anyway"


def test_duplicate_ticked_frames_are_assigned_once(session_factory):
    """A frame ticked twice is still one frame; the recorded count is the distinct count."""
    now = datetime.now(UTC).replace(tzinfo=None)
    with session_factory() as db:
        frames = [frame(index, 0, now) for index in range(3)]
        db.add_all(frames)
        db.commit()

        ids = [frames[1].frame_id, frames[2].frame_id, frames[1].frame_id]
        task = create_batch(db, BatchBody(asset_count=len(ids), frame_ids=ids))

        assert task.asset_count == 2, "the recorded count is the number of distinct frames"
        assert work_list(db, task.task_id) == [frames[1].asset_id, frames[2].asset_id], (
            "a duplicate tick was assigned twice"
        )


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("refused", "画质"),
        ("unknown", "不存在"),
        ("detected", "识别结果"),
        ("owned", "占用"),
    ],
)
def test_one_ineligible_frame_refuses_the_whole_selection(session_factory, case, reason):
    """Not dropped and not partly honoured: a tick the queue cannot take refuses the request."""
    now = datetime.now(UTC).replace(tzinfo=None)
    with session_factory() as db:
        accepted = frame(0, 0, now)
        ineligible = frame(1, 1 if case == "refused" else 0, now)
        db.add_all([accepted, ineligible])
        db.commit()

        if case == "unknown":
            bad_id = "20261127T099999-9999"
        else:
            bad_id = ineligible.frame_id
            if case == "detected":
                db.add(
                    DetectObject(
                        task_id=earlier_task(db),
                        asset_id=ineligible.asset_id,
                        frame_id=bad_id,
                        class_code="holothurian",
                        confidence=0.9,
                        x=0.1,
                        y=0.1,
                        w=0.1,
                        h=0.1,
                    )
                )
                db.commit()
            if case == "owned":
                db.add(
                    DetectTaskItem(task_id=earlier_task(db), asset_id=ineligible.asset_id, state=0)
                )
                db.commit()

        before = queue_counts(db)
        with pytest.raises(ApiError) as caught:
            create_batch(db, BatchBody(asset_count=2, frame_ids=[accepted.frame_id, bad_id]))

        assert caught.value.code == BAD_PARAM
        assert reason in caught.value.message, caught.value.message
        assert queue_counts(db) == before, "a refused selection still wrote a task or an item"


def test_the_automatic_form_still_takes_accepted_frames(session_factory):
    """Absent a selection, the route keeps taking the first N eligible frames by id."""
    now = datetime.now(UTC).replace(tzinfo=None)
    with session_factory() as db:
        accepted = [frame(index, 0, now) for index in range(3)]
        refused = [frame(10 + index, 1, now) for index in range(2)]
        db.add_all(accepted + refused)
        db.commit()

        task = create_batch(db, BatchBody(asset_count=2))

        assert task.asset_count == 2, "the automatic form records the requested size"
        assert work_list(db, task.task_id) == [accepted[0].asset_id, accepted[1].asset_id]
