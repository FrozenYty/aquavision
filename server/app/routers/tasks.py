"""Detection tasks: listing, progress, cancel and retry (FR-M3-02, AC-11).

A task row is the queue. Nothing executes yet — the worker arrives with the model — but the record,
its state machine and its guards are real, because the interface and the review flow both read them.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from app import serializers
from app.deps import SessionDep, UserDep, get_current_user
from app.envelope import CONFLICT, NOT_FOUND, ApiError, ok
from app.models import DetectObject, DetectTask, ModelVersion, SysLog

router = APIRouter(prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(get_current_user)])

#: States in which a task can be cancelled: queued or running.
CANCELLABLE = (0, 1)


class BatchBody(BaseModel):
    asset_count: int = Field(ge=1, le=5000)
    conf_thr: float = Field(default=0.5, ge=0.0, le=1.0)
    iou_thr: float = Field(default=0.45, ge=0.0, le=1.0)
    max_det: int = Field(default=100, ge=1, le=1000)
    class_filter: list[str] | None = None


@router.get("")
def list_tasks(
    db: SessionDep,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=24, ge=1, le=100),
    status: str | None = Query(default=None, pattern="^(queued|running|done|failed|cancelled)$"),
) -> dict[str, object]:
    stmt = select(DetectTask)
    if status:
        code = {v: k for k, v in serializers.TASK_STATUS.items()}[status]
        stmt = stmt.where(DetectTask.status == code)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(DetectTask.task_id.desc()).limit(size).offset((page - 1) * size)
    ).all()
    return ok(
        {
            "items": [serializers.task(row) for row in rows],
            "total": total,
            "page": page,
            "size": size,
        }
    )


@router.get("/{task_id}")
def get_task(task_id: int, db: SessionDep) -> dict[str, object]:
    return ok(serializers.task(_task(db, task_id)))


@router.post("/{task_id}/cancel")
def cancel_task(task_id: int, db: SessionDep, user: UserDep) -> dict[str, object]:
    row = _task(db, task_id)
    if row.status not in CANCELLABLE:
        raise ApiError(CONFLICT, "只有排队中或运行中的任务可以取消")
    row.status = 4
    row.finished_at = datetime.now(UTC).replace(tzinfo=None)
    db.add(
        SysLog(
            user_id=user.user_id,
            module="detect",
            action="cancel",
            target_type="detect_task",
            target_id=str(task_id),
            before_value=str(row.progress),
        )
    )
    db.commit()
    return ok(serializers.task(row))


@router.post("/{task_id}/retry")
def retry_task(task_id: int, db: SessionDep, user: UserDep) -> dict[str, object]:
    """Reset a failed task to queued.

    The same row rather than a new one: the task code and its parameters stay attached to the frame
    set they describe, and the history keeps one line per intent. A new row would make the queue look
    like more work than there is.
    """
    row = _task(db, task_id)
    if row.status != 3:
        raise ApiError(CONFLICT, "只有失败的任务可以重试")
    # A retry reprocesses the same frames, so the previous partial result must not survive it.
    db.execute(delete(DetectObject).where(DetectObject.task_id == task_id))
    row.status = 0
    row.progress = 0
    row.obj_count = 0
    row.error_msg = None
    row.finished_at = None
    db.add(
        SysLog(
            user_id=user.user_id,
            module="detect",
            action="retry",
            target_type="detect_task",
            target_id=str(task_id),
        )
    )
    db.commit()
    return ok(serializers.task(row))


def create_batch(db, body: BatchBody) -> DetectTask:
    """Insert a queued batch task. Shared with `/api/detect/batches`."""
    online = db.scalar(select(ModelVersion).where(ModelVersion.is_online == 1))
    serial = db.scalar(select(func.count(DetectTask.task_id))) or 0
    row = DetectTask(
        task_code=f"DT{datetime.now(UTC):%y%m%d}-{serial + 1:03d}",
        task_type=2,
        model_version_id=online.model_id if online else None,
        asset_count=body.asset_count,
        conf_thr=body.conf_thr,
        iou_thr=body.iou_thr,
        max_det=body.max_det,
        class_filter=("[" + ",".join(body.class_filter) + "]") if body.class_filter else None,
        status=0,
        progress=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _task(db, task_id: int) -> DetectTask:
    row = db.get(DetectTask, task_id)
    if row is None:
        raise ApiError(NOT_FOUND, "任务不存在")
    return row


# Re-exported for the batch router; importing back would make a cycle.
__all__ = ["router", "create_batch", "BatchBody"]
