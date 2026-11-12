"""The live capture socket (`/ws/capture`, api-contract §7, P2-08).

The capture page opens one socket per tab and expects its whole live state - picture, boxes, quality,
latency - to arrive here. Authentication is in-band: a browser cannot put an `Authorization` header on
a WebSocket handshake, and §7 forbids the token in the query string because query strings leak into
access logs and referrers, so the first message carries it (`auth`, answered by `auth_ok`).

**A server with no capture source does not hide it and does not invent pictures.** After the token is
accepted, such a server closes with `1011` and a reason. The close happens *before* `auth_ok` on
purpose: the client only rejects its socket promise before `auth_ok`, and that rejection is what makes
its REST polling fallback run instead of leaving the page on a dead socket.

**Detection runs off the event loop** (`run_in_threadpool`): it is synchronous CPU work, and awaiting
it inline would stall every other page for each connected tab.

A binary frame carries no id of its own (§8); it is paired with the `frame` message immediately before
it, and results are correlated by `frame_id`, never by arrival order.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from app import timebase
from app.config import Settings, get_settings
from app.detector import CONF_THRESHOLD
from app.envelope import ApiError
from app.models import MediaAsset, SysUser
from app.security import load_user
from app.vision.capture import CameraSource, CaptureError, make_frame_id
from app.vision.quality import Quality, score_frame

log = logging.getLogger("aquavision.live")

router = APIRouter(tags=["live"])

#: §7's close codes. 1011 is the generic internal error the contract adds for "no capture source".
CLOSE_UNAUTHORIZED = 4401
CLOSE_AUTH_TIMEOUT = 4408
CLOSE_CAPTURE_UNAVAILABLE = 1011

#: The five seconds §7 allows before the first message must be `auth`. A module constant, not a
#: literal in the call, so the test can shorten it instead of waiting five real seconds.
AUTH_TIMEOUT_SECONDS = 5.0

#: A close reason is at most 123 bytes on the wire; a device error message in Chinese can be longer.
CLOSE_REASON_BYTES = 120

#: JPEG quality used for the frame unit. The REST capture route re-encodes from the uploaded bytes
#: with OpenCV's default too, and both paths score the decoded image, not the in-memory one.
JPEG_QUALITY = 90

#: A feed rate outside this range is a client mistake, not a preference worth honouring.
MIN_FPS = 1.0
MAX_FPS = 30.0
DEFAULT_FPS = 10.0
DEFAULT_DETECT_INTERVAL_MS = 300
STATUS_INTERVAL_SECONDS = 1.0


class FrameSource(Protocol):
    """The part of `app.vision.capture.CameraSource` this module uses.

    A test supplies a stand-in so the socket can be exercised without hardware.
    """

    def open(self) -> None: ...

    def read(self) -> np.ndarray: ...

    def close(self) -> None: ...


class Detector(Protocol):
    """The part of `app.detector.Detector` the socket calls; a test supplies a fake."""

    version_name: str

    def predict(self, asset: Any, conf_thr: float = ...) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class _CapturedFrame:
    frame_id: str
    captured_at: str
    quality: Quality
    jpeg: bytes
    captured_monotonic: float


@dataclass(frozen=True)
class _StartConfig:
    fps: float
    detect_interval_ms: int

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> _StartConfig:
        try:
            fps = float(message.get("fps", DEFAULT_FPS))
        except (TypeError, ValueError):
            fps = DEFAULT_FPS
        try:
            interval = int(message.get("detect_interval_ms", DEFAULT_DETECT_INTERVAL_MS))
        except (TypeError, ValueError):
            interval = DEFAULT_DETECT_INTERVAL_MS
        return cls(
            fps=min(max(fps, MIN_FPS), MAX_FPS),
            detect_interval_ms=max(0, interval),
        )


@router.websocket("/ws/capture")
async def capture_socket(websocket: WebSocket) -> None:
    """One capture connection: auth, then a frames-and-detections stream until `stop`."""
    settings = get_settings()
    source: FrameSource | None = None
    try:
        await websocket.accept()
        if await _authenticate(websocket, settings) is None:
            return

        source = _frame_source(websocket, settings)
        try:
            await run_in_threadpool(source.open)
        except (CaptureError, OSError) as err:
            # Before auth_ok on purpose: see the module docstring. The client then takes its REST
            # polling path, which is the documented fallback for a server that cannot serve the feed.
            await _close(websocket, CLOSE_CAPTURE_UNAVAILABLE, _reason(err))
            return

        detector = getattr(websocket.app.state, "detector", None)
        await websocket.send_json({"type": "auth_ok"})
        await _serve(websocket, source, detector, settings)
    except WebSocketDisconnect:
        return
    finally:
        if source is not None:
            with contextlib.suppress(Exception):
                await run_in_threadpool(source.close)


async def _authenticate(websocket: WebSocket, settings: Settings) -> SysUser | None:
    """Read the first message, validate its token, and answer on failure with the §7 close code."""
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS)
    except TimeoutError:
        await _close(websocket, CLOSE_AUTH_TIMEOUT, "五秒内没有收到 auth 消息")
        return None

    token = _token_from(raw)
    if token:
        with websocket.app.state.session_factory() as session:
            try:
                return load_user(session, token, settings)
            except ApiError:
                pass
    await _close(websocket, CLOSE_UNAUTHORIZED, "登录状态无效或已过期")
    return None


async def _serve(
    websocket: WebSocket,
    source: FrameSource,
    detector: Detector | None,
    settings: Settings,
) -> None:
    """Wait for `start`, run the feed until `stop`, and cancel it if the client goes away."""
    sender = _Sender(websocket)
    feed: asyncio.Task[None] | None = None
    try:
        while True:
            message = _message(await websocket.receive_text())
            if message is None:
                continue
            kind = message.get("type")
            if kind == "start" and feed is None:
                session_id = message.get("session_id")
                log.info("live: feed started for session %s", session_id)
                feed = asyncio.create_task(
                    _feed(
                        sender,
                        source,
                        detector,
                        settings,
                        _StartConfig.from_message(message),
                    )
                )
            elif kind == "stop":
                break
    finally:
        if feed is not None:
            feed.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await feed
    # §7's flow ends with `stop`; close cleanly rather than leaving the handshake to time out.
    await _close(websocket, 1000, "")


async def _feed(
    sender: _Sender,
    source: FrameSource,
    detector: Detector | None,
    settings: Settings,
    config: _StartConfig,
) -> None:
    """Capture at the requested rate and stream frame units; detections run beside the feed."""
    index = 0
    frames_in_window = 0
    window_started = time.monotonic()
    next_detect = time.monotonic()
    detection: asyncio.Task[None] | None = None
    try:
        while True:
            frame_started = time.monotonic()
            captured = await run_in_threadpool(_grab, source, index + 1)
            index += 1
            await sender.frame(
                {
                    "frame_id": captured.frame_id,
                    "captured_at": captured.captured_at,
                    "quality": {
                        "score": captured.quality.score,
                        "verdict": captured.quality.verdict,
                    },
                },
                captured.jpeg,
            )

            now = time.monotonic()
            if detection is not None and detection.done():
                detection = None
            # One detection in flight at a time: a slow model must not queue an inference per frame.
            if detector is not None and detection is None and now * 1000 >= next_detect:
                detection = asyncio.create_task(_detect(sender, detector, captured, settings))
                next_detect = now + config.detect_interval_ms / 1000

            frames_in_window += 1
            if now - window_started >= STATUS_INTERVAL_SECONDS:
                await sender.message(
                    {
                        "type": "status",
                        "fps": round(frames_in_window / (now - window_started), 1),
                        "queue": 0,
                        "model": _model_name(detector),
                    }
                )
                frames_in_window = 0
                window_started = now

            elapsed = time.monotonic() - frame_started
            await asyncio.sleep(max(0.0, 1 / config.fps - elapsed))
    except (CaptureError, OSError) as err:
        await sender.close(CLOSE_CAPTURE_UNAVAILABLE, _reason(err))
    except Exception:  # noqa: BLE001 - a broken feed is a closed socket, not a silent page
        log.exception("live: feed failed")
        await sender.close(CLOSE_CAPTURE_UNAVAILABLE, "实时推送失败")
    finally:
        if detection is not None:
            detection.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await detection


async def _detect(
    sender: _Sender, detector: Detector, captured: _CapturedFrame, settings: Settings
) -> None:
    """Run one frame through the detector in the thread pool and answer with §7's `detect`."""
    try:
        boxes, latency_ms = await run_in_threadpool(_run_detector, detector, captured, settings)
    except Exception:  # noqa: BLE001 - one failed inference must not end the stream
        log.exception("live: detection failed for %s", captured.frame_id)
        return
    await sender.detect(
        {
            "type": "detect",
            "frame_id": captured.frame_id,
            "boxes": boxes,
            "latency_ms": latency_ms,
            "model_version": _model_name(detector),
            "conf_threshold": CONF_THRESHOLD,
        }
    )


