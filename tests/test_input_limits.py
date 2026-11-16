"""Upload and input limits on the capture path (P3-26).

The capture route wrote whatever bytes arrived into a path built partly from request values, and no
maximum was stated anywhere: a client could post a hundred-megabyte body, an image of any size, or a
"point code" of `../../etc` and the server would happily build the path and write the file. Each of the
four inputs below is refused with the project envelope - a 400 with a sentence naming the limit, not an
acceptance and not a 500 - and each refusal leaves nothing behind: no row, no file.

The numbers are declared in `server/app/routers/capture.py` once, next to the reason for them, and
stated in the contract so a client author can read them.
"""

from __future__ import annotations

import base64

import cv2
import numpy as np
import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.envelope import BAD_PARAM
from app.models import MediaAsset, SysUser
from app.security import hash_password
from app.seed import seed_species
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

LOCAL = ("127.0.0.1", 50000)


def jpeg(width: int, height: int, seed: int = 1) -> str:
    image = np.random.default_rng(seed).integers(40, 220, (height, width, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert ok
    return base64.b64encode(buffer.tobytes()).decode("ascii")


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_DSN", f"sqlite:///{(tmp_path / 'limits.db').as_posix()}")
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'limits.db').as_posix()}")
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with app.state.session_factory() as session:
        seed_species(session)
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

    with TestClient(app, client=LOCAL) as client:
        yield client, app, tmp_path
    get_settings.cache_clear()


def sign_in(client: TestClient) -> dict[str, str]:
    body = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password123"}
    ).json()
    return {"Authorization": f"Bearer {body['data']['token']}"}


def post(client: TestClient, headers, *, image: str, point_code: str = "A3", session: str = "s-1"):
    return client.post(
        f"/api/capture/sessions/{session}/frames",
        json={"point_code": point_code, "image_b64": image},
        headers=headers,
    )


def frames_on_disk(root) -> list:
    data = root / "data"
    return sorted(path for path in data.rglob("*.jpg")) if data.exists() else []


def assert_refused(response, word: str) -> None:
    body = response.json()
    assert response.status_code == 400, body
    assert body["code"] == BAD_PARAM, body
    assert word in body["message"], body


def test_a_frame_above_the_declared_size_is_refused(rig, monkeypatch):
    """The declared byte ceiling, exercised at the boundary by shrinking it (the value is a constant)."""
    client, app, root = rig
    headers = sign_in(client)
    monkeypatch.setattr("app.routers.capture.MAX_FRAME_BYTES", 2048)

    assert_refused(post(client, headers, image=jpeg(640, 480)), "大小")


def test_an_image_beyond_the_declared_dimensions_is_refused(rig):
    """The pipeline declares 1080p (the SRS's acquisition chain); a bigger image is a client mistake."""
    client, app, root = rig
    headers = sign_in(client)

    response = post(client, headers, image=jpeg(2000, 1100))
    assert_refused(response, "尺寸")
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(MediaAsset)) == 0
    assert frames_on_disk(root) == []


def test_a_body_above_the_declared_maximum_is_refused_before_it_is_parsed(rig):
    client, app, root = rig
    headers = sign_in(client)

    huge = "A" * (9 * 1024 * 1024)
    response = client.post(
        "/api/capture/sessions/s-1/frames",
        json={"point_code": "A3", "image_b64": huge},
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert response.json()["code"] == BAD_PARAM
    assert "请求体" in response.json()["message"], response.json()
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(MediaAsset)) == 0


@pytest.mark.parametrize("name", ["../escape", "a/b", "a\\b", ".."])
def test_a_name_carrying_a_traversal_is_refused(rig, name):
    """The point code and the session id end up in a path; neither may carry `..` or a separator."""
    client, app, root = rig
    headers = sign_in(client)

    assert_refused(post(client, headers, image=jpeg(320, 240), point_code=name), "名称")
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(MediaAsset)) == 0
    assert frames_on_disk(root) == []


# `a%2Fb` is not in this list on purpose: the client and the router both decode it before routing, so
# the request never reaches the handler with a slash in the session id. A backslash does arrive.
@pytest.mark.parametrize("encoded", ["..%2E", "a%5Cb"])
def test_a_session_id_carrying_a_traversal_is_refused(rig, encoded):
    """A separator has to arrive percent-encoded to survive routing; it still must not reach the path."""
    client, app, root = rig
    headers = sign_in(client)

    response = client.post(
        f"/api/capture/sessions/{encoded}/frames",
        json={"point_code": "A3", "image_b64": jpeg(320, 240)},
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert response.json()["code"] == BAD_PARAM
    assert "会话编号" in response.json()["message"], response.json()
    assert frames_on_disk(root) == []


def test_a_legitimate_frame_still_passes(rig):
    """The limits must cost the capture page nothing: a 1280x720 frame is well inside all of them."""
    client, app, root = rig
    headers = sign_in(client)

    response = post(client, headers, image=jpeg(1280, 720))
    body = response.json()
    assert response.status_code == 200, body
    assert body["code"] == 0, body
    assert body["data"]["width"] == 1280
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(MediaAsset)) == 1
    assert len(frames_on_disk(root)) == 1
