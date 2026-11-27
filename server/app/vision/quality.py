"""Frame quality scoring.

Implements FR-M2-03 (SRS §3.3.2): three measurements, weighted, below the pass mark the frame is
stored but kept out of the detection queue.

The SRS fixes the weights (0.5 / 0.3 / 0.2) and a pass mark of 60. How each raw measurement maps to
a 0-100 sub-score is ours, so the constants below are named and separated from the formula: tuning
them against real footage must not mean editing arithmetic. The pass mark is the documented default;
`score_frame` takes the threshold in force, so an operator's value decides the verdict.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# Laplacian variance that earns a full 100. Underwater frames sit well below a bright studio shot.
SHARPNESS_FULL = 120.0
# Brightness is scored by distance from mid-grey; beyond the tolerance a frame scores zero.
BRIGHTNESS_IDEAL = 128.0
BRIGHTNESS_TOLERANCE = 90.0
# Spread between channel means that earns a zero. A strong blue-green cast in water reaches ~30.
COLORCAST_FULL = 36.0

WEIGHT_SHARPNESS = 0.5
WEIGHT_BRIGHTNESS = 0.3
WEIGHT_COLORCAST = 0.2
#: The SRS pass mark, used when no caller supplies the operator's effective threshold. The capture
#: route passes `settings`/`sys_param`'s value in, so a verdict and the `quality_flag` stored beside
#: it cannot disagree after the parameter changes (ADR 15).
PASS_MARK = 60


@dataclass(frozen=True)
class Quality:
    """Three sub-scores, the weighted total and the verdict."""

    sharpness: int
    brightness: int
    colorcast: int
    score: int
    verdict: str  # "ok" | "retake"

    def as_dict(self) -> dict[str, int | str]:
        return {
            "sharpness": self.sharpness,
            "brightness": self.brightness,
            "colorcast": self.colorcast,
            "score": self.score,
            "verdict": self.verdict,
        }


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _grey(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def measure(image: np.ndarray) -> tuple[float, float, float]:
    """Raw measurements: Laplacian variance, mean brightness, spread between channel means.

    Kept separate from scoring so a test can assert the measurement without pinning the curve.
    """
    if image.size == 0:
        raise ValueError("empty image")

    grey = _grey(image)
    sharpness = float(cv2.Laplacian(grey, cv2.CV_64F).var())
    brightness = float(grey.mean())

    if image.ndim == 3:
        means = image.reshape(-1, image.shape[2]).mean(axis=0)
        colorcast = float(means.max() - means.min())
    else:
        colorcast = 0.0

    return sharpness, brightness, colorcast


def score_frame(image: np.ndarray, pass_mark: int = PASS_MARK) -> Quality:
    """Score one frame, with the verdict decided against `pass_mark`.

    Same input and threshold, same output — no randomness, no state. The default is the documented
    SRS pass mark; a caller that answers to the operator's threshold passes the effective one here.
    """
    sharpness_raw, brightness_raw, colorcast_raw = measure(image)

    sharpness = _clamp(100.0 * sharpness_raw / SHARPNESS_FULL)
    brightness = _clamp(
        100.0 * (1.0 - abs(brightness_raw - BRIGHTNESS_IDEAL) / BRIGHTNESS_TOLERANCE)
    )
    colorcast = _clamp(100.0 * (1.0 - colorcast_raw / COLORCAST_FULL))

    total = (
        WEIGHT_SHARPNESS * sharpness + WEIGHT_BRIGHTNESS * brightness + WEIGHT_COLORCAST * colorcast
    )
    score = int(round(total))
    verdict = "ok" if score >= pass_mark else "retake"
    return Quality(
        sharpness=int(round(sharpness)),
        brightness=int(round(brightness)),
        colorcast=int(round(colorcast)),
        score=score,
        verdict=verdict,
    )
