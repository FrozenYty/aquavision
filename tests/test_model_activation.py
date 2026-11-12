"""Model versions and activation, through the API (P3-03, FR-M6-01, FR-M6-02, AC-23, AC-24).

`POST /api/models/{id}/activate` has been implemented and never called by a test: `test_register_model.py`
covers the script that writes rows, and nothing covered the route that switches which row is live. These
tests hold the three claims `PLAN.md` makes for the task:

- exactly one version is online at any moment, including across a rollback;
- a version without metrics cannot go online, and the refusal names the reason;
- every result records the version that produced it, and the detection response carries that name.

No torch: a fake detector stands in for the loaded model where the single-frame route is exercised, and
the batch path reads the online row at creation, which is what AC-24's "new jobs use the new version"
means here (a live single-frame call uses the process's loaded model until restart - the P2-06c decision).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.envelope import CONFLICT, FORBIDDEN, NOT_FOUND
from app.models import DetectTask, MediaAsset, ModelVersion, SysLog, SysUser
from app.security import hash_password
from app.seed import seed_species
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

METRICS = {"map50": 0.77, "map50_95": 0.56, "recall_avg": 0.69, "fps": 499.0, "params_m": 3.14}


class FakeDetector:
    """The online model as the route sees it: an id, a name, and boxes."""

    def __init__(self, model_id: int, version_name: str):
        self.model_version_id = model_id
        self.version_name = version_name

    def predict(self, _asset: MediaAsset, conf_thr: float = 0.5) -> list[dict]:
        return [
            {
                "class_code": "holothurian",
                "confidence": min(0.9, conf_thr + 0.4),
                "x": 0.1,
                "y": 0.1,
                "w": 0.2,
                "h": 0.2,
            }
        ]


def _version(session, name: str, **columns) -> ModelVersion:
    row = ModelVersion(
        version_name=name,
        # The route under test never opens the file; the column is NOT NULL.
        weight_path=f"models/{name}/best.pt",
        labels_path=f"models/{name}/labels.txt",
        dataset_ref="DUO-85:15-subset-1800",
        **columns,
    )
    session.add(row)
    session.flush()
    return row


@pytest.fixture
def rig(tmp_path, monkeypatch):
    """An app with four accounts, a few frames, and four versions: two usable, two without metrics."""
    monkeypatch.setenv("DB_DSN", f"sqlite:///{(tmp_path / 'models.db').as_posix()}")
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'models.db').as_posix()}")
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    factory = app.state.session_factory
    with factory() as session:
        seed_species(session)
        for role in ("admin", "algo", "analyst", "observer"):
            hashed, salt = hash_password("password123")
            session.add(
                SysUser(
                    username=role,
                    password_hash=hashed,
                    salt=salt,
                    role_code=role,
                    real_name=role,
                    status=1,
                    fail_count=0,
                )
            )
        now = datetime.now(UTC).replace(tzinfo=None)
        for index in range(6):
            session.add(
                MediaAsset(
                    frame_id=f"20261112T100000-{index:04d}",
                    session_id="s-models",
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
        first = _version(session, "v8n-E0-candidate", status=0, is_online=0, **METRICS)
        second = _version(session, "v8n-E1-candidate", status=0, is_online=0, **METRICS)
        # The two shapes a version can be incomplete in: no metrics at all, and only half of them.
        _version(session, "v8n-no-metrics", status=0, is_online=0)
        _version(session, "v8n-half-metrics", status=0, is_online=0, map50=0.71)
        session.commit()
        ids = {"first": first.model_id, "second": second.model_id}

    with TestClient(app) as client:
        yield client, factory, ids
    get_settings.cache_clear()


def sign_in(client: TestClient, role: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": role, "password": "password123"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def online_versions(factory) -> list[ModelVersion]:
    with factory() as session:
        return list(session.scalars(select(ModelVersion).where(ModelVersion.is_online == 1)))


def activation_log(factory) -> list[tuple[str | None, str]]:
    with factory() as session:
        rows = session.scalars(
            select(SysLog).where(SysLog.action == "activate").order_by(SysLog.log_id)
        ).all()
        return [(row.before_value, row.after_value) for row in rows]


def test_activation_leaves_exactly_one_version_online(rig):
    """AC-23/AC-24: two activations, never two online rows and never a moment without one."""
    client, factory, ids = rig
    admin = sign_in(client, "admin")

    assert client.get("/api/models", headers=admin).json()["data"]["online_model_id"] is None

    first = client.post(f"/api/models/{ids['first']}/activate", headers=admin)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["version_name"] == "v8n-E0-candidate"
    assert first.json()["data"]["is_online"] is True
    assert [row.version_name for row in online_versions(factory)] == ["v8n-E0-candidate"]

    second = client.post(f"/api/models/{ids['second']}/activate", headers=admin)
    assert second.status_code == 200, second.text
    online = online_versions(factory)
    assert [row.version_name for row in online] == ["v8n-E1-candidate"]
    with factory() as session:
        previous = session.get(ModelVersion, ids["first"])
        assert (previous.is_online, previous.status) == (0, 2)
        assert online[0].status == 1

    # The list route agrees with the rows, and the audit trail carries both sides of each change.
    listing = client.get("/api/models", headers=admin).json()["data"]
    assert listing["online_model_id"] == ids["second"]
    assert activation_log(factory) == [
        (None, "v8n-E0-candidate"),
        ("v8n-E0-candidate", "v8n-E1-candidate"),
    ]


def test_a_version_without_metrics_cannot_go_online(rig):
    """AC-23: missing metrics are refused, with the reason, and nothing changes."""
    client, factory, ids = rig
    admin = sign_in(client, "admin")
    assert client.post(f"/api/models/{ids['first']}/activate", headers=admin).status_code == 200

    with factory() as session:
        by_name = {
            row.version_name: row.model_id for row in session.scalars(select(ModelVersion)).all()
        }

    for name in ("v8n-no-metrics", "v8n-half-metrics"):
        response = client.post(f"/api/models/{by_name[name]}/activate", headers=admin)
        body = response.json()
        assert response.status_code == 409, body
        assert body["code"] == CONFLICT, body
        assert "指标" in body["message"], body
        assert [row.version_name for row in online_versions(factory)] == ["v8n-E0-candidate"]

    # A refused activation is not an activation: the trail holds only the one that worked.
    assert activation_log(factory) == [(None, "v8n-E0-candidate")]


def test_activating_an_unknown_version_is_not_found(rig):
    client, _factory, _ids = rig
    admin = sign_in(client, "admin")
    response = client.post("/api/models/9999/activate", headers=admin)
    assert response.status_code == 404
    assert response.json()["code"] == NOT_FOUND


def test_the_version_already_online_cannot_be_activated_again(rig):
    client, _factory, ids = rig
    admin = sign_in(client, "admin")
    assert client.post(f"/api/models/{ids['first']}/activate", headers=admin).status_code == 200
    again = client.post(f"/api/models/{ids['first']}/activate", headers=admin)
    assert again.status_code == 409
    assert again.json()["code"] == CONFLICT


def test_only_the_engineer_and_the_administrator_may_activate(rig):
    client, _factory, ids = rig
    for role in ("observer", "analyst"):
        response = client.post(
            f"/api/models/{ids['first']}/activate", headers=sign_in(client, role)
        )
        assert response.status_code == 403, f"{role}: {response.text}"
        assert response.json()["code"] == FORBIDDEN
    assert (
        client.post(
            f"/api/models/{ids['first']}/activate", headers=sign_in(client, "algo")
        ).status_code
        == 200
    )


def test_a_task_records_the_version_that_was_online_when_it_was_created(rig):
    """AC-24: new jobs use the new version; rolling back switches new jobs back with it."""
    client, factory, ids = rig
    admin = sign_in(client, "admin")

    def new_task() -> int | None:
        body = client.post("/api/detect/batches", json={"asset_count": 1}, headers=admin).json()
        assert body["code"] == 0, body
        with factory() as session:
            return session.get(DetectTask, body["data"]["task_id"]).model_version_id

    assert new_task() is None, "a job with no online version must record none, not a guess"

    client.post(f"/api/models/{ids['first']}/activate", headers=admin)
    assert new_task() == ids["first"]

    client.post(f"/api/models/{ids['second']}/activate", headers=admin)
    assert new_task() == ids["second"]

    # Rollback is an activation of the earlier version: the new job carries its number again.
    client.post(f"/api/models/{ids['first']}/activate", headers=admin)
    assert new_task() == ids["first"]
    assert len(online_versions(factory)) == 1


def test_the_detection_response_names_the_online_version_and_records_it(rig):
    """FR-M6-02's other half: the result says which version produced it, in the row and in the reply."""
    client, factory, ids = rig
    admin = sign_in(client, "admin")
    client.post(f"/api/models/{ids['second']}/activate", headers=admin)

    # What a restart would load: the online row. The route is exercised without torch.
    client.app.state.detector = FakeDetector(ids["second"], "v8n-E1-candidate")

    response = client.post("/api/detect/frames/20261112T100000-0000", headers=admin)
    body = response.json()
    assert response.status_code == 200, body
    assert body["data"]["model_version"] == "v8n-E1-candidate"
    assert body["data"]["boxes"], "the fake detector returned one box"

    with factory() as session:
        task = session.get(DetectTask, body["data"]["task_id"])
        assert task.model_version_id == ids["second"]
        assert task.status == 2
        assert task.obj_count == 1
        assert session.scalar(select(func.count()).select_from(DetectTask)) == 1
