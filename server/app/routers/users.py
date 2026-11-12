"""Account management (AC-03, FR-M1-03). Administrator only.

Disabling an account keeps its history: the row stays, `status` flips, and every query that reads
history keeps working. Deleting the row would break the audit trail that AC-04 requires.
"""

from __future__ import annotations

import secrets
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import serializers
from app.deps import SessionDep, UserDep, require
from app.envelope import CONFLICT, NOT_FOUND, ApiError, ok
from app.models import SysLog, SysUser
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require("admin"))])


class StatusBody(BaseModel):
    status: int = Field(ge=0, le=1, description="1 enables, 0 disables")


class ResetBody(BaseModel):
    # bcrypt truncates beyond 72 bytes; capping here makes that visible instead of silent.
    password: str = Field(min_length=8, max_length=72)


class CreateBody(BaseModel):
    """FR-M1-03's input: name, phone, role, initial password, enabled state.

    `role` is the closed set the database and the matrix know; `password` may be omitted, and then the
    server generates one and returns it exactly once, which is the requirement's "one-time initial
    password".
    """

    username: str = Field(min_length=1, max_length=64)
    real_name: str = Field(min_length=1, max_length=64)
    role: Literal["observer", "analyst", "algo", "admin"]
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, min_length=8, max_length=72)


@router.get("")
def list_users(db: SessionDep) -> dict[str, object]:
    rows = db.scalars(select(SysUser).order_by(SysUser.user_id)).all()
    return ok({"items": [serializers.user(row) for row in rows], "total": len(rows)})


@router.post("")
def create_user(body: CreateBody, db: SessionDep, user: UserDep) -> dict[str, object]:
    """Create one account (FR-M1-03, AC-03).

    The duplicate check is the requirement's own acceptance: a phone number that already belongs to an
    account is refused with an "already exists" message, not a 500 from the unique index. Username and
    email are unique in the table too, so they are checked together with it.
    """
    for label, column, value in (
        ("用户名", SysUser.username, body.username),
        ("手机号", SysUser.phone, body.phone),
        ("邮箱", SysUser.email, body.email),
    ):
        if value is not None and db.scalar(select(SysUser.user_id).where(column == value)):
            raise ApiError(CONFLICT, f"{label}已存在：{value}")

    password = body.password or secrets.token_urlsafe(9)
    hashed, salt = hash_password(password)
    row = SysUser(
        username=body.username,
        phone=body.phone,
        email=body.email,
        password_hash=hashed,
        salt=salt,
        role_code=body.role,
        real_name=body.real_name,
        status=1,
        fail_count=0,
        token_epoch=0,
    )
    db.add(row)
    db.flush()
    # AC-04: who created the account, and what it is. The password never reaches the log.
    db.add(
        SysLog(
            user_id=user.user_id,
            module="user",
            action="create",
            target_type="sys_user",
            target_id=str(row.user_id),
            after_value=body.role,
        )
    )
    db.commit()
    db.refresh(row)

    payload = serializers.user(row)
    if body.password is None:
        # Returned by this response only; the list route never carries it again.
        payload["initial_password"] = password
    return ok(payload)


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
    # NFR-S-05: every token issued under the old password stops working now, not in eight hours.
    row.token_epoch = int(row.token_epoch or 0) + 1
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
