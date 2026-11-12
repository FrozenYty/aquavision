"""A parameter changed at the page takes effect in the running process (P3-19, AC-27, ADR 15).

The audit's finding was not a missing route: `PATCH /api/params` writes `sys_param` and an audit row,
and always has. The defect was that **nothing read the table** — the consumers used `Settings`, loaded
once at process start — so the operator edited a copy nobody consulted, and AC-27's "a new concurrency
limit constrains new jobs" was false without any test noticing.

Every test here fails against that behaviour: the pool test because a freed thread claims a task the
lowered limit forbids, the application test because the app's own pool does the same, the capture test
because the verdict comes from the start-up settings, and the range tests because nothing enforced a
range at all.
"""

from __future__ import annotations

import base64
import threading
import time
from datetime import UTC, datetime

import cv2
import numpy as np
import pytest
from app import params
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.envelope import MISSING_PARAM
from app.models import DetectTask, MediaAsset, SysLog, SysParam, SysUser
from app.security import hash_password
from app.seed import seed_species
from app.worker import Worker
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

FRAMES = 24
PER_TASK = 4
POLL = 0.05
BOX = {"class_code": "holothurian", "confidence": 0.9, "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}


def _app_rig(tmp_path, monkeypatch, *, worker_enabled: str):
    """An app over a throwaway database, with an admin account and frames waiting to be detected."""
    dsn = f"sqlite:///{(tmp_path / 'params.db').as_posix()}"
    monkeypatch.setenv("DB_DSN", dsn)
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", worker_enabled)
    monkeypatch.setenv("AV_WORKER_POLL_SECONDS", str(POLL))
    get_settings.cache_clear()
    params.forget()

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
                    frame_id=f"20261112T090000-{index:04d}",
                    session_id="s-params",
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
    return app, factory


@pytest.fixture
def rig(tmp_path, monkeypatch):
    app, factory = _app_rig(tmp_path, monkeypatch, worker_enabled="0")
    with TestClient(app) as client:
        yield client, factory
    get_settings.cache_clear()
    params.forget()


def sign_in(client: TestClient) -> dict[str, str]:
    body = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password123"}
    ).json()
    return {"Authorization": f"Bearer {body['data']['token']}"}


def create_batch(client: TestClient, headers: dict[str, str], count: int = PER_TASK) -> int:
    body = client.post("/api/detect/batches", json={"asset_count": count}, headers=headers).json()
    assert body["code"] == 0, body
    return body["data"]["task_id"]


def _running(factory: sessionmaker) -> set[int]:
    with factory() as session:
        return set(session.scalars(select(DetectTask.task_id).where(DetectTask.status == 1)))


def wait_until(predicate, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(POLL)
    return False


class ParkedDetector:
    """Every frame waits for `release`, then a short, finite inference.

    Parking the first tasks is what makes "how many run at once" observable at a moment of our
    choosing instead of at the speed of the machine.
    """

    def __init__(self, release: threading.Event, seconds: float = 0.15):
        self.release = release
        self.seconds = seconds

    def __call__(self, _asset: MediaAsset) -> list[dict]:
        self.release.wait(timeout=30)
        time.sleep(self.seconds)
        return [dict(BOX)]


def _effective(factory: sessionmaker, key: str) -> int:
    return params.effective(factory, key, get_settings())


def test_a_limit_changed_at_the_page_binds_the_claims_that_follow(rig):
    """AC-27: a new limit constrains the jobs created after it, and leaves running work alone."""
    client, factory = rig
    headers = sign_in(client)

    before = create_batch(client, headers)
    running = create_batch(client, headers)
    release = threading.Event()
    worker = Worker(
        factory,
        workers=2,
        poll_seconds=POLL,
        detector=ParkedDetector(release),
        limit=lambda: _effective(factory, "max_concurrency"),
    )
    worker.start()
    try:
        assert wait_until(lambda: _running(factory) == {before, running}), (
            f"the two tasks created under the old limit did not both start: {_running(factory)}"
        )

        # The change happens while those two are parked, and three more tasks are created after it.
        body = client.patch("/api/params", json={"max_concurrency": 1}, headers=headers).json()
        assert body["code"] == 0, body
        after = [create_batch(client, headers) for _ in range(3)]
        # The accessor caches for its TTL; the operator's own delay between the click and the
        # observation is at least this long.
        time.sleep(params.CACHE_TTL_SECONDS + 0.3)

        release.set()
        # Those two finish at whatever concurrency they started with; the limit below applies to the
        # queue behind them. Measuring from here is what keeps the two statements apart.
        assert wait_until(lambda: not _running(factory) & {before, running}), (
            "the change interrupted work that was already running"
        )

        most, seen = 0, set()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            ids = _running(factory)
            most = max(most, len(ids))
            seen |= ids
            time.sleep(POLL)
    finally:
        worker.stop()

    assert most <= 1, f"{most} tasks ran at once under a limit of 1"
    assert len(seen) >= 2, f"the queue behind the change never moved: {sorted(seen)}"
    assert set(seen) <= set(after), (
        f"a task created before the change ran under the new limit: {seen}"
    )

    with factory() as session:
        assert session.get(DetectTask, before).status == 2, (
            "a task running when the limit changed failed"
        )
        assert session.get(DetectTask, running).status == 2
        # TC-SYS-01's other half: the change is in the audit log with both values.
        log = session.scalar(select(SysLog).where(SysLog.target_id == "max_concurrency"))
        assert log is not None and log.before_value == "2" and log.after_value == "1"


def test_the_applications_own_worker_obeys_the_limit_at_claim_time(tmp_path, monkeypatch):
    """The wiring in `main.py`, not a hand-built pool: the app's worker must read the same value."""
    app, factory = _app_rig(tmp_path, monkeypatch, worker_enabled="1")
    with factory() as session:
        session.add(SysParam(param_key="max_concurrency", param_value="1", value_type="int"))
        session.commit()

    with TestClient(app):
        # Inserted after start-up, so `requeue_stale` does not undo the running one.
        with factory() as session:
            session.add(
                DetectTask(task_code="DT-T-001", task_type=2, asset_count=1, status=1, progress=10)
            )
            session.add(
                DetectTask(task_code="DT-T-002", task_type=2, asset_count=1, status=0, progress=0)
            )
            session.commit()

        time.sleep(0.6)  # many poll cycles
        with factory() as session:
            queued = session.scalar(select(DetectTask).where(DetectTask.task_code == "DT-T-002"))
            assert queued.status == 0, (
                "the application's pool claimed a task while the limit of 1 was already running one"
            )
    get_settings.cache_clear()
    params.forget()


def test_the_effective_value_comes_from_the_database_and_the_cache_expires(rig, monkeypatch):
    client, factory = rig
    monkeypatch.setattr(params, "CACHE_TTL_SECONDS", 0.2)
    params.forget()
    settings_default = get_settings().max_concurrency

    with factory() as session:
        session.add(SysParam(param_key="max_concurrency", param_value="5", value_type="int"))
        session.commit()
    assert _effective(factory, "max_concurrency") == 5, "the row was not read"

    with factory() as session:
        row = session.scalar(select(SysParam).where(SysParam.param_key == "max_concurrency"))
        row.param_value = "6"
        session.commit()
    assert _effective(factory, "max_concurrency") == 5, "the value was not cached for its TTL"

    time.sleep(0.3)
    assert _effective(factory, "max_concurrency") == 6, "the cache outlived its TTL"

    with factory() as session:
        session.execute(SysParam.__table__.delete())
        session.commit()
    time.sleep(0.3)
    assert _effective(factory, "max_concurrency") == settings_default, (
        "a removed row did not fall back to the configured default"
    )


def test_an_out_of_range_value_is_refused_at_the_page(rig):
    client, factory = rig
    headers = sign_in(client)

    for payload in (
        {"max_concurrency": 0},
        {"max_concurrency": 33},
        {"retention_days": 0},
        {"quality_threshold": 101},
        {"camera_index": 10},
    ):
        body = client.patch("/api/params", json=payload, headers=headers).json()
        assert body["code"] == MISSING_PARAM, f"{payload} was accepted: {body}"

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(SysParam)) == 0
        assert (
            session.scalar(
                select(func.count()).select_from(SysLog).where(SysLog.action == "config")
            )
            == 0
        )


