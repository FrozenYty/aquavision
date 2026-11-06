"""Quality scoring and capture persistence (P1-03).

The scoring tests run without a camera: they build synthetic images that are, by construction,
sharp or blurred, correctly exposed or not, neutral or blue-cast, and assert that the score orders
them the way the operator would.
"""

from __future__ import annotations

import json

import cv2
import numpy as np
import pytest
from app.vision.capture import CaptureSession, ImageFolderSource, make_frame_id, verify
from app.vision.quality import PASS_MARK, Quality, measure, score_frame

SIZE = (240, 320)  # height, width — small enough to keep the tests fast


def sharp_image(seed: int = 7) -> np.ndarray:
    """High-frequency noise: a sharp frame."""
    rng = np.random.default_rng(seed)
    return rng.integers(60, 200, size=(*SIZE, 3), dtype=np.uint8)


def blurred_image() -> np.ndarray:
    """The same noise after a heavy blur: a defocused frame."""
    return cv2.GaussianBlur(sharp_image(), (31, 31), 0)


def flat_image(value: int = 128) -> np.ndarray:
    """A uniform frame: perfectly smooth, so sharpness collapses."""
    return np.full((*SIZE, 3), value, dtype=np.uint8)


def blue_cast_image() -> np.ndarray:
    """Neutral grey with the blue channel pushed up, as water does."""
    image = np.full((*SIZE, 3), 120, dtype=np.uint8)
    image[:, :, 0] = 190  # BGR
    return image


def test_measure_orders_sharpness():
    sharp, _, _ = measure(sharp_image())
    blurred, _, _ = measure(blurred_image())
    assert sharp > blurred * 5


def test_sharp_scores_above_blurred():
    assert score_frame(sharp_image()).score > score_frame(blurred_image()).score


def test_flat_frame_is_a_retake():
    result = score_frame(flat_image())
    assert result.verdict == "retake"
    assert result.score < PASS_MARK


def test_blue_cast_loses_colorcast_points():
    neutral = score_frame(flat_image())
    cast = score_frame(blue_cast_image())
    assert cast.colorcast < neutral.colorcast
    assert cast.score < neutral.score


def test_score_is_deterministic():
    image = sharp_image()
    assert score_frame(image) == score_frame(image)


def test_quality_components_are_ints_in_range():
    result = score_frame(sharp_image())
    assert isinstance(result, Quality)
    for value in (result.sharpness, result.brightness, result.colorcast, result.score):
        assert isinstance(value, int)
        assert 0 <= value <= 100


def test_empty_image_is_rejected():
    with pytest.raises(ValueError):
        score_frame(np.zeros((0, 0, 3), dtype=np.uint8))


def test_frame_id_shape():
    from datetime import datetime

    from app.vision.capture import LOCAL_TZ

    frame_id = make_frame_id(datetime(2026, 11, 6, 9, 46, 12, tzinfo=LOCAL_TZ), 7)
    assert frame_id == "20261106T094612-0007"


def test_session_writes_files_and_manifest(tmp_path):
    images = tmp_path / "in"
    images.mkdir()
    for i in range(3):
        cv2.imwrite(str(images / f"src{i}.jpg"), sharp_image(seed=i + 1))

    source = ImageFolderSource(images)
    source.open()
    session = CaptureSession(source, tmp_path / "out", site="A3")
    records = [session.grab() for _ in range(5)]
    source.close()

    assert len(records) == 5
    manifest = json.loads(session.manifest_path.read_text(encoding="utf-8"))
    assert manifest["frame_count"] == 5
    assert [f["frame_id"] for f in manifest["frames"]] == [r.frame_id for r in records]
    assert len({r.frame_id for r in records}) == 5, "frame ids must be unique inside a session"

    for record in records:
        path = tmp_path / "out" / record.path
        assert path.is_file(), f"missing {path}"
        assert path.stem == record.frame_id
        assert record.quality.verdict in {"ok", "retake"}


def test_verify_passes_on_a_fresh_session_and_catches_a_tampered_score(tmp_path):
    images = tmp_path / "in"
    images.mkdir()
    cv2.imwrite(str(images / "a.jpg"), sharp_image())

    source = ImageFolderSource(images)
    source.open()
    session = CaptureSession(source, tmp_path / "out", site="A3")
    for _ in range(2):
        session.grab()
    source.close()

    assert verify(session.directory) == []

    manifest = json.loads(session.manifest_path.read_text(encoding="utf-8"))
    manifest["frames"][0]["quality"]["score"] = 1
    session.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    problems = verify(session.directory)
    assert any("重算质量分" in p for p in problems)


def test_verify_reports_a_missing_file(tmp_path):
    images = tmp_path / "in"
    images.mkdir()
    cv2.imwrite(str(images / "a.jpg"), sharp_image())

    source = ImageFolderSource(images)
    source.open()
    session = CaptureSession(source, tmp_path / "out", site="A3")
    record = session.grab()
    source.close()

    (tmp_path / "out" / record.path).unlink()
    problems = verify(session.directory)
    assert any("文件不存在" in p for p in problems)


def test_recorded_score_matches_the_stored_file(tmp_path):
    """A score must be taken from the bytes on disk, not from the frame in memory.

    JPEG is lossy, and it smooths high frequencies, so Laplacian variance drops between the frame and
    the file. On a very sharp frame the sharpness sub-score clamps at 100 and the difference hides; on
    a borderline frame it does not. This test uses the borderline case on purpose.
    """
    images = tmp_path / "in"
    images.mkdir()
    borderline = cv2.GaussianBlur(sharp_image(), (11, 11), 0)
    cv2.imwrite(str(images / "borderline.jpg"), borderline)

    source = ImageFolderSource(images)
    source.open()
    session = CaptureSession(source, tmp_path / "out", site="A3")
    record = session.grab()
    source.close()

    stored = cv2.imread(str(tmp_path / "out" / record.path), cv2.IMREAD_COLOR)
    assert score_frame(stored).score == record.quality.score
    assert verify(session.directory) == []
