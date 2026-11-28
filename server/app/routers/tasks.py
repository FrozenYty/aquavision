"""Detection tasks: listing, progress, cancel and retry (FR-M3-02, AC-11).

A task row is the queue. `app.worker` claims the rows and walks their frames; this module only reads and
writes the record, its state machine and its guards, because the interface and the review flow both read
them.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update

from app import serializers, timebase
from app.deps import SessionDep, UserDep, get_current_user
from app.envelope import BAD_PARAM, CONFLICT, MISSING_PARAM, NOT_FOUND, ApiError, ok
from app.models import DetectObject, DetectTask, DetectTaskItem, MediaAsset, ModelVersion, SysLog

router = APIRouter(prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(get_current_user)])

#: States in which a task can be cancelled: queued or running.
CANCELLABLE = (0, 1)

#: detect_task_item.state code (data model §3.14). The router only writes `pending`: both creating a
#: task and retrying one mean "this frame has not been run yet".
ITEM_PENDING = 0


class BatchBody(BaseModel):
    """A batch request: a frame count, or the frames the operator ticked.

    `asset_count` is the automatic form - "take this many from the queue". `frame_ids` is the
    selection the image browser sends; it wins when present, and `asset_count` may travel beside it
    as a convenience count that the recorded value does not come from.
    """

    asset_count: int | None = Field(default=None, ge=1, le=5000)
    frame_ids: list[str] | None = None
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
    # A retry is a fresh attempt at the same work: every item goes back to pending and the boxes the
    # failed run produced are dropped. This is deliberately not what a restart does - a restart keeps
    # the finished items (ADR 12), while a retry is the operator asking for the run again.
    db.execute(delete(DetectObject).where(DetectObject.task_id == task_id))
    db.execute(
        update(DetectTaskItem)
        .where(DetectTaskItem.task_id == task_id)
        .values(state=ITEM_PENDING, box_count=0, claimed_at=None, finished_at=None)
    )
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


def next_task_code(db) -> str:
    """`DTyyMMdd-serial` (data model §3.4), shared by the live and the batch entry points.

    The date is the operator's local day (ADR 14), not the UTC day the timestamps are stored under.
    """
    serial = db.scalar(select(func.count(DetectTask.task_id))) or 0
    return f"DT{timebase.now().strftime('%y%m%d')}-{serial + 1:03d}"


def create_batch(db, body: BatchBody) -> DetectTask:
    """Insert a queued batch task and assign the frames it will run (ADR 12).

    The selection happens once, here. A task's work list is fixed at creation and identical for every
    worker, and two forms are accepted: `asset_count` takes that many frames from the queue,
    `frame_ids` takes exactly the frames the operator ticked. Both apply the same queue rules - the
    frame passed the quality gate (AC-07: a defocused frame stays out of the queue), has not been
    detected, and is owned by no other task - because a batch is the queue.

    A ticked selection is all-or-nothing. One frame the queue cannot take refuses the whole request
    with 40002, naming the frame and the reason: dropping it instead would run a different job than
    the one the operator confirmed.
    """
    if body.frame_ids is None:
        if body.asset_count is None:
            raise ApiError(MISSING_PARAM, "asset_count 与 frame_ids 至少需要一个")
        assigned = _automatic_selection(db, body.asset_count)
        recorded = body.asset_count
    else:
        assigned = _selected_frames(db, body.frame_ids)
        recorded = len(assigned)
    online = db.scalar(select(ModelVersion).where(ModelVersion.is_online == 1))
    row = DetectTask(
        task_code=next_task_code(db),
        task_type=2,
        model_version_id=online.model_id if online else None,
        asset_count=recorded,
        conf_thr=body.conf_thr,
        iou_thr=body.iou_thr,
        max_det=body.max_det,
        class_filter=("[" + ",".join(body.class_filter) + "]") if body.class_filter else None,
        status=0,
        progress=0,
    )
    db.add(row)
    db.flush()
    db.add_all(
        DetectTaskItem(task_id=row.task_id, asset_id=asset_id, state=ITEM_PENDING)
        for asset_id in assigned
    )
    db.commit()
    db.refresh(row)
    return row


def _automatic_selection(db, asset_count: int) -> list[int]:
    """The first eligible frames, up to the requested count."""
    return list(
        db.scalars(
            select(MediaAsset.asset_id)
            .where(
                MediaAsset.quality_flag == 0,
                MediaAsset.asset_id.not_in(select(DetectObject.asset_id)),
                MediaAsset.asset_id.not_in(select(DetectTaskItem.asset_id)),
            )
            .order_by(MediaAsset.asset_id)
            .limit(asset_count)
        ).all()
    )


def _selected_frames(db, frame_ids: list[str]) -> list[int]:
    """Resolve the ticked frame ids to asset ids in the ticked order, or refuse the whole list.

    Duplicates describe one frame, and an empty list describes none of them. Every other refusal
    names the frame and why it cannot be queued, so the operator can fix the tick instead of guessing
    which frames the server quietly dropped.
    """
    wanted = list(dict.fromkeys(frame_ids))
    if not wanted:
        raise ApiError(BAD_PARAM, "所选帧为空，请至少选择一帧")
    assets = db.scalars(select(MediaAsset).where(MediaAsset.frame_id.in_(wanted))).all()
    by_frame = {asset.frame_id: asset for asset in assets}
    asset_ids = {asset.asset_id for asset in assets}
    detected: set[int] = set()
    owned: set[int] = set()
    if asset_ids:
        detected = set(
            db.scalars(
                select(DetectObject.asset_id).where(DetectObject.asset_id.in_(asset_ids))
            ).all()
        )
        owned = set(
            db.scalars(
                select(DetectTaskItem.asset_id).where(DetectTaskItem.asset_id.in_(asset_ids))
            ).all()
        )
    problems: list[str] = []
    for frame_id in wanted:
        asset = by_frame.get(frame_id)
        if asset is None:
            problems.append(f"帧 {frame_id} 不存在")
        elif asset.quality_flag == 1:
            problems.append(f"帧 {frame_id} 画质不合格，已被质量门禁拒绝")
        elif asset.asset_id in detected:
            problems.append(f"帧 {frame_id} 已有识别结果")
        elif asset.asset_id in owned:
            problems.append(f"帧 {frame_id} 已被其他任务占用")
    if problems:
        raise ApiError(BAD_PARAM, "无法按所选帧创建任务：" + "；".join(problems))
    return [by_frame[frame_id].asset_id for frame_id in wanted]


def _task(db, task_id: int) -> DetectTask:
    row = db.get(DetectTask, task_id)
    if row is None:
        raise ApiError(NOT_FOUND, "任务不存在")
    return row


# Re-exported for the batch router; importing back would make a cycle.
__all__ = ["router", "create_batch", "BatchBody"]
