"""Per-class thresholds and labels validation (P3-15, FR-M6-04, AC-26).

`species_dict.conf_thr` existed and **nothing read it**: the detection paths passed the caller's global
`conf_thr` straight to the model, so an operator editing a class threshold on the species page changed a
number that had no effect - the same shape of defect `P3-19` closed for the system parameters.

The two sentences this file holds are AC-26's: a new threshold applies to **new jobs** and not to ones
already finished, and a class code that disagrees with the model's `labels.txt` is refused.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.envelope import CONFLICT
from app.models import DetectObject, MediaAsset, ModelVersion, SpeciesDict, SysUser
from app.security import hash_password
from app.seed import SPECIES_SEED, seed_species
from app.worker import Worker
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

LOCAL = ("127.0.0.1", 50000)
CODES = [str(row["class_code"]) for row in SPECIES_SEED]


class SoftDetector:
    """A model that always sees every class at a confidence the test chooses.

    It also remembers what it was asked for: a per-class threshold below the task's own floor can only
    work if the floor the model receives is lowered to it, and that is worth asserting rather than
    assuming.
    """

    def __init__(self, confidence: float = 0.60):
        self.confidence = confidence
        self.model_version_id = 1
        self.version_name = "fake-v8n"
        self.floors: list[float] = []

    def predict(self, _asset, conf_thr: float = 0.5, iou_thr: float = 0.45, max_det: int = 100):
        self.floors.append(float(conf_thr))
        return [
            {
                "class_code": code,
                "confidence": self.confidence,
                "x": 0.1,
                "y": 0.1,
                "w": 0.2,
                "h": 0.2,
            }
            for code in CODES
        ]


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_DSN", f"sqlite:///{(tmp_path / 'species.db').as_posix()}")
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'species.db').as_posix()}")
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    factory = app.state.session_factory
    with factory() as session:
        seed_species(session)
        hashed, salt = hash_password("password123")
        session.add(
            SysUser(
                username="admin",
                password_hash=hashed,
                salt=salt,
                role_code="admin",
                real_name="admin",
                status=1,
                fail_count=0,
            )
        )
        now = datetime.now(UTC).replace(tzinfo=None)
        for index in range(4):
            session.add(
                MediaAsset(
                    frame_id=f"20261116T100000-{index:04d}",
                    session_id="s-species",
                    point_code="A3",
                    file_path=f"frames/{index:04d}.jpg",
                    file_size=1024 + index,
                    file_hash=f"{index:064d}",
                    captured_at=now,
                    width=640,
                    height=480,
                    quality_score=80,
                    quality_flag=0,
                    is_retake=0,
                )
            )
        session.commit()

    with TestClient(app, client=LOCAL) as client:
        yield client, app, factory
    get_settings.cache_clear()


def sign_in(client: TestClient) -> dict[str, str]:
    body = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password123"}
    ).json()
    return {"Authorization": f"Bearer {body['data']['token']}"}


def patch_threshold(client, headers, code: str, value: float):
    return client.patch(f"/api/species/{code}", json={"conf_thr": value}, headers=headers)


def boxes_of(factory, task_id: int) -> list[str]:
    with factory() as session:
        rows = session.scalars(
            select(DetectObject.class_code).where(DetectObject.task_id == task_id)
        ).all()
        return sorted(rows)


def run_batch(factory, detector, count: int = 1) -> int:
    """Create a queued task the way the API does, then let a real Worker take it."""
    from app.routers.tasks import BatchBody, create_batch

    with factory() as session:
        task = create_batch(session, BatchBody(asset_count=count))
        task_id = task.task_id
    worker = Worker(factory, workers=1, poll_seconds=0.05, detector=detector)
    worker.start()
    worker.stop()
    return task_id


def test_a_raised_class_threshold_binds_a_new_job_and_leaves_the_finished_one(rig):
    client, app, factory = rig
    headers = sign_in(client)
    detector = SoftDetector(confidence=0.60)

    before = run_batch(factory, detector)
    assert boxes_of(factory, before) == sorted(CODES), "the job before the change sees every class"

    assert patch_threshold(client, headers, "holothurian", 0.80).status_code == 200

    after = run_batch(factory, detector)
    kept = boxes_of(factory, after)
    assert "holothurian" not in kept, (
        f"a 0.60 box must not clear holothurian's new 0.80 floor: {kept}"
    )
    assert kept == sorted(CODES[1:])
    # The finished job is untouched: its boxes are rows and the change does not rewrite them.
    assert boxes_of(factory, before) == sorted(CODES)


def test_a_lowered_class_threshold_lowers_the_floor_the_model_is_asked_for(rig):
    """Below the task's own 0.5, the model has to be asked for the lower number or the box never exists."""
    client, app, factory = rig
    headers = sign_in(client)
    detector = SoftDetector(confidence=0.25)

    assert patch_threshold(client, headers, "chlamys", 0.20).status_code == 200

    task = run_batch(factory, detector)
    assert min(detector.floors) <= 0.20, f"the model was asked for {detector.floors}"
    assert "chlamys" in boxes_of(factory, task)

    late = run_batch(factory, detector)
    assert "chlamys" in boxes_of(factory, late)


