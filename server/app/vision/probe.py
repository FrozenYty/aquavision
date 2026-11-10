"""Camera arrival check (P1-06): can this device hold an exposure?

The rig depends on a locked exposure — the quality score compares frames, and the cross-polarisation
setup assumes the scene brightness does not drift. A module that only offers automatic exposure will
look fine in a video call and fail this rig, so the check runs before the camera is accepted.

Three questions, in order:

1. **Does it open, and what does it report?** Backend, resolution, frame rate.
2. **Does manual exposure actually change the image?** Writing a property and reading it back proves
   only that the driver echoes numbers. The proof is that the picture gets darker and brighter.
3. **Does a pinned exposure hold still?** Twenty frames; the SRS allows a 10 % spread.

Exit codes: 0 pass, 1 a check failed, 2 no camera at all — so a script can tell "broken camera" from
"no camera plugged in".

    cd server && python -m app.vision.probe
    cd server && python -m app.vision.probe --index 1 --frames 30
"""

from __future__ import annotations

import argparse
import statistics
import time
from dataclasses import dataclass

from app.vision.capture import CameraSource, CaptureError

# SRS NFR-U-08: once exposure is locked, mean brightness between frames varies by under 10 %.
TOLERANCE = 0.10
DEFAULT_FRAMES = 20
# Frames discarded after the lock: the sensor is still settling from the exposure sweep.
SETTLE_FRAMES = 8
# Exposure units differ per backend (log2 seconds on DirectShow, absolute on V4L2), so the response
# test uses a relative step rather than an absolute exposure time.
RESPONSE_STEPS = (3.0,)


@dataclass(frozen=True)
class Check:
    """One line of the verdict: what was asked, whether it held, and the evidence."""

    name: str
    passed: bool
    detail: str


def relative_spread(values: list[float]) -> float:
    """Peak-to-peak brightness over the mean, as a fraction. Empty or all-black input is 0."""
    if not values:
        return 0.0
    mean = statistics.fmean(values)
    if mean <= 0:
        return 0.0
    return (max(values) - min(values)) / mean


def verdict(checks: list[Check]) -> tuple[bool, list[str]]:
    """Overall pass, and the names of the checks that failed."""
    failed = [check.name for check in checks if not check.passed]
    return (not failed, failed)


def render(checks: list[Check], meta: dict[str, object]) -> str:
    lines = ["摄像头到货检查", ""]
    for key, value in meta.items():
        lines.append(f"  {key:<10} {value}")
    lines.append("")
    for check in checks:
        mark = "通过" if check.passed else "不通过"
        lines.append(f"  [{mark}] {check.name}：{check.detail}")
    ok, failed = verdict(checks)
    lines.append("")
    lines.append("结论：可以用于本项目" if ok else f"结论：不可用（{', '.join(failed)} 未通过）")
    return "\n".join(lines)


def sample_brightness(source: CameraSource, count: int) -> tuple[list[float], float]:
    """Mean grey level of ``count`` consecutive frames, and the measured frame rate."""
    values: list[float] = []
    started = time.perf_counter()
    for _ in range(count):
        frame = source.read()
        values.append(float(frame.mean()))
    elapsed = time.perf_counter() - started
    fps = count / elapsed if elapsed > 0 else 0.0
    return values, fps


def check_device(source: CameraSource) -> list[Check]:
    """Open the device and report what it says about itself."""
    source.open()
    width, height = source.size
    checks = [
        Check("设备可打开", True, f"后端 {source.backend}，分辨率 {width}×{height}"),
    ]
    if (width, height) == (1920, 1080):
        checks.append(Check("分辨率", True, "1920×1080"))
    else:
        checks.append(
            Check("分辨率", False, f"报告 {width}×{height}，方案要求 1080P；仍可继续测曝光")
        )
    return checks


def check_response(source: CameraSource) -> list[Check]:
    """Does the picture actually answer the exposure property?

    DirectShow and V4L2 disagree about the unit and even the sign, so absolute times are useless
    here. The test walks the value up and down by a fixed step and watches the mean brightness.
    """
    checks: list[Check] = []
    base = source.get_exposure()
    if base is None:
        return [Check("曝光可控", False, "驱动不提供曝光属性，只能自动曝光")]

    readings: list[float] = []
    for step in RESPONSE_STEPS:
        source.set_exposure(base + step)
        time.sleep(0.25)  # let the sensor settle
        frames, _ = sample_brightness(source, 3)
        readings.append(statistics.fmean(frames))
        source.set_exposure(base - step)
        time.sleep(0.25)
        frames, _ = sample_brightness(source, 3)
        readings.append(statistics.fmean(frames))

    source.set_exposure(base)  # leave the device where it was found, not at the end of a sweep

    bright, dark = max(readings), min(readings)
    ratio = (bright - dark) / bright if bright > 0 else 0.0
    changed = ratio > 0.05
    checks.append(
        Check(
            "曝光可控",
            changed,
            f"调整后亮度变化 {ratio:.1%}"
            + ("" if changed else "，几乎没有反应，可能只支持自动曝光"),
        )
    )
    return checks


def check_stability(source: CameraSource, frames: int) -> list[Check]:
    """Pin the exposure and confirm the frames stay within the tolerance.

    The verdict comes from the measurement taken *after* the lock, not from the one the lock itself
    reported: an earlier version printed the fresh number beside the old verdict, so a 639 % swing
    appeared in a line that said "passed". Settling frames are dropped first — the probe has just
    swept exposure up and down, and the sensor needs a moment before it can be called stable.
    """
    lock = source.lock_exposure()
    for _ in range(SETTLE_FRAMES):
        source.read()
    values, fps = sample_brightness(source, frames)
    spread = relative_spread(values)
    held = lock.locked and spread <= TOLERANCE

    reason = ""
    if not lock.locked:
        reason = f"；{lock.reason}"
    elif not held:
        reason = f"；锁定后重新测量为 {spread:.1%}，超过上限"

    checks = [
        Check(
            "曝光锁定",
            held,
            f"帧间亮度波动 {spread:.1%}（上限 {TOLERANCE:.0%}）" + reason,
        )
    ]
    checks.append(Check("帧率", fps >= 5.0, f"{fps:.1f} 帧/秒（连续读帧，非持续采集）"))
    return checks


def run(index: int, frames: int) -> int:
    source = CameraSource(index=index)
    try:
        checks = check_device(source)
    except CaptureError as err:
        print(f"打不开摄像头 {index}：{err}")
        print("检查 USB 连接；没有设备时换一台机器。")
        return 2

    try:
        checks += check_response(source)
        checks += check_stability(source, frames)
        width, height = source.size
        meta = {
            "设备索引": index,
            "后端": source.backend,
            "分辨率": f"{width}×{height}",
            "采样帧数": frames,
        }
    except CaptureError as err:
        print(f"采集过程中失败：{err}")
        return 1
    finally:
        source.close()

    print(render(checks, meta))
    ok, _ = verdict(checks)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查摄像头能否锁定曝光（到货验收）")
    parser.add_argument("--index", type=int, default=0, help="摄像头索引，默认 0")
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES, help="稳定性采样帧数")
    args = parser.parse_args(argv)
    return run(args.index, args.frames)


if __name__ == "__main__":
    raise SystemExit(main())
