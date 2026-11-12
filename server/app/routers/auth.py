"""Sign-in and the current user (AC-01, AC-02).

The lockout lives in the account row, not in memory: a restart must not clear an attacker's five
failures. Remaining time is returned in seconds so the interface can count down without guessing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app import timebase
from app.deps import SessionDep, SettingsDep, UserDep
from app.envelope import CONFLICT, UNAUTHENTICATED, ApiError, ok
from app.models import SysLog, SysUser
from app.security import issue_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

MAX_FAILURES = 5
LOCK_MINUTES = 15


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)


def public_user(user: SysUser) -> dict[str, object]:
    return {
        "user_id": user.user_id,
        "username": user.username,
        "real_name": user.real_name,
        "role": user.role_code,
    }


@router.post("/login")
def login(body: LoginBody, db: SessionDep, settings: SettingsDep) -> dict[str, object]:
    user = db.scalar(
        select(SysUser).where(
            or_(
                SysUser.username == body.username,
                SysUser.phone == body.username,
                SysUser.email == body.username,
            )
        )
    )
    # The same message for "no such account" and "wrong password": telling them apart hands an
    # attacker a list of valid usernames.
    if user is None:
        raise ApiError(UNAUTHENTICATED, "账号或密码不正确")

    now = datetime.now(UTC).replace(tzinfo=None)
    if user.locked_until is not None and user.locked_until > now:
        remaining = int((user.locked_until - now).total_seconds())
        raise ApiError(CONFLICT, f"账号已锁定，请 {remaining} 秒后再试")
    if user.status != 1:
        raise ApiError(UNAUTHENTICATED, "账号已停用")

    if not verify_password(body.password, user.password_hash):
        user.fail_count = (user.fail_count or 0) + 1
        if user.fail_count >= MAX_FAILURES:
            user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            user.fail_count = 0
            db.commit()
            # The attempt that trips the lock reports a conflict, the same code every later attempt
            # gets: to the caller the account is now locked, which is a state, not a bad password.
            raise ApiError(
                CONFLICT, f"连续 {MAX_FAILURES} 次密码错误，账号锁定 {LOCK_MINUTES} 分钟"
            )
        left = MAX_FAILURES - user.fail_count
        db.commit()
        raise ApiError(UNAUTHENTICATED, f"账号或密码不正确，还可尝试 {left} 次")

    user.fail_count = 0
    user.locked_until = None
    user.last_login_at = now
    token, expires_at = issue_token(user, settings)
    db.add(
        SysLog(
            user_id=user.user_id,
            module="auth",
            action="login",
            target_type="sys_user",
            target_id=str(user.user_id),
        )
    )
    db.commit()
    return ok(
        {
            "token": token,
            "expires_at": timebase.iso(expires_at),
            "user": public_user(user),
        }
    )


@router.get("/me")
def me(user: UserDep) -> dict[str, object]:
    return ok(public_user(user))
