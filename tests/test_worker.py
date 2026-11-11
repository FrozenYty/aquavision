"""The detection queue consumer (P2-05a).

The worker is exercised against a plain SQLite database, without the HTTP app: the task row is the
queue, and a task owns its frames through `detect_task_item` (ADR 12), so the tests seed frames, create
a task through `create_batch`, run the consumer, and read the rows back. A detector is injected because
P2-05a runs before weights exist; the production worker passes none and fails the task with a reason
rather than inventing boxes.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import DetectObject, DetectTask, DetectTaskItem, MediaAsset, SysUser
from app.routers.tasks import BatchBody, create_batch, retry_task
from app.seed import seed_species
from app.worker import ITEM_DONE, process_task, requeue_stale, run_once
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


def add_task(factory: sessionmaker, asset_count: int = 100) -> int:
    """Create a task through the real entry point, so it owns the frames it will run (ADR 12)."""
    with factory() as session:
        return create_batch(session, BatchBody(asset_count=asset_count)).task_id


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


def asset_ids(factory: sessionmaker) -> set[int]:
    """Every frame in the database; a test explains a task's share by subtracting from this."""
    with factory() as session:
        return set(session.scalars(select(MediaAsset.asset_id)))


def item_assets(factory: sessionmaker, task_id: int) -> set[int]:
    """The frames a task owns, which is the item rows rather than whatever boxes exist."""
    with factory() as session:
        return set(
            session.scalars(
                select(DetectTaskItem.asset_id).where(DetectTaskItem.task_id == task_id)
            )
        )


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


def no_boxes(_asset: MediaAsset) -> list[dict]:
    return []


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


def test_a_frame_with_no_boxes_finishes_and_is_not_queued_again(session_factory):
    """Zero boxes is a result, not the absence of one: the frame is done and the next task skips it."""
    add_frames(session_factory, 10)
    first = add_task(session_factory, asset_count=5)
    process_task(session_factory, first, detector=no_boxes)

    state = task_state(session_factory, first)
    assert state["status"] == 2
    assert state["progress"] == 100
    assert state["obj_count"] == 0
    assert count_objects(session_factory, first) == 0

    with session_factory() as session:
        items = list(session.scalars(select(DetectTaskItem).where(DetectTaskItem.task_id == first)))
    assert {item.state for item in items} == {ITEM_DONE}
    assert {item.box_count for item in items} == {0}

    second = add_task(session_factory, asset_count=5)
    assert item_assets(session_factory, first).isdisjoint(item_assets(session_factory, second))
    assert item_assets(session_factory, first) | item_assets(session_factory, second) == asset_ids(
        session_factory
    )


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


def test_restart_resumes_and_keeps_the_frames_already_finished(session_factory):
    """A crash leaves done items done; the resumed task continues instead of restarting (ADR 12)."""
    add_frames(session_factory, 100)
    task_id = add_task(session_factory)
    calls = {"n": 0}

    def detector(asset):
        calls["n"] += 1
        return one_box(asset)

    # Stop the first run after forty frames: the row a killed process leaves behind.
    process_task(session_factory, task_id, detector=detector, should_stop=lambda: calls["n"] >= 40)
    state = task_state(session_factory, task_id)
    assert state["status"] == 1
    assert state["progress"] == 40
    assert state["obj_count"] == 40
    assert count_objects(session_factory, task_id) == 40

    # A crash can also land after an item was claimed but before it finished; that one is not done.
    with session_factory() as session:
        interrupted = session.scalar(
            select(DetectTaskItem)
            .where(DetectTaskItem.task_id == task_id, DetectTaskItem.state == 0)
            .order_by(DetectTaskItem.item_id)
            .limit(1)
        )
        interrupted.state = 1
        interrupted.claimed_at = datetime.now(UTC).replace(tzinfo=None)
        session.commit()

    assert requeue_stale(session_factory) == 1
    state = task_state(session_factory, task_id)
    assert state["status"] == 0
    assert state["progress"] == 40
    assert state["obj_count"] == 40
    assert count_objects(session_factory, task_id) == 40

    assert run_once(session_factory, detector=one_box) is True
    state = task_state(session_factory, task_id)
    assert state["status"] == 2
    assert state["progress"] == 100
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


def test_a_task_runs_with_its_own_inference_parameters(session_factory):
    """The batch row carries conf/iou/max_det; the worker must hand them to the model."""
    add_frames(session_factory, 1)
    task_id = add_task(session_factory, asset_count=1)
    with session_factory() as session:
        task = session.get(DetectTask, task_id)
        task.conf_thr = 0.7
        task.iou_thr = 0.5
        task.max_det = 42
        session.commit()

    seen: dict = {}

    class RecordingDetector:
        def predict(self, asset, conf_thr=0.5, iou_thr=0.45, max_det=100):
            seen.update(conf_thr=conf_thr, iou_thr=iou_thr, max_det=max_det)
            return one_box(asset)

    process_task(session_factory, task_id, detector=RecordingDetector())

    assert seen == {"conf_thr": 0.7, "iou_thr": 0.5, "max_det": 42}
    assert task_state(session_factory, task_id)["status"] == 2


def test_a_missing_model_uses_the_loaders_reason(session_factory):
    """No detector: the task fails with the sentence the loader produced, not with a guess."""
    add_frames(session_factory, 2)
    task_id = add_task(session_factory, asset_count=2)

    process_task(session_factory, task_id, detector=None, reason="运行环境缺少推理依赖 torch")

    state = task_state(session_factory, task_id)
    assert state["status"] == 3
    assert "torch" in (state["error_msg"] or "")
    assert state["obj_count"] == 0


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
