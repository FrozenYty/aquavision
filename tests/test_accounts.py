"""Account management, end to end (P3-04, FR-M1-03, AC-03, AC-04).

FR-M1-03 says administrators **create**, disable and restore accounts and reset passwords. Disable,
restore and reset existed; there was no way to create one at all - the only account a fresh database
ever had was the one `scripts/init_db.py` writes - so "one account per person" was a promise the API
could not keep.

AC-03 names the three things the tests below hold: a disabled account cannot sign in, its history stays
searchable, and a duplicate phone number is refused with an "already exists" message. AC-04's half is
that the account actions are readable afterwards with the operator and the before/after values, and
that nothing offers to delete a log entry.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.envelope import CONFLICT, FORBIDDEN, MISSING_PARAM
from app.models import MediaAsset, SysLog, SysUser
from app.security import hash_password
from app.seed import seed_species
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

LOCAL = ("127.0.0.1", 50000)
ROLES = ("observer", "analyst", "algo", "admin")

NEW = {
    "username": "wang-fang",
    "real_name": "Wang Fang",
    "phone": "13800000001",
    "role": "observer",
    "password": "initial-pass-1",
}


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_DSN", f"sqlite:///{(tmp_path / 'accounts.db').as_posix()}")
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'accounts.db').as_posix()}")
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    factory = app.state.session_factory
    with factory() as session:
        seed_species(session)
        for name, role in (("admin", "admin"), ("analyst", "analyst")):
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
        now = datetime.now(UTC).replace(tzinfo=None)
        for index in range(2):
            session.add(
                MediaAsset(
                    frame_id=f"20261112T130000-{index:04d}",
                    session_id="s-accounts",
                    point_code="A3",
                    file_path=f"frames/{index:04d}.jpg",
                    file_size=1024 + index,
                    file_hash=f"{index:064d}",
                    captured_at=now,
                    width=640,
                    height=480,
                    quality_score=80,
                    quality_flag=0,
                    is_retake=0,
                )
            )
        session.commit()

    with TestClient(app, client=LOCAL) as client:
        yield client, factory
    get_settings.cache_clear()


def sign_in(client: TestClient, username: str, password: str) -> dict:
    return client.post("/api/auth/login", json={"username": username, "password": password}).json()


def auth(client: TestClient, username: str = "admin") -> dict[str, str]:
    body = sign_in(client, username, "password123")
    assert body["code"] == 0, body
    return {"Authorization": f"Bearer {body['data']['token']}"}


def create(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    payload = {**NEW, **overrides}
    response = client.post("/api/users", json=payload, headers=headers)
    assert response.status_code != 404, "there is no POST /api/users"
    return response.json()


def find(factory, username: str) -> SysUser | None:
    with factory() as session:
        return session.scalar(select(SysUser).where(SysUser.username == username))


def test_an_administrator_creates_an_account_that_can_sign_in(rig):
    client, factory = rig
    admin = auth(client)

    body = create(client, admin)
    assert body["code"] == 0, body
    assert body["data"]["username"] == NEW["username"]
    assert body["data"]["role"] == "observer"
    assert body["data"]["status"] == 1

    # The account works immediately, with the password the administrator set.
    signed_in = sign_in(client, NEW["username"], NEW["password"])
    assert signed_in["code"] == 0, signed_in
    assert signed_in["data"]["user"]["role"] == "observer"

    with factory() as session:
        row = find(factory, NEW["username"])
        assert row is not None and row.password_hash != NEW["password"]
        assert row.salt
        assert row.token_epoch == 0
        # AC-04: the creation is in the log with the operator and what was created.
        log = session.scalar(select(SysLog).where(SysLog.action == "create"))
        assert log is not None
        assert log.target_id == str(body["data"]["user_id"])
        assert log.module == "user"


def test_a_generated_initial_password_is_returned_once(rig):
    """FR-M1-03's output: a one-time initial password when the administrator does not set one."""
    client, factory = rig
    admin = auth(client)

    body = create(client, admin, username="li-ming", phone="13800000002", password=None)
    assert body["code"] == 0, body
    generated = body["data"].get("initial_password")
    assert generated and len(generated) >= 8, body
    assert sign_in(client, "li-ming", generated)["code"] == 0

    # It is returned by the creation only: the list never carries it again.
    listing = client.get("/api/users", headers=admin).json()["data"]
    assert all("initial_password" not in item for item in listing["items"])


