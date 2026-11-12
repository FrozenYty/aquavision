"""Capture: cameras, sessions, frames, and the quality gate (FR-M2-01..04, AC-05, AC-07).

A frame arrives as base64 in JSON rather than multipart, because the only uploader is the capture page
posting one JPEG at a time and JSON costs no extra dependency. The bytes are scored **after encoding**,
the same rule the offline capture module follows: JPEG smoothing changes the Laplacian variance, so a
score taken from the in-memory array would not match the file that is stored.

Deduplication is by SHA-256: the same frame posted twice must not become two rows (AC-05).
"""

from __future__ import annotations

import base64
import binascii
import errno
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app import serializers, timebase
from app.deps import SessionDep, SettingsDep, UserDep, get_current_user
from app.envelope import BAD_PARAM, INTERNAL, NOT_FOUND, ApiError, ok
from app.models import MediaAsset, SysLog
from app.vision.quality import score_frame

router = APIRouter(prefix="/api", tags=["capture"], dependencies=[Depends(get_current_user)])

#: A frame whose capture time is further than this from the server is refused (AC-05).
CAPTURE_SKEW = timedelta(seconds=5)


class FrameBody(BaseModel):
    point_code: str = Field(min_length=1, max_length=32)
    image_b64: str = Field(min_length=16, description="JPEG bytes, base64 encoded")
    captured_at: datetime | None = None
    turbidity_rel: int | None = Field(default=None, ge=0, le=100)


@router.get("/cameras")
def list_cameras(settings: SettingsDep) -> dict[str, object]:
    """Report the local device without claiming one exists.

    The server is assumed to run on the capture machine (architecture §2). When no device opens the
    list is empty — that is the truth, and the interface already has an empty state for it.
    """
    from app.vision.capture import CameraSource, CaptureError

    try:
        source = CameraSource(index=settings.camera_index)
        source.open()
        width, height = source.size
        source.close()
        return ok(
            {
                "items": [
                    {
                        "index": settings.camera_index,
                        "name": f"本地摄像头 {settings.camera_index}",
                        "width": width,
                        "height": height,
                        "available": True,
                    }
                ]
            }
        )
    except CaptureError:
        return ok({"items": []})


@router.post("/capture/sessions")
def open_session(user: UserDep) -> dict[str, object]:
    """A session identifier. Nothing is persisted until a frame arrives, so an abandoned session
    leaves no trace — the alternative is a row per click of a button."""
    session_id = f"s-{uuid.uuid4().hex[:12]}"
    return ok({"session_id": session_id, "opened_at": serializers.iso(datetime.now(UTC))})


@router.get("/capture/sessions")
def list_sessions(
    db: SessionDep,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=24, ge=1, le=100),
) -> dict[str, object]:
    """Sessions are derived from the frames that reference them; there is no session table."""
    total = db.scalar(select(func.count(func.distinct(MediaAsset.session_id)))) or 0
    rows = db.execute(
        select(
            MediaAsset.session_id,
            func.min(MediaAsset.captured_at).label("started_at"),
            func.count(MediaAsset.asset_id).label("frames"),
            func.sum(MediaAsset.is_retake).label("retakes"),
        )
        .group_by(MediaAsset.session_id)
        .order_by(func.min(MediaAsset.captured_at).desc())
        .limit(size)
        .offset((page - 1) * size)
    ).all()
    return ok(
        {
            "items": [
                {
                    "session_id": row.session_id,
                    "started_at": serializers.iso(row.started_at),
                    "frames": row.frames,
                    "retakes": int(row.retakes or 0),
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "size": size,
        }
    )


@router.post("/capture/sessions/{session_id}/frames")
def grab_frame(
    session_id: str,
    body: FrameBody,
    db: SessionDep,
    user: UserDep,
    settings: SettingsDep,
) -> dict[str, object]:
    """Store one frame, score it, and decide whether it may enter the detection queue."""
    raw = _decode(body.image_b64)
    stored = _reencode(raw)
    quality = score_frame(stored)

    captured_at = body.captured_at or datetime.now(UTC)
    if captured_at.tzinfo is not None:
        captured_at = captured_at.astimezone(UTC).replace(tzinfo=None)
    if (
        abs((datetime.now(UTC).replace(tzinfo=None) - captured_at).total_seconds())
        > CAPTURE_SKEW.seconds
    ):
        raise ApiError(BAD_PARAM, "采集时间与服务器相差超过 5 秒，拒绝入库")

    digest = hashlib.sha256(stored).hexdigest()
    existing = db.scalar(select(MediaAsset).where(MediaAsset.file_hash == digest))
    if existing is not None:
        # Idempotent by content: the second post returns the first row instead of duplicating it.
        return ok(serializers.frame(existing), message="同一帧已存在")

    try:
        relative = _write(stored, digest, Path(settings.data_dir), body.point_code, session_id)
    except OSError as err:
        # The frame is not in the database yet, so nothing is left half-stored; the caller is told
        # which resource refused the write and what to do about it.
        raise _storage_error(err) from err
    verdict_ok = quality.score >= settings.quality_threshold
    asset = MediaAsset(
        frame_id=_frame_id(captured_at, digest),
        session_id=session_id,
        point_code=body.point_code,
        file_path=relative,
        file_size=len(stored),
        file_hash=digest,
        captured_at=captured_at,
        width=stored.shape[1],
        height=stored.shape[0],
        quality_score=int(quality.score),
        quality_flag=0 if verdict_ok else 1,
        is_retake=0,
        turbidity_rel=body.turbidity_rel,
    )
    db.add(asset)
    db.add(
        SysLog(
            user_id=user.user_id,
            module="capture",
            action="frame",
            target_type="media_asset",
            target_id=asset.frame_id,
            after_value=str(int(quality.score)),
        )
    )
    db.commit()
    db.refresh(asset)

    payload = serializers.frame(asset)
    # Components are returned here, not stored: the data model keeps the score and the flag only.
    payload["quality_components"] = {
        "sharpness": round(quality.sharpness, 2),
        "brightness": round(quality.brightness, 2),
        "colorcast": round(quality.colorcast, 2),
    }
    payload["queued"] = verdict_ok
    return ok(payload)


@router.post("/capture/sessions/{session_id}/close")
def close_session(session_id: str, db: SessionDep) -> dict[str, object]:
    frames = db.scalar(
        select(func.count(MediaAsset.asset_id)).where(MediaAsset.session_id == session_id)
    )
    if not frames:
        raise ApiError(NOT_FOUND, "采集会话不存在或没有任何帧")
    return ok({"session_id": session_id, "frames": frames, "closed": True})


@router.get("/frames")
def list_frames(
    db: SessionDep,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=24, ge=1, le=100),
    session: str | None = None,
    site: str | None = None,
    quality: str | None = Query(default=None, pattern="^(ok|retake)$"),
    start: str | None = None,
    end: str | None = None,
) -> dict[str, object]:
    stmt = select(MediaAsset)
    if session:
        stmt = stmt.where(MediaAsset.session_id == session)
    if site:
        stmt = stmt.where(MediaAsset.point_code == site)
    if quality:
        stmt = stmt.where(MediaAsset.quality_flag == (0 if quality == "ok" else 1))
    # ADR 14: a day means the operator's day in the configured zone, not the UTC day the column holds.
    try:
        start_at, end_at = timebase.day_bounds(start, end)
    except ValueError as err:
        raise ApiError(BAD_PARAM, f"日期格式应为 YYYY-MM-DD：{err}") from err
    if start_at is not None:
        stmt = stmt.where(MediaAsset.captured_at >= start_at)
    if end_at is not None:
        stmt = stmt.where(MediaAsset.captured_at < end_at)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(MediaAsset.captured_at.desc()).limit(size).offset((page - 1) * size)
    ).all()
    return ok(
        {
            "items": [serializers.frame(row) for row in rows],
            "total": total,
            "page": page,
            "size": size,
        }
    )


