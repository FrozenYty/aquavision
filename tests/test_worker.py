"""The detection queue consumer (P2-05a).

The worker is exercised against a plain SQLite database, without the HTTP app: the task row is the
queue, so the tests can seed frames and a task, run the consumer, and read the row back. A detector is
injected because P2-05a runs before weights exist; the production worker passes none and fails the
task with a reason rather than inventing boxes.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import DetectObject, DetectTask, MediaAsset, SysUser
from app.routers.tasks import retry_task
from app.seed import seed_species
from app.worker import process_task, requeue_stale, run_once
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def session_factory(tmp_path):
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'worker.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        seed_species(session)
    yield factory
    engine.dispose()


def add_frames(factory: sessionmaker, count: int = 100) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    with factory() as session:
        for index in range(count):
            session.add(
                MediaAsset(
                    frame_id=f"20261110T120000-{index:04d}",
                    session_id="s-worker",
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


def add_task(factory: sessionmaker, asset_count: int = 100, status: int = 0) -> int:
    with factory() as session:
        task = DetectTask(
            task_code=f"DT-{uuid4().hex[:8]}",
            task_type=2,
            asset_count=asset_count,
            status=status,
            progress=0,
            obj_count=0,
        )
        session.add(task)
        session.commit()
        return task.task_id


def task_state(factory: sessionmaker, task_id: int) -> dict:
    with factory() as session:
        row = session.get(DetectTask, task_id)
        return {
            "status": row.status,
            "progress": row.progress,
            "obj_count": row.obj_count,
            "error_msg": row.error_msg,
            "finished_at": row.finished_at,
        }


def count_objects(factory: sessionmaker, task_id: int | None = None) -> int:
    with factory() as session:
        stmt = select(func.count(DetectObject.object_id))
        if task_id is not None:
            stmt = stmt.where(DetectObject.task_id == task_id)
        return session.scalar(stmt) or 0


def one_box(_asset: MediaAsset) -> list[dict]:
    return [
        {
            "class_code": "holothurian",
            "confidence": 0.9,
            "x": 0.1,
            "y": 0.1,
            "w": 0.2,
            "h": 0.2,
        }
    ]


def test_queue_runs_100_frames_to_done(session_factory):
    add_frames(session_factory, 100)
    task_id = add_task(session_factory)
    progress = []

    process_task(session_factory, task_id, detector=one_box, on_progress=progress.append)

    state = task_state(session_factory, task_id)
    assert state["status"] == 2
    assert state["progress"] == 100
    assert state["obj_count"] == 100
    assert len(progress) == 100
    assert progress == sorted(progress)
    assert progress[0] == 1 and progress[-1] == 100
    assert count_objects(session_factory, task_id) == 100


def test_cancel_at_frame_40_stops_within_five_seconds(session_factory):
    add_frames(session_factory, 100)
    task_id = add_task(session_factory)
    calls = 0
    cancelled_at = None

    def detector(asset):
        nonlocal calls, cancelled_at
        calls += 1
        if calls == 40:
            with session_factory() as session:
                row = session.get(DetectTask, task_id)
                row.status = 4
                row.finished_at = datetime.now(UTC).replace(tzinfo=None)
                session.commit()
            cancelled_at = time.monotonic()
        return one_box(asset)

    process_task(session_factory, task_id, detector=detector)

    state = task_state(session_factory, task_id)
    assert state["status"] == 4
    assert state["progress"] == 40
    assert count_objects(session_factory, task_id) == 40
    assert cancelled_at is not None
    assert time.monotonic() - cancelled_at < 5


def test_failure_is_retryable(session_factory):
    add_frames(session_factory, 100)
    task_id = add_task(session_factory)
    calls = 0

    def failing(asset):
        nonlocal calls
        calls += 1
        if calls == 10:
            raise RuntimeError("forced failure")
        return one_box(asset)

    process_task(session_factory, task_id, detector=failing)

    state = task_state(session_factory, task_id)
    assert state["status"] == 3
    assert "forced failure" in (state["error_msg"] or "")
    assert state["obj_count"] == 9
    assert count_objects(session_factory, task_id) == 9

    with session_factory() as session:
        user = SysUser(
            username="worker-test",
            password_hash="x",
            salt="x",
            role_code="admin",
            real_name="Worker Test",
        )
        session.add(user)
        session.commit()
        retry_task(task_id, session, user)

    state = task_state(session_factory, task_id)
    assert state["status"] == 0
    assert state["obj_count"] == 0
    assert count_objects(session_factory, task_id) == 0

    process_task(session_factory, task_id, detector=one_box)
    state = task_state(session_factory, task_id)
    assert state["status"] == 2
    assert state["obj_count"] == 100


def test_restart_requeues_a_running_task_and_reprocesses(session_factory):
    add_frames(session_factory, 100)
    task_id = add_task(session_factory, status=1)
    with session_factory() as session:
        task = session.get(DetectTask, task_id)
        task.progress = 40
        task.obj_count = 40
        asset = session.scalar(select(MediaAsset).order_by(MediaAsset.asset_id).limit(1))
        session.add(
            DetectObject(
                task_id=task_id,
                asset_id=asset.asset_id,
                frame_id=asset.frame_id,
                class_code="holothurian",
                confidence=0.9,
                x=0.1,
                y=0.1,
                w=0.2,
                h=0.2,
                is_manual=0,
                review_status=0,
            )
        )
        session.commit()
    assert count_objects(session_factory, task_id) == 1
    assert requeue_stale(session_factory) == 1

    state = task_state(session_factory, task_id)
    assert state["status"] == 0
    assert state["progress"] == 0
    assert state["obj_count"] == 0
    assert count_objects(session_factory, task_id) == 0

    assert run_once(session_factory, detector=one_box) is True
    state = task_state(session_factory, task_id)
    assert state["status"] == 2
    assert state["obj_count"] == 100
    assert count_objects(session_factory, task_id) == 100


def test_no_detector_fails_with_a_reason(session_factory):
    add_frames(session_factory, 5)
    task_id = add_task(session_factory, asset_count=5)

    process_task(session_factory, task_id, detector=None)

    state = task_state(session_factory, task_id)
    assert state["status"] == 3
    assert state["obj_count"] == 0
    assert "权重" in (state["error_msg"] or "")
    assert count_objects(session_factory, task_id) == 0


def test_run_once_takes_one_queued_task_at_a_time(session_factory):
    add_frames(session_factory, 10)
    first = add_task(session_factory, asset_count=5)
    second = add_task(session_factory, asset_count=5)

    assert run_once(session_factory, detector=one_box) is True
    assert task_state(session_factory, first)["status"] == 2
    assert task_state(session_factory, first)["obj_count"] == 5
    assert task_state(session_factory, second)["status"] == 0

    assert run_once(session_factory, detector=one_box) is True
    assert task_state(session_factory, second)["status"] == 2
    assert task_state(session_factory, second)["obj_count"] == 5

    assert run_once(session_factory, detector=one_box) is False


def test_app_lifespan_starts_and_stops_the_worker(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_DSN", f"sqlite:///{(tmp_path / 'app.db').as_posix()}")
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "1")
    monkeypatch.setenv("AV_WORKER_POLL_SECONDS", "0.05")
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as client:
        assert client.get("/api/health").json()["code"] == 0
        assert app.state.worker is not None
    get_settings.cache_clear()
