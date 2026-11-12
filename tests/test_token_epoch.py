"""A password change retires the tokens issued before it (NFR-S-05, P3-20).

NFR-S-05 promised that a password change invalidates issued tokens and the system did not do it: the
tokens are stateless and `sys_user` had no column to revoke them, so a stolen token stayed good for its
full eight hours. Disabling an account was already immediate - the guard reads `status` on every
request - so this test holds the half that was missing: the account's `token_epoch` is bumped by a
password reset, and a token carrying the older number is refused.

A reset of somebody else's password must not end the administrator's own session, which is why the
assertions below check both accounts after the change.
"""

from __future__ import annotations

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.envelope import TOKEN_EXPIRED
from app.models import SysUser
from app.security import hash_password
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_DSN", f"sqlite:///{(tmp_path / 'epoch.db').as_posix()}")
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    get_settings.cache_clear()

    from app.main import create_app

    made = create_app()
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'epoch.db').as_posix()}")
    made.state.engine = engine
    made.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with made.state.session_factory() as session:
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
        session.commit()
    yield made
    get_settings.cache_clear()


def sign_in(client: TestClient, username: str, password: str = "password123") -> dict[str, str]:
    body = client.post("/api/auth/login", json={"username": username, "password": password}).json()
    assert body["code"] == 0, body
    return {"Authorization": f"Bearer {body['data']['token']}"}


def user_id(app, username: str) -> int:
    with sessionmaker(bind=app.state.engine)() as session:
        found = session.scalar(select(SysUser.user_id).where(SysUser.username == username))
    assert found is not None
    return found


def test_a_password_reset_ends_the_sessions_that_password_created(app):
    with TestClient(app) as client:
        admin = sign_in(client, "admin")
        analyst = sign_in(client, "analyst")
        assert client.get("/api/auth/me", headers=analyst).status_code == 200

        reset = client.post(
            f"/api/users/{user_id(app, 'analyst')}/reset-password",
            json={"password": "replacement1"},
            headers=admin,
        ).json()
        assert reset["code"] == 0, reset

        # The token issued under the old password is dead now, with the contract's "sign in again".
        stale = client.get("/api/auth/me", headers=analyst)
        assert stale.status_code == 401, stale.text
        assert stale.json()["code"] == TOKEN_EXPIRED, stale.text

        # The new password signs in, and the token it gets works.
        renewed = sign_in(client, "analyst", "replacement1")
        assert client.get("/api/auth/me", headers=renewed).status_code == 200

        # Somebody else's reset does not touch the administrator's own session.
        assert client.get("/api/auth/me", headers=admin).status_code == 200


def test_the_epoch_is_what_survives_a_reset_and_the_count_is_kept(app):
    """The column moves by exactly one per reset; that number is what the next token carries."""
    with TestClient(app) as client:
        admin = sign_in(client, "admin")
        analyst = sign_in(client, "analyst")
        for attempt in range(2):
            body = client.post(
                f"/api/users/{user_id(app, 'analyst')}/reset-password",
                json={"password": f"replacement{attempt}"},
                headers=admin,
            ).json()
            assert body["code"] == 0, body
        with sessionmaker(bind=app.state.engine)() as session:
            epoch = session.scalar(select(SysUser.token_epoch).where(SysUser.username == "analyst"))
        assert epoch == 2
        # The first session is long dead; the last password still signs in.
        assert client.get("/api/auth/me", headers=analyst).status_code == 401
        fresh = sign_in(client, "analyst", "replacement1")
        assert client.get("/api/auth/me", headers=fresh).status_code == 200