@router.get("/frames/{frame_id}")
def get_frame(frame_id: str, db: SessionDep) -> dict[str, object]:
    return ok(serializers.frame(_asset(db, frame_id)))


@router.get("/frames/{frame_id}/objects")
def get_objects(frame_id: str, db: SessionDep, class_code: str | None = None) -> dict[str, object]:
    from app.models import DetectObject

    _asset(db, frame_id)
    stmt = select(DetectObject).where(DetectObject.frame_id == frame_id)
    if class_code:
        stmt = stmt.where(DetectObject.class_code == class_code)
    rows = db.scalars(stmt.order_by(DetectObject.object_id)).all()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.class_code] = counts.get(row.class_code, 0) + 1
    return ok({"items": [serializers.box(row) for row in rows], "counts": counts})


def _asset(db, frame_id: str) -> MediaAsset:
    row = db.scalar(select(MediaAsset).where(MediaAsset.frame_id == frame_id))
    if row is None:
        raise ApiError(NOT_FOUND, "帧不存在")
    return row


def _decode(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as err:
        raise ApiError(BAD_PARAM, "图像数据不是合法的 base64") from err


def _reencode(raw: bytes) -> np.ndarray:
    """Decode and re-encode once, so the bytes scored are the bytes stored."""
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ApiError(BAD_PARAM, "无法解码图像")
    ok, buffer = cv2.imencode(".jpg", image)
    if not ok:
        raise ApiError(BAD_PARAM, "无法重新编码图像")
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def _storage_error(err: OSError) -> ApiError:
    """The operator's sentence for a frame that could not be written, and the action that fixes it.

    The reason is kept rather than flattened into the generic 500: "disk full" and "the data directory
    is not writable" are different chores, and neither is fixed by retrying the same click.
    """
    if err.errno == errno.ENOSPC:
        problem = "磁盘空间不足"
        action = "请清理磁盘空间，或把 AV_DATA_DIR 换到有空间的目录"
    elif err.errno in (errno.EACCES, errno.EPERM, errno.EROFS):
        problem = "数据目录不可写"
        action = "请检查 AV_DATA_DIR 指向的目录权限"
    else:
        problem = "数据目录写入失败"
        action = "请检查 AV_DATA_DIR 是否存在、磁盘是否已满"
    return ApiError(
        INTERNAL,
        f"帧图像未能保存（{problem}），这一帧没有入库。{action}，然后重新采集这一帧。",
    )


def _write(stored: np.ndarray, digest: str, root: Path, site: str, session: str) -> str:
    """Write one frame where the data model says frames live.

    `data/frames/<site>/<YYYYMMDD>/<session>/<frame_id>` - the same layout `vision/capture.py` writes. This
    function used to drop the site and the session and file everything under the day, which made the stored
    path disagree with `docs/data-model-en.md` §5 and put thousands of frames from different sessions in one
    folder.

    OpenCV reports a write it could not finish by returning ``False``, not by raising. That must fail
    here too: a row pointing at a file that was never written is worse than a refused capture.
    """
    day = datetime.now(UTC).strftime("%Y%m%d")
    folder = root / "frames" / site / day / session
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{digest[:16]}.jpg"
    if not cv2.imwrite(str(path), stored):
        path.unlink(missing_ok=True)
        raise OSError(errno.EIO, "OpenCV could not write the frame image")
    return str(path.relative_to(root)).replace("\\", "/")


def _frame_id(captured_at: datetime, digest: str) -> str:
    return captured_at.strftime("%Y%m%dT%H%M%S") + f"-{digest[:4]}"
