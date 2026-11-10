"""The rig acceptance numbers, measured on synthetic frames.

Every assertion here is a number the procurement document asks for. Testing them against generated
images means the script can be trusted on the day the tank is filled, when a wrong reading costs a
rebuild rather than a rerun.
"""

from __future__ import annotations

import numpy as np
from app.vision import rig


def frame(value: int = 128, height: int = 480, width: int = 640) -> np.ndarray:
    return np.full((height, width, 3), value, dtype=np.uint8)


def with_square(size: int, frame_width: int = 640, background: int = 60) -> np.ndarray:
    """A white square `size` px wide, centred on a dim background."""
    image = frame(background, width=frame_width)
    height, width = image.shape[:2]
    top = (height - size) // 2
    left = (width - size) // 2
    image[top : top + size, left : left + size] = 250
    return image


def test_uniform_lighting_scores_one():
    assert rig.half_ratio(frame(128)) == 1.0


def test_a_dark_left_half_fails_the_uniformity_check():
    image = frame(128)
    image[:, : image.shape[1] // 2] = 32
    ratio = rig.half_ratio(image)
    assert ratio < rig.UNIFORMITY_MIN
    passed, measurement = rig.uniformity_check([image])
    assert passed is False
    assert measurement.value == ratio


def test_a_background_outside_the_border_does_not_count():
    """The border is glass and frame; it must not decide the uniformity figure."""
    image = frame(128)
    image[: int(image.shape[0] * 0.02), :] = 0
    assert rig.half_ratio(image) == 1.0


def test_a_five_centimetre_square_is_found_at_the_expected_width():
    image = with_square(106)
    width = rig.target_width_px(image)
    assert 100 <= width <= 112


def test_a_square_that_is_too_small_fails_the_target_check():
    image = with_square(30)
    assert rig.target_width_px(image) == 0.0
    passed, _ = rig.target_check([image])
    assert passed is False


def test_a_bright_window_is_not_mistaken_for_a_target():
    """A wide bright region used to be reported as a 346 px target on a desk photo."""
    image = frame(40)
    image[40:300, 20:600] = 250  # much wider than a 5 cm target could ever be
    assert rig.target_width_px(image) == 0.0


def test_a_thin_reflection_is_not_a_target():
    image = frame(40)
    image[40:320, 300:316] = 250  # tall and thin, as a lamp streak on glass
    assert rig.target_width_px(image) == 0.0


def test_identical_frames_show_no_flicker():
    passed, measurement = rig.flicker_check(frame(120), frame(120))
    assert passed is True
    assert measurement.value == 0.0


def test_a_brightness_drop_beyond_the_tolerance_fails():
    passed, measurement = rig.flicker_check(frame(120), frame(100))
    assert passed is False
    assert measurement.value > rig.FLICKER_TOLERANCE


def test_an_all_black_frame_does_not_crash_the_measurements():
    black = frame(0)
    assert rig.half_ratio(black) == 0.0
    assert rig.target_width_px(black) == 0.0
    assert rig.brightness_ratio(black, black) == 0.0
