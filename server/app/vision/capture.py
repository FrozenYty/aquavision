"""Capture: open the camera, lock exposure, grab, score and persist.

Implements P1-03 and the capture interface conventions of SRS §2.4.3. The pipeline is deliberately
split from the device: `FrameSink` owns ids, naming and scoring, while a source only has to produce
frames. That is what lets the same code run from a camera today and from a folder of images when no
camera is attached — the demo path and the product path stay identical downstream.

Run it from the server directory:

    cd server
    python -m app.vision.capture --count 20 --site A3
    python -m app.vision.capture --count 20 --site A3 --images ../samples   # no camera attached
    python -m app.vision.capture --verify ../data/frames/A3/20261106/s-a3-001

Frame ids follow the contract: ``YYYYMMDDTHHMMSS-####`` in the local zone, unique inside a session.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np

from app.vision.quality import Quality, score_frame

LOCAL_TZ = timezone(timedelta(hours=8))
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
# SRS §2.4.3: once exposure is locked, mean brightness between frames must vary by under 10 %.
BRIGHTNESS_TOLERANCE = 0.10
LOCK_SAMPLE_FRAMES = 5


class CaptureError(RuntimeError):
    """Raised when a capture cannot proceed; the message is shown to the operator."""


@dataclass(frozen=True)
class ExposureLock:
    """What the lock actually achieved, not what was requested."""

    locked: bool
    exposure_raw: float
    gain_raw: float
    brightness_spread: float
    reason: str = ""

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class FrameRecord:
    """One captured frame and everything needed to find it again."""

    frame_id: str
    session_id: str
    site: str
    path: str
    captured_at: str
    width: int
    height: int
    quality: Quality

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["quality"] = self.quality.as_dict()
        return data


def make_frame_id(moment: datetime, index: int) -> str:
    return f"{moment.astimezone(LOCAL_TZ).strftime('%Y%m%dT%H%M%S')}-{index:04d}"


def default_session_id(site: str, moment: datetime) -> str:
    return f"s-{site.lower()}-{moment.strftime('%Y%m%d%H%M%S')}"


# --- sources -------------------------------------------------------------------------------------


class CameraSource:
    """A local UVC camera.

    On Windows DirectShow gives dependable manual exposure, so it is tried first; MSMF and the
    backend default follow. Any backend that cannot open the device is reported, not skipped
    silently.
    """

    def __init__(self, index: int = 0, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT):
        self.index = index
        self.width = width
        self.height = height
        self._cap: cv2.VideoCapture | None = None
        self.backend = ""

    def open(self) -> None:
        attempts = []
        backends = [
            ("dshow", getattr(cv2, "CAP_DSHOW", None)),
            ("msmf", getattr(cv2, "CAP_MSMF", None)),
        ]
        backends.append(("default", None))

        for name, flag in backends:
            cap = (
                cv2.VideoCapture(self.index) if flag is None else cv2.VideoCapture(self.index, flag)
            )
            if cap.isOpened():
                self._cap = cap
                self.backend = name
                break
            cap.release()
            attempts.append(name)

        if self._cap is None:
            raise CaptureError(
                f"摄像头 {self.index} 不可用（已尝试 {', '.join(attempts)}）。"
                "请检查 USB 连接后重试；没有摄像头时可用 --images 指定图片目录。"
            )

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

    def lock_exposure(self) -> ExposureLock:
        """Switch to manual exposure, pin it, then prove the lock by measuring brightness drift."""
        if self._cap is None:
            raise CaptureError("摄像头尚未打开")

        # 0.25 is manual on DirectShow and on most UVC drivers; 1 means manual on V4L2.
        for mode in (0.25, 1.0):
            self._cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, mode)
            if int(self._cap.get(cv2.CAP_PROP_AUTO_EXPOSURE)) != 3:
                break

        current = self._cap.get(cv2.CAP_PROP_EXPOSURE)
        pinned = current if current not in (0.0, -1.0) else -6.0
        self._cap.set(cv2.CAP_PROP_EXPOSURE, pinned)
        gain = self._cap.get(cv2.CAP_PROP_GAIN)

        spreads = []
        for _ in range(LOCK_SAMPLE_FRAMES):
            frame = self._read_raw()
            spreads.append(float(frame.mean()))
        if not spreads:
            raise CaptureError("锁定曝光后读不到帧")

        low, high = min(spreads), max(spreads)
        spread = 0.0 if low == 0 else (high - low) / low
        locked = spread <= BRIGHTNESS_TOLERANCE
        return ExposureLock(
            locked=locked,
            exposure_raw=pinned,
            gain_raw=gain,
            brightness_spread=round(spread, 4),
            reason="" if locked else f"帧间亮度波动 {spread:.1%}，超过 10%，曝光可能未真正锁定",
        )

    def read(self) -> np.ndarray:
        if self._cap is None:
            raise CaptureError("摄像头尚未打开")
        return self._read_raw()

    def _read_raw(self) -> np.ndarray:
        assert self._cap is not None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise CaptureError("读帧失败，摄像头可能已断开")
        return frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def size(self) -> tuple[int, int]:
        if self._cap is None:
            return self.width, self.height
        return (
            int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or self.width,
            int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or self.height,
        )


class ImageFolderSource:
    """Stands in for the camera when no hardware is attached.

    Same interface, same downstream path: the frames are real images, only the device is absent.
    """

    SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp")

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self._files: list[Path] = []
        self._cursor = 0
        self.backend = "images"

    def open(self) -> None:
        if not self.folder.is_dir():
            raise CaptureError(f"图片目录不存在：{self.folder}")
        self._files = sorted(p for p in self.folder.iterdir() if p.suffix.lower() in self.SUFFIXES)
        if not self._files:
            raise CaptureError(f"目录里没有图片：{self.folder}")

    def lock_exposure(self) -> ExposureLock:
        # Nothing to lock; report it honestly rather than pretending.
        return ExposureLock(
            locked=False,
            exposure_raw=0.0,
            gain_raw=0.0,
            brightness_spread=0.0,
            reason="图片目录输入，无曝光可锁（仅用于无摄像头时验证链路）",
        )

    def read(self) -> np.ndarray:
        if not self._files:
            raise CaptureError("图片目录尚未打开")
        path = self._files[self._cursor % len(self._files)]
        self._cursor += 1
        frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if frame is None:
            raise CaptureError(f"图片无法读取：{path}")
        return frame

    def close(self) -> None:
        return None

    @property
    def size(self) -> tuple[int, int]:
        if not self._files:
            return DEFAULT_WIDTH, DEFAULT_HEIGHT
        frame = cv2.imread(str(self._files[0]), cv2.IMREAD_COLOR)
        if frame is None:
            return DEFAULT_WIDTH, DEFAULT_HEIGHT
        height, width = frame.shape[:2]
        return width, height


# --- sink ----------------------------------------------------------------------------------------


class CaptureSession:
    """Owns the output directory, frame ids, scoring and the manifest."""

    def __init__(
        self,
        source: CameraSource | ImageFolderSource,
        root: str | Path,
        site: str,
        session_id: str | None = None,
        jpeg_quality: int = 90,
    ):
        self.source = source
        self.root = Path(root)
        self.site = site
        self.started_at = datetime.now(LOCAL_TZ)
        self.session_id = session_id or default_session_id(site, self.started_at)
        self.jpeg_quality = jpeg_quality
        self.records: list[FrameRecord] = []
        self._index = 0

    @property
    def directory(self) -> Path:
        return self.root / self.site / self.started_at.strftime("%Y%m%d") / self.session_id

    @property
    def manifest_path(self) -> Path:
        return self.directory / "manifest.json"

    def grab(self) -> FrameRecord:
        frame = self.source.read()
        self._index += 1
        captured_at = datetime.now(LOCAL_TZ)
        frame_id = make_frame_id(captured_at, self._index)

        # Encode first, then score the decoded bytes: JPEG smoothing shifts Laplacian variance, so a
        # score taken from the in-memory frame would not match the file. Score what you store, or the
        # record and the artefact can never be reconciled.
        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        if not ok:
            raise CaptureError("JPEG 编码失败")
        stored = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if stored is None:
            raise CaptureError("编码后的帧无法解码")
        quality = score_frame(stored)

        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{frame_id}.jpg"
        try:
            path.write_bytes(buffer.tobytes())
        except OSError as err:
            raise CaptureError(f"写盘失败：{path}（{err}）") from err

        height, width = frame.shape[:2]
        record = FrameRecord(
            frame_id=frame_id,
            session_id=self.session_id,
            site=self.site,
            path=str(path.relative_to(self.root)),
            captured_at=captured_at.isoformat(timespec="milliseconds"),
            width=int(width),
            height=int(height),
            quality=quality,
        )
        self.records.append(record)
        self.write_manifest()
        return record

    def write_manifest(self) -> None:
        payload = {
            "session_id": self.session_id,
            "site": self.site,
            "started_at": self.started_at.isoformat(timespec="milliseconds"),
            "frame_count": len(self.records),
            "frames": [r.as_dict() for r in self.records],
        }
        self.manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# --- verification --------------------------------------------------------------------------------


def verify(session_dir: str | Path) -> list[str]:
    """Check that file, score and frame_id agree. Returns a list of problems; empty means pass."""
    session_dir = Path(session_dir)
    manifest_path = session_dir / "manifest.json"
    if not manifest_path.is_file():
        return [f"缺少 manifest：{manifest_path}"]

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    frames = payload.get("frames", [])
    if not frames:
        return ["manifest 里没有帧"]

    problems: list[str] = []
    root = session_dir.parents[2]
    for record in frames:
        frame_id = record["frame_id"]
        path = root / record["path"]
        if not path.is_file():
            problems.append(f"{frame_id}: 文件不存在 {path}")
            continue
        if path.stem != frame_id:
            problems.append(f"{frame_id}: 文件名 {path.stem} 与 frame_id 不一致")
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            problems.append(f"{frame_id}: 图片读不出来")
            continue
        if (int(image.shape[1]), int(image.shape[0])) != (record["width"], record["height"]):
            problems.append(f"{frame_id}: 尺寸与 manifest 不一致")
        rescored = score_frame(image)
        if rescored.score != record["quality"]["score"]:
            problems.append(
                f"{frame_id}: 重算质量分 {rescored.score} != manifest {record['quality']['score']}"
            )
    return problems


def _build_source(args: argparse.Namespace) -> CameraSource | ImageFolderSource:
    if args.images:
        return ImageFolderSource(args.images)
    return CameraSource(index=args.camera, width=args.width, height=args.height)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="采集若干帧并落盘，或校验一次采集会话")
    parser.add_argument("--count", type=int, default=20, help="抓取帧数（默认 20）")
    parser.add_argument("--site", default="A3", help="点位编号")
    parser.add_argument("--root", default="../data/frames", help="落盘根目录")
    parser.add_argument("--camera", type=int, default=0, help="摄像头索引")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--images", help="用图片目录代替摄像头（无硬件时用）")
    parser.add_argument("--verify", metavar="SESSION_DIR", help="只校验，不采集")
    args = parser.parse_args(argv)

    if args.verify:
        problems = verify(args.verify)
        if problems:
            print("校验未通过：")
            for line in problems:
                print(f"  - {line}")
            return 1
        print(f"校验通过：{args.verify}")
        return 0

    source = _build_source(args)
    try:
        source.open()
        lock = source.lock_exposure()
        if not lock.locked:
            print(f"提示：{lock.reason}")

        session = CaptureSession(source, args.root, args.site)
        verdicts = {"ok": 0, "retake": 0}
        for i in range(args.count):
            record = session.grab()
            verdicts[record.quality.verdict] += 1
            print(
                f"[{i + 1:>2}/{args.count}] {record.frame_id}  质量 {record.quality.score:>3} "
                f"{record.quality.verdict:<6} {record.path}"
            )
    except CaptureError as err:
        print(f"采集失败：{err}", file=sys.stderr)
        return 1
    finally:
        source.close()

    print(
        f"\n会话 {session.session_id}：{len(session.records)} 帧（合格 {verdicts['ok']}，"
        f"需重拍 {verdicts['retake']}）\n目录 {session.directory}"
    )

    problems = verify(session.directory)
    if problems:
        print("落盘校验未通过：")
        for line in problems:
            print(f"  - {line}")
        return 1
    print("落盘校验通过：文件、质量分与 frame_id 一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
