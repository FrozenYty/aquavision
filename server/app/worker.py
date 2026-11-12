"""The detection queue consumer (P2-05a, FR-M3-02, AC-11).

The task row is the queue. A worker claims a queued task, walks the frames the task owns - its
`detect_task_item` rows, written when the task was created (ADR 12) - and records each frame's outcome
on its item row. Cancellation is a row state, not an in-memory flag, so a cancel from the API is seen
before the next frame; a restart leaves nothing behind because every task and every frame it owns is a
row.

The detector is injected. P2-05b supplies the real one, which the app loads at start-up; when it
could not be loaded the task fails with that same reason rather than inventing boxes.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.models import DetectObject, DetectTask, DetectTaskItem, MediaAsset

log = logging.getLogger("aquavision.worker")

Detector = Callable[[MediaAsset], list[dict[str, Any]]]
ProgressHook = Callable[[int], None]

QUEUED = 0
RUNNING = 1
DONE = 2
FAILED = 3
CANCELLED = 4

#: detect_task_item.state codes (data model §3.14). This module only moves an item forward; putting
#: one back to pending is the router's job (create_batch and retry_task).
ITEM_PENDING = 0
ITEM_RUNNING = 1
ITEM_DONE = 2
ITEM_FAILED = 3

NO_DETECTOR = "模型权重未注册，无法识别"


def requeue_stale(session_factory: sessionmaker) -> int:
    """Put tasks left running by a crash back in the queue, keeping the frames already finished.

    One process owns the queue; a row still marked running at start-up has no worker behind it. An
    item still running is work that was interrupted and returns to pending; a done item keeps its
    boxes, so the resumed task continues instead of reprocessing what it already has (ADR 12).
    """
    with session_factory() as session:
        rows = list(session.scalars(select(DetectTask).where(DetectTask.status == RUNNING)))
        for row in rows:
            session.execute(
                update(DetectTaskItem)
                .where(
                    DetectTaskItem.task_id == row.task_id,
                    DetectTaskItem.state == ITEM_RUNNING,
                )
                .values(state=ITEM_PENDING, claimed_at=None)
            )
            row.status = QUEUED
            row.error_msg = None
            row.finished_at = None
            _sync_progress(session, row)
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
    reason: str = NO_DETECTOR,
) -> None:
    """Run the frames this task owns to done, failure, or cancellation.

    `detector` is injected so P2-05a can be tested without weights and P2-05b can replace it. With
    no detector the task fails with `reason` — the sentence the loader produced when it could not
    build one; this function never writes a box of its own.
    """
    with session_factory() as session:
        task = session.get(DetectTask, task_id)
        if task is None or task.status not in (QUEUED, RUNNING):
            return
        if detector is None:
            _finish(session, task, FAILED, reason)
            return

        if _item_count(session, task_id) == 0:
            _finish(session, task, DONE, None)
            return

        run = _runner(detector, task)
        task.status = RUNNING
        session.commit()

        while True:
            if should_stop is not None and should_stop():
                return
            # End the read transaction before the detector runs; a cancel from another session must
            # be able to write while this frame is being processed.
            session.refresh(task)
            cancelled = task.status == CANCELLED
            session.commit()
            if cancelled:
                return

            claim = _claim_item(session, task_id)
            if claim is None:
                break
            item_id, asset_id = claim
            asset = session.get(MediaAsset, asset_id)
            # The claim and the frame read are the only open transactions; inference runs with none,
            # for the same reason the read above was ended.
            session.commit()

            try:
                boxes = run(asset)
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
                session.execute(
                    update(DetectTaskItem)
                    .where(DetectTaskItem.item_id == item_id)
                    .values(
                        state=ITEM_DONE,
                        box_count=len(boxes),
                        finished_at=datetime.now(UTC).replace(tzinfo=None),
                    )
                )
                _sync_progress(session, task)
                session.commit()
            except Exception as exc:  # noqa: BLE001 - the reason belongs on the task row
                session.rollback()
                _fail_item(session, item_id)
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
    reason: str = NO_DETECTOR,
) -> bool:
    """Claim and process one task. Returns True when a task was taken."""
    if claim_lock is None:
        task_id = claim_one(session_factory)
    else:
        with claim_lock:
            task_id = claim_one(session_factory)
    if task_id is None:
        return False
    process_task(session_factory, task_id, detector, reason=reason)
    return True


class Worker:
    """A small fixed pool, matching architecture §5: task state is in the database, not in Redis."""

    def __init__(
        self,
        session_factory: sessionmaker,
        workers: int = 2,
        poll_seconds: float = 1.0,
        detector: Detector | None = None,
        unavailable_reason: str | None = None,
    ):
        self._session_factory = session_factory
        self._workers = max(1, workers)
        self._poll_seconds = max(0.05, poll_seconds)
        self._detector = detector
        self._unavailable_reason = unavailable_reason or NO_DETECTOR
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

    @property
    def alive(self) -> bool:
        """Whether any pool thread is still running; a stopped or killed pool answers False.

        This is the process-side fact `/api/monitor` reports: when no thread is alive, a task row that
        still says running has nothing behind it, and the operator is told so instead of watching a
        progress bar that will never move.
        """
        return any(thread.is_alive() for thread in self._threads)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                worked = run_once(
                    self._session_factory,
                    detector=self._detector,
                    claim_lock=self._claim_lock,
                    reason=self._unavailable_reason,
                )
            except Exception:  # noqa: BLE001 - one bad task must not kill the pool
                log.exception("detect worker iteration failed")
                worked = False
            if not worked:
                self._stop.wait(self._poll_seconds)


def _runner(detector: Detector, task: DetectTask) -> Detector:
    """Bind the task's own inference parameters when the detector accepts them.

    A test injects a plain callable and gets it back unchanged; the real `Detector` gets the row's
    `conf_thr`, `iou_thr` and `max_det`, so a batch task means what its row says instead of silently
    running at the module defaults.
    """
    predict = getattr(detector, "predict", None)
    if callable(predict):
        return partial(
            predict,
            conf_thr=float(task.conf_thr),
            iou_thr=float(task.iou_thr),
            max_det=int(task.max_det),
        )
    return detector


def _item_count(session: Session, task_id: int) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(DetectTaskItem)
            .where(DetectTaskItem.task_id == task_id)
        )
        or 0
    )


def _claim_item(session: Session, task_id: int) -> tuple[int, int] | None:
    """Take the next pending item, or None when the task has no work left.

    Compare-and-swap rather than a held lock: two workers may read the same pending row, and only an
    update that still sees `pending` may run it. A zero row count means another worker won, so this
    takes the next one - and no lock is held across inference.
    """
    while True:
        candidate = session.execute(
            select(DetectTaskItem.item_id, DetectTaskItem.asset_id)
            .where(DetectTaskItem.task_id == task_id, DetectTaskItem.state == ITEM_PENDING)
            .order_by(DetectTaskItem.item_id)
            .limit(1)
        ).first()
        if candidate is None:
            return None
        item_id, asset_id = candidate
        claimed = session.execute(
            update(DetectTaskItem)
            .where(DetectTaskItem.item_id == item_id, DetectTaskItem.state == ITEM_PENDING)
            .values(state=ITEM_RUNNING, claimed_at=datetime.now(UTC).replace(tzinfo=None))
        )
        session.commit()
        if claimed.rowcount:
            return int(item_id), int(asset_id)


def _fail_item(session: Session, item_id: int) -> None:
    """Mark the item this worker was running as failed; a retry puts it back to pending."""
    session.execute(
        update(DetectTaskItem)
        .where(DetectTaskItem.item_id == item_id)
        .values(state=ITEM_FAILED, finished_at=datetime.now(UTC).replace(tzinfo=None))
    )


def _sync_progress(session: Session, task: DetectTask) -> None:
    """Set progress and obj_count from the task's own items, never from whatever boxes exist.

    `detect_object` cannot answer either question: a frame the model found nothing in produced no row.
    The items can, because a done item is a finished frame whether or not it contains anything.
    """
    total = _item_count(session, task.task_id)
    finished, boxes = session.execute(
        select(
            func.count(DetectTaskItem.item_id),
            func.coalesce(func.sum(DetectTaskItem.box_count), 0),
        ).where(DetectTaskItem.task_id == task.task_id, DetectTaskItem.state == ITEM_DONE)
    ).one()
    task.progress = int(finished * 100 / total) if total else 0
    task.obj_count = int(boxes)


def _finish(session: Session, task: DetectTask, status: int, reason: str | None) -> None:
    task.status = status
    task.error_msg = reason[:512] if reason else None
    task.finished_at = datetime.now(UTC).replace(tzinfo=None)
    if status == DONE:
        task.progress = 100
    session.commit()
