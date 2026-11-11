"""Detection entry points (FR-M3-01, FR-M3-02, P2-05b).

Single-frame detection runs the model that `app.state.detector` holds — the online `model_version`
row, loaded once at start-up — writes `detect_object` through the same statement the queue uses, and
answers with the boxes, the model version and a measured latency.

Two failures are stated rather than papered over. A frame that never came through capture has no
`media_asset` row and is refused with 404 (AC-10); when no usable weight exists the route answers 501
with the sentence `load_online` produced. Neither path invents a box.

The batch endpoint is the queue: it writes a task row the worker picks up with the same detector.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import delete, func, select

from app import serializers
from app.deps import SessionDep, UserDep, get_current_user
from app.detector import IOU_THRESHOLD, MAX_DET
from app.envelope import INTERNAL, NOT_FOUND, NOT_IMPLEMENTED, ApiError, not_built, ok
from app.models import DetectObject, DetectTask, MediaAsset
from app.routers.tasks import BatchBody, create_batch, next_task_code

router = APIRouter(prefix="/api/detect", tags=["detect"], dependencies=[Depends(get_current_user)])

#: detect_task status codes (data model §3.4).
DONE = 2
FAILED = 3


@router.post("/frames/{frame_id}")
def detect_frame(
    frame_id: str,
    request: Request,
    db: SessionDep,
    user: UserDep,
    conf_thr: float = Query(default=0.5, ge=0.0, le=1.0),
) -> dict[str, object]:
    asset = db.scalar(select(MediaAsset).where(MediaAsset.frame_id == frame_id))
    if asset is None:
        # AC-10: the guard belongs in the handler, so no caller reaches inference with an id that
        # was never captured.
        raise ApiError(NOT_FOUND, f"帧 {frame_id} 不存在或未经采集入库")

    detector = getattr(request.app.state, "detector", None)
    if detector is None:
        reason = getattr(request.app.state, "detector_error", None) or "在线模型权重未注册"
        raise ApiError(NOT_IMPLEMENTED, f"单帧识别不可用：{reason}")

    task = DetectTask(
        task_code=next_task_code(db),
        task_type=1,  # live
        model_version_id=detector.model_version_id,
        asset_count=1,
        conf_thr=conf_thr,
        iou_thr=IOU_THRESHOLD,
        max_det=MAX_DET,
        status=1,  # running
        progress=0,
        obj_count=0,
        created_by=user.user_id,
    )
    db.add(task)
    db.flush()

    # Contract §8 defines latency as capture-to-result for the live socket, where the capture happens
    # in the same call. Here the frame is already on disk, so the measurement covers what this route
    # actually does with it: handing the image to the model, pre-processing, inference and NMS. The
    # database writes and the JSON encoding that follow are outside it.
    started = time.perf_counter()
    try:
        boxes = detector.predict(asset, conf_thr)
    except Exception as exc:  # noqa: BLE001 - the reason goes into the response and the task row
        task.status = FAILED
        task.error_msg = f"{type(exc).__name__}: {exc}"[:512]
        task.finished_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()
        raise ApiError(INTERNAL, f"识别失败：{exc}") from exc
    latency_ms = round((time.perf_counter() - started) * 1000)

    # One automatic result per frame. Re-running detection replaces the previous automatic boxes
    # instead of appending a second set, which every statistic would count twice. Boxes a reviewer
    # drew are kept — the model cannot reproduce them — and a replaced set is still recorded in the
    # `sys_log` row the review submission wrote.
    db.execute(
        delete(DetectObject).where(DetectObject.frame_id == frame_id, DetectObject.is_manual == 0)
    )
    rows = []
    for box in boxes:
        row = DetectObject(
            task_id=task.task_id,
            asset_id=asset.asset_id,
            frame_id=frame_id,
            class_code=str(box["class_code"]),
            confidence=float(box["confidence"]),
            x=float(box["x"]),
            y=float(box["y"]),
            w=float(box["w"]),
            h=float(box["h"]),
            is_manual=0,
            review_status=0,
        )
        db.add(row)
        rows.append(row)

    task.status = DONE
    task.progress = 100
    task.obj_count = len(rows)
    task.finished_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    for row in rows:
        db.refresh(row)

    return ok(
        {
            "frame_id": frame_id,
            "boxes": [serializers.box(row) for row in rows],
            "model_version": detector.version_name,
            "conf_threshold": conf_thr,
            "latency_ms": latency_ms,
            "task_id": task.task_id,
        }
    )


@router.post("/batches")
def start_batch(body: BatchBody, db: SessionDep) -> dict[str, object]:
    if (db.scalar(select(func.count(MediaAsset.asset_id))) or 0) == 0:
        raise not_built("批量识别（还没有可识别的帧）")
    return ok(serializers.task(create_batch(db, body)))
