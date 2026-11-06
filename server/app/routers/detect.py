"""Detection entry points (FR-M3-01, FR-M3-02).

Single-frame detection returns 501: there is no weight file yet, and inventing boxes would be worse
than saying so — the frontend would build against fiction. The batch endpoint is real, because the
queue it writes to is real; it refuses to create a task when there is nothing to run on, since an
entry that can never start reads as pending work on the dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app import serializers
from app.deps import SessionDep, get_current_user
from app.envelope import not_built, ok
from app.models import MediaAsset
from app.routers.tasks import BatchBody, create_batch

router = APIRouter(prefix="/api/detect", tags=["detect"], dependencies=[Depends(get_current_user)])


@router.post("/frames/{frame_id}")
def detect_frame(frame_id: str) -> dict[str, object]:
    raise not_built(f"单帧识别 {frame_id}（等待模型权重）")


@router.post("/batches")
def start_batch(body: BatchBody, db: SessionDep) -> dict[str, object]:
    if (db.scalar(select(func.count(MediaAsset.asset_id))) or 0) == 0:
        raise not_built("批量识别（还没有可识别的帧）")
    return ok(serializers.task(create_batch(db, body)))
