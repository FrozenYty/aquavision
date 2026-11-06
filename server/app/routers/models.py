"""Model versions and activation (FR-M6-01, FR-M6-02, AC-23, AC-24).

Activation is exclusive: the previous online version is switched off in the same transaction, so there
is never a moment with two online models or none — a race between two activations would otherwise
leave the detector without a version to run.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app import serializers
from app.deps import SessionDep, UserDep, get_current_user, require
from app.envelope import CONFLICT, NOT_FOUND, ApiError, ok
from app.models import ModelVersion, SysLog

router = APIRouter(prefix="/api/models", tags=["models"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_models(db: SessionDep) -> dict[str, object]:
    rows = db.scalars(select(ModelVersion).order_by(ModelVersion.model_id.desc())).all()
    online = next((row.model_id for row in rows if row.is_online), None)
    return ok(
        {
            "items": [serializers.model_version(row) for row in rows],
            "online_model_id": online,
            "total": len(rows),
        }
    )


@router.post("/{model_id}/activate", dependencies=[Depends(require("algo", "admin"))])
def activate(model_id: int, db: SessionDep, user: UserDep) -> dict[str, object]:
    target = db.get(ModelVersion, model_id)
    if target is None:
        raise ApiError(NOT_FOUND, "模型版本不存在")
    if target.is_online:
        raise ApiError(CONFLICT, "该版本已经在线")
    # A version without metrics cannot be compared against the baseline, so it cannot go online.
    if target.map50 is None or target.map50_95 is None:
        raise ApiError(CONFLICT, "该版本缺少评估指标，不能上线")

    previous = db.scalar(select(ModelVersion).where(ModelVersion.is_online == 1))
    before = previous.version_name if previous else None
    if previous is not None:
        previous.is_online = 0
        previous.status = 2
    target.is_online = 1
    target.status = 1

    db.add(
        SysLog(
            user_id=user.user_id,
            module="model",
            action="activate",
            target_type="model_version",
            target_id=str(model_id),
            before_value=before,
            after_value=target.version_name,
        )
    )
    db.commit()
    return ok(serializers.model_version(target))
