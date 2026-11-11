"""Demo mode's reset action (P3-06, AC-36).

The fixture follows `test_api_skeleton.py`: a real app over a throwaway SQLite database and a real
TestClient, with the demo setting supplied through the environment the way a deployment supplies it.
The tests seed one row in every business table so a missed table shows up as a non-zero count rather
than as a claim that the reset happened.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import (
    Dataset,
    DatasetItem,
    DetectObject,
    DetectTask,
    DetectTaskItem,
    MediaAsset,
    ModelVersion,
    Report,
    SpeciesDict,
    SysLog,
    SysMessage,
    SysParam,
    SysUser,
    TrainExperiment,
)
from app.security import hash_password
from app.seed import seed_species
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

MODEL_NAME = "v8n-E0-exploratory"
FRAME_ID = "20261111T120000-0001"

#: The business tables a reset empties, in the order the route reports them.
DELETED_MODELS = (
    DetectObject,
    DetectTaskItem,
    DetectTask,
    Report,
    DatasetItem,
    Dataset,
    TrainExperiment,
    SysMessage,
    SysLog,
    MediaAsset,
)


@contextmanager
def _app_client(tmp_path, monkeypatch, *, demo_enabled: bool):
    dsn = f"sqlite:///{(tmp_path / 'demo.db').as_posix()}"
    monkeypatch.setenv("DB_DSN", dsn)
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    monkeypatch.setenv("AV_DEMO_ENABLED", "1" if demo_enabled else "0")
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    engine = engine_from_dsn(dsn)
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    factory = app.state.session_factory
    with factory() as session:
        seed_species(session)
        session.add(
            ModelVersion(
                version_name=MODEL_NAME,
                weight_path="weights/e0.pt",
                labels_path="labels.txt",
                status=1,
                is_online=1,
            )
        )
        session.add(SysParam(param_key="retention_days", param_value="30", value_type="int"))
        for name, role in (("admin", "admin"), ("observer", "observer")):
            hashed, salt = hash_password("password123")
            session.add(
                SysUser(
                    username=name,
                    password_hash=hashed,
                    salt=salt,
                    role_code=role,
                    real_name=name,
                    status=1,
                    fail_count=0,
                )
            )
        session.commit()

    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
def client(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, demo_enabled=True) as test_client:
        yield test_client


@pytest.fixture
def demo_disabled_client(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, demo_enabled=False) as test_client:
        yield test_client


def sign_in(client: TestClient, username: str = "admin") -> str:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": "password123"}
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def seed_business_rows(client: TestClient) -> Path:
    """One row in every business table, plus a frame file the reset has to remove.

    The login that precedes this in each test already wrote the `sys_log` row, so the reset has one
    row to delete in all ten tables.
    """
    data_dir = Path(get_settings().data_dir)
    frame_file = data_dir / "frames" / "A3" / "20261111" / "s-demo" / "frame.jpg"
    frame_file.parent.mkdir(parents=True, exist_ok=True)
    frame_file.write_bytes(b"jpeg-bytes")

    with client.app.state.session_factory() as session:
        asset = MediaAsset(
            frame_id=FRAME_ID,
            session_id="s-demo",
            point_code="A3",
            file_path="frames/A3/20261111/s-demo/frame.jpg",
            file_size=10,
            file_hash="a" * 64,
            captured_at=datetime(2026, 11, 11, 12, 0, 0),
            width=640,
            height=480,
            quality_score=80,
            quality_flag=0,
            is_retake=0,
        )
        session.add(asset)
        session.flush()

        task = DetectTask(
            task_code="DT-demo",
            task_type=2,
            asset_count=1,
            status=2,
            progress=100,
            obj_count=1,
        )
        session.add(task)
        session.flush()
        session.add(
            DetectTaskItem(task_id=task.task_id, asset_id=asset.asset_id, state=2, box_count=1)
        )
        session.add(
            DetectObject(
                task_id=task.task_id,
                asset_id=asset.asset_id,
                frame_id=FRAME_ID,
                class_code="holothurian",
                confidence=0.9,
                x=0.1,
                y=0.1,
                w=0.2,
                h=0.2,
                is_manual=0,
                review_status=0,
            )
        )
        session.add(
            Report(
                report_code="RP261111-001",
                period_start=datetime(2026, 11, 1),
                period_end=datetime(2026, 11, 11),
                template="standard",
                basis="reviewed",
                status=1,
            )
        )
        dataset = Dataset(
            snapshot_name="DS-DEMO",
            manifest_path="data/DS-DEMO.csv",
            split_ratio="7:2:1",
            seed=42,
            frame_count=1,
        )
        session.add(dataset)
        session.flush()
        session.add(DatasetItem(dataset_id=dataset.dataset_id, asset_id=asset.asset_id, split=1))
        session.add(
            TrainExperiment(
                exp_name="E0",
                dataset_snapshot="DS-DEMO",
                split_ratio="7:2:1",
                seed=42,
                epochs=10,
                batch_size=8,
                lr=0.001,
            )
        )
        session.add(SysMessage(msg_type="task_failed", level=2, title="demo"))
        session.commit()

    return frame_file


def table_counts(client: TestClient) -> dict[str, int]:
    with client.app.state.session_factory() as session:
        return {
            model.__tablename__: session.scalar(select(func.count()).select_from(model)) or 0
            for model in DELETED_MODELS
        }


def test_reset_clears_the_business_rows_and_keeps_the_rest(client):
    admin = auth(sign_in(client))
    frame_file = seed_business_rows(client)

    body = client.post("/api/demo/reset", headers=admin).json()
    assert body["code"] == 0, body
    data = body["data"]

    # Every table it touches is reported, and every seeded row is gone. The login wrote the one
    # sys_log row, which the reset removes as well.
    expected = {model.__tablename__: 1 for model in DELETED_MODELS}
    assert data["deleted"] == expected
    assert data["frame_files_removed"] == 1
    assert data["model_online"] == MODEL_NAME

    assert not frame_file.exists()
    assert not (Path(get_settings().data_dir) / "frames").exists()
    assert table_counts(client) == {name: 0 for name in expected}

    with client.app.state.session_factory() as session:
        # The three keeps, each for its own reason: the rehearsal needs its model and class order, and
        # the caller must still be able to sign in afterwards.
        assert session.scalar(select(func.count()).select_from(SpeciesDict)) == 4
        assert session.scalar(select(func.count()).select_from(ModelVersion)) == 1
        model = session.scalar(select(ModelVersion))
        assert (model.version_name, model.is_online) == (MODEL_NAME, 1)
        assert session.scalar(select(func.count()).select_from(SysUser)) == 2
        assert session.scalar(select(func.count()).select_from(SysParam)) == 1

    again = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password123"}
    ).json()
    assert again["code"] == 0, again


def test_a_second_reset_reports_zeros_and_does_not_fail(client):
    admin = auth(sign_in(client))
    seed_business_rows(client)

    first = client.post("/api/demo/reset", headers=admin).json()["data"]
    assert first["deleted"]["media_asset"] == 1
    assert first["frame_files_removed"] == 1

    body = client.post("/api/demo/reset", headers=admin).json()
    assert body["code"] == 0
    data = body["data"]
    assert data["deleted"] == {model.__tablename__: 0 for model in DELETED_MODELS}
    assert data["frame_files_removed"] == 0
    assert data["model_online"] == MODEL_NAME


def test_reset_is_not_found_until_demo_mode_is_enabled(demo_disabled_client):
    client = demo_disabled_client
    admin = auth(sign_in(client))
    frame_file = seed_business_rows(client)

    response = client.post("/api/demo/reset", headers=admin)
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == 40401
    assert "演示模式未开启" in body["message"]

    # Refused before the handler ran: nothing was deleted.
    assert table_counts(client)["media_asset"] == 1
    assert frame_file.exists()


def test_reset_is_admin_only(client):
    observer = auth(sign_in(client, "observer"))
    frame_file = seed_business_rows(client)

    response = client.post("/api/demo/reset", headers=observer)
    assert response.status_code == 403
    assert response.json()["code"] == 40301

    assert table_counts(client)["media_asset"] == 1
    assert frame_file.exists()
