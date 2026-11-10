#!/usr/bin/env python3
"""Rig acceptance: is the assembled tank good enough to detect on?

The three numbers are in the procurement document, section 5. This script measures them from frames
instead of asking anyone to eyeball a screen.

    python scripts/test_rig.py
    python scripts/test_rig.py --index 1 --minutes 10
    python scripts/test_rig.py --images ../data/frames/A3/20261110/...   # a captured session

A directory of images has no time axis, so the flicker check is skipped there rather than passed:
a check that did not run must not look like a check that held.

Exit codes: 0 pass, 1 a check failed, 2 the source could not be read.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The server package is not on the path when a script runs from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from app.vision import rig  # noqa: E402  (import follows the path setup on purpose)
from app.vision.probe import Check, render, verdict  # noqa: E402  (reuse the check renderer)

DEFAULT_FRAMES = 20


def uniformity_checks(frames: list) -> Check:
    passed, measurement = rig.uniformity_check(frames)
    return Check(
        "布光均匀",
        passed,
        f"左右亮度比 {measurement.as_text()}（下限 {rig.UNIFORMITY_MIN:.0%}）",
    )


def target_checks(frames: list) -> Check:
    passed, measurement = rig.target_check(frames)
    return Check(
        "靶标尺寸",
        passed,
        f"最宽目标 {measurement.as_text()}（640 宽下，下限 {rig.TARGET_MIN_PX} px）"
        "；把 5cm 白方块放进水箱再测",
    )


def flicker_checks(frames: list) -> Check:
    passed, measurement = rig.flicker_check(frames[0], frames[-1])
    return Check(
        "频闪",
        passed,
        f"首尾亮度差 {measurement.as_text()}（上限 {rig.FLICKER_TOLERANCE:.0%}）",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, default=0, help="camera index")
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES, help="frames per check")
    parser.add_argument("--minutes", type=float, default=0.2, help="flicker run length, in minutes")
    parser.add_argument("--images", metavar="DIR", help="read frames from a directory instead")
    args = parser.parse_args(argv)

    try:
        if args.images:
            directory = Path(args.images)
            frames = rig.sample_from_images(directory, args.frames)
            source = f"目录 {directory}"
        else:
            seconds = max(1.0, args.minutes * 60)
            frames = rig.sample_from_camera(args.index, args.frames, seconds)
            source = f"摄像头 {args.index}"
    except RuntimeError as err:
        print(f"无法取样：{err}", file=sys.stderr)
        return 2

    if len(frames) < 2:
        print("帧数不足，无法测量", file=sys.stderr)
        return 2

    checks = [uniformity_checks(frames), target_checks(frames)]
    if args.images:
        print(f"  注：{source} 没有时间轴，频闪检查已跳过\n")
    else:
        checks.append(flicker_checks(frames))

    print(render(checks, {"取样来源": source, "帧数": len(frames)}))
    ok, _failed = verdict(checks)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
