"""A refused request is written to `sys_log` (FR-M1-02, AC-02).

The requirement's processing step is "allow on a hit, return 403 otherwise -> write a rejection log",
and the log half was missing: the guard raised the 403 and recorded nothing, while every successful
action in the application writes a `SysLog` row.

The row is read through a **second session, after the response**. That is not pedantry: `get_db`
closes its session without committing, so a row that was only `add`ed disappears with the request.
Reading it back from the request's own session would pass on the broken shape too, and would not
prove the commit the requirement needs.
"""

from __future__ import annotations

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import SysLog, SysUser
from app.security import hash_password
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

FORBIDDEN = 40301
FORBIDDEN_MESSAGE = "当前角色无权执行此操作"

#: What one refusal row looks like: (user_id, module, action, target_type, target_id).
Refusal = tuple[int | None, str, str, str | None, str | None]


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Two accounts, one SQLite database, no background worker — the skeleton fixture, narrowed."""
    monkeypatch.setenv("DB_DSN", f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    with app.state.session_factory() as session:
        for name, role in (("admin", "admin"), ("observer", "observer")):
            hashed, salt = hash_password("password123")
            session.add(
                SysUser(
                    username=name,
                    password_hash=hashed,
                    salt=salt,
                    role_code=role,
                    real_name=name,
                    status=1,
                    fail_count=0,
                )
            )
        session.commit()

    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def sign_in(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": "password123"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def fresh_session(client: TestClient) -> Session:
    """A session built after the request, sharing no state with the one the request used."""
    return sessionmaker(bind=client.app.state.engine)()


def refusals(client: TestClient) -> list[Refusal]:
    """Every refusal row, oldest first, read outside the request that wrote it."""
    with fresh_session(client) as session:
        rows = session.scalars(
            select(SysLog).where(SysLog.action == "forbidden").order_by(SysLog.log_id)
        ).all()
        return [
            (row.user_id, row.module, row.action, row.target_type, row.target_id) for row in rows
        ]


def user_id(client: TestClient, username: str) -> int:
    with fresh_session(client) as session:
        found = session.scalar(select(SysUser.user_id).where(SysUser.username == username))
    assert found is not None, f"{username} is not in the database"
    return found


def test_a_refused_request_writes_the_attempt(client):
    observer = sign_in(client, "observer")
    response = client.get("/api/users", headers=observer)

    # The response is unchanged: same status, same envelope, same message.
    assert response.status_code == 403
    body = response.json()
    assert (body["code"], body["message"], body["data"]) == (
        FORBIDDEN,
        FORBIDDEN_MESSAGE,
        None,
    )

    # The row is readable through a second session after the response: only a commit survives that.
    assert refusals(client) == [
        (user_id(client, "observer"), "user", "forbidden", "route", "GET /api/users")
    ]


def test_a_route_level_guard_logs_the_attempt_too(client):
    """AC-02 names the model activation endpoint: it is guarded per route, not per router."""
    observer = sign_in(client, "observer")
    response = client.post("/api/models/1/activate", headers=observer)
    assert response.status_code == 403

    expected = (
        user_id(client, "observer"),
        "model",
        "forbidden",
        "route",
        "POST /api/models/1/activate",
    )
    assert refusals(client) == [expected]


def test_an_allowed_role_writes_no_refusal(client):
    admin = sign_in(client, "admin")
    assert client.get("/api/users", headers=admin).status_code == 200
    assert refusals(client) == []
