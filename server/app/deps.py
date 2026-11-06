"""FastAPI dependencies: the database session, the caller, and the role guard.

The engine is built once at import of the app and kept on `app.state`; the session is per request and
closed by FastAPI when the response is done. Roles are checked here so routers declare them once,
next to the group of endpoints they protect.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.envelope import FORBIDDEN, UNAUTHENTICATED, ApiError
from app.models import SysUser
from app.security import load_user


def get_db(request: Request) -> Iterator[Session]:
    """A session for this request, closed afterwards whether or not the handler raised."""
    factory = request.app.state.session_factory
    session: Session = factory()
    try:
        yield session
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_current_user(request: Request, db: SessionDep, settings: SettingsDep) -> SysUser:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError(UNAUTHENTICATED, "请先登录")
    return load_user(db, token, settings)


UserDep = Annotated[SysUser, Depends(get_current_user)]


def require(*roles: str):
    """A dependency asserting the caller holds one of `roles`.

    Written as a factory so a router can say `dependencies=[Depends(require("admin"))]` once, and every
    route it adds later inherits the check — a route that forgets its guard is the failure mode this
    avoids.
    """

    def guard(user: UserDep) -> SysUser:
        if roles and user.role_code not in roles:
            raise ApiError(FORBIDDEN, "当前角色无权执行此操作")
        return user

    return guard
