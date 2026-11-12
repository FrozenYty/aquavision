"""Runtime monitoring answers what AC-28 asks (P3-09, FR-M8-01).

The route already reported the queue, the disk and the worker (P3-12), and nothing asserted the two
sentences AC-28 actually grades: a large batch **moves the queue figure**, and disk usage past its
threshold **turns the item red with a note**. The failure rate is in the requirement's own acceptance
("submitting a large batch visibly moves queue length and failure rate") and was not reported at all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import DetectTask, MediaAsset, SysUser
from app.security import hash_password
from app.seed import seed_species
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

LOCAL = ("127.0.0.1", 50000)


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_DSN", f"sqlite:///{(tmp_path / 'monitor.db').as_posix()}")
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'monitor.db').as_posix()}")
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
        for index in range(9):
            session.add(
                MediaAsset(
                    frame_id=f"20261112T120000-{index:04d}",
                    session_id="s-monitor",
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


def monitor(client: TestClient, headers: dict[str, str]) -> dict:
    body = client.get("/api/monitor", headers=headers).json()
    assert body["code"] == 0, body
    return body["data"]


def test_a_large_batch_moves_the_queue_figure(rig):
    """Three queued tasks read back as three, then as one running and two queued."""
    client, factory = rig
    headers = sign_in(client)
    assert monitor(client, headers)["queue"] == {"queued": 0, "running": 0}

    tasks = [
        client.post("/api/detect/batches", json={"asset_count": 3}, headers=headers).json()["data"][
            "task_id"
        ]
        for _ in range(3)
    ]
    assert monitor(client, headers)["queue"] == {"queued": 3, "running": 0}

    with factory() as session:
        session.get(DetectTask, tasks[0]).status = 1
        session.commit()
    assert monitor(client, headers)["queue"] == {"queued": 2, "running": 1}


def test_disk_past_its_threshold_turns_the_item_red_with_a_note(rig, monkeypatch):
    client, _factory = rig
    headers = sign_in(client)

    def usage(percent: float):
        total = 100 * 1024**3
        return SimpleNamespace(used=int(total * percent / 100), total=int(total), free=0)

    for percent, level in ((10.0, "ok"), (80.0, "warn"), (95.0, "crit")):
        monkeypatch.setattr("app.routers.system.shutil.disk_usage", lambda *_a, p=percent: usage(p))
        disk = monitor(client, headers)["disk"]
        assert disk["percent"] == percent, disk
        assert disk["level"] == level, disk
        if level == "ok":
            assert not disk.get("note"), disk
        else:
            assert "95" in disk["note"] or f"{percent:g}" in disk["note"], disk


def test_the_failure_rate_follows_the_task_rows(rig):
    """The requirement's acceptance names it: a batch moves queue length and failure rate."""
    client, factory = rig
    headers = sign_in(client)
    assert monitor(client, headers)["failure_rate"] == 0.0

    ids = [
        client.post("/api/detect/batches", json={"asset_count": 1}, headers=headers).json()["data"][
            "task_id"
        ]
        for _ in range(2)
    ]
    with factory() as session:
        session.get(DetectTask, ids[0]).status = 2  # done
        session.get(DetectTask, ids[1]).status = 3  # failed
        session.commit()
    assert monitor(client, headers)["failure_rate"] == 50.0

    with factory() as session:
        queued = session.scalar(select(DetectTask).where(DetectTask.status == 0))
        assert queued is None, "the fixture should have exactly the two finished tasks"
