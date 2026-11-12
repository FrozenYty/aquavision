"""P3-12: the three failures an operator must be able to act on, reproduced without hardware.

Each test forces one of the states this task names - the database unreachable, the data directory
unable to take a frame, the detection worker gone while rows still say work is happening - and asserts
what the API says. The assertions read the message, not only the code: a reply of "服务器内部错误" for
a full disk is exactly the state this task removes, and a code-only assertion would not notice it.

The replies must be the project's own envelope (`code`/`message`/`data`/`request_id`) with a Chinese
message that names the cause and the next action; no test here introduces a second error shape.
"""

from __future__ import annotations

import base64
import errno

import cv2
import numpy as np
import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import DetectTask, SysUser
from app.security import hash_password
from app.worker import Worker
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client(tmp_path, monkeypatch):
    """An app over a throwaway database, detection worker off, with the one account requests need."""
    dsn = f"sqlite:///{(tmp_path / 'failure.db').as_posix()}"
    monkeypatch.setenv("DB_DSN", dsn)
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    engine = engine_from_dsn(dsn)
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    factory = app.state.session_factory
    with factory() as session:
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

    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def sign_in(client: TestClient) -> str:
    body = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password123"}
    ).json()
    assert body["code"] == 0, body
    return body["data"]["token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def a_frame(seed: int = 0) -> str:
    """A sharp, textured JPEG, base64 encoded; the seed makes two frames differ (dedup is by hash)."""
    image = np.random.default_rng(seed).integers(0, 255, (120, 160, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return base64.b64encode(buffer.tobytes()).decode("ascii")


def post_frame(client: TestClient, token: str) -> dict:
    return client.post(
        "/api/capture/sessions/s-failure/frames",
        json={"point_code": "A3", "image_b64": a_frame()},
        headers=auth(token),
    ).json()


# ---- 1. The database is unreachable -------------------------------------------------------------


def test_an_unreachable_database_answers_with_an_actionable_message(client, tmp_path):
    """A file where the database's directory should be: sqlite cannot open a database behind it."""
    token = sign_in(client)
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")
    broken = engine_from_dsn(f"sqlite:///{(blocker / 'app.db').as_posix()}")
    client.app.state.engine = broken
    client.app.state.session_factory = sessionmaker(
        bind=broken, autoflush=False, expire_on_commit=False
    )
    try:
        response = client.get("/api/frames", headers=auth(token))
    finally:
        broken.dispose()

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == 50001
    assert body["data"] is None
    assert "数据库无法连接" in body["message"]
    assert "DB_DSN" in body["message"], "the message must name the setting the operator can fix"
    assert body["request_id"].startswith("req-")


# ---- 2. The data directory cannot take the frame ------------------------------------------------


def test_a_full_disk_says_the_frame_could_not_be_stored(client, monkeypatch):
    token = sign_in(client)

    def no_space(*_args, **_kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr("app.routers.capture._write", no_space)
    body = post_frame(client, token)

    assert body["code"] == 50001
    assert "磁盘空间不足" in body["message"]
    assert "未能保存" in body["message"]
    assert "没有入库" in body["message"]
    assert body["data"] is None
    # The frame was not stored, so the API must not claim one exists.
    assert client.get("/api/frames", headers=auth(token)).json()["data"]["total"] == 0


def test_an_unwritable_data_root_names_the_permission(client, monkeypatch):
    token = sign_in(client)

    def denied(*_args, **_kwargs):
        raise OSError(errno.EACCES, "Permission denied")

    monkeypatch.setattr("app.routers.capture._write", denied)
    body = post_frame(client, token)

    assert body["code"] == 50001
    assert "数据目录不可写" in body["message"]
    assert "AV_DATA_DIR" in body["message"], "the message must name the setting to check"
    assert client.get("/api/frames", headers=auth(token)).json()["data"]["total"] == 0


def test_a_write_that_reports_failure_is_not_recorded_as_stored(client, monkeypatch):
    """OpenCV reports a failed write with False rather than an exception; that must not become a row."""
    token = sign_in(client)
    monkeypatch.setattr("app.routers.capture.cv2.imwrite", lambda *_args, **_kwargs: False)
    body = post_frame(client, token)

    assert body["code"] == 50001
    assert "未能保存" in body["message"]
    assert "没有入库" in body["message"]
    assert client.get("/api/frames", headers=auth(token)).json()["data"]["total"] == 0


# ---- 3. The detection worker is gone ------------------------------------------------------------


def _seed_blocked_tasks(client: TestClient) -> None:
    """One task still 'running' and one queued, the way a killed worker leaves the rows behind."""
    factory = client.app.state.session_factory
    with factory() as session:
        session.add(
            DetectTask(
                task_code="DT-DEAD-0001",
                task_type=2,
                asset_count=3,
                status=1,  # running
                progress=40,
            )
        )
        session.add(
            DetectTask(
                task_code="DT-DEAD-0002",
                task_type=2,
                asset_count=2,
                status=0,  # queued
                progress=0,
            )
        )
        session.commit()


def test_a_dead_worker_is_reported_with_the_tasks_it_is_not_advancing(client):
    token = sign_in(client)
    # A worker that was started and then stopped, as a killed pool leaves the process: the rows still
    # say work is happening, and nothing will advance them.
    worker = Worker(client.app.state.session_factory, workers=1, poll_seconds=60.0)
    worker.start()
    client.app.state.worker_enabled = True
    client.app.state.worker = worker
    healthy = client.get("/api/monitor", headers=auth(token)).json()["data"]
    assert healthy["worker"]["alive"] is True
    assert healthy["worker"]["problem"] is None
    worker.stop()

    _seed_blocked_tasks(client)
    body = client.get("/api/monitor", headers=auth(token)).json()
    assert body["code"] == 0
    monitor = body["data"]
    assert monitor["queue"] == {"queued": 1, "running": 1}
    assert monitor["worker"]["enabled"] is True
    assert monitor["worker"]["alive"] is False
    problem = monitor["worker"]["problem"]
    assert "检测线程已停止" in problem
    assert "1 个任务排队" in problem and "1 个任务停在运行中" in problem
    assert "不会推进" in problem and "重启服务" in problem


def test_a_disabled_worker_is_named_as_the_cause(client):
    token = sign_in(client)
    _seed_blocked_tasks(client)
    monitor = client.get("/api/monitor", headers=auth(token)).json()["data"]
    worker = monitor["worker"]
    assert worker["enabled"] is False
    assert worker["alive"] is False
    assert "AV_WORKER_ENABLED" in worker["problem"]
    assert "不会推进" in worker["problem"]