def _run_detector(
    detector: Detector, captured: _CapturedFrame, settings: Settings
) -> tuple[list[dict[str, Any]], int]:
    """Inference on one live frame, with §8's latency measured from capture to result.

    `Detector.predict` reads a `MediaAsset` row's `file_path`; a live frame has no row (the `start`
    message carries no site to fill `point_code`), so the bytes are written to a scratch file under
    the data directory and removed again. The carrier object is never added to a session: it exists
    only so the loaded model can open the image.
    """
    data_dir = Path(settings.data_dir)
    # Two tabs can capture in the same second, so their frame_ids can be equal; the scratch name must
    # not be, or one connection's inference would read a file the other is deleting.
    path = data_dir / "frames" / "live" / f"{captured.frame_id}-{uuid4().hex[:8]}.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(captured.jpeg)
    try:
        carrier = MediaAsset(
            frame_id=captured.frame_id,
            file_path=path.relative_to(data_dir).as_posix(),
        )
        predict = getattr(detector, "predict", None)
        if callable(predict):
            boxes = predict(carrier, conf_thr=CONF_THRESHOLD)
        else:
            boxes = detector(carrier)  # type: ignore[operator] - the worker's callable shape
    finally:
        path.unlink(missing_ok=True)
    latency_ms = max(0, int((time.monotonic() - captured.captured_monotonic) * 1000))
    return boxes, latency_ms


