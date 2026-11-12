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


#: The addresses a browser on the capture machine reaches the server from. `testclient` is
#: deliberately absent: a test that exercises a capture route has to state that its client is local,
#: so the test runner gets no bypass the product does not have.
LOCAL_HOSTS = frozenset({"127.0.0.1", "::1"})


def is_local(host: str | None) -> bool:
    return host in LOCAL_HOSTS


def only_local(request: Request, db: SessionDep, user: UserDep) -> SysUser:
    """Refuse a capture call that did not come from this machine (FR-M1-02, AC-05).

    The pages are served by the same process that owns the camera, so the operator's browser is
    loopback. A signed-in client on another machine has no business posting frames: the requirement
    keeps the capture endpoints local, and a frame that did not come from the camera in front of the
    tank is exactly what AC-05 forbids. The refusal is logged like a role refusal, and the message
    says where the page has to be opened.

    Authentication runs first, so an unauthenticated call still answers 401 - FR-M1-02's acceptance
    names that case and this guard must not turn it into a 403.
    """

    host = request.client.host if request.client else None
    if not is_local(host):
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
        raise ApiError(
            FORBIDDEN,
            f"采集端点只接受本机访问（来源 {host or '未知'}），请在本机浏览器打开采集页",
        )
    return user


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
