"""The `/ws/capture` server (P2-08, api-contract §7 and §8).

The client half and the contract's text checks already exist (`web/static/js/live.js`,
`tests/test_live_socket.py`). These tests drive the server: the handshake and its two close codes, the
frame unit's adjacency, detection correlated by `frame_id`, §8's stale rule, `status`, and the
no-camera close. The frame source and the detector are injected, so nothing here needs a camera or a
weight file.
"""

from __future__ import annotations

import json
import threading
import time

import numpy as np
import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import SysUser
from app.routers import live
from app.security import hash_password
from app.vision.capture import CaptureError
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from starlette.websockets import WebSocketDisconnect

BOX = {
    "class_code": "holothurian",
    "confidence": 0.9,
    "x": 0.1,
    "y": 0.1,
    "w": 0.2,
    "h": 0.2,
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    dsn = f"sqlite:///{(tmp_path / 'live.db').as_posix()}"
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

    # The capture routes accept only the local machine (FR-M1-02, P3-20), so this client says
    # where it is instead of relying on the test runner's default address.
    with TestClient(app, client=("127.0.0.1", 50000)) as test_client:
        yield test_client
    get_settings.cache_clear()


def sign_in(client: TestClient) -> str:
    body = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password123"}
    ).json()
    assert body["code"] == 0, body
    return body["data"]["token"]


class FakeSource:
    """A camera that is always attached; the tests need no hardware."""

    def __init__(self) -> None:
        self.opened = False
        self.closed = False

    def open(self) -> None:
        self.opened = True

    def read(self) -> np.ndarray:
        return np.full((48, 64, 3), 120, dtype=np.uint8)

    def close(self) -> None:
        self.closed = True


class MissingCamera:
    """The no-camera case, injected rather than detected from the machine running the suite."""

    def open(self) -> None:
        raise CaptureError("没有可用摄像头（测试注入）")

    def read(self) -> np.ndarray:  # pragma: no cover - the socket must never reach this
        raise AssertionError("no frame should be read without a camera")

    def close(self) -> None:
        pass


class FakeDetector:
    """The detector's contract without a weight file: one box and a version name."""

    version_name = "fake-v8n"

    def __init__(self) -> None:
        self.calls = 0

    def predict(self, asset, conf_thr=0.5, iou_thr=0.45, max_det=100):
        self.calls += 1
        return [dict(BOX)]


class BlockingDetector(FakeDetector):
    """The first inference is held until the test releases it, so a frame can overtake its result."""

    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()
        self._lock = threading.Lock()

    def predict(self, asset, conf_thr=0.5, iou_thr=0.45, max_det=100):
        with self._lock:
            self.calls += 1
            first = self.calls == 1
        if first:
            assert self.release.wait(timeout=10), "the test never released the first detection"
        return [dict(BOX)]


def next_message(websocket) -> dict | bytes:
    """The next application message; a server close is raised as Starlette's disconnect."""
    message = websocket.receive()
    if message["type"] == "websocket.close":
        raise WebSocketDisconnect(code=message.get("code", 1000), reason=message.get("reason", ""))
    assert message["type"] == "websocket.send", f"unexpected ASGI message {message['type']}"
    if message.get("bytes") is not None:
        return message["bytes"]
    return json.loads(message["text"])


def next_json(websocket) -> dict:
    message = next_message(websocket)
    assert isinstance(message, dict), f"expected JSON, got {type(message).__name__}"
    return message


def expect_close(websocket) -> tuple[int, str]:
    """Drain until the server closes, then return (code, reason)."""
    with pytest.raises(WebSocketDisconnect) as caught:
        while True:
            next_message(websocket)
    return caught.value.code, caught.value.reason


def read_frame_unit(websocket) -> tuple[dict, bytes]:
    """One `frame` message and the binary image immediately after it (§7's frame unit)."""
    frame = next_json(websocket)
    assert frame["type"] == "frame", f"expected a frame message, got {frame}"
    binary = next_message(websocket)
    assert isinstance(binary, bytes), "a frame message must be followed by its binary image"
    return frame, binary


def read_until(websocket, predicate, timeout: float = 10.0):
    """Read messages, asserting the frame unit pairing, until `predicate` accepts one.

    `frames` maps every `frame_id` seen to its header, so a detection can be checked against the frame
    it claims to belong to rather than against arrival order.
    """
    frames: dict[str, dict] = {}
    expect_binary = False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        message = next_message(websocket)
        if expect_binary:
            assert isinstance(message, bytes), "a frame unit's binary image is missing"
            expect_binary = False
            continue
        assert isinstance(message, dict), "binary message with no frame message before it"
        if message["type"] == "frame":
            frames[message["frame_id"]] = message
            expect_binary = True
        elif predicate(message, frames):
            return message, frames
    raise AssertionError("timed out waiting for the expected message")


