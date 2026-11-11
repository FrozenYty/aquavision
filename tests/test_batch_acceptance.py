"""P3-01's acceptance, exercised through the API rather than through the database.

The worker's own tests (`tests/test_worker.py`) read the task row back after the run. `P3-01` says three
things that are not the same statement:

1. a 100-frame task completes — covered here end to end;
2. progress is **queryable while it runs** — nothing covered this: every existing check either read the
   database directly or looked only at the final state, so a route that stopped returning progress
   mid-flight would have passed every test in the suite;
3. a restart mid-task **resumes it rather than losing it** — covered at unit level by
   `test_worker.py::test_restart_resumes_and_keeps_the_frames_already_finished`, which stops a run
   after forty frames. Here the interruption is produced by stopping a real run, and the restart is
   the real `Worker.start()`, which is what the application calls on boot.

The detector is a slow stub on purpose: the point is to poll the API while the task is genuinely in
flight, and a detector that returns instantly would finish before the first poll.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import MediaAsset, SysUser
from app.security import hash_password
from app.seed import seed_species
from app.worker import Worker, process_task
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

FRAMES = 100
#: Slow enough that a poll lands mid-run, fast enough that the whole file stays a few seconds.
FRAME_SECONDS = 0.015
#: The frame a task is expected to reach before an interruption counts as "mid-task".
INTERRUPT_AFTER = 5


@pytest.fixture
def rig(tmp_path, monkeypatch):
    """An app over a throwaway database, plus frames waiting to be detected.

    `AV_WORKER_ENABLED=0` keeps the application's own pool out of the way: these tests need a worker
    whose detector is slow and whose lifetime they control.
    """
    dsn = f"sqlite:///{(tmp_path / 'batch.db').as_posix()}"
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
        for index in range(FRAMES):
            session.add(
                MediaAsset(
                    frame_id=f"20261111T090000-{index:04d}",
                    session_id="s-batch",
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

    with TestClient(app) as client:
        yield client, factory
    get_settings.cache_clear()


def sign_in(client: TestClient) -> dict[str, str]:
    body = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password123"}
    ).json()
    return {"Authorization": f"Bearer {body['data']['token']}"}


def slow_detector(_asset: MediaAsset) -> list[dict]:
    """One box per frame, slowly. A stub, because P3-01 is about the queue, not about the weights."""
    time.sleep(FRAME_SECONDS)
    return [
        {"class_code": "holothurian", "confidence": 0.9, "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    ]


def create_batch(client: TestClient, headers: dict[str, str]) -> int:
    body = client.post("/api/detect/batches", json={"asset_count": FRAMES}, headers=headers).json()
    assert body["code"] == 0, body
    assert body["data"]["status"] == "queued"
    return body["data"]["task_id"]


def task_now(client: TestClient, headers: dict[str, str], task_id: int) -> dict:
    return client.get(f"/api/tasks/{task_id}", headers=headers).json()["data"]


def poll_until(client: TestClient, headers: dict[str, str], task_id: int, predicate, timeout=30.0):
    """Poll the API for a task state, recording every reading so a failure can show the series."""
    seen: list[tuple[str, int]] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = task_now(client, headers, task_id)
        seen.append((body["status"], body["progress"]))
        if predicate(body):
            return body, seen
        time.sleep(0.05)
    return None, seen


def test_progress_is_queryable_while_a_batch_task_runs(rig):
    """The route answers with a real, moving progress figure while the task is mid-flight."""
    client, factory = rig
    headers = sign_in(client)
    task_id = create_batch(client, headers)

    worker = Worker(factory, workers=1, poll_seconds=0.05, detector=slow_detector)
    worker.start()
    try:
        final, seen = poll_until(client, headers, task_id, lambda body: body["status"] == "done")
    finally:
        worker.stop()

    assert final is not None, f"the task never finished; last readings {seen[-8:]}"
    running = [progress for status, progress in seen if status == "running"]
    assert running, f"the API never reported the task as running; readings {seen[:8]}"
    mid_flight = [progress for progress in running if 0 < progress < 100]
    assert mid_flight, f"progress was never visible mid-run, only these readings {seen[:12]}"
    # Monotonic, because a progress bar that goes backwards is worse than one that lags.
    assert running == sorted(running), f"progress went backwards: {running}"


def test_a_restart_mid_task_resumes_it_instead_of_losing_it(rig):
    """One run is cut short, then the boot path is run: the task finishes rather than being stranded."""
    client, factory = rig
    headers = sign_in(client)
    task_id = create_batch(client, headers)

    # A run that stops itself part-way: this is what a process killed mid-task leaves behind.
    stop = threading.Event()

    def run_until_stopped() -> None:
        process_task(
            factory,
            task_id,
            detector=slow_detector,
            should_stop=lambda: stop.is_set(),
        )

    runner = threading.Thread(target=run_until_stopped, name="interrupted-run", daemon=True)
    runner.start()
    try:
        _, seen = poll_until(
            client,
            headers,
            task_id,
            lambda body: body["status"] == "running" and body["progress"] >= INTERRUPT_AFTER,
            timeout=20.0,
        )
        stop.set()
    finally:
        runner.join(timeout=20)
    assert not runner.is_alive(), "the interrupted run did not stop"

    # The row survived the crash, with the progress it had reached — it is not lost and not stranded at
    # zero, which is the failure P3-01 asks to be ruled out.
    stranded = task_now(client, headers, task_id)
    assert stranded["status"] == "running", f"expected a stale running row, got {stranded}"
    assert 0 < stranded["progress"] < 100, f"the interrupted task lost its progress: {stranded}"

    # The restart is the real boot path: Worker.start() calls requeue_stale() first.
    worker = Worker(factory, workers=1, poll_seconds=0.05, detector=slow_detector)
    worker.start()
    try:
        resumed, _ = poll_until(client, headers, task_id, lambda body: body["status"] == "done")
    finally:
        worker.stop()

    assert resumed is not None, (
        f"the task was not resumed after the restart: {task_now(client, headers, task_id)}"
    )
    assert resumed["progress"] == 100
    # Every frame was processed exactly once: the finished items kept their boxes and only the
    # pending ones ran after the restart.
    assert resumed["obj_count"] == FRAMES, f"expected one box per frame, got {resumed['obj_count']}"
