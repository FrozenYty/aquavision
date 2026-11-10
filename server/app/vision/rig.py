"""Rig acceptance: the three numbers that decide whether the assembled rig is usable.

`probe.py` answers "is the camera usable?" — it opens the device and pins the exposure. This module
answers a different question, asked after the tank, the lamp and the polariser are in place: **is the
picture good enough to detect on?**

The numbers come from the procurement document, section 5, and the SRS behind it:

| Check | Pass |
|---|---|
| Lighting uniformity | left half / right half mean brightness ≥ 0.7 |
| Target size | a 5 cm square is at least 45 px wide at 640 input |
| Flicker | first and last frame of a 10-minute run differ by < 5 % |

None of them needs a model, a database or the API — only frames. That is deliberate: when the rig is
wrong, the reason should not be buried under three other layers.

    python scripts/test_rig.py                            # from a camera
    python scripts/test_rig.py --index 1 --minutes 10
    python scripts/test_rig.py --images data/frames/...   # from captured frames
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# From the procurement document: the left/right halves of the tank must not differ by more than 30 %.
UNIFORMITY_MIN = 0.70
# A 5 cm target at 640 px across a 30 cm tank is 45 px; smaller means the camera is too far away.
TARGET_MIN_PX = 45
TARGET_MIN_PX_WIDTH = 640
# Rows within this fraction of the border are ignored: the glass edge and the frame corner are dark.
BORDER_FRACTION = 0.03
# A target is any bright, roughly square region; this is the area floor as a fraction of the frame.
TARGET_MIN_AREA_FRACTION = 0.0005
# Upper bound on the target width, in 640-wide pixels. A 5 cm square in a 30 cm tank is about 106 px;
# anything much wider is a reflection, a window or the tank edge, and reporting it would be a false pass.
TARGET_MAX_PX = 300
# A square target fills its bounding box; a reflection does not.
TARGET_MIN_FILL = 0.80
# Flicker: the first and the last frame of a continuous run.
FLICKER_TOLERANCE = 0.05


@dataclass(frozen=True)
class Measurement:
    """One number, with the evidence that produced it."""

    name: str
    value: float
    unit: str

    def as_text(self) -> str:
        if self.unit == "%":
            return f"{self.value:.1%}"
        return f"{self.value:.0f} px" if self.unit == "px" else f"{self.value:.3f}"


def split_halves(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Left and right halves, with the border rows and columns dropped."""
    height, width = frame.shape[:2]
    top, bottom = int(height * BORDER_FRACTION), int(height * (1 - BORDER_FRACTION))
    left, right = int(width * BORDER_FRACTION), int(width * (1 - BORDER_FRACTION))
    inner = frame[top:bottom, left:right]
    middle = inner.shape[1] // 2
    return inner[:, :middle], inner[:, middle:]


def half_ratio(frame: np.ndarray) -> float:
    """Left mean brightness over right mean brightness, the lower side on top."""
    left, right = split_halves(frame)
    left_mean, right_mean = float(left.mean()), float(right.mean())
    if left_mean <= 0 or right_mean <= 0:
        return 0.0
    return min(left_mean, right_mean) / max(left_mean, right_mean)


def brightness_ratio(first: np.ndarray, last: np.ndarray) -> float:
    """Change in mean brightness between two frames, as a fraction of the earlier one."""
    before = float(first.mean())
    if before <= 0:
        return 0.0
    return abs(float(last.mean()) - before) / before


def target_width_px(frame: np.ndarray, min_px_width: int = TARGET_MIN_PX_WIDTH) -> float:
    """Width of the widest bright region, scaled to `min_px_width` across.

    The operator puts a white 5 cm square in the tank; this finds it. The threshold is Otsu's rather
    than a fixed percentile: a target that occupies a few percent of the frame does not move a
    percentile at all, so a 60th-percentile cut left the whole frame in the bright class and every
    image looked like one enormous target. Otsu splits the two populations instead, and a frame with no
    target has no second population to find.
    """
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    height, width = grey.shape[:2]
    scale = width / min_px_width
    scaled = cv2.resize(grey, (min_px_width, max(1, int(height / scale))))

    _, mask = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0.0

    min_area = max(4.0, scaled.shape[0] * scaled.shape[1] * TARGET_MIN_AREA_FRACTION)
    widest = 0.0
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        _, _, rect_width, rect_height = cv2.boundingRect(contour)
        if rect_height == 0 or not 0.75 <= rect_width / rect_height <= 1.33:
            continue
        # A filled square, not a smear: this is what rejects a window edge or a lamp reflection.
        if area / (rect_width * rect_height) < TARGET_MIN_FILL:
            continue
        # Too wide to be a 5 cm target, so it is something else bright in the scene.
        if not TARGET_MIN_PX <= rect_width <= TARGET_MAX_PX:
            continue
        widest = max(widest, float(rect_width))
    return widest


def uniformity_check(frames: list[np.ndarray]) -> tuple[bool, Measurement]:
    """The worst half-ratio across the sampled frames."""
    if not frames:
        return False, Measurement("布光均匀", 0.0, "ratio")
    ratios = [half_ratio(frame) for frame in frames]
    worst = min(ratios)
    return worst >= UNIFORMITY_MIN, Measurement("布光均匀", worst, "ratio")


def target_check(frames: list[np.ndarray]) -> tuple[bool, Measurement]:
    """The widest target found in any frame, in 640-wide pixels."""
    if not frames:
        return False, Measurement("靶标尺寸", 0.0, "px")
    widths = [target_width_px(frame) for frame in frames]
    best = max(widths)
    return best >= TARGET_MIN_PX, Measurement("靶标尺寸", best, "px")


def flicker_check(first: np.ndarray, last: np.ndarray) -> tuple[bool, Measurement]:
    """Brightness drift between the first and last frame of a continuous run."""
    drift = brightness_ratio(first, last)
    return drift < FLICKER_TOLERANCE, Measurement("频闪", drift, "%")


def sample_from_camera(index: int, frames: int, seconds: float) -> list[np.ndarray]:
    """Grab `frames` frames spread over `seconds` from a camera."""
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"打不开摄像头 {index}")
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        for _ in range(10):  # let the sensor settle before the first sample
            cap.read()
        gap = seconds / max(1, frames - 1)
        out: list[np.ndarray] = []
        for i in range(frames):
            ok, frame = cap.read()
            if ok:
                out.append(frame)
            if i < frames - 1:
                time.sleep(gap)
        return out
    finally:
        cap.release()


def sample_from_images(directory: Path, frames: int) -> list[np.ndarray]:
    """Read up to `frames` images from a directory, in name order."""
    paths = sorted(directory.glob("*.jpg")) + sorted(directory.glob("*.png"))
    if not paths:
        raise RuntimeError(f"{directory} 里没有图片")
    out: list[np.ndarray] = []
    for path in paths[:frames]:
        frame = cv2.imread(str(path))
        if frame is not None:
            out.append(frame)
    return out