def test_a_stored_value_outside_its_range_is_ignored_not_obeyed(rig):
    """A row written by hand, or under an older range, must not stop the queue."""
    _client, factory = rig
    params.forget()

    with factory() as session:
        session.add(SysParam(param_key="max_concurrency", param_value="0", value_type="int"))
        session.commit()

    assert _effective(factory, "max_concurrency") == get_settings().max_concurrency


def _frame(seed: int) -> str:
    rng = np.random.default_rng(seed)
    image = rng.integers(60, 200, size=(240, 320, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return base64.b64encode(buffer.tobytes()).decode()


def test_the_capture_verdict_uses_the_threshold_in_force(rig):
    client, factory = rig
    headers = sign_in(client)
    session_id = client.post("/api/capture/sessions", headers=headers).json()["data"]["session_id"]

    first = client.post(
        f"/api/capture/sessions/{session_id}/frames",
        json={"point_code": "A3", "image_b64": _frame(1)},
        headers=headers,
    ).json()
    assert first["code"] == 0, first
    assert first["data"]["quality"]["verdict"] == "ok"

    body = client.patch("/api/params", json={"quality_threshold": 100}, headers=headers).json()
    assert body["code"] == 0, body
    # The TTL delay is exercised once, in the effective-value test; here the question is which
    # threshold the route consults, not how long it takes to notice.
    params.forget()

    second = client.post(
        f"/api/capture/sessions/{session_id}/frames",
        json={"point_code": "A3", "image_b64": _frame(2)},
        headers=headers,
    ).json()
    assert second["code"] == 0, second
    assert second["data"]["quality"]["score"] < 100
    assert second["data"]["quality"]["verdict"] == "retake", (
        "the verdict came from the start-up setting, not from the threshold in force"
    )


def test_the_camera_is_asked_for_by_the_index_in_force(rig, monkeypatch):
    client, _factory = rig
    headers = sign_in(client)

    body = client.patch("/api/params", json={"camera_index": 3}, headers=headers).json()
    assert body["code"] == 0, body
    params.forget()

    from app.vision import capture as capture_module

    opened: list[int] = []

    class Recorder:
        def __init__(self, index: int = 0, **_kwargs):
            opened.append(index)

        def open(self) -> None:
            raise capture_module.CaptureError("there is no camera in a test")

    monkeypatch.setattr(capture_module, "CameraSource", Recorder)
    assert client.get("/api/cameras", headers=headers).json()["code"] == 0
    assert opened == [3], f"the route opened camera {opened}, not the index in force"


def test_the_live_socket_defaults_its_interval_to_the_parameter(rig):
    from app.routers.live import _StartConfig

    client, factory = rig
    headers = sign_in(client)
    body = client.patch("/api/params", json={"detect_interval_ms": 750}, headers=headers).json()
    assert body["code"] == 0, body
    params.forget()

    config = _StartConfig.from_message(
        {}, default_interval=_effective(factory, "detect_interval_ms")
    )
    assert config.detect_interval_ms == 750
