"""Submitting a review, its version history and rollback (FR-M4-01, FR-M4-02, AC-15, AC-16, AC-17).

The request carries the **whole corrected set**, not a diff: the canvas is the authority, and a diff
would have to be merged against a version that may have moved on since it was read.

Every submission writes:
- the boxes, with `is_manual` and `review_status` set;
- a `sys_log` row holding the previous and the current set, so AC-04 can be answered and so the
  version timeline has something to read (FR-M4-02);
- `hard_flag` on anything that changed, which is what puts the frame in the pool (AC-17).

Rollback replays one of those stored sets as a new version. Nothing is deleted: a box leaving the set
becomes `review_status = 3` and stays in the table, because the record of the correction is the
training signal (AC-15).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import serializers
from app.deps import SessionDep, UserDep, get_current_user, require
from app.envelope import CONFLICT, NOT_FOUND, ApiError, ok
from app.models import DetectObject, MediaAsset, SysLog, SysUser

router = APIRouter(prefix="/api/review", tags=["review"], dependencies=[Depends(get_current_user)])

#: The roles that may change a frame's boxes (SRS Table 3-17). Reading the history is open to every
#: signed-in user; only the two routes that write are guarded.
REVIEW_ROLES = ("analyst", "algo", "admin")


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


class RollbackBody(BaseModel):
    log_id: int


@router.post("/frames/{frame_id}", dependencies=[Depends(require(*REVIEW_ROLES))])
def submit(frame_id: str, body: ReviewBody, db: SessionDep, user: UserDep) -> dict[str, object]:
    asset = _asset(db, frame_id)
    current = _current_boxes(db, frame_id)
    before = [serializers.box(row) for row in current]
    version, rejected, added = _apply_boxes(
        db, asset, frame_id, current, [box.model_dump() for box in body.objects], user
    )

    after_rows = _flush_and_read(db, frame_id)
    after = [serializers.box(row) for row in after_rows if row.review_status != 3]
    _log(db, user, frame_id, "submit", before, after)
    db.commit()

    hard = any(row.hard_flag == 1 for row in after_rows)
    return ok(
        {
            "frame_id": frame_id,
            "version_no": version,
            "object_count": len(after),
            "hard_sample": hard,
            "rejected": rejected,
            "added": added,
            "note": body.note,
        }
    )


@router.get("/frames/{frame_id}/versions")
def list_versions(frame_id: str, db: SessionDep) -> dict[str, object]:
    """The frame's review timeline, newest first, read from the stored before/after lists.

    The counts come from the JSON that each submission wrote, not from the current boxes: an entry has
    to describe what happened then, even after later reviews changed the frame. `before_count` counts
    every box stored at that moment - including boxes already rejected earlier, which is what the
    submission recorded - and `after_count` counts only the set that was accepted.
    """
    _asset(db, frame_id)
    logs = db.scalars(
        select(SysLog)
        .where(
            SysLog.module == "review",
            SysLog.action.in_(("submit", "rollback")),
            SysLog.target_type == "media_asset",
            SysLog.target_id == frame_id,
        )
        .order_by(SysLog.log_id.desc())
    ).all()
    authors = _author_names(db, {row.user_id for row in logs})
    items = [
        {
            "log_id": row.log_id,
            "action": row.action,
            "created_at": serializers.iso(row.created_at),
            "author": authors.get(row.user_id) if row.user_id is not None else None,
            "before_count": _stored_count(row.before_value),
            "after_count": _stored_count(row.after_value),
        }
        for row in logs
    ]
    return ok({"frame_id": frame_id, "items": items})


@router.post("/frames/{frame_id}/rollback", dependencies=[Depends(require(*REVIEW_ROLES))])
def rollback(frame_id: str, body: RollbackBody, db: SessionDep, user: UserDep) -> dict[str, object]:
    """Restore one stored version as a new version; the history is appended to, never rewritten.

    A rollback to the set the frame already has is refused as a no-op: an empty entry in the timeline
    pushes the versions that actually matter out of a reader's attention.
    """
    asset = _asset(db, frame_id)
    log = db.get(SysLog, body.log_id)
    if (
        log is None
        or log.module != "review"
        or log.action not in ("submit", "rollback")
        or log.target_type != "media_asset"
    ):
        raise ApiError(NOT_FOUND, "复核记录不存在")
    if log.target_id != frame_id:
        raise ApiError(CONFLICT, "该复核记录属于另一帧，不能用于回滚")

    target = json.loads(log.after_value) if log.after_value else []
    current = _current_boxes(db, frame_id)
    before = [serializers.box(row) for row in current]
    if _same_box_set(target, [box for box in before if box["review_status"] != 3]):
        raise ApiError(CONFLICT, "该版本与当前结果相同，无需回滚")

    version, rejected, added = _apply_boxes(db, asset, frame_id, current, target, user)

    after_rows = _flush_and_read(db, frame_id)
    after = [serializers.box(row) for row in after_rows if row.review_status != 3]
    _log(db, user, frame_id, "rollback", before, after)
    db.commit()

    hard = any(row.hard_flag == 1 for row in after_rows)
    return ok(
        {
            "log_id": log.log_id,
            "frame_id": frame_id,
            "version_no": version,
            "object_count": len(after),
            "hard_sample": hard,
            "rejected": rejected,
            "added": added,
        }
    )


def _apply_boxes(
    db,
    asset: MediaAsset,
    frame_id: str,
    current: list[DetectObject],
    desired: list[dict[str, Any]],
    user: SysUser,
) -> tuple[int, int, int]:
    """Apply one box set to a frame: reject what left it, restore what is in it, add what is new.

    Shared by submit and rollback so the two paths cannot drift: however a version arrives, the rule
    that turns a box list into rows is the same one. Returns the version this application belongs to,
    the rejected count and the added count, which is what both responses report.
    """
    version = _next_version(current)
    kept = {box["object_id"] for box in desired if box.get("object_id") is not None}
    removed = [row for row in current if row.object_id not in kept]
    for row in removed:
        row.review_status = 3  # rejected, not deleted: the automatic result stays queryable (AC-15)

    by_id = {row.object_id: row for row in current}
    added = 0
    for box in desired:
        target = by_id.get(box.get("object_id")) if box.get("object_id") is not None else None
        if target is None:
            # A box the model missed, one redrawn after rejection, or one this rollback restores.
            target = DetectObject(
                task_id=removed[0].task_id if removed else _task_of(current, frame_id),
                asset_id=asset.asset_id,
                frame_id=frame_id,
                class_code=box["class_code"],
                confidence=box["confidence"],
                x=box["x"],
                y=box["y"],
                w=box["w"],
                h=box["h"],
                is_manual=1,
                review_status=2,
                version_no=version,
            )
            db.add(target)
            added += 1
        else:
            changed = (
                target.class_code != box["class_code"]
                or abs(float(target.x) - float(box["x"])) > 1e-4
                or abs(float(target.y) - float(box["y"])) > 1e-4
            )
            target.class_code = box["class_code"]
            target.confidence = box["confidence"]
            target.x, target.y, target.w, target.h = box["x"], box["y"], box["w"], box["h"]
            target.review_status = 2 if changed else 1

    changed_rows = [row for row in current if row.review_status == 2 or row.object_id not in kept]
    for row in changed_rows:
        row.hard_flag = 1
        row.hard_reason = row.hard_reason or "modified"
        row.reviewed_by = user.user_id
        row.reviewed_at = datetime.now(UTC).replace(tzinfo=None)
    return version, len(removed), added


def _same_box_set(target: list[dict[str, Any]], current: list[dict[str, Any]]) -> bool:
    """Whether two box lists describe the same boxes, order and object ids aside."""
    return sorted(_box_signature(box) for box in target) == sorted(
        _box_signature(box) for box in current
    )


def _box_signature(box: dict[str, Any]) -> tuple[str, float, float, float, float, float]:
    """One box at the precision its columns store, so a round trip through them compares equal."""
    return (
        str(box["class_code"]),
        round(float(box["confidence"]), 4),
        round(float(box["x"]), 5),
        round(float(box["y"]), 5),
        round(float(box["w"]), 5),
        round(float(box["h"]), 5),
    )


def _asset(db, frame_id: str) -> MediaAsset:
    asset = db.scalar(select(MediaAsset).where(MediaAsset.frame_id == frame_id))
    if asset is None:
        raise ApiError(NOT_FOUND, "帧不存在")
    return asset


def _current_boxes(db, frame_id: str) -> list[DetectObject]:
    return list(
        db.scalars(
            select(DetectObject)
            .where(DetectObject.frame_id == frame_id)
            .order_by(DetectObject.object_id)
        )
    )


def _flush_and_read(db, frame_id: str) -> list[DetectObject]:
    db.flush()
    return _current_boxes(db, frame_id)


def _log(
    db, user: SysUser, frame_id: str, action: str, before: list[dict], after: list[dict]
) -> None:
    """Append one history row. `before` is the stored state, `after` the accepted set that follows."""
    db.add(
        SysLog(
            user_id=user.user_id,
            module="review",
            action=action,
            target_type="media_asset",
            target_id=frame_id,
            before_value=json.dumps(before, ensure_ascii=False),
            after_value=json.dumps(after, ensure_ascii=False),
        )
    )


def _stored_count(value: str | None) -> int:
    """How many boxes a stored JSON list holds; the timeline is read from it, not recomputed."""
    return len(json.loads(value)) if value else 0


def _author_names(db, user_ids: set[int | None]) -> dict[int, str]:
    """Resolve the log rows' user ids to readable names in one query, not one per row."""
    ids = {user_id for user_id in user_ids if user_id is not None}
    if not ids:
        return {}
    rows = db.execute(select(SysUser.user_id, SysUser.real_name).where(SysUser.user_id.in_(ids)))
    return {user_id: real_name for user_id, real_name in rows}


def _next_version(rows) -> int:
    return max((row.version_no for row in rows), default=0) + 1


def _task_of(rows, frame_id: str) -> int:
    """Every box belongs to a task; a frame with no boxes yet needs a queued one to attach to."""
    if rows:
        return rows[0].task_id
    raise ApiError(NOT_FOUND, f"帧 {frame_id} 还没有识别结果，无法复核")
