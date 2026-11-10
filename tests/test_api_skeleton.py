"""The HTTP skeleton: the envelope, the guards, and the route set (P1-02).

The first test is the one that matters most — it compares the mounted operations against
`docs/api-contract-en.md`, so the contract stays the list of routes rather than a document that
describes an older system. The rest check behaviour that the frontend depends on: an envelope on
every response, a token required everywhere but login, roles enforced server-side, and 501 where a
module is honestly not built.

The P2-07 section at the bottom asserts the documented payload shape of every P0 route against the
same fixture and SQLite database.
"""

from __future__ import annotations

import base64
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import (
    DetectObject,
    DetectTask,
    MediaAsset,
    ModelVersion,
    SysUser,
    TrainExperiment,
)
from app.security import hash_password
from app.seed import seed_species
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

CONTRACT = Path(__file__).resolve().parent.parent / "docs" / "api-contract-en.md"


def _contract_operations() -> set[tuple[str, str]]:
    text = CONTRACT.read_text(encoding="utf-8")
    rows = re.findall(r"^\| (GET|POST|PATCH|DELETE) \| `([^`]+)` \|", text, re.M)
    return {(method, re.sub(r"\{[^}]+\}", "{}", path)) for method, path in rows}


def _mounted_operations(app) -> set[tuple[str, str]]:
    return {
        (method.upper(), re.sub(r"\{[^}]+\}", "{}", path))
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_DSN", f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    # Reports and manifests land here, not in the repository.
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    factory = app.state.session_factory
    with factory() as session:
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


def sign_in(client: TestClient, username: str = "admin") -> str:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": "password123"}
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def a_frame() -> str:
    """A sharp, textured JPEG, base64 encoded — flat grey scores zero for sharpness."""
    image = np.random.default_rng(0).integers(0, 255, (120, 160, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return base64.b64encode(buffer.tobytes()).decode("ascii")


def test_every_contract_route_is_mounted(client):
    from app.main import app as mounted

    contract = _contract_operations()
    present = _mounted_operations(mounted)
    missing = sorted(contract - present)
    assert not missing, f"契约里有、服务端没挂载: {missing}"
    assert len(contract) == 42


def test_health_answers_in_the_envelope(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["database"] == "ok"
    assert body["data"]["routes"] >= 42
    assert body["request_id"].startswith("req-")


def test_login_returns_a_token_and_the_user(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "password123"})
    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 0
    assert isinstance(body["data"]["token"], str) and body["data"]["token"]
    assert isinstance(body["data"]["expires_at"], str)
    user = body["data"]["user"]
    assert user["username"] == "admin"
    assert user["role"] == "admin"
    assert isinstance(user["user_id"], int)
    assert isinstance(user["real_name"], str)


def test_wrong_password_counts_down_then_locks(client):
    for attempt in range(1, 5):
        body = client.post(
            "/api/auth/login", json={"username": "observer", "password": "wrong-password"}
        ).json()
        assert body["code"] == 40102
        assert str(5 - attempt) in body["message"]

    locked = client.post(
        "/api/auth/login", json={"username": "observer", "password": "wrong-password"}
    ).json()
    assert locked["code"] == 40901
    assert "锁定" in locked["message"]

    # The correct password is refused while the lock stands — that is the point of the lock.
    still_locked = client.post(
        "/api/auth/login", json={"username": "observer", "password": "password123"}
    ).json()
    assert still_locked["code"] == 40901


def test_every_route_but_login_needs_a_token(client):
    for method, path in [("GET", "/api/frames"), ("GET", "/api/models"), ("PATCH", "/api/params")]:
        response = client.request(method, path)
        assert response.status_code == 401
        assert response.json()["code"] == 40102


def test_a_role_cannot_reach_a_privileged_route(client):
    """Every guarded surface is checked: it is the one defect a passing happy path never catches."""
    token = sign_in(client, "observer")
    attempts = [
        ("GET", "/api/users", None),
        ("GET", "/api/logs", None),
        ("PATCH", "/api/params", {"max_concurrency": 3}),
    ]
    for method, path, payload in attempts:
        response = client.request(method, path, json=payload, headers=auth(token))
        assert response.status_code == 403, f"{method} {path} was not refused"
        assert response.json()["code"] == 40301
        assert response.json()["data"] is None


def test_capture_scores_the_frame_and_is_idempotent(client):
    token = sign_in(client)
    session = client.post("/api/capture/sessions", headers=auth(token)).json()["data"]

    payload = {
        "point_code": "A3",
        "image_b64": a_frame(),
        "captured_at": None,
    }
    first = client.post(
        f"/api/capture/sessions/{session['session_id']}/frames", json=payload, headers=auth(token)
    ).json()
    assert first["code"] == 0
    frame = first["data"]
    assert isinstance(frame["frame_id"], str)
    assert frame["session_id"] == session["session_id"]
    assert isinstance(frame["captured_at"], str)
    assert isinstance(frame["quality"], dict)
    assert frame["quality"]["score"] > 0
    assert frame["quality"]["verdict"] in {"ok", "retake"}
    assert isinstance(frame["env"], dict) and "turbidity_rel" in frame["env"]
    assert frame["width"] == 160
    assert isinstance(frame["height"], int)
    assert set(frame["quality_components"]) == {"sharpness", "brightness", "colorcast"}
    assert isinstance(frame["queued"], bool)

    second = client.post(
        f"/api/capture/sessions/{session['session_id']}/frames", json=payload, headers=auth(token)
    ).json()
    assert second["data"]["frame_id"] == frame["frame_id"], "同一帧不能变成两条记录"

    listed = client.get("/api/frames", headers=auth(token)).json()["data"]
    assert listed["total"] == 1
    assert listed["items"][0]["frame_id"] == frame["frame_id"]


def test_a_frame_with_a_skewed_clock_is_refused(client):
    token = sign_in(client)
    session = client.post("/api/capture/sessions", headers=auth(token)).json()["data"]
    body = client.post(
        f"/api/capture/sessions/{session['session_id']}/frames",
        json={
            "point_code": "A3",
            "image_b64": a_frame(),
            "captured_at": "2020-01-01T00:00:00+00:00",
        },
        headers=auth(token),
    ).json()
    assert body["code"] == 40002
    assert "5 秒" in body["message"]


def test_reviewing_a_frame_without_results_is_refused(client):
    token = sign_in(client)
    session = client.post("/api/capture/sessions", headers=auth(token)).json()["data"]
    frame = client.post(
        f"/api/capture/sessions/{session['session_id']}/frames",
        json={"point_code": "A3", "image_b64": a_frame()},
        headers=auth(token),
    ).json()["data"]

    body = client.post(
        f"/api/review/frames/{frame['frame_id']}",
        json={
            "objects": [
                {
                    "class_code": "holothurian",
                    "confidence": 0.9,
                    "x": 0.1,
                    "y": 0.1,
                    "w": 0.2,
                    "h": 0.2,
                }
            ]
        },
        headers=auth(token),
    ).json()
    assert body["code"] == 40401


def test_modules_that_need_a_model_say_so(client):
    """The one remaining 501 is the one that genuinely cannot run: no weights, no detection."""
    token = sign_in(client)
    response = client.post("/api/detect/frames/any-frame", headers=auth(token))
    assert response.status_code == 501
    body = response.json()
    assert body["code"] == 50100
    assert body["data"] is None
    assert isinstance(body["request_id"], str) and body["request_id"].startswith("req-")
    assert "模型" in body["message"]


def test_datasets_and_reports_start_empty_rather_than_failing(client):
    token = sign_in(client)
    for path in ("/api/datasets", "/api/reports"):
        body = client.get(path, headers=auth(token)).json()
        assert body["code"] == 0
        assert body["data"]["items"] == []
        assert body["data"]["total"] == 0


def test_parameters_persist_and_are_audited(client):
    token = sign_in(client)
    before = client.get("/api/params", headers=auth(token)).json()["data"]
    assert before["max_concurrency"] >= 1

    changed = client.patch("/api/params", json={"max_concurrency": 4}, headers=auth(token)).json()
    assert changed["code"] == 0
    assert changed["data"]["params"]["max_concurrency"] == 4
    assert changed["data"]["changed"]["max_concurrency"] == {
        "before": before["max_concurrency"],
        "after": 4,
    }

    # Read back through a fresh request: the value came from the table, not from memory.
    assert client.get("/api/params", headers=auth(token)).json()["data"]["max_concurrency"] == 4

    log = client.get("/api/logs?action=config", headers=auth(token)).json()["data"]["items"]
    assert log and log[0]["target_id"] == "max_concurrency"
    assert log[0]["before_value"] == str(before["max_concurrency"])
    assert log[0]["after_value"] == "4"

    # No-op patch is a conflict, not a silent success.
    assert (
        client.patch("/api/params", json={"max_concurrency": 4}, headers=auth(token)).json()["code"]
        == 40901
    )


def test_dataset_export_is_deterministic_and_keeps_groups_together(client, tmp_path):
    token = sign_in(client)
    session = client.post("/api/capture/sessions", headers=auth(token)).json()["data"]

    # Three visually different frames, so the hash-based dedup keeps all three.
    for seed in (1, 2, 3):
        image = np.random.default_rng(seed).integers(0, 255, (90, 120, 3), dtype=np.uint8)
        ok, buffer = cv2.imencode(".jpg", image)
        client.post(
            f"/api/capture/sessions/{session['session_id']}/frames",
            json={"point_code": "A3", "image_b64": base64.b64encode(buffer.tobytes()).decode()},
            headers=auth(token),
        )

    first = client.post(
        "/api/datasets",
        json={"snapshot_name": "DS-T1", "split_ratio": "7:2:1", "seed": 7, "only_reviewed": False},
        headers=auth(token),
    ).json()
    assert first["code"] == 0, first
    assert first["data"]["frame_count"] == 3
    assert sum(first["data"]["splits"].values()) == 3

    second = client.post(
        "/api/datasets",
        json={"snapshot_name": "DS-T2", "split_ratio": "7:2:1", "seed": 7, "only_reviewed": False},
        headers=auth(token),
    ).json()
    assert second["code"] == 0

    one = json.loads(Path(first["data"]["manifest_path"]).read_text(encoding="utf-8"))
    two = json.loads(Path(second["data"]["manifest_path"]).read_text(encoding="utf-8"))
    assert [f["split"] for f in one["frames"]] == [f["split"] for f in two["frames"]], (
        "同样的帧与种子必须给出同样的划分"
    )

    listed = client.get("/api/datasets", headers=auth(token)).json()["data"]
    assert listed["total"] == 2


def test_export_without_reviewed_frames_is_refused(client):
    token = sign_in(client)
    session = client.post("/api/capture/sessions", headers=auth(token)).json()["data"]
    client.post(
        f"/api/capture/sessions/{session['session_id']}/frames",
        json={"point_code": "A3", "image_b64": a_frame()},
        headers=auth(token),
    )
    body = client.post(
        "/api/datasets",
        json={"snapshot_name": "DS-UNREVIEWED", "seed": 1},
        headers=auth(token),
    ).json()
    assert body["code"] == 40002
    assert "没有符合条件的帧" in body["message"]


def test_report_is_generated_from_the_same_figures_as_the_dashboard(client):
    token = sign_in(client)
    body = client.post(
        "/api/reports",
        json={
            "period_start": "2026-01-01T00:00:00+00:00",
            "period_end": "2026-12-31T00:00:00+00:00",
            "template": "standard",
            "basis": "reviewed",
        },
        headers=auth(token),
    ).json()
    assert body["code"] == 0, body
    assert body["data"]["status"] == "ready"

    document = Path(body["data"]["file_path"]).read_text(encoding="utf-8")
    assert "巡检报告" in document
    assert "模型版本" in document and "统计口径" in document

    history = client.get("/api/reports", headers=auth(token)).json()["data"]
    assert history["total"] == 1
    assert history["items"][0]["report_code"].startswith("RP")


def test_a_reversed_period_is_refused(client):
    token = sign_in(client)
    body = client.post(
        "/api/reports",
        json={
            "period_start": "2026-12-31T00:00:00+00:00",
            "period_end": "2026-01-01T00:00:00+00:00",
        },
        headers=auth(token),
    ).json()
    assert body["code"] == 40002


def test_statistics_answer_with_real_figures(client):
    token = sign_in(client)
    quality = client.get("/api/stats/quality", headers=auth(token)).json()
    assert quality["code"] == 0
    assert isinstance(quality["data"]["days"], int)
    assert isinstance(quality["data"]["total"], int)
    assert isinstance(quality["data"]["rejected"], int)
    assert quality["data"]["total"] == 0
    assert isinstance(quality["data"]["rate"], float)
    assert quality["data"]["rate"] == 0.0

    trend = client.get("/api/stats/trend?days=7", headers=auth(token)).json()
    assert len(trend["data"]["items"]) == 7


def test_validation_errors_use_the_envelope(client):
    body = client.post(
        "/api/auth/login",
        json={"username": ""},
    ).json()
    assert body["code"] == 40001
    assert body["data"] is None


# --- P2-07: one payload-shape test for every P0 route -------------------------------------------


def capture_one(client: TestClient, token: str) -> tuple[dict, dict]:
    """Open a session and post one frame; return both payloads."""
    session = client.post("/api/capture/sessions", headers=auth(token)).json()["data"]
    frame = client.post(
        f"/api/capture/sessions/{session['session_id']}/frames",
        json={"point_code": "A3", "image_b64": a_frame()},
        headers=auth(token),
    ).json()["data"]
    return session, frame


def seed_species_rows(client: TestClient) -> None:
    with client.app.state.session_factory() as session:
        seed_species(session)


def seed_task_and_box(client: TestClient, frame_id: str) -> tuple[int, int]:
    """A queued task and one box, so the object and review routes have rows to return."""
    with client.app.state.session_factory() as session:
        seed_species(session)
        asset = session.scalar(select(MediaAsset).where(MediaAsset.frame_id == frame_id))
        task = DetectTask(
            task_code=f"DT-{uuid4().hex[:8]}",
            task_type=2,
            asset_count=1,
            status=0,
            progress=0,
        )
        session.add(task)
        session.flush()
        box = DetectObject(
            task_id=task.task_id,
            asset_id=asset.asset_id,
            frame_id=frame_id,
            class_code="holothurian",
            confidence=0.9,
            x=0.1,
            y=0.1,
            w=0.2,
            h=0.2,
            is_manual=0,
            review_status=0,
        )
        session.add(box)
        session.commit()
        return task.task_id, box.object_id


def test_me_returns_the_signed_in_user(client):
    token = sign_in(client, "admin")
    body = client.get("/api/auth/me", headers=auth(token)).json()
    assert body["code"] == 0
    user = body["data"]
    assert isinstance(user["user_id"], int)
    assert user["username"] == "admin"
    assert isinstance(user["real_name"], str)
    assert isinstance(user["role"], str)


def test_cameras_answers_with_an_items_list(client, monkeypatch):
    from app.vision.capture import CaptureError

    class NoCamera:
        def __init__(self, index):
            self.index = index

        def open(self):
            raise CaptureError("no camera in the test environment")

    monkeypatch.setattr("app.vision.capture.CameraSource", NoCamera)
    token = sign_in(client)
    body = client.get("/api/cameras", headers=auth(token)).json()
    assert body["code"] == 0
    assert isinstance(body["data"]["items"], list)


def test_opening_a_session_returns_an_id_and_a_timestamp(client):
    token = sign_in(client)
    body = client.post("/api/capture/sessions", headers=auth(token)).json()
    assert body["code"] == 0
    session = body["data"]
    assert isinstance(session["session_id"], str)
    assert session["session_id"].startswith("s-")
    assert isinstance(session["opened_at"], str)


def test_closing_a_session_reports_the_frame_count(client):
    token = sign_in(client)
    session, _ = capture_one(client, token)
    body = client.post(
        f"/api/capture/sessions/{session['session_id']}/close", headers=auth(token)
    ).json()
    assert body["code"] == 0
    assert body["data"]["session_id"] == session["session_id"]
    assert body["data"]["frames"] == 1
    assert body["data"]["closed"] is True

    missing = client.post("/api/capture/sessions/s-nope/close", headers=auth(token)).json()
    assert missing["code"] == 40401


def test_frame_detail_matches_the_captured_frame(client):
    token = sign_in(client)
    _, frame = capture_one(client, token)
    body = client.get(f"/api/frames/{frame['frame_id']}", headers=auth(token)).json()
    assert body["code"] == 0
    detail = body["data"]
    assert detail["frame_id"] == frame["frame_id"]
    assert isinstance(detail["session_id"], str)
    assert isinstance(detail["captured_at"], str)
    assert isinstance(detail["quality"], dict)
    assert isinstance(detail["quality"]["score"], int)
    assert detail["quality"]["verdict"] in {"ok", "retake"}
    assert isinstance(detail["env"], dict) and "turbidity_rel" in detail["env"]
    assert isinstance(detail["width"], int) and isinstance(detail["height"], int)

    missing = client.get("/api/frames/nope", headers=auth(token)).json()
    assert missing["code"] == 40401


def test_frame_objects_returns_boxes_and_counts(client):
    token = sign_in(client)
    _, frame = capture_one(client, token)
    seed_task_and_box(client, frame["frame_id"])

    body = client.get(f"/api/frames/{frame['frame_id']}/objects", headers=auth(token)).json()
    assert body["code"] == 0
    data = body["data"]
    assert len(data["items"]) == 1
    box = data["items"][0]
    expected = {
        "object_id": int,
        "class_code": str,
        "confidence": float,
        "x": float,
        "y": float,
        "w": float,
        "h": float,
        "is_manual": int,
        "review_status": int,
    }
    for key, kind in expected.items():
        assert isinstance(box[key], kind), key
    assert data["counts"] == {"holothurian": 1}


def test_review_submission_returns_the_documented_result(client):
    token = sign_in(client)
    _, frame = capture_one(client, token)
    _, object_id = seed_task_and_box(client, frame["frame_id"])

    body = client.post(
        f"/api/review/frames/{frame['frame_id']}",
        json={
            "objects": [
                {
                    "object_id": object_id,
                    "class_code": "holothurian",
                    "confidence": 0.9,
                    "x": 0.1,
                    "y": 0.1,
                    "w": 0.2,
                    "h": 0.2,
                },
                {
                    "class_code": "chlamys",
                    "confidence": 0.8,
                    "x": 0.3,
                    "y": 0.3,
                    "w": 0.1,
                    "h": 0.1,
                },
            ],
            "note": "one manual box",
        },
        headers=auth(token),
    ).json()
    assert body["code"] == 0
    data = body["data"]
    assert data["frame_id"] == frame["frame_id"]
    assert isinstance(data["version_no"], int)
    assert isinstance(data["object_count"], int)
    assert isinstance(data["hard_sample"], bool)
    assert isinstance(data["rejected"], int)
    assert isinstance(data["added"], int)
    assert data["added"] == 1


def test_batch_detection_refuses_an_empty_queue(client):
    token = sign_in(client)
    body = client.post("/api/detect/batches", json={"asset_count": 1}, headers=auth(token)).json()
    assert body["code"] == 50100
    assert body["data"] is None
    assert "尚未实现" in body["message"]


def test_batch_detection_creates_a_queued_task(client):
    token = sign_in(client)
    capture_one(client, token)
    body = client.post("/api/detect/batches", json={"asset_count": 1}, headers=auth(token)).json()
    assert body["code"] == 0
    task = body["data"]
    assert isinstance(task["task_id"], int)
    assert isinstance(task["task_code"], str) and task["task_code"].startswith("DT")
    assert task["type"] == "batch"
    assert task["status"] == "queued"
    assert isinstance(task["progress"], int)
    assert isinstance(task["asset_count"], int)
    assert isinstance(task["obj_count"], int)
    assert task["model_version_id"] is None or isinstance(task["model_version_id"], int)
    assert task["error_msg"] is None
    assert isinstance(task["created_at"], str)
    assert task["finished_at"] is None


def test_task_list_and_detail_return_the_queued_task(client):
    token = sign_in(client)
    capture_one(client, token)
    task = client.post("/api/detect/batches", json={"asset_count": 1}, headers=auth(token)).json()[
        "data"
    ]

    listed = client.get("/api/tasks", headers=auth(token)).json()
    assert listed["code"] == 0
    assert listed["data"]["total"] == 1
    assert listed["data"]["page"] == 1
    assert listed["data"]["size"] == 24
    assert listed["data"]["items"][0]["task_id"] == task["task_id"]

    detail = client.get(f"/api/tasks/{task['task_id']}", headers=auth(token)).json()
    assert detail["code"] == 0
    assert detail["data"]["task_code"] == task["task_code"]
    assert detail["data"]["status"] == "queued"

    missing = client.get("/api/tasks/999999", headers=auth(token)).json()
    assert missing["code"] == 40401


def test_cancel_moves_a_queued_task_to_cancelled(client):
    token = sign_in(client)
    capture_one(client, token)
    task = client.post("/api/detect/batches", json={"asset_count": 1}, headers=auth(token)).json()[
        "data"
    ]

    body = client.post(f"/api/tasks/{task['task_id']}/cancel", headers=auth(token)).json()
    assert body["code"] == 0
    assert body["data"]["status"] == "cancelled"
    assert isinstance(body["data"]["finished_at"], str)

    again = client.post(f"/api/tasks/{task['task_id']}/cancel", headers=auth(token)).json()
    assert again["code"] == 40901


def test_retry_requeues_a_failed_task(client):
    token = sign_in(client)
    with client.app.state.session_factory() as session:
        task = DetectTask(
            task_code=f"DT-{uuid4().hex[:8]}",
            task_type=2,
            asset_count=1,
            status=3,
            progress=50,
            error_msg="forced failure",
            finished_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(task)
        session.commit()
        task_id = task.task_id

    body = client.post(f"/api/tasks/{task_id}/retry", headers=auth(token)).json()
    assert body["code"] == 0
    assert body["data"]["status"] == "queued"
    assert body["data"]["progress"] == 0
    assert body["data"]["error_msg"] is None
    assert body["data"]["finished_at"] is None

    again = client.post(f"/api/tasks/{task_id}/retry", headers=auth(token)).json()
    assert again["code"] == 40901


def test_models_list_reports_versions_and_the_online_id(client):
    token = sign_in(client)
    with client.app.state.session_factory() as session:
        session.add(
            ModelVersion(
                version_name="v8n-test",
                weight_path="weights/test.pt",
                labels_path="labels.txt",
                dataset_ref="DUO-85:15",
                map50=0.5,
                map50_95=0.3,
                recall_avg=0.6,
                fps=30.0,
                params_m=3.2,
                status=1,
                is_online=1,
            )
        )
        session.commit()

    body = client.get("/api/models", headers=auth(token)).json()
    assert body["code"] == 0
    assert body["data"]["total"] == 1
    assert isinstance(body["data"]["online_model_id"], int)
    item = body["data"]["items"][0]
    expected = {
        "model_id": int,
        "version_name": str,
        "dataset_ref": str,
        "map50": float,
        "map50_95": float,
        "recall_avg": float,
        "fps": float,
        "params_m": float,
        "is_online": bool,
        "status": int,
        "created_at": str,
    }
    for key, kind in expected.items():
        assert isinstance(item[key], kind), key


def test_experiments_list_reports_metrics_and_baseline(client):
    token = sign_in(client)
    with client.app.state.session_factory() as session:
        session.add(
            TrainExperiment(
                exp_name="E0-test",
                dataset_snapshot="DUO-85:15",
                split_ratio="85:15",
                seed=42,
                epochs=30,
                batch_size=16,
                lr=0.01,
                map50=0.5,
                map50_95=0.3,
                recall_avg=0.6,
                fps=30.0,
                params_m=3.2,
                is_baseline=1,
            )
        )
        session.commit()

    body = client.get("/api/experiments", headers=auth(token)).json()
    assert body["code"] == 0
    assert body["data"]["total"] == 1
    assert body["data"]["baseline"] == "E0-test"
    item = body["data"]["items"][0]
    expected = {
        "exp_id": int,
        "exp_name": str,
        "dataset_snapshot": str,
        "split_ratio": str,
        "seed": int,
        "epochs": int,
        "map50": float,
        "map50_95": float,
        "recall_avg": float,
        "fps": float,
        "is_baseline": bool,
        "created_at": str,
    }
    for key, kind in expected.items():
        assert isinstance(item[key], kind), key
    assert item["delta_map50"] == 0.0


def test_compare_answers_not_built(client):
    token = sign_in(client)
    response = client.post("/api/compare/frames/any-frame", headers=auth(token))
    assert response.status_code == 501
    body = response.json()
    assert body["code"] == 50100
    assert body["data"] is None
    assert "尚未实现" in body["message"]


def test_species_list_returns_the_four_seeded_classes(client):
    token = sign_in(client)
    seed_species_rows(client)
    body = client.get("/api/species", headers=auth(token)).json()
    assert body["code"] == 0
    assert body["data"]["total"] == 4
    assert [item["class_code"] for item in body["data"]["items"]] == [
        "holothurian",
        "strongylocentrotus",
        "chlamys",
        "asterias",
    ]
    item = body["data"]["items"][0]
    expected = {
        "class_code": str,
        "cn_name": str,
        "latin_name": str,
        "category": int,
        "conf_thr": float,
        "in_stat": bool,
        "status": int,
    }
    for key, kind in expected.items():
        assert isinstance(item[key], kind), key


def test_species_patch_updates_one_threshold(client):
    token = sign_in(client)
    seed_species_rows(client)
    body = client.patch(
        "/api/species/holothurian",
        json={"conf_thr": 0.66, "in_stat": False},
        headers=auth(token),
    ).json()
    assert body["code"] == 0
    assert body["data"]["conf_thr"] == 0.66
    assert body["data"]["in_stat"] is False

    missing = client.patch("/api/species/nope", json={"conf_thr": 0.5}, headers=auth(token)).json()
    assert missing["code"] == 40401

    observer = sign_in(client, "observer")
    forbidden = client.patch(
        "/api/species/holothurian", json={"conf_thr": 0.5}, headers=auth(observer)
    ).json()
    assert forbidden["code"] == 40301
