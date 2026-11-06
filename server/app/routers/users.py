"""Account management (AC-03, FR-M1-03). Administrator only.

Disabling an account keeps its history: the row stays, `status` flips, and every query that reads
history keeps working. Deleting the row would break the audit trail that AC-04 requires.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import serializers
from app.deps import SessionDep, require
from app.envelope import CONFLICT, NOT_FOUND, ApiError, ok
from app.models import SysLog, SysUser
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require("admin"))])


class StatusBody(BaseModel):
    status: int = Field(ge=0, le=1, description="1 enables, 0 disables")


class ResetBody(BaseModel):
    # bcrypt truncates beyond 72 bytes; capping here makes that visible instead of silent.
    password: str = Field(min_length=8, max_length=72)


@router.get("")
def list_users(db: SessionDep) -> dict[str, object]:
    rows = db.scalars(select(SysUser).order_by(SysUser.user_id)).all()
    return ok({"items": [serializers.user(row) for row in rows], "total": len(rows)})


@router.post("/{user_id}/status")
def set_status(user_id: int, body: StatusBody, db: SessionDep) -> dict[str, object]:
    row = db.get(SysUser, user_id)
    if row is None:
        raise ApiError(NOT_FOUND, "账号不存在")
    if row.status == body.status:
        raise ApiError(CONFLICT, "账号状态已经是该值")

    before, after = row.status, body.status
    row.status = after
    if after == 0:
        # A disabled account must not keep a live session; the token check reads this same lock.
        row.locked_until = None
        row.fail_count = 0
    db.add(
        SysLog(
            module="user",
            action="disable" if after == 0 else "restore",
            target_type="sys_user",
            target_id=str(user_id),
            before_value=str(before),
            after_value=str(after),
        )
    )
    db.commit()
    return ok(serializers.user(row))


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, body: ResetBody, db: SessionDep) -> dict[str, object]:
    row = db.get(SysUser, user_id)
    if row is None:
        raise ApiError(NOT_FOUND, "账号不存在")

    hashed, salt = hash_password(body.password)
    row.password_hash = hashed
    row.salt = salt
    row.fail_count = 0
    row.locked_until = None
    # The password itself never reaches the log — the action is what gets recorded.
    db.add(
        SysLog(
            module="user",
            action="reset_password",
            target_type="sys_user",
            target_id=str(user_id),
        )
    )
    db.commit()
    return ok({"user_id": user_id, "reset": True})
