"""The capture surface belongs to this machine (FR-M1-02, AC-05).

FR-M1-02's business rules say the capture endpoints "accept only the local process and are never
exposed", and they were ordinary JWT routes: a signed-in client on another machine could post frames,
which is exactly what AC-05 forbids — a frame that did not come from the camera in front of the tank.
The guard is the loopback address, not a flag, and the tests state their own client address rather than
relying on the test runner's default, so nothing is bypassed for the suite's convenience.

Authentication still runs first: FR-M1-02's acceptance says an unauthenticated call to a capture
endpoint receives 401, and a locality guard must not swallow that into a 403.
"""

from __future__ import annotations

import numpy as np
import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.envelope import FORBIDDEN, UNAUTHENTICATED
from app.models import SysLog, SysUser
from app.security import hash_password
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from starlette.websockets import WebSocketDisconnect

REMOTE = ("203.0.113.9", 51000)
LOCAL = ("127.0.0.1", 51000)
#: The capture surface: the routes that touch the camera, the sessions around it, and the live socket.
CAPTURE_CALLS = (
    ("GET", "/api/cameras"),
    ("GET", "/api/capture/sessions"),
    ("POST", "/api/capture/sessions"),
    ("POST", "/api/capture/sessions/s-1/frames"),
    ("POST", "/api/capture/sessions/s-1/close"),
)


class FakeSource:
    """A camera that is always attached: the socket test must not depend on the runner's hardware.

    CI has no camera, and the first CI run of this file failed exactly there - the server closed the
    socket with capture-unavailable before `auth_ok`, and `receive_json` raised. Injecting the source
    is the same seam `tests/test_ws_capture.py` uses.
    """

    def open(self) -> None:
        pass

    def read(self) -> np.ndarray:
        return np.full((48, 64, 3), 120, dtype=np.uint8)

    def close(self) -> None:
        pass


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_DSN", f"sqlite:///{(tmp_path / 'local.db').as_posix()}")
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    get_settings.cache_clear()

    from app.main import create_app

    made = create_app()
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'local.db').as_posix()}")
    made.state.engine = engine
    made.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with made.state.session_factory() as session:
        hashed, salt = hash_password("password123")
        session.add(
            SysUser(
                username="admin",
                password_hash=hashed,
                salt=salt,
                role_code="admin",
                real_name="admin",
                status=1,
                fail_count=0,
            )
        )
        session.commit()
    yield made
    get_settings.cache_clear()


def sign_in(client: TestClient) -> dict[str, str]:
    body = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password123"}
    ).json()
    return {"Authorization": f"Bearer {body['data']['token']}"}


def refusals(app) -> list[str]:
    with sessionmaker(bind=app.state.engine)() as session:
        rows = session.scalars(
            select(SysLog).where(SysLog.action == "forbidden").order_by(SysLog.log_id)
        ).all()
        return [str(row.target_id) for row in rows]


def test_a_client_on_another_machine_is_refused_the_whole_capture_surface(app):
    with TestClient(app, client=REMOTE) as client:
        headers = sign_in(client)
        for method, path in CAPTURE_CALLS:
            response = client.request(method, path, json={}, headers=headers)
            body = response.json()
            assert response.status_code == 403, f"{method} {path}: {response.text}"
            assert body["code"] == FORBIDDEN, body
            assert "本机" in body["message"], body
        # Every refusal is recorded, like a role refusal (FR-M1-02's processing step).
        assert refusals(app) == [f"{method} {path}" for method, path in CAPTURE_CALLS]


def test_a_remote_call_without_a_token_is_still_a_401(app):
    """The requirement's own acceptance: authentication is answered before locality."""
    with TestClient(app, client=REMOTE) as client:
        response = client.post("/api/capture/sessions/s-1/frames", json={})
        assert response.status_code == 401
        assert response.json()["code"] == UNAUTHENTICATED
        assert refusals(app) == []


def test_the_operator_on_this_machine_is_not_refused(app):
    """The guard must not cost the loopback client anything, including a bad request body."""
    with TestClient(app, client=LOCAL) as client:
        headers = sign_in(client)
        cameras = client.get("/api/cameras", headers=headers)
        assert cameras.status_code == 200, cameras.text
        assert cameras.json()["code"] == 0
        session = client.post("/api/capture/sessions", headers=headers)
        assert session.status_code == 200, session.text
        # An empty body is a 400 about the body, not a 403 about the address.
        frames = client.post("/api/capture/sessions/s-1/frames", json={}, headers=headers)
        assert frames.status_code == 400, frames.text
        assert refusals(app) == []


def test_the_live_socket_is_refused_at_the_handshake_from_another_machine(app):
    with TestClient(app, client=REMOTE) as client:
        headers = sign_in(client)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/capture") as socket:
                socket.send_json(
                    {"type": "auth", "token": headers["Authorization"].split(" ", 1)[1]}
                )
                socket.receive_json()


def test_the_live_socket_still_serves_the_machine_it_runs_on(app):
    """A local socket gets past the handshake and answers the auth message."""
    app.state.frame_source = FakeSource()
    with TestClient(app, client=LOCAL) as client:
        headers = sign_in(client)
        with client.websocket_connect("/ws/capture") as socket:
            socket.send_json({"type": "auth", "token": headers["Authorization"].split(" ", 1)[1]})
            first = socket.receive_json()
            assert first["type"] in {"auth_ok", "status"}
