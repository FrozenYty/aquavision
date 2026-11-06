"""The hard-example pool (FR-M4-03, AC-17).

The pool is not a table: it is the set of frames whose boxes carry `hard_flag`. That keeps one source
of truth — a frame is a hard example because a reviewer changed it, and removing it from the pool is
clearing that flag, not deleting evidence.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app import serializers
from app.deps import SessionDep, UserDep, get_current_user
from app.envelope import NOT_FOUND, ApiError, ok
from app.models import DetectObject, MediaAsset, SysLog

router = APIRouter(
    prefix="/api/hard-samples", tags=["review"], dependencies=[Depends(get_current_user)]
)

#: Why a frame is in the pool, in the order the interface shows them.
REASONS = ("low_conf", "modified", "inconsistent")


@router.get("")
def list_samples(
    db: SessionDep,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=24, ge=1, le=100),
    source: str | None = Query(default=None, pattern="^(low_conf|modified|inconsistent)$"),
) -> dict[str, object]:
    stmt = select(DetectObject.frame_id, DetectObject.hard_reason).where(
        DetectObject.hard_flag == 1,
        DetectObject.review_status != 3,
    )
    if source:
        stmt = stmt.where(DetectObject.hard_reason == source)
    grouped = stmt.group_by(DetectObject.frame_id, DetectObject.hard_reason).subquery()

    total = db.scalar(select(func.count()).select_from(grouped)) or 0
    rows = db.execute(
        select(grouped.c.frame_id, grouped.c.hard_reason)
        .order_by(grouped.c.frame_id.desc())
        .limit(size)
        .offset((page - 1) * size)
    ).all()

    items = []
    for row in rows:
        asset = db.scalar(select(MediaAsset).where(MediaAsset.frame_id == row.frame_id))
        item = serializers.frame(asset) if asset else {"frame_id": row.frame_id}
        item["source"] = row.hard_reason or "modified"
        items.append(item)
    return ok({"items": items, "total": total, "page": page, "size": size})


@router.delete("/{frame_id}")
def remove_sample(frame_id: str, db: SessionDep, user: UserDep) -> dict[str, object]:
    rows = db.scalars(
        select(DetectObject).where(DetectObject.frame_id == frame_id, DetectObject.hard_flag == 1)
    ).all()
    if not rows:
        raise ApiError(NOT_FOUND, "该帧不在难例池中")

    for row in rows:
        row.hard_flag = 0
    db.add(
        SysLog(
            user_id=user.user_id,
            module="review",
            action="hard_sample_remove",
            target_type="media_asset",
            target_id=frame_id,
            before_value=str(len(rows)),
            after_value="0",
        )
    )
    db.commit()
    return ok({"frame_id": frame_id, "removed": len(rows)})
