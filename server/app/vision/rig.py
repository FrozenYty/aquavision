"""Rig acceptance: the three numbers that decide whether the assembled rig is usable.

`probe.py` answers "is the camera usable?" — it opens the device and pins the exposure. This module
answers a different question, asked after the tank, the lamp and the polariser are in place: **is the
picture good enough to detect on?**

The numbers come from the procurement document, section 6, and the SRS behind it:

| Check | Pass |
|---|---|
| Lighting uniformity | left half / right half mean brightness ≥ 0.7 |
| Target size | a 5 cm square is 45-300 px wide at 640 input |
| Light stability | first and last frame of a 10-minute run differ by < 5 % |

Procurement section 6 also lists a flicker row: filmed by a phone camera, no rolling bars. That one is
outside this script - it needs the lamp photographed by a phone, not frames from the camera under test.

None of them needs a model, a database or the API — only frames. That is deliberate: when the rig is
wrong, the reason should not be buried under three other layers.

    python scripts/test_rig.py                            # from a camera
    python scripts/test_rig.py --index 1 --minutes 10
    python scripts/test_rig.py --images data/frames/...   # from captured frames
"""

from __future__ import annotations

import time
from collections.abc import Iterator
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
# Light stability: the first and the last frame of a continuous run.
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


# Why a bright shape was not accepted as the target. One "0 px" used to stand for all of these, and
# the operator's next move depends on which one it is: an empty tank, a target too small at this
# distance, a lamp streak on the glass, or a reflection wider than any 5 cm square.
TARGET_REJECT_NOTHING = "nothing"
TARGET_REJECT_AREA = "area"
TARGET_REJECT_SHAPE = "shape"
TARGET_REJECT_FILL = "fill"
TARGET_REJECT_NARROW = "narrow"
TARGET_REJECT_WIDE = "wide"

_TARGET_REJECTION_TEXT = {
    TARGET_REJECT_NOTHING: "画面里没有亮区（水箱里没有靶标，或者灯没开）",
    TARGET_REJECT_AREA: "有亮区，但都太小，够不到面积下限",
    TARGET_REJECT_SHAPE: "亮区不是近方形，多半是灯或窗在玻璃上的长条反光",
    TARGET_REJECT_FILL: "亮区不成块，边缘被反光切走",
    TARGET_REJECT_NARROW: f"靶标窄于 {TARGET_MIN_PX} px：相机离得太远，或靶标不在动物所在的那一层",
    TARGET_REJECT_WIDE: f"近方形的亮区宽于 {TARGET_MAX_PX} px：靶标离镜头太近，或那是一块反光",
}


def target_shapes(
    frame: np.ndarray, min_px_width: int = TARGET_MIN_PX_WIDTH
) -> Iterator[tuple[float, str | None]]:
    """Every bright shape worth considering, as `(width_px, rejection)`.

    `rejection` is None when the shape is the target. One contour loop decides both the number
    `target_width_px` reports and the reason `target_hint` prints, so the two cannot disagree. The
    threshold is Otsu's rather than a fixed percentile: a target that occupies a few percent of the
    frame does not move a percentile at all, so a 60th-percentile cut left the whole frame in the
    bright class and every image looked like one enormous target, while a frame with no target has no
    second population to find.
    """
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    height, width = grey.shape[:2]
    scale = width / min_px_width
    scaled = cv2.resize(grey, (min_px_width, max(1, int(height / scale))))

    _, mask = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = max(4.0, scaled.shape[0] * scaled.shape[1] * TARGET_MIN_AREA_FRACTION)
    for contour in contours:
        area = cv2.contourArea(contour)
        _, _, rect_width, rect_height = cv2.boundingRect(contour)
        if area < min_area:
            yield float(rect_width), TARGET_REJECT_AREA
        elif rect_height == 0 or not 0.75 <= rect_width / rect_height <= 1.33:
            yield float(rect_width), TARGET_REJECT_SHAPE
        # A filled square, not a smear: this is what rejects a window edge or a lamp reflection.
        elif area / (rect_width * rect_height) < TARGET_MIN_FILL:
            yield float(rect_width), TARGET_REJECT_FILL
        # The width tests sit behind the aspect test, so only a near-square shape can reach the
        # ceiling: an elongated bright region is reported as a shape, which is what it is.
        elif rect_width < TARGET_MIN_PX:
            yield float(rect_width), TARGET_REJECT_NARROW
        # Too wide to be a 5 cm target, so it is something else bright in the scene.
        elif rect_width > TARGET_MAX_PX:
            yield float(rect_width), TARGET_REJECT_WIDE
        else:
            yield float(rect_width), None


def target_width_px(frame: np.ndarray, min_px_width: int = TARGET_MIN_PX_WIDTH) -> float:
    """Width of the widest accepted target, scaled to `min_px_width` across.

    The operator puts a white 5 cm square in the tank; this finds it. **A rejection is not a
    measurement**: no bright region, a shape too small to count, a non-square streak, an unfilled
    smear and a shape past the width ceiling are five different situations, so `target_hint` names the
    one that happened instead of printing one zero for all of them.
    """
    widths = [w for w, rejection in target_shapes(frame, min_px_width) if rejection is None]
    return max(widths, default=0.0)


def target_rejections(
    frames: list[np.ndarray], min_px_width: int = TARGET_MIN_PX_WIDTH
) -> dict[str, int]:
    """Count the reasons no target was accepted, per reason, across `frames`.

    A frame whose bright class holds no contour at all counts as `TARGET_REJECT_NOTHING`: nothing
    bright in the frame. This is the difference between "the tank has no target", "the target is too
    small at this distance" and "a reflection swamped it", which one number could not carry.
    """
    counts: dict[str, int] = {}
    for frame in frames:
        shapes = list(target_shapes(frame, min_px_width))
        if not shapes:
            counts[TARGET_REJECT_NOTHING] = counts.get(TARGET_REJECT_NOTHING, 0) + 1
            continue
        for _width, rejection in shapes:
            if rejection is not None:
                counts[rejection] = counts.get(rejection, 0) + 1
    return counts


def target_hint(frames: list[np.ndarray], min_px_width: int = TARGET_MIN_PX_WIDTH) -> str:
    """One sentence naming why the target check read nothing, for the operator."""
    counts = target_rejections(frames, min_px_width)
    if not counts:
        return "已认定靶标"
    parts = [
        f"{_TARGET_REJECTION_TEXT.get(reason, reason)}（{count} 处）"
        for reason, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return "未认定靶标：" + "；".join(parts) + "。把 5cm 白方块放到动物所在那一层再测"


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
    """Light stability: brightness drift between the first and last frame of a continuous run.

    The symbol keeps its old name because `tests/test_rig_measure.py` imports it; the check it performs
    is light stability, while flicker is the phone-camera row procurement §6 measures with a phone.
    """
    drift = brightness_ratio(first, last)
    return drift < FLICKER_TOLERANCE, Measurement("补光稳定", drift, "%")


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
