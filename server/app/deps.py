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
from app.models import SysLog, SysUser
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


#: The module tag a refusal is filed under, per route area. The log viewer filters by the same
#: singular names the routers write (`module="user"` for accounts, `module="model"` for versions), so
#: the path segment is mapped to that vocabulary rather than adding a second one.
_MODULE_BY_SEGMENT = {
    "users": "user",
    "models": "model",
    "datasets": "dataset",
    "reports": "report",
    "hard-samples": "review",
    "logs": "system",
}


def _module_of(path: str) -> str:
    """The module tag of the route being refused, from its first segment after `/api`."""
    segments = [segment for segment in path.split("/") if segment]
    if len(segments) > 1 and segments[0] == "api":
        area = segments[1]
    else:
        area = segments[0] if segments else "api"
    return _MODULE_BY_SEGMENT.get(area, area)


def require(*roles: str):
    """A dependency asserting the caller holds one of `roles`.

    Written as a factory so a router can say `dependencies=[Depends(require("admin"))]` once, and every
    route it adds later inherits the check — a route that forgets its guard is the failure mode this
    avoids.

    A refusal is recorded before it is returned (FR-M1-02, AC-02). The commit is not redundant:
    `get_db` closes the session without committing, so a row that is only added is lost when the
    guard raises — the caller would get the 403 and the attempt would vanish. The response itself is
    unchanged; the log row is a side effect, not part of the envelope.
    """

    def guard(request: Request, db: SessionDep, user: UserDep) -> SysUser:
        if roles and user.role_code not in roles:
            db.add(
                SysLog(
                    user_id=user.user_id,
                    module=_module_of(request.url.path),
                    action="forbidden",
                    target_type="route",
                    target_id=f"{request.method} {request.url.path}"[:64],
                )
            )
            db.commit()
            raise ApiError(FORBIDDEN, "当前角色无权执行此操作")
        return user

    return guard
