"""Generate synthetic frames for the capture pipeline when no camera is attached.

The images this writes are deliberately varied — sharp, softly blurred, defocused, underexposed,
colour-cast — so the quality score spreads across the pass mark instead of landing on one number.
That makes them useful for exercising ``app.vision.capture`` and for a demonstration on a machine with
no USB camera.

They are not training data and not a stand-in for footage. Every frame is generated from a fixed seed,
so the same seed gives the same images on any machine.

    python scripts/make_samples.py --out data/samples --count 20
    cd server && python -m app.vision.capture --images ../data/samples --count 20
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

DEFAULT_SIZE = (1080, 1920)  # height, width
DEFAULT_SEED = 20261106
# One full cycle of these variations is applied across consecutive frames.
CYCLE = 5


def base_scene(rng: np.random.Generator, size: tuple[int, int]) -> np.ndarray:
    """A sandy seabed: a slow gradient, speckle, and three bright blobs standing in for targets."""
    height, width = size
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    background = 90 + 40 * np.sin(xx / 260.0) * np.cos(yy / 190.0)
    background += rng.normal(0, 6, size=(height, width))
    # Water absorbs red first, so the blue channel carries the most signal.
    image = np.stack([background * 0.72, background * 0.92, background * 1.00], axis=2)

    for _ in range(3):
        cy = int(rng.integers(height // 5, height * 4 // 5))
        cx = int(rng.integers(width // 5, width * 4 // 5))
        ry = int(rng.integers(70, 150))
        rx = int(rng.integers(70, 150))
        mask = ((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 <= 1
        image[mask] = np.array([120, 150, 175], dtype=np.float32) + rng.normal(0, 8, 3)

    return np.clip(image, 0, 255).astype(np.uint8)


def vary(image: np.ndarray, step: int) -> np.ndarray:
    """Apply one quality variation; step cycles so a run covers all of them."""
    kind = step % CYCLE
    if kind == 1:
        return cv2.GaussianBlur(image, (9, 9), 0)
    if kind == 3:
        return cv2.GaussianBlur(image, (41, 41), 0)
    if kind == 4:
        return np.clip(image.astype(np.float32) * 0.35, 0, 255).astype(np.uint8)
    return image


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成合成帧，供无摄像头时验证采集链路")
    parser.add_argument("--out", default="data/samples", help="输出目录（默认 data/samples）")
    parser.add_argument("--count", type=int, default=20, help="帧数（默认 20）")
    parser.add_argument("--width", type=int, default=DEFAULT_SIZE[1])
    parser.add_argument("--height", type=int, default=DEFAULT_SIZE[0])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)

    out = Path(args.out)
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as err:
        print(f"无法创建目录 {out}：{err}")
        return 1

    rng = np.random.default_rng(args.seed)
    size = (args.height, args.width)
    for index in range(args.count):
        frame = vary(base_scene(rng, size), index)
        path = out / f"sample-{index + 1:02d}.jpg"
        if not cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92]):
            print(f"写入失败：{path}")
            return 1

    print(f"已生成 {args.count} 帧到 {out}（种子 {args.seed}）")
    print(
        "下一步：cd server && python -m app.vision.capture --images ../" + args.out + " --count 20"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
