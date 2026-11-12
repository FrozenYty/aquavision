"""Messages and alerts (P3-09, FR-M8-02, AC-29).

FR-M8-02 asks for in-app messages on capture failures, job failures and finished reports, with two
rules that matter: the same type and object collapse into one message within an hour, and a message
never blocks the main flow. `sys_message` had a table, a list route and a mark-read route, and
**nothing ever wrote a row** - so the unread count was permanently zero and the page was decorative.

These tests drive the events the requirement names and read the result through the API, because the
unread count is what the operator sees. The dedup assertions all happen inside the hour, so no test
sleeps.
"""

from __future__ import annotations

import base64
import errno
from datetime import UTC, datetime

import cv2
import numpy as np
import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import DetectTask, MediaAsset, SysMessage, SysUser
from app.security import hash_password
from app.seed import seed_species
from app.worker import process_task
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

LOCAL = ("127.0.0.1", 50000)
BOX = {"class_code": "holothurian", "confidence": 0.9, "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}


def _frame(seed: int) -> str:
    image = np.random.default_rng(seed).integers(60, 200, (120, 160, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return base64.b64encode(buffer.tobytes()).decode("ascii")


@pytest.fixture
def rig(tmp_path, monkeypatch):
    """An app with an administrator, frames waiting to be detected, and no background worker."""
    monkeypatch.setenv("DB_DSN", f"sqlite:///{(tmp_path / 'messages.db').as_posix()}")
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'messages.db').as_posix()}")
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    factory = app.state.session_factory
    with factory() as session:
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
        now = datetime.now(UTC).replace(tzinfo=None)
        for index in range(4):
            session.add(
                MediaAsset(
                    frame_id=f"20261112T110000-{index:04d}",
                    session_id="s-messages",
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


def sign_in(client: TestClient) -> dict[str, str]:
    body = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password123"}
    ).json()
    return {"Authorization": f"Bearer {body['data']['token']}"}


def messages(client: TestClient, headers: dict[str, str]) -> tuple[list[dict], int]:
    body = client.get("/api/messages", headers=headers).json()["data"]
    return body["items"], body["unread"]


def broken_disk(monkeypatch) -> None:
    def no_space(*_args, **_kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr("app.routers.capture._write", no_space)


def post_frame(client: TestClient, headers: dict[str, str], seed: int, session_id: str = "s-live"):
    return client.post(
        f"/api/capture/sessions/{session_id}/frames",
        json={"point_code": "A3", "image_b64": _frame(seed)},
        headers=headers,
    ).json()


def test_a_capture_failure_leaves_one_unread_message(rig, monkeypatch):
    client, _factory = rig
    headers = sign_in(client)
    broken_disk(monkeypatch)

    body = post_frame(client, headers, 1)
    assert body["code"] == 50001, body

    items, unread = messages(client, headers)
    assert unread == 1, items
    assert [item["type"] for item in items] == ["capture_failed"]
    assert items[0]["level"] == 2
    assert "采集" in items[0]["title"]


def test_repeated_failures_within_the_hour_add_nothing(rig, monkeypatch):
    """AC-29's second half, and the object matters: a different session is a different message."""
    client, factory = rig
    headers = sign_in(client)
    broken_disk(monkeypatch)

    for seed in (2, 3, 4):
        assert post_frame(client, headers, seed)["code"] == 50001
    items, unread = messages(client, headers)
    assert unread == 1, "the three failures of one session must collapse into one message"
    assert len(items) == 1

    assert post_frame(client, headers, 5, session_id="s-other")["code"] == 50001
    items, unread = messages(client, headers)
    assert unread == 2, "another capture session is another object"

    with factory() as session:
        rows = session.query(SysMessage).all()
        assert len(rows) == 2
        assert len({row.ref_id for row in rows}) == 2


def test_a_failed_detection_task_leaves_one_message(rig):
    """A job failure is the other event FR-M8-02 names."""
    client, factory = rig
    headers = sign_in(client)

    task = client.post("/api/detect/batches", json={"asset_count": 2}, headers=headers).json()
    task_id = task["data"]["task_id"]
    # No detector is loaded in this fixture, which is exactly the failure an operator must hear about.
    process_task(factory, task_id, detector=None)

    items, unread = messages(client, headers)
    assert unread == 1, items
    assert items[0]["type"] == "task_failed"
    assert task["data"]["task_code"] in items[0]["title"] or task["data"]["task_code"] in (
        items[0]["content"] or ""
    )

    # The same task failing again - a retry that fails for the same reason - adds nothing.
    with factory() as session:
        row = session.get(DetectTask, task_id)
        row.status = 0
        session.commit()
    process_task(factory, task_id, detector=None)

    items, unread = messages(client, headers)
    assert unread == 1, "the second failure of the same task must not add a message"


def test_a_finished_report_leaves_a_message(rig):
    """The third event FR-M8-02 names, and it points at a report that really exists."""
    client, _factory = rig
    headers = sign_in(client)

    body = client.post(
        "/api/reports",
        json={
            "period_start": "2026-11-01T00:00:00+08:00",
            "period_end": "2026-11-02T00:00:00+08:00",
            "template": "standard",
            "basis": "reviewed",
        },
        headers=headers,
    ).json()
    assert body["code"] == 0, body

    items, unread = messages(client, headers)
    assert unread == 1, items
    assert [item["type"] for item in items] == ["report_done"]
    assert body["data"]["report_code"] in items[0]["title"]
    assert items[0]["level"] == 1


def test_a_message_is_read_and_the_count_follows(rig, monkeypatch):
    client, _factory = rig
    headers = sign_in(client)
    broken_disk(monkeypatch)
    assert post_frame(client, headers, 6)["code"] == 50001

    items, unread = messages(client, headers)
    assert unread == 1
    read = client.post(f"/api/messages/{items[0]['msg_id']}/read", headers=headers).json()
    assert read["code"] == 0, read
    assert messages(client, headers)[1] == 0


def test_a_failing_message_write_does_not_break_the_request(rig, monkeypatch):
    """FR-M8-02: a message never blocks the main flow."""
    client, _factory = rig
    headers = sign_in(client)
    broken_disk(monkeypatch)

    def exploding(*_args, **_kwargs):
        raise RuntimeError("the message store is gone")

    # `_write` is where the row is made; `notify` is the guard the callers rely on.
    monkeypatch.setattr("app.notify._write", exploding)
    assert post_frame(client, headers, 7)["code"] == 50001