def test_a_duplicate_identifier_is_refused_with_the_message(rig):
    """AC-03: "saving a duplicate phone number is refused with an 'already exists' message"."""
    client, _factory = rig
    admin = auth(client)
    assert create(client, admin)["code"] == 0

    for overrides, field in (
        ({"username": "someone-else"}, "手机号"),
        ({"phone": "13800000009", "username": NEW["username"]}, "用户名"),
    ):
        response = client.post("/api/users", json={**NEW, **overrides}, headers=admin)
        body = response.json()
        assert response.status_code == 409, body
        assert body["code"] == CONFLICT, body
        assert "已存在" in body["message"], body
        assert field in body["message"], body


def test_an_unknown_role_is_refused(rig):
    client, _factory = rig
    admin = auth(client)
    response = client.post("/api/users", json={**NEW, "role": "manager"}, headers=admin)
    assert response.status_code == 400
    assert response.json()["code"] == MISSING_PARAM
    assert client.get("/api/users", headers=admin).json()["data"]["total"] == 2, (
        "an invalid role must not create a row"
    )


def test_only_an_administrator_may_create_an_account(rig):
    client, factory = rig
    analyst = auth(client, "analyst")
    response = client.post("/api/users", json=NEW, headers=analyst)
    assert response.status_code == 403
    assert response.json()["code"] == FORBIDDEN
    assert find(factory, NEW["username"]) is None


def test_a_disabled_account_cannot_sign_in_but_keeps_its_history(rig):
    """AC-03's first half, and the session it was holding."""
    client, factory = rig
    admin = auth(client)
    created = create(client, admin)["data"]
    user_id = created["user_id"]
    reader = sign_in(client, NEW["username"], NEW["password"])
    assert reader["code"] == 0
    token = {"Authorization": f"Bearer {reader['data']['token']}"}

    # The account does something that leaves history: it reads the frame list, and we log a review of
    # its own by hand is unnecessary - the point is the rows survive the disable.
    with factory() as session:
        session.add(
            SysLog(
                user_id=user_id,
                module="capture",
                action="frame",
                target_type="media_asset",
                target_id="20261112T130000-0000",
            )
        )
        session.commit()

    disabled = client.post(f"/api/users/{user_id}/status", json={"status": 0}, headers=admin).json()
    assert disabled["code"] == 0, disabled

    refused = sign_in(client, NEW["username"], NEW["password"])
    assert refused["code"] == 40102, refused
    assert "停用" in refused["message"], refused
    # The token it was already holding stops working on the next request.
    assert client.get("/api/auth/me", headers=token).status_code == 403

    # Its history is still there: the log rows it wrote are readable through the log route.
    with factory() as session:
        rows = session.scalars(select(SysLog).where(SysLog.user_id == user_id)).all()
        assert [row.action for row in rows if row.target_type == "media_asset"] == ["frame"]
    logs = client.get("/api/logs", params={"size": 50}, headers=admin).json()["data"]
    assert any(item["user_id"] == user_id for item in logs["items"])


def test_a_restored_account_signs_in_again(rig):
    client, factory = rig
    admin = auth(client)
    user_id = create(client, admin)["data"]["user_id"]
    client.post(f"/api/users/{user_id}/status", json={"status": 0}, headers=admin)

    restored = client.post(f"/api/users/{user_id}/status", json={"status": 1}, headers=admin).json()
    assert restored["code"] == 0, restored
    assert restored["data"]["status"] == 1
    assert sign_in(client, NEW["username"], NEW["password"])["code"] == 0

    # AC-04: disable and restore are both in the log, with before and after.
    with factory() as session:
        rows = session.scalars(
            select(SysLog).where(SysLog.target_id == str(user_id)).order_by(SysLog.log_id)
        ).all()
        pairs = [(row.action, row.before_value, row.after_value) for row in rows]
    assert ("disable", "1", "0") in pairs
    assert ("restore", "0", "1") in pairs


def test_the_log_route_offers_no_way_to_delete_an_entry(rig):
    """AC-04's last clause: the trail is append-only as far as the API is concerned."""
    client, _factory = rig
    admin = auth(client)
    assert create(client, admin)["code"] == 0

    with sessionmaker(bind=client.app.state.engine)() as session:
        before = session.scalar(select(func.count()).select_from(SysLog))

    client.get("/api/logs", headers=admin)
    client.get("/api/users", headers=admin)
    client.post("/api/users/1/status", json={"status": 1}, headers=admin)  # unchanged -> 409

    with sessionmaker(bind=client.app.state.engine)() as session:
        after = session.scalar(select(func.count()).select_from(SysLog))
    assert after >= before, "reading the log must not remove entries"
    methods = {
        method
        for method, path in (
            (method.upper(), route)
            for route, operations in client.app.openapi()["paths"].items()
            for method in operations
        )
        if path == "/api/logs"
    }
    assert methods == {"GET"}, f"the log route grew a writer: {methods}"
