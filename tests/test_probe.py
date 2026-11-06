"""The camera arrival check, minus the camera.

The interesting part of ``app.vision.probe`` is not opening a device — it is deciding, from a series
of brightness readings, whether the exposure held. That judgement is pure, so it is tested here; the
device half needs a camera and runs on arrival.
"""

from __future__ import annotations

from app.vision.probe import Check, relative_spread, render, verdict


def test_relative_spread_of_steady_frames_is_zero():
    assert relative_spread([120.0, 120.0, 120.0]) == 0.0


def test_relative_spread_is_peak_to_peak_over_mean():
    assert round(relative_spread([100.0, 110.0]), 4) == round(10 / 105, 4)


def test_relative_spread_handles_black_and_empty():
    assert relative_spread([0.0, 0.0]) == 0.0
    assert relative_spread([]) == 0.0


def test_spread_at_the_tolerance_boundary():
    # 10 % is the SRS limit; a series exactly on it must not be reported as worse.
    values = [100.0, 110.0]
    assert round(relative_spread(values), 2) <= 0.10


def test_verdict_passes_when_every_check_passes():
    checks = [Check("设备可打开", True, ""), Check("曝光锁定", True, "")]
    ok, failed = verdict(checks)
    assert ok is True
    assert failed == []


def test_verdict_names_the_failures():
    checks = [
        Check("设备可打开", True, ""),
        Check("曝光可控", False, "亮度不变"),
        Check("曝光锁定", False, "波动 23%"),
    ]
    ok, failed = verdict(checks)
    assert ok is False
    assert failed == ["曝光可控", "曝光锁定"]


def test_render_says_so_when_the_camera_is_unusable():
    checks = [Check("曝光可控", False, "只支持自动曝光")]
    text = render(checks, {"设备索引": 0})
    assert "不可用" in text
    assert "曝光可控" in text


def test_render_says_so_when_everything_passes():
    checks = [Check("曝光锁定", True, "波动 3.1%")]
    text = render(checks, {"设备索引": 0})
    assert "可以用于本项目" in text
