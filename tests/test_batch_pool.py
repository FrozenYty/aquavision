"""Two workers on two batch tasks must not claim the same frame (P3-01, ADR 12).

The measured defect lived here: `_frames_for` re-evaluated "frames with no `detect_object` row" for
every worker, so two workers that started together both read the same ten frames before either wrote a
box. The detector below holds both workers at their first frame until the second has chosen its work,
which turns that race from occasional into deterministic - without it the test would pass or fail on
thread timing.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime

from app.db import Base, engine_from_dsn
from app.models import DetectObject, DetectTask, MediaAsset
from app.routers.tasks import BatchBody, create_batch
from app.worker import Worker
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

FRAMES = 20
ASSETS_PER_TASK = 10
TASKS = 2
#: Generous enough that a loaded machine does not turn the barrier into a failure.
TIMEOUT = 30.0


def test_two_workers_on_two_tasks_never_share_a_frame(tmp_path):
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'pool.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        now = datetime.now(UTC).replace(tzinfo=None)
        with factory() as session:
            for index in range(FRAMES):
                session.add(
                    MediaAsset(
                        frame_id=f"20261111T100000-{index:04d}",
                        session_id="s-pool",
                        point_code="A3",
                        file_path=f"frames/{index:04d}.jpg",
                        file_size=1024 + index,
                        file_hash=f"{index:064d}",
                        captured_at=now,
                        width=640,
                        height=480,
                        quality_score=80,
                        quality_flag=0,
                        is_retake=0,
                    )
                )
            session.commit()
            task_ids = [
                create_batch(session, BatchBody(asset_count=ASSETS_PER_TASK)).task_id
                for _ in range(TASKS)
            ]

        first_calls = 0
        calls_lock = threading.Lock()
        both_chose = threading.Barrier(TASKS)

        def detector(_asset: MediaAsset) -> list[dict]:
            nonlocal first_calls
            with calls_lock:
                first_calls += 1
                is_first = first_calls <= TASKS
            if is_first:
                both_chose.wait(timeout=TIMEOUT)
            time.sleep(0.005)
            return [
                {
                    "class_code": "holothurian",
                    "confidence": 0.9,
                    "x": 0.1,
                    "y": 0.1,
                    "w": 0.2,
                    "h": 0.2,
                }
            ]

        worker = Worker(factory, workers=TASKS, poll_seconds=0.02, detector=detector)
        worker.start()
        try:
            deadline = time.monotonic() + TIMEOUT
            states: list[int] = []
            while time.monotonic() < deadline:
                with factory() as session:
                    states = [session.get(DetectTask, task_id).status for task_id in task_ids]
                if all(state == 2 for state in states):
                    break
                time.sleep(0.02)
        finally:
            worker.stop()
        assert all(state == 2 for state in states), f"the tasks did not finish: states {states}"

        def assets_of(task_id: int) -> set[int]:
            with factory() as session:
                return set(
                    session.scalars(
                        select(DetectObject.asset_id).where(DetectObject.task_id == task_id)
                    )
                )

        first, second = (assets_of(task_id) for task_id in task_ids)
        with factory() as session:
            every_frame = set(session.scalars(select(MediaAsset.asset_id)))

        overlap = first & second
        assert len(first) == len(second) == ASSETS_PER_TASK
        assert not overlap, f"OVERLAP: {len(overlap)} frame(s) were claimed by both tasks"
        assert first | second == every_frame, "the two tasks together did not cover every frame"
    finally:
        engine.dispose()
