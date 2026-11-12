"""Parameters, monitoring, messages and the audit log (FR-M7-01, FR-M8-01, FR-M8-02, AC-04).

Parameters are read from `Settings` for the values nothing overrides, and a `PATCH` persists the changed
keys in `sys_param` and returns both the full set and what moved. An earlier version answered 501 because
the data model had no parameter table; that table exists now, so the endpoint does too — a change that
lived in process memory would vanish on restart and the operator would believe it stuck.

Monitoring and the log are computed from rows that already exist.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import serializers
from app.config import Settings
from app.deps import SessionDep, SettingsDep, UserDep, get_current_user, require
from app.envelope import CONFLICT, NOT_FOUND, ApiError, ok
from app.models import DetectTask, MediaAsset, SysLog, SysMessage, SysParam
from app.params import PARAMETERS, effective

router = APIRouter(prefix="/api", tags=["system"], dependencies=[Depends(get_current_user)])


def _current(db: Session, settings: Settings) -> dict[str, object]:
    """Defaults from the environment, overridden by rows. A row that vanished falls back again."""
    values = {key: getattr(settings, key) for key in PARAMETERS}
    for row in db.scalars(select(SysParam)).all():
        if row.param_key not in PARAMETERS:
            continue
        try:
            values[row.param_key] = int(row.param_value)
        except (TypeError, ValueError):
            # A corrupt row must not take the settings page down with it.
            continue
    return values


@router.get("/params")
def get_params(db: SessionDep, settings: SettingsDep) -> dict[str, object]:
    return ok(_current(db, settings))


class ParamUpdate(BaseModel):
    """The accepted range comes from `app.params`, where the accessor reads the same declaration.

    A value outside it is refused here, with the project envelope, rather than stored and obeyed: a
    concurrency of zero does not slow detection down, it stops it.
    """

    retention_days: int | None = Field(
        default=None, ge=PARAMETERS["retention_days"].low, le=PARAMETERS["retention_days"].high
    )
    max_concurrency: int | None = Field(
        default=None, ge=PARAMETERS["max_concurrency"].low, le=PARAMETERS["max_concurrency"].high
    )
    detect_interval_ms: int | None = Field(
        default=None,
        ge=PARAMETERS["detect_interval_ms"].low,
        le=PARAMETERS["detect_interval_ms"].high,
    )
    quality_threshold: int | None = Field(
        default=None,
        ge=PARAMETERS["quality_threshold"].low,
        le=PARAMETERS["quality_threshold"].high,
    )
    camera_index: int | None = Field(
        default=None, ge=PARAMETERS["camera_index"].low, le=PARAMETERS["camera_index"].high
    )


@router.patch("/params", dependencies=[Depends(require("algo", "admin"))])
def update_params(
    body: ParamUpdate, db: SessionDep, settings: SettingsDep, user: UserDep
) -> dict[str, object]:
    """Write the supplied subset, one audit row per changed key (AC-27).

    One row per key rather than one row per request: the log is read by key ("who changed the
    concurrency limit"), and a single row holding five fields answers that question badly.
    """
    before = _current(db, settings)
    changed: dict[str, dict[str, object]] = {}

    for key, value in body.model_dump(exclude_none=True).items():
        if value == before.get(key):
            continue
        row = db.scalar(select(SysParam).where(SysParam.param_key == key))
        if row is None:
            row = SysParam(param_key=key, param_value=str(value), value_type=type(value).__name__)
            db.add(row)
        else:
            row.param_value = str(value)
            row.value_type = type(value).__name__
        row.updated_by = user.user_id
        row.updated_at = datetime.now(UTC).replace(tzinfo=None)
        db.add(
            SysLog(
                user_id=user.user_id,
                module="system",
                action="config",
                target_type="sys_param",
                target_id=key,
                before_value=str(before.get(key)),
                after_value=str(value),
            )
        )
        changed[key] = {"before": before.get(key), "after": value}

    if not changed:
        raise ApiError(CONFLICT, "没有改动")
    db.commit()
    return ok({"params": _current(db, settings), "changed": changed})


def _worker_state(app_state) -> dict[str, object]:
    """Whether a detection worker is running here, and why the queue is frozen when it is not.

    There is no worker heartbeat in the database, so the cheapest honest surface is the process that
    would do the work: the pool's threads. A task row says running because no worker is behind it, and
    the operator must read that instead of watching progress that will never change.
    """
    enabled = bool(getattr(app_state, "worker_enabled", False))
    pool = getattr(app_state, "worker", None)
    alive = bool(pool is not None and getattr(pool, "alive", False))
    return {"enabled": enabled, "alive": alive, "problem": None}


@router.get("/monitor")
def monitor(request: Request, db: SessionDep, settings: SettingsDep) -> dict[str, object]:
    queued = db.scalar(select(func.count(DetectTask.task_id)).where(DetectTask.status == 0)) or 0
    running = db.scalar(select(func.count(DetectTask.task_id)).where(DetectTask.status == 1)) or 0
    frames = db.scalar(select(func.count(MediaAsset.asset_id))) or 0
    worker = _worker_state(request.app.state)
    if (queued or running) and not worker["alive"]:
        cause = (
            "检测线程已关闭（AV_WORKER_ENABLED=0）" if not worker["enabled"] else "检测线程已停止"
        )
        worker["problem"] = (
            f"{cause}：{queued} 个任务排队、{running} 个任务停在运行中，进度不会推进。"
            "请查看服务日志并重启服务。"
        )

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
            "worker": worker,
            # The limit in force, not the one the process started with: the page reads this figure
            # back and must not be told a number the queue is not honouring (ADR 15).
            "max_concurrency": effective(
                request.app.state.session_factory, "max_concurrency", settings
            ),
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