def test_the_single_frame_route_applies_the_same_thresholds(rig):
    client, app, factory = rig
    headers = sign_in(client)
    detector = SoftDetector(confidence=0.60)
    app.state.detector = detector

    assert patch_threshold(client, headers, "asterias", 0.90).status_code == 200

    body = client.post("/api/detect/frames/20261116T100000-0000", headers=headers).json()
    assert body["code"] == 0, body
    classes = sorted(box["class_code"] for box in body["data"]["boxes"])
    assert "asterias" not in classes, body["data"]["boxes"]
    assert classes == sorted(CODES[:-1])


def _labels_file(tmp_path, codes) -> str:
    path = tmp_path / "labels.txt"
    path.write_text("\n".join(codes) + "\n", encoding="utf-8")
    return path.as_posix()


def test_a_class_code_that_disagrees_with_the_labels_is_refused(rig, tmp_path):
    """AC-26's other half: the dictionary and the model's labels are one contract, in order."""
    client, app, factory = rig
    headers = sign_in(client)

    with factory() as session:
        session.add(
            ModelVersion(
                version_name="v8n-labels-check",
                weight_path="models/v8n-E0-exploratory/best.pt",
                labels_path=_labels_file(tmp_path, CODES),
                status=1,
                is_online=1,
            )
        )
        session.commit()

    # Order matches the labels: the edit is accepted.
    assert patch_threshold(client, headers, "chlamys", 0.40).status_code == 200

    # Swap two codes in the dictionary, as a bad seed or a hand edit would. A temporary value keeps
    # the unique index happy while the two rows trade places.
    with factory() as session:
        first = session.scalar(select(SpeciesDict).where(SpeciesDict.class_code == CODES[0]))
        second = session.scalar(select(SpeciesDict).where(SpeciesDict.class_code == CODES[1]))
        first.class_code = "zz-temporary"
        session.flush()
        second.class_code = CODES[0]
        session.flush()
        first.class_code = CODES[1]
        session.commit()

    response = patch_threshold(client, headers, "chlamys", 0.45)
    body = response.json()
    assert response.status_code == 409, body
    assert body["code"] == CONFLICT, body
    assert "labels" in body["message"], body
    with factory() as session:
        row = session.scalar(select(SpeciesDict).where(SpeciesDict.class_code == "chlamys"))
        assert float(row.conf_thr) == pytest.approx(0.40), "the refused edit must not be stored"


def test_a_code_the_labels_do_not_declare_is_refused(rig, tmp_path):
    client, app, factory = rig
    headers = sign_in(client)

    with factory() as session:
        session.add(
            ModelVersion(
                version_name="v8n-labels-check",
                weight_path="models/v8n-E0-exploratory/best.pt",
                labels_path=_labels_file(tmp_path, CODES[:3]),
                status=1,
                is_online=1,
            )
        )
        session.commit()

    response = patch_threshold(client, headers, CODES[3], 0.55)
    body = response.json()
    assert response.status_code == 409, body
    assert CODES[3] in body["message"], body