def handshake(websocket, token: str) -> None:
    websocket.send_json({"type": "auth", "token": token})
    assert next_json(websocket) == {"type": "auth_ok"}


def start(websocket, *, fps: float = 10, detect_interval_ms: int = 300) -> None:
    websocket.send_json(
        {
            "type": "start",
            "session_id": "s-live-test",
            "fps": fps,
            "detect_interval_ms": detect_interval_ms,
        }
    )


def test_a_bad_token_closes_with_4401(client):
    client.app.state.frame_source = FakeSource()
    with client.websocket_connect("/ws/capture") as websocket:
        websocket.send_json({"type": "auth", "token": "not-a-token"})
        code, reason = expect_close(websocket)
    assert code == 4401
    assert reason


def test_no_auth_within_the_timeout_closes_with_4408(client, monkeypatch):
    # §7 allows five seconds. The handler reads this module constant at call time, so the test runs in
    # a tenth of a second instead of waiting the real five.
    monkeypatch.setattr(live, "AUTH_TIMEOUT_SECONDS", 0.1)
    with client.websocket_connect("/ws/capture") as websocket:
        code, reason = expect_close(websocket)
    assert code == 4408
    assert reason


def test_auth_then_start_streams_a_frame_and_its_image(client):
    source = FakeSource()
    client.app.state.frame_source = source
    with client.websocket_connect("/ws/capture") as websocket:
        handshake(websocket, sign_in(client))
        start(websocket)
        frame, binary = read_frame_unit(websocket)
        assert frame["frame_id"]
        assert frame["captured_at"].endswith("+08:00")
        assert isinstance(frame["quality"]["score"], int)
        assert frame["quality"]["verdict"] in {"ok", "retake"}
        assert binary.startswith(b"\xff\xd8"), "the binary must be a JPEG"
        websocket.send_json({"type": "stop"})
        code, _reason = expect_close(websocket)
    assert code == 1000
    assert source.opened and source.closed


def test_detect_carries_its_frame_id_and_the_documented_fields(client):
    detector = FakeDetector()
    client.app.state.frame_source = FakeSource()
    client.app.state.detector = detector
    with client.websocket_connect("/ws/capture") as websocket:
        handshake(websocket, sign_in(client))
        start(websocket, detect_interval_ms=0)
        detect, frames = read_until(websocket, lambda message, _frames: message["type"] == "detect")

    # Correlated by frame_id: the detection names a frame this connection actually sent.
    assert detect["frame_id"] in frames
    assert detect["boxes"] == [BOX]
    assert detect["model_version"] == "fake-v8n"
    assert detect["conf_threshold"] == 0.5
    assert isinstance(detect["latency_ms"], int) and detect["latency_ms"] >= 0


def test_status_reports_fps_queue_and_model(client):
    client.app.state.frame_source = FakeSource()
    client.app.state.detector = FakeDetector()
    with client.websocket_connect("/ws/capture") as websocket:
        handshake(websocket, sign_in(client))
        start(websocket)
        status, _frames = read_until(
            websocket, lambda message, _frames: message["type"] == "status"
        )

    assert isinstance(status["fps"], (int, float))
    assert status["queue"] == 0
    assert status["model"] == "fake-v8n"


def test_a_result_for_an_older_frame_is_not_sent_as_the_current_one(client):
    """§8: frames move on while a slow model is still working; the stale result is dropped."""
    detector = BlockingDetector()
    client.app.state.frame_source = FakeSource()
    client.app.state.detector = detector
    with client.websocket_connect("/ws/capture") as websocket:
        handshake(websocket, sign_in(client))
        start(websocket, fps=30, detect_interval_ms=0)

        # The first frame's inference is held; capture keeps producing, so later frames overtake it.
        first, _first_jpeg = read_frame_unit(websocket)
        second, _second_jpeg = read_frame_unit(websocket)
        assert second["frame_id"] > first["frame_id"]
        detector.release.set()

        detect, frames = read_until(websocket, lambda message, _frames: message["type"] == "detect")

    assert detect["frame_id"] != first["frame_id"], "a stale result was sent as the current frame"
    assert detect["frame_id"] >= second["frame_id"]
    assert detect["frame_id"] in frames
    assert detect["boxes"] == [BOX]


def test_a_server_without_a_camera_closes_with_1011(client):
    client.app.state.frame_source = MissingCamera()
    with client.websocket_connect("/ws/capture") as websocket:
        websocket.send_json({"type": "auth", "token": sign_in(client)})
        # No auth_ok: the close itself is what lets the client fall back to polling.
        code, reason = expect_close(websocket)
    assert code == 1011
    assert "摄像头" in reason
