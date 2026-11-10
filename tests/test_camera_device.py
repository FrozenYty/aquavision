"""The camera device path, tested without a camera.

Every failure this catches is one we would otherwise discover on arrival day, standing over a tank:
a backend that cannot open, an exposure that never pins, a read that returns nothing. The fake below
speaks the same four calls OpenCV makes (`isOpened`, `set`, `get`, `read`), so the real code under
test is the real code.
"""

from __future__ import annotations

import numpy as np
import pytest
from app.vision import capture
from app.vision.capture import CameraSource, CaptureError

DSHOW = 700
MSMF = 1400
DEFAULT = None

CONFIG: dict[str, object] = {}


class FakeDevice:
    """A `cv2.VideoCapture` that answers from CONFIG."""

    def __init__(self, index: int, flag: int | None = None):
        self.index = index
        self.flag = flag
        self.released = False
        self.props: dict[int, float] = dict(CONFIG.get("props", {}))
        openable = CONFIG.get("openable")
        self._open = True if openable is None else bool(openable.get(flag, False))

    def isOpened(self) -> bool:
        return self._open

    def set(self, prop: int, value: float) -> bool:
        self.props[prop] = value
        return True

    def get(self, prop: int) -> float:
        return float(self.props.get(prop, 0.0))

    def read(self) -> tuple[bool, np.ndarray | None]:
        frames = CONFIG.get("frames", [])
        if not frames:
            return False, None
        mean = frames.pop(0) if isinstance(frames, list) else frames
        return True, np.full((8, 8, 3), mean, dtype=np.uint8)

    def release(self) -> None:
        self.released = True


@pytest.fixture(autouse=True)
def fake_camera(monkeypatch):
    """Point the capture module at the fake and keep CONFIG clean between tests."""
    CONFIG.clear()
    CONFIG["props"] = {
        capture.cv2.CAP_PROP_EXPOSURE: -5.0,
        capture.cv2.CAP_PROP_GAIN: 2.0,
        capture.cv2.CAP_PROP_FRAME_WIDTH: 1920.0,
        capture.cv2.CAP_PROP_FRAME_HEIGHT: 1080.0,
    }
    CONFIG["frames"] = [120.0] * 40
    monkeypatch.setattr(capture.cv2, "VideoCapture", FakeDevice)
    yield
    CONFIG.clear()


def test_open_keeps_the_first_backend_that_works():
    camera = CameraSource(index=0)
    camera.open()
    assert camera.backend == "dshow"
    camera.close()


def test_open_falls_through_to_a_working_backend():
    CONFIG["openable"] = {DSHOW: False, MSMF: True, DEFAULT: False}
    camera = CameraSource(index=1)
    camera.open()
    assert camera.backend == "msmf"
    camera.close()


def test_open_reports_every_backend_it_tried():
    CONFIG["openable"] = {DSHOW: False, MSMF: False, DEFAULT: False}
    camera = CameraSource(index=3)
    with pytest.raises(CaptureError) as caught:
        camera.open()
    message = str(caught.value)
    for name in ("dshow", "msmf", "default"):
        assert name in message
    assert "3" in message


def test_lock_holds_when_brightness_is_steady():
    lock = CameraSource(index=0)
    lock.open()
    result = lock.lock_exposure()
    assert result.locked is True
    assert result.brightness_spread == 0.0
    lock.close()


def test_lock_pins_gain_and_returns_white_balance_to_automatic():
    """The SRS names shutter and gain. Manual balance made the colour cast worse on the real camera,
    which remembers the manual setting across opens, so the lock asks for automatic explicitly."""
    camera = CameraSource(index=0)
    camera.open()
    result = camera.lock_exposure()
    device = camera._cap  # the fake, so the properties it received can be read back
    assert device.props[capture.cv2.CAP_PROP_GAIN] == 0.0
    assert device.props[capture.cv2.CAP_PROP_AUTO_WB] == 1.0
    assert result.gain_raw == 0.0
    camera.close()


def test_lock_reports_drift_instead_of_pretending():
    # Settling frames first (the sensor does return them), then the drift the check must catch.
    CONFIG["frames"] = [0.0] * capture.LOCK_SETTLE_FRAMES + [100.0, 140.0] * (
        capture.LOCK_SAMPLE_FRAMES // 2
    )
    camera = CameraSource(index=0)
    camera.open()
    result = camera.lock_exposure()
    assert result.locked is False
    assert result.brightness_spread > capture.BRIGHTNESS_TOLERANCE
    assert "10%" in result.reason
    camera.close()


def test_read_raises_when_the_device_stops_delivering():
    CONFIG["frames"] = []
    camera = CameraSource(index=0)
    camera.open()
    with pytest.raises(CaptureError, match="读帧失败"):
        camera.read()
    camera.close()


def test_read_before_open_is_an_error_not_a_crash():
    with pytest.raises(CaptureError, match="尚未打开"):
        CameraSource(index=0).read()


def test_exposure_round_trip_returns_what_the_driver_reports():
    camera = CameraSource(index=0)
    camera.open()
    camera.set_exposure(-7.0)
    assert camera.get_exposure() == -7.0
    camera.close()


def test_a_driver_without_an_exposure_control_is_reported_as_such():
    CONFIG["props"][capture.cv2.CAP_PROP_EXPOSURE] = 0.0
    camera = CameraSource(index=0)
    camera.open()
    assert camera.get_exposure() is None
    camera.close()


def test_close_releases_the_device():
    camera = CameraSource(index=0)
    camera.open()
    device = camera._cap
    camera.close()
    assert device is not None and device.released is True
    assert camera._cap is None
