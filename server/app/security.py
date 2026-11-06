"""Passwords and tokens (contract §4). No FastAPI dependencies here — those live in `deps`.

**bcrypt**, because the requirements pin it and it is the safe default. The data model also carries a
`salt` column, so the salt is stored there as well: it is the prefix of the bcrypt hash, not a second
secret. A reader of the table then finds the salt where the dictionary says it lives, and verification
still uses only the hash.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.envelope import FORBIDDEN, TOKEN_EXPIRED, UNAUTHENTICATED, ApiError
from app.models import SysUser

ALGORITHM = "HS256"

#: Roles allowed to reach the algorithmic and system-configuration endpoints (SRS FR-M1-02).
PRIVILEGED = ("algo", "admin")

#: bcrypt refuses to check a password longer than this; truncation is silent in some libraries.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> tuple[str, str]:
    """Return (hash, salt-prefix). The prefix is the salt bcrypt already embedded."""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
    return hashed, hashed[:29]


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        # A malformed hash in the database must read as "wrong password", not as a crash.
        return False


def issue_token(user: SysUser, settings: Settings) -> tuple[str, datetime]:
    """A signed token and its expiry — eight hours by default, no refresh (contract §4)."""
    expires_at = datetime.now(UTC) + timedelta(hours=settings.jwt_hours)
    payload = {
        "sub": str(user.user_id),
        "role": user.role_code,
        "name": user.real_name,
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), expires_at


def decode_token(token: str, settings: Settings) -> dict[str, object]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as err:
        raise ApiError(TOKEN_EXPIRED, "登录已过期，请重新登录") from err


def load_user(db: Session, token: str, settings: Settings) -> SysUser:
    """Resolve a bearer token to an enabled account."""
    claims = decode_token(token, settings)
    try:
        user_id = int(str(claims["sub"]))
    except (KeyError, TypeError, ValueError) as err:
        raise ApiError(UNAUTHENTICATED, "登录状态无效") from err

    user = db.scalar(select(SysUser).where(SysUser.user_id == user_id))
    if user is None:
        raise ApiError(UNAUTHENTICATED, "账号不存在")
    if user.status != 1:
        raise ApiError(FORBIDDEN, "账号已停用")
    return user
