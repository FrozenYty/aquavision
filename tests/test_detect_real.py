"""One real inference through the API (P2-05b).

This file separates "the route answers something" from "the route runs the registered weights". It
copies the development database, lets the app load the online model the same way `uvicorn` does, and
compares the boxes the API returned with a direct run of the same weights on the same image.

What it needs and a clean checkout does not have: `data/app.db`, exactly one online `model_version`
row in it, the weight file that row names, and ultralytics with torch installed. A missing piece
**skips** the test with that reason in the report — never silently, and never by weakening the
comparison.

The frame is a labelled image from the DUO test split, written into the copied database the way the
capture route would have written it. That split is not in git either, so a machine without it falls
back to a frame the capture pipeline wrote.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import cv2
import pytest
from app.config import get_settings
from app.db import engine_from_dsn
from app.models import DetectObject, DetectTask, MediaAsset, ModelVersion, SpeciesDict, SysUser
from app.security import hash_password
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
DEV_DB = DATA / "app.db"
TEST_IMAGES = DATA / "dataset" / "test" / "images"
TEST_LABELS = DATA / "dataset" / "test" / "labels"
CONF_THRESHOLD = 0.5


def _weights_for(row: ModelVersion) -> Path:
    weights = Path(row.weight_path)
    return weights if weights.is_absolute() else REPO / weights


def _most_populated_test_image() -> Path | None:
    """The busiest DUO test image among the first 200 files, so the run has something to find."""
    if not TEST_IMAGES.is_dir():
        return None
    candidates = sorted(TEST_IMAGES.glob("*.jpg"))
    if not candidates:
        return None

    def boxes(image: Path) -> int:
        label = TEST_LABELS / f"{image.stem}.txt"
        if not label.is_file():
            return 0
        return len(
            [line for line in label.read_text(encoding="utf-8").splitlines() if line.strip()]
        )

    return max(candidates[:200], key=boxes)


@pytest.fixture
def real_client(tmp_path, monkeypatch):
    """A client on a *copy* of the development database, with the real online detector loaded."""
    if not DEV_DB.is_file():
        pytest.skip(f"the development database is not on this machine: {DEV_DB.name} is missing")

    try:
        import ultralytics  # noqa: F401
    except ImportError as exc:  # the CI environment installs neither ultralytics nor torch
        pytest.skip(f"ultralytics is not installed here ({exc.name}), so no model can be loaded")

    copied = tmp_path / "app.db"
    shutil.copy2(DEV_DB, copied)
    engine = engine_from_dsn(f"sqlite:///{copied.as_posix()}")
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    labeled = _most_populated_test_image()
    with factory() as session:
        online = list(session.scalars(select(ModelVersion).where(ModelVersion.is_online == 1)))
        if len(online) != 1:
            pytest.skip(f"expected exactly one online model_version row, found {len(online)}")
        row = online[0]
        weights = _weights_for(row)
        if not weights.is_file():
            pytest.skip(f"the registered weight file is absent: {row.weight_path}")

        if labeled is not None:
            frame_id = "20260101T000000-t001"
            height, width = cv2.imread(str(labeled)).shape[:2]
            session.add(
                MediaAsset(
                    frame_id=frame_id,
                    session_id="s-smoke",
                    point_code="A3",
                    file_path=labeled.relative_to(DATA).as_posix(),
                    file_size=labeled.stat().st_size,
                    file_hash="0" * 64,
                    captured_at=datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None),
                    width=width,
                    height=height,
                    quality_score=90,
                    quality_flag=0,
                    is_retake=0,
                )
            )
        else:
            asset = next(
                (
                    a
                    for a in session.scalars(select(MediaAsset).order_by(MediaAsset.asset_id))
                    if (DATA / a.file_path).is_file()
                ),
                None,
            )
            if asset is None:
                pytest.skip("no captured frame has its image under data/ any more")
            frame_id = asset.frame_id

        hashed, salt = hash_password("password123")
        username = f"smoke-{uuid4().hex[:8]}"
        session.add(
            SysUser(
                username=username,
                password_hash=hashed,
                salt=salt,
                role_code="admin",
                real_name="Smoke Test",
                status=1,
                fail_count=0,
            )
        )
        session.commit()

    monkeypatch.setenv("DB_DSN", f"sqlite:///{copied.as_posix()}")
    monkeypatch.setenv("AV_DATA_DIR", str(DATA))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    try:
        with TestClient(app) as client:
            # The loader's own verdict, not a test fixture: weights, torch and class order included.
            assert app.state.detector is not None, app.state.detector_error
            token = client.post(
                "/api/auth/login", json={"username": username, "password": "password123"}
            ).json()["data"]["token"]
            yield client, factory, row, frame_id, token, labeled is not None
    finally:
        get_settings.cache_clear()
        engine.dispose()


def _manual_boxes(image: Path, row: ModelVersion) -> list[dict]:
    """The same weights, the same parameters, run without the server in the way."""
    from ultralytics import YOLO

    model = YOLO(str(_weights_for(row)))
    result = model.predict(
        source=str(image), conf=CONF_THRESHOLD, iou=0.45, max_det=100, imgsz=640, verbose=False
    )[0]
    boxes = []
    for box in result.boxes:
        x1, y1, x2, y2 = (float(value) for value in box.xyxyn[0].tolist())
        boxes.append(
            {
                "class_code": str(model.names[int(box.cls)]),
                "confidence": float(box.conf),
                "x": x1,
                "y": y1,
                "w": x2 - x1,
                "h": y2 - y1,
            }
        )
    return boxes


def test_one_real_inference_matches_a_manual_run_of_the_same_weights(real_client):
    client, factory, row, frame_id, token, labeled = real_client
    response = client.post(
        f"/api/detect/frames/{frame_id}", headers={"Authorization": f"Bearer {token}"}
    )
    body = response.json()
    assert response.status_code == 200, body
    data = body["data"]

    assert data["frame_id"] == frame_id
    assert data["model_version"] == row.version_name
    assert data["conf_threshold"] == CONF_THRESHOLD
    assert isinstance(data["latency_ms"], int)
    # Contract §8 asks for a measurement, not an estimate. Zero would mean nothing was timed.
    assert data["latency_ms"] > 0

    with factory() as session:
        asset = session.scalar(select(MediaAsset).where(MediaAsset.frame_id == frame_id))
        image = DATA / asset.file_path
    expected = _manual_boxes(image, row)

    if labeled:
        # The chosen image is a labelled DUO frame with the most boxes in the split: an empty result
        # would mean the weights, the parameters or the class order are wrong, not that the scene is
        # quiet.
        assert expected, "a labelled test image produced no box at conf 0.5 — check the weights"
    assert len(data["boxes"]) == len(expected)
    # The response carries the stored rows, and the columns are the data model's NUMERIC sizes:
    # confidence keeps four decimals, coordinates five (§2, §3.5). Compare at that precision.
    for got, want in zip(data["boxes"], expected, strict=True):
        assert got["class_code"] == want["class_code"]
        assert got["confidence"] == pytest.approx(want["confidence"], abs=1e-4)
        assert got["x"] == pytest.approx(want["x"], abs=1e-5)
        assert got["y"] == pytest.approx(want["y"], abs=1e-5)
        assert got["w"] == pytest.approx(want["w"], abs=1e-5)
        assert got["h"] == pytest.approx(want["h"], abs=1e-5)

    # What was stored is what was answered, and the task records the version that produced it.
    with factory() as session:
        rows = session.scalars(select(DetectObject).where(DetectObject.frame_id == frame_id)).all()
        assert len(rows) == len(expected)
        assert {row.class_code for row in rows} == {box["class_code"] for box in expected}
        task = session.get(DetectTask, data["task_id"])
        assert task.status == 2
        assert task.obj_count == len(expected)
        assert task.model_version_id == row.model_id


def test_the_loader_refuses_a_model_whose_class_order_disagrees(real_client):
    """Data model §3.6 makes the class order a contract: a mismatch would mislabel every box."""
    from app.detector import load_online

    client, factory, _row, _frame_id, _token, _labeled = real_client
    with factory() as session:
        session.execute(delete(SpeciesDict).where(SpeciesDict.class_code == "asterias"))
        session.commit()

    detector, reason = load_online(client.app.state.session_factory, get_settings())
    assert detector is None
    assert "species_dict" in reason


def test_a_frame_whose_image_is_gone_is_an_error_not_an_empty_result(real_client):
    """Ultralytics answers a missing source with no boxes; that empty result would be a lie."""
    client, factory, _row, _frame_id, token, _labeled = real_client
    with factory() as session:
        session.add(
            MediaAsset(
                frame_id="20260101T000000-gone",
                session_id="s-smoke",
                point_code="A3",
                file_path="frames/this-file-does-not-exist.jpg",
                file_size=1024,
                file_hash="1" * 64,
                captured_at=datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None),
                width=640,
                height=480,
                quality_score=90,
                quality_flag=0,
                is_retake=0,
            )
        )
        session.commit()

    response = client.post(
        "/api/detect/frames/20260101T000000-gone", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == 50001
    assert "帧文件不存在" in body["message"]

    with factory() as session:
        assert (
            session.scalars(
                select(DetectObject).where(DetectObject.frame_id == "20260101T000000-gone")
            ).all()
            == []
        )
