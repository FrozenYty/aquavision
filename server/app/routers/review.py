"""Submitting a review (FR-M4-01, AC-15, AC-16, AC-17).

The request carries the **whole corrected set**, not a diff: the canvas is the authority, and a diff
would have to be merged against a version that may have moved on since it was read.

Every submission writes:
- the boxes, with `is_manual` and `review_status` set;
- a `sys_log` row holding the previous and the current set, so AC-04 can be answered;
- `hard_flag` on anything that changed, which is what puts the frame in the pool (AC-17).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import serializers
from app.deps import SessionDep, UserDep, get_current_user, require
from app.envelope import NOT_FOUND, ApiError, ok
from app.models import DetectObject, MediaAsset, SysLog

router = APIRouter(prefix="/api/review", tags=["review"], dependencies=[Depends(get_current_user)])


class BoxBody(BaseModel):
    object_id: int | None = None
    class_code: str
    confidence: float = Field(ge=0.0, le=1.0)
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)


class ReviewBody(BaseModel):
    objects: list[BoxBody]
    note: str | None = Field(default=None, max_length=255)


@router.post("/frames/{frame_id}", dependencies=[Depends(require("analyst", "algo", "admin"))])
def submit(frame_id: str, body: ReviewBody, db: SessionDep, user: UserDep) -> dict[str, object]:
    asset = db.scalar(select(MediaAsset).where(MediaAsset.frame_id == frame_id))
    if asset is None:
        raise ApiError(NOT_FOUND, "帧不存在")

    current = db.scalars(
        select(DetectObject)
        .where(DetectObject.frame_id == frame_id)
        .order_by(DetectObject.object_id)
    ).all()
    before = [serializers.box(row) for row in current]

    kept = {box.object_id for box in body.objects if box.object_id is not None}
    removed = [row for row in current if row.object_id not in kept]
    for row in removed:
        row.review_status = 3  # rejected, not deleted: the automatic result stays queryable (AC-15)

    by_id = {row.object_id: row for row in current}
    added = 0
    for box in body.objects:
        target = by_id.get(box.object_id) if box.object_id is not None else None
        if target is None:
            # A box the model missed, or one that was rejected earlier and is now redrawn.
            target = DetectObject(
                task_id=removed[0].task_id if removed else _task_of(current, frame_id),
                asset_id=asset.asset_id,
                frame_id=frame_id,
                class_code=box.class_code,
                confidence=box.confidence,
                x=box.x,
                y=box.y,
                w=box.w,
                h=box.h,
                is_manual=1,
                review_status=2,
                version_no=_next_version(current),
            )
            db.add(target)
            added += 1
        else:
            changed = (
                target.class_code != box.class_code
                or abs(float(target.x) - box.x) > 1e-4
                or abs(float(target.y) - box.y) > 1e-4
            )
            target.class_code = box.class_code
            target.confidence = box.confidence
            target.x, target.y, target.w, target.h = box.x, box.y, box.w, box.h
            target.review_status = 2 if changed else 1

    changed_rows = [row for row in current if row.review_status == 2 or row.object_id not in kept]
    for row in changed_rows:
        row.hard_flag = 1
        row.hard_reason = row.hard_reason or "modified"
        row.reviewed_by = user.user_id
        row.reviewed_at = datetime.now(UTC).replace(tzinfo=None)

    db.flush()
    after_rows = db.scalars(
        select(DetectObject)
        .where(DetectObject.frame_id == frame_id)
        .order_by(DetectObject.object_id)
    ).all()
    after = [serializers.box(row) for row in after_rows if row.review_status != 3]

    version = _next_version(current)
    db.add(
        SysLog(
            user_id=user.user_id,
            module="review",
            action="submit",
            target_type="media_asset",
            target_id=frame_id,
            before_value=json.dumps(before, ensure_ascii=False),
            after_value=json.dumps(after, ensure_ascii=False),
        )
    )
    db.commit()

    hard = any(row.hard_flag == 1 for row in after_rows)
    return ok(
        {
            "frame_id": frame_id,
            "version_no": version,
            "object_count": len(after),
            "hard_sample": hard,
            "rejected": len(removed),
            "added": added,
            "note": body.note,
        }
    )


def _next_version(rows) -> int:
    return max((row.version_no for row in rows), default=0) + 1


def _task_of(rows, frame_id: str) -> int:
    """Every box belongs to a task; a frame with no boxes yet needs a queued one to attach to."""
    if rows:
        return rows[0].task_id
    raise ApiError(NOT_FOUND, f"帧 {frame_id} 还没有识别结果，无法复核")