def _grab(source: FrameSource, index: int) -> _CapturedFrame:
    """Read, encode and score one frame, exactly as `vision.capture.CaptureSession.grab` does."""
    captured_monotonic = time.monotonic()
    frame = source.read()
    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        raise CaptureError("JPEG 编码失败")
    # Score the decoded bytes: JPEG smoothing moves the Laplacian, so a score from the in-memory array
    # would not describe the image this socket sends - the same rule the REST capture route follows.
    stored = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if stored is None:
        raise CaptureError("编码后的帧无法解码")
    captured_at = timebase.now()
    return _CapturedFrame(
        frame_id=make_frame_id(captured_at, index),
        captured_at=timebase.iso(captured_at, timespec="milliseconds"),
        quality=score_frame(stored),
        jpeg=buffer.tobytes(),
        captured_monotonic=captured_monotonic,
    )


class _Sender:
    """Serialises outgoing messages so a frame unit is never split by another message.

    The `frame` header and its JPEG are two ASGI messages; a `detect` or `status` sent between them
    would break §7's adjacency rule. The same lock is where §8 is applied: a detection for a frame
    older than the newest one already sent is dropped here, not queued and never relabelled.
    """

    def __init__(self, websocket: WebSocket) -> None:
        self._websocket = websocket
        self._lock = asyncio.Lock()
        self.latest_frame_id = ""

    async def frame(self, header: dict[str, Any], jpeg: bytes) -> None:
        async with self._lock:
            await self._websocket.send_json({"type": "frame", **header})
            await self._websocket.send_bytes(jpeg)
            self.latest_frame_id = str(header["frame_id"])

    async def message(self, message: dict[str, Any]) -> None:
        async with self._lock:
            await self._websocket.send_json(message)

    async def detect(self, message: dict[str, Any]) -> None:
        async with self._lock:
            if str(message["frame_id"]) < self.latest_frame_id:
                return
            await self._websocket.send_json(message)

    async def close(self, code: int, reason: str) -> None:
        await _close(self._websocket, code, _reason_text(reason))


def _frame_source(websocket: WebSocket, settings: Settings) -> FrameSource:
    """The injected source when a test supplies one, otherwise the real camera path."""
    injected = getattr(websocket.app.state, "frame_source", None)
    if injected is not None:
        return injected
    return CameraSource(index=settings.camera_index)


def _token_from(raw: str) -> str:
    message = _message(raw)
    if message is None or message.get("type") != "auth":
        return ""
    token = message.get("token")
    return token if isinstance(token, str) else ""


def _message(raw: str) -> dict[str, Any] | None:
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _model_name(detector: Detector | None) -> str | None:
    return getattr(detector, "version_name", None) if detector is not None else None


def _reason(err: Exception) -> str:
    return _reason_text(str(err) or type(err).__name__)


def _reason_text(reason: str) -> str:
    """Keep a close reason inside the 123-byte frame limit without splitting a UTF-8 character."""
    return reason.encode("utf-8")[:CLOSE_REASON_BYTES].decode("utf-8", "ignore")


async def _close(websocket: WebSocket, code: int, reason: str) -> None:
    with contextlib.suppress(RuntimeError):
        await websocket.close(code=code, reason=_reason_text(reason))
