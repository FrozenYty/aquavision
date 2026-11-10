"""The detection queue consumer (P2-05a, FR-M3-02, AC-11).

The task row is the queue. A worker claims a queued task, walks its frames, and advances `progress`
after each one. Cancellation is a row state, not an in-memory flag, so a cancel from the API is seen
before the next frame; a restart leaves nothing behind because every task is a row.

There is no model yet. `process_task` takes a detector callable; the production worker passes none,
which fails the task with a reason instead of inventing boxes. P2-05b supplies the real detector.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import DetectObject, DetectTask, MediaAsset

log = logging.getLogger("aquavision.worker")

Detector = Callable[[MediaAsset], list[dict[str, Any]]]
ProgressHook = Callable[[int], None]

QUEUED = 0
RUNNING = 1
DONE = 2
FAILED = 3
CANCELLED = 4

NO_DETECTOR = "模型权重未注册，无法识别"


def requeue_stale(session_factory: sessionmaker) -> int:
    """Put tasks left running by a crash back in the queue, dropping their partial results.

    One process owns the queue; a row still marked running at start-up has no worker behind it.
    Reprocessing is idempotent because the task row, not memory, is the state.
    """
    with session_factory() as session:
        rows = list(session.scalars(select(DetectTask).where(DetectTask.status == RUNNING)))
        for row in rows:
            session.execute(delete(DetectObject).where(DetectObject.task_id == row.task_id))
            row.status = QUEUED
            row.progress = 0
            row.obj_count = 0
            row.error_msg = None
            row.finished_at = None
        session.commit()
        return len(rows)


def claim_one(session_factory: sessionmaker) -> int | None:
    """Mark one queued task running and return its id, or None when the queue is empty."""
    with session_factory() as session:
        row = session.scalar(
            select(DetectTask)
            .where(DetectTask.status == QUEUED)
            .order_by(DetectTask.task_id)
            .limit(1)
        )
        if row is None:
            return None
        row.status = RUNNING
        session.commit()
        return row.task_id


def process_task(
    session_factory: sessionmaker,
    task_id: int,
    detector: Detector | None = None,
    on_progress: ProgressHook | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> None:
    """Run one task's frames to done, failure, or cancellation.

    `detector` is injected so P2-05a can be tested without weights and P2-05b can replace it. With
    no detector the task fails with a stated reason; this function never writes a box of its own.
    """
    with session_factory() as session:
        task = session.get(DetectTask, task_id)
        if task is None or task.status not in (QUEUED, RUNNING):
            return
        if detector is None:
            _finish(session, task, FAILED, NO_DETECTOR)
            return

        frames = _frames_for(session, task)
        if not frames:
            _finish(session, task, DONE, None)
            return

        task.status = RUNNING
        session.commit()
        total = len(frames)

        for index, asset in enumerate(frames, start=1):
            if should_stop is not None and should_stop():
                return
            # End the read transaction before the detector runs; a cancel from another session must
            # be able to write while this frame is being processed.
            session.refresh(task)
            cancelled = task.status == CANCELLED
            session.commit()
            if cancelled:
                return

            try:
                boxes = detector(asset)
                for box in boxes:
                    session.add(
                        DetectObject(
                            task_id=task.task_id,
                            asset_id=asset.asset_id,
                            frame_id=asset.frame_id,
                            class_code=str(box["class_code"]),
                            confidence=float(box["confidence"]),
                            x=float(box["x"]),
                            y=float(box["y"]),
                            w=float(box["w"]),
                            h=float(box["h"]),
                            is_manual=0,
                            review_status=0,
                        )
                    )
                task.obj_count = (task.obj_count or 0) + len(boxes)
                task.progress = max(task.progress or 0, int(index * 100 / total))
                session.commit()
            except Exception as exc:  # noqa: BLE001 - the reason belongs on the task row
                session.rollback()
                task = session.get(DetectTask, task_id)
                if task is not None and task.status != CANCELLED:
                    _finish(session, task, FAILED, str(exc) or type(exc).__name__)
                return

            if on_progress is not None:
                on_progress(task.progress)

        session.refresh(task)
        if task.status != CANCELLED:
            _finish(session, task, DONE, None)


def run_once(
    session_factory: sessionmaker,
    detector: Detector | None = None,
    claim_lock: threading.Lock | None = None,
) -> bool:
    """Claim and process one task. Returns True when a task was taken."""
    if claim_lock is None:
        task_id = claim_one(session_factory)
    else:
        with claim_lock:
            task_id = claim_one(session_factory)
    if task_id is None:
        return False
    process_task(session_factory, task_id, detector)
    return True


class Worker:
    """A small fixed pool, matching architecture §5: task state is in the database, not in Redis."""

    def __init__(
        self,
        session_factory: sessionmaker,
        workers: int = 2,
        poll_seconds: float = 1.0,
        detector: Detector | None = None,
    ):
        self._session_factory = session_factory
        self._workers = max(1, workers)
        self._poll_seconds = max(0.05, poll_seconds)
        self._detector = detector
        self._stop = threading.Event()
        self._claim_lock = threading.Lock()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        requeue_stale(self._session_factory)
        for index in range(self._workers):
            thread = threading.Thread(target=self._loop, name=f"detect-worker-{index}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                worked = run_once(
                    self._session_factory,
                    detector=self._detector,
                    claim_lock=self._claim_lock,
                )
            except Exception:  # noqa: BLE001 - one bad task must not kill the pool
                log.exception("detect worker iteration failed")
                worked = False
            if not worked:
                self._stop.wait(self._poll_seconds)


def _frames_for(session: Session, task: DetectTask) -> list[MediaAsset]:
    """The frames with no detection rows yet, capped at the task's requested asset count.

    A frame with zero boxes is indistinguishable from an unprocessed one without a join table; the
    data model has none. That is a P2-05b concern, not a reason to invent a marker here.
    """
    done = select(DetectObject.asset_id)
    return list(
        session.scalars(
            select(MediaAsset)
            .where(MediaAsset.asset_id.not_in(done))
            .order_by(MediaAsset.asset_id)
            .limit(task.asset_count)
        )
    )


def _finish(session: Session, task: DetectTask, status: int, reason: str | None) -> None:
    task.status = status
    task.error_msg = reason[:512] if reason else None
    task.finished_at = datetime.now(UTC).replace(tzinfo=None)
    if status == DONE:
        task.progress = 100
    session.commit()
