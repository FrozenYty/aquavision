"""Parameters, monitoring, messages and the audit log (FR-M7-01, FR-M8-01, FR-M8-02, AC-04).

Parameters are read from `Settings` and returned as-is. `PATCH` answers 501: **the data model has no
parameter table**, so a change would live in process memory and vanish on restart — worse than being
unavailable, because the operator would believe it stuck. The fix is a tenth table, not a dictionary.

Monitoring and the log are computed from rows that already exist.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app import serializers
from app.deps import SessionDep, SettingsDep, UserDep, get_current_user, require
from app.envelope import NOT_FOUND, ApiError, not_built, ok
from app.models import DetectTask, MediaAsset, SysLog, SysMessage

router = APIRouter(prefix="/api", tags=["system"], dependencies=[Depends(get_current_user)])


@router.get("/params")
def get_params(settings: SettingsDep) -> dict[str, object]:
    return ok(
        {
            "retention_days": settings.retention_days,
            "max_concurrency": settings.max_concurrency,
            "detect_interval_ms": settings.detect_interval_ms,
            "quality_threshold": settings.quality_threshold,
            "camera_index": settings.camera_index,
        }
    )


class ParamUpdate(BaseModel):
    """The shape a future implementation validates; declared now so the contract is visible."""

    retention_days: int | None = Field(default=None, ge=1, le=3650)
    max_concurrency: int | None = Field(default=None, ge=1, le=32)
    detect_interval_ms: int | None = Field(default=None, ge=50, le=10000)
    quality_threshold: int | None = Field(default=None, ge=0, le=100)


@router.patch("/params")
def update_params(_body: ParamUpdate) -> dict[str, object]:
    raise not_built("系统参数修改（数据模型中还没有 param 表，改了就重启丢失）")


@router.get("/monitor")
def monitor(db: SessionDep, settings: SettingsDep) -> dict[str, object]:
    queued = db.scalar(select(func.count(DetectTask.task_id)).where(DetectTask.status == 0)) or 0
    running = db.scalar(select(func.count(DetectTask.task_id)).where(DetectTask.status == 1)) or 0
    frames = db.scalar(select(func.count(MediaAsset.asset_id))) or 0

    data_dir = Path(settings.data_dir)
    usage = shutil.disk_usage(data_dir if data_dir.exists() else Path("."))
    percent = round(usage.used / usage.total * 100, 1)
    return ok(
        {
            "queue": {"queued": queued, "running": running},
            "frames": frames,
            "disk": {
                "used_gb": round(usage.used / 1024**3, 2),
                "total_gb": round(usage.total / 1024**3, 2),
                "percent": percent,
                "level": "crit" if percent >= 90 else "warn" if percent >= 75 else "ok",
            },
            "max_concurrency": settings.max_concurrency,
            "at": serializers.iso(datetime.now(UTC)),
        }
    )


@router.get("/messages")
def list_messages(
    db: SessionDep,
    user: UserDep,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=24, ge=1, le=100),
) -> dict[str, object]:
    stmt = select(SysMessage).where(
        or_(SysMessage.target_role.is_(None), SysMessage.target_role == user.role_code)
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(SysMessage.msg_id.desc()).limit(size).offset((page - 1) * size)
    ).all()
    unread = (
        db.scalar(
            select(func.count(SysMessage.msg_id)).where(
                SysMessage.is_read == 0,
                or_(SysMessage.target_role.is_(None), SysMessage.target_role == user.role_code),
            )
        )
        or 0
    )
    return ok(
        {
            "items": [
                {
                    "msg_id": row.msg_id,
                    "type": row.msg_type,
                    "level": row.level,
                    "title": row.title,
                    "content": row.content,
                    "is_read": bool(row.is_read),
                    "created_at": serializers.iso(row.created_at),
                }
                for row in rows
            ],
            "unread": unread,
            "total": total,
            "page": page,
            "size": size,
        }
    )


@router.post("/messages/{msg_id}/read")
def mark_read(msg_id: int, db: SessionDep) -> dict[str, object]:
    row = db.get(SysMessage, msg_id)
    if row is None:
        raise ApiError(NOT_FOUND, "消息不存在")
    row.is_read = 1
    db.commit()
    return ok({"msg_id": msg_id, "is_read": True})


@router.get("/logs", dependencies=[Depends(require("admin"))])
def list_logs(
    db: SessionDep,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=24, ge=1, le=100),
    action: str | None = None,
    module: str | None = None,
) -> dict[str, object]:
    stmt = select(SysLog)
    if action:
        stmt = stmt.where(SysLog.action == action)
    if module:
        stmt = stmt.where(SysLog.module == module)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(SysLog.log_id.desc()).limit(size).offset((page - 1) * size)
    ).all()
    return ok(
        {
            "items": [
                {
                    "log_id": row.log_id,
                    "user_id": row.user_id,
                    "module": row.module,
                    "action": row.action,
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "before_value": row.before_value,
                    "after_value": row.after_value,
                    "created_at": serializers.iso(row.created_at),
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "size": size,
        }
    )
