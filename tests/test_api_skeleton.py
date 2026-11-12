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
from sqlalchemy import func, select
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
    # The queue is exercised directly in test_worker.py; a background pool here would race the tests.
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
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

    # The capture routes accept only the local machine (FR-M1-02, P3-20), so this client says
    # where it is instead of relying on the test runner's default address.
    with TestClient(app, client=("127.0.0.1", 50000)) as test_client:
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


def a_frame(seed: int = 0) -> str:
    """A sharp, textured JPEG, base64 encoded — flat grey scores zero for sharpness.

    The seed picks the pixels: capture refuses a second frame with the same hash (AC-05), so a test
    that needs two frames asks for two seeds.
    """
    image = np.random.default_rng(seed).integers(0, 255, (120, 160, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return base64.b64encode(buffer.tobytes()).decode("ascii")


def test_every_contract_route_is_mounted(client):
    from app.main import app as mounted

    contract = _contract_operations()
    present = _mounted_operations(mounted)
    missing = sorted(contract - present)
    assert not missing, f"契约里有、服务端没挂载: {missing}"
    # The reverse direction: a route the contract does not list is invisible to every client that reads
    # the contract, so a newly mounted one must not slip in unannounced. `/api/health` is the one named
    # exception: it is the deployer's liveness check (database, mounted-route count, default secret) and
    # deliberately not part of the client contract. `/` is the page redirect and is
    # `include_in_schema=False`, so it never reaches openapi(); naming it here would hide a real route.
    documented_infrastructure = {("GET", "/api/health")}
    extra = sorted(present - contract - documented_infrastructure)
    assert not extra, f"服务端挂载了契约没有列出的接口: {extra}"
    assert len(contract) == 45
    # `/api/health` publishes the contract size as `contract_routes`. Tying it to the table here is the
    # point: it was hardcoded and stayed at 42 while the contract grew to 44, and nothing noticed.
    health = client.get("/api/health").json()["data"]
    assert health["contract_routes"] == len(contract), (
        f"health says {health['contract_routes']} contract routes, the contract lists {len(contract)}"
    )


def test_health_answers_in_the_envelope(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["database"] == "ok"
    assert body["data"]["routes"] >= 45
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


def test_detection_without_weights_says_why(client):
    """A captured frame with no usable model still answers 501, and no box is invented."""
    token = sign_in(client)
    _, frame = capture_one(client, token)
    client.app.state.detector = None
    client.app.state.detector_error = "没有在线模型版本"
    response = client.post(f"/api/detect/frames/{frame['frame_id']}", headers=auth(token))
    assert response.status_code == 501
    body = response.json()
    assert body["code"] == 50100
    assert body["data"] is None
    assert isinstance(body["request_id"], str) and body["request_id"].startswith("req-")
    assert "没有在线模型版本" in body["message"]


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


def capture_one(client: TestClient, token: str, seed: int = 0) -> tuple[dict, dict]:
    """Open a session and post one frame; return both payloads."""
    session = client.post("/api/capture/sessions", headers=auth(token)).json()["data"]
    frame = client.post(
        f"/api/capture/sessions/{session['session_id']}/frames",
        json={"point_code": "A3", "image_b64": a_frame(seed)},
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


# --- P2-05b: the detection path, with a fake detector --------------------------------------------


class FakeDetector:
    """The detector's contract without a weight file: one box, a model id and a version name."""

    def __init__(self, model_id: int, version_name: str = "fake-v8n"):
        self.model_version_id = model_id
        self.version_name = version_name
        self.calls = 0

    def predict(self, asset, conf_thr=0.5, iou_thr=0.45, max_det=100):
        self.calls += 1
        return [
            {
                "class_code": "holothurian",
                "confidence": 0.9,
                "x": 0.1,
                "y": 0.1,
                "w": 0.2,
                "h": 0.2,
            }
        ]

    def __call__(self, asset):
        return self.predict(asset)


def register_fake_model(client) -> int:
    """An online `model_version` row, so the task's foreign key points at something real."""
    with client.app.state.session_factory() as session:
        model = ModelVersion(
            version_name=f"fake-v8n-{uuid4().hex[:6]}",
            weight_path="weights/fake.pt",
            labels_path="labels.txt",
            status=1,
            is_online=1,
        )
        session.add(model)
        session.commit()
        return model.model_id


def test_detect_frame_rejects_a_frame_that_never_came_through_capture(client):
    token = sign_in(client)
    response = client.post("/api/detect/frames/not-a-captured-frame", headers=auth(token))
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == 40401
    assert body["data"] is None


def test_detect_frame_writes_boxes_with_the_contract_fields(client):
    token = sign_in(client)
    _, frame = capture_one(client, token)
    seed_species_rows(client)
    model_id = register_fake_model(client)
    client.app.state.detector = FakeDetector(model_id)

    body = client.post(f"/api/detect/frames/{frame['frame_id']}", headers=auth(token)).json()
    assert body["code"] == 0
    data = body["data"]
    assert data["frame_id"] == frame["frame_id"]
    assert data["model_version"] == "fake-v8n"
    assert data["conf_threshold"] == 0.5
    assert isinstance(data["task_id"], int)
    assert isinstance(data["latency_ms"], int) and data["latency_ms"] >= 0

    # Contract §6 "Detection box": every documented field, in its documented type, normalised.
    assert len(data["boxes"]) == 1
    box = data["boxes"][0]
    assert isinstance(box["object_id"], int)
    assert box["class_code"] == "holothurian"
    assert isinstance(box["confidence"], float) and 0.0 <= box["confidence"] <= 1.0
    for axis in ("x", "y", "w", "h"):
        assert isinstance(box[axis], float) and 0.0 <= box[axis] <= 1.0, axis
    assert box["x"] + box["w"] <= 1.0
    assert box["y"] + box["h"] <= 1.0
    assert box["is_manual"] == 0
    assert box["review_status"] == 0

    with client.app.state.session_factory() as session:
        task = session.get(DetectTask, data["task_id"])
        assert task.status == 2
        assert task.progress == 100
        assert task.obj_count == 1
        assert task.model_version_id == model_id
        assert task.finished_at is not None
        rows = session.scalars(
            select(DetectObject).where(DetectObject.frame_id == frame["frame_id"])
        ).all()
        assert len(rows) == 1
        assert rows[0].task_id == task.task_id


def test_boxes_come_back_by_frame_id(client):
    """P2-02: what detection stored, the query route returns — same rows, same ids, same counts."""
    token = sign_in(client)
    _, frame = capture_one(client, token)
    seed_species_rows(client)
    client.app.state.detector = FakeDetector(register_fake_model(client))

    detected = client.post(f"/api/detect/frames/{frame['frame_id']}", headers=auth(token)).json()[
        "data"
    ]
    body = client.get(f"/api/frames/{frame['frame_id']}/objects", headers=auth(token)).json()
    assert body["code"] == 0
    assert body["data"]["items"] == detected["boxes"]
    assert body["data"]["counts"] == {"holothurian": 1}

    missing = client.get("/api/frames/no-such-frame/objects", headers=auth(token)).json()
    assert missing["code"] == 40401


def test_a_frame_with_no_detection_returns_an_empty_result(client):
    token = sign_in(client)
    _, frame = capture_one(client, token)
    body = client.get(f"/api/frames/{frame['frame_id']}/objects", headers=auth(token)).json()
    assert body["code"] == 0
    assert body["data"] == {"items": [], "counts": {}}


def test_detecting_the_same_frame_twice_leaves_one_automatic_result(client):
    """A second run replaces the previous automatic set; a duplicate would be counted twice."""
    token = sign_in(client)
    _, frame = capture_one(client, token)
    seed_species_rows(client)
    client.app.state.detector = FakeDetector(register_fake_model(client))

    first = client.post(f"/api/detect/frames/{frame['frame_id']}", headers=auth(token)).json()[
        "data"
    ]
    second = client.post(f"/api/detect/frames/{frame['frame_id']}", headers=auth(token)).json()[
        "data"
    ]

    assert first["task_id"] != second["task_id"]
    objects = client.get(f"/api/frames/{frame['frame_id']}/objects", headers=auth(token)).json()[
        "data"
    ]
    assert objects["items"] == second["boxes"]
    assert objects["counts"] == {"holothurian": 1}
    with client.app.state.session_factory() as session:
        rows = session.scalars(
            select(DetectObject).where(DetectObject.frame_id == frame["frame_id"])
        ).all()
        assert len(rows) == 1


def test_redetection_keeps_the_boxes_a_reviewer_drew(client):
    token = sign_in(client)
    _, frame = capture_one(client, token)
    seed_species_rows(client)
    client.app.state.detector = FakeDetector(register_fake_model(client))
    client.post(f"/api/detect/frames/{frame['frame_id']}", headers=auth(token))

    # The reviewer's canvas is the authority: the automatic box is not in it, so it is rejected.
    reviewed = client.post(
        f"/api/review/frames/{frame['frame_id']}",
        json={
            "objects": [
                {
                    "class_code": "chlamys",
                    "confidence": 1.0,
                    "x": 0.3,
                    "y": 0.3,
                    "w": 0.1,
                    "h": 0.1,
                }
            ],
            "note": "drawn by hand",
        },
        headers=auth(token),
    ).json()
    assert reviewed["code"] == 0
    after_review = client.get(
        f"/api/frames/{frame['frame_id']}/objects", headers=auth(token)
    ).json()["data"]["items"]
    manual_id = next(item["object_id"] for item in after_review if item["is_manual"] == 1)

    client.post(f"/api/detect/frames/{frame['frame_id']}", headers=auth(token))
    objects = client.get(f"/api/frames/{frame['frame_id']}/objects", headers=auth(token)).json()[
        "data"
    ]
    by_id = {item["object_id"]: item for item in objects["items"]}
    assert manual_id in by_id
    assert by_id[manual_id]["is_manual"] == 1
    assert by_id[manual_id]["class_code"] == "chlamys"
    # The automatic box came back with the new run, and the rejected one is gone with the old set.
    assert objects["counts"] == {"chlamys": 1, "holothurian": 1}
    assert sum(1 for item in objects["items"] if item["is_manual"] == 0) == 1


# --- P2-05c: the statistics are the rows, on the basis the route names ---------------------------


def test_stats_figures_follow_the_rows_detection_and_review_wrote(client):
    token = sign_in(client)
    _, first = capture_one(client, token, seed=1)
    _, second = capture_one(client, token, seed=2)
    seed_species_rows(client)
    client.app.state.detector = FakeDetector(register_fake_model(client))
    for frame in (first, second):
        body = client.post(f"/api/detect/frames/{frame['frame_id']}", headers=auth(token)).json()
        assert body["code"] == 0

    raw = client.get("/api/stats/species?basis=raw", headers=auth(token)).json()["data"]
    assert raw["basis"] == "raw"
    assert raw["total"] == 2
    assert [(item["class_code"], item["count"]) for item in raw["items"]] == [("holothurian", 2)]
    assert sum(item["share"] for item in raw["items"]) == pytest.approx(1.0)

    reviewed = client.get("/api/stats/species?basis=reviewed", headers=auth(token)).json()["data"]
    assert reviewed["total"] == 2

    # The reviewer rejects the one box in the first frame: raw still counts it, reviewed does not.
    rejected = client.post(
        f"/api/review/frames/{first['frame_id']}", json={"objects": []}, headers=auth(token)
    ).json()
    assert rejected["code"] == 0

    after = client.get("/api/stats/species?basis=reviewed", headers=auth(token)).json()["data"]
    assert after["total"] == 1
    raw_after = client.get("/api/stats/species?basis=raw", headers=auth(token)).json()["data"]
    assert raw_after["total"] == 2

    corrections = client.get("/api/stats/corrections", headers=auth(token)).json()["data"]
    assert corrections["rejected"] == 1
    assert corrections["modified"] == 0
    assert corrections["added"] == 0
    assert corrections["total"] == 1

    # The two capture-side figures count the frames that exist, not a fixture.
    with client.app.state.session_factory() as session:
        frames_total = session.scalar(select(func.count(MediaAsset.asset_id)))
        rejected_frames = session.scalar(
            select(func.count()).select_from(MediaAsset).where(MediaAsset.quality_flag == 1)
        )
    quality = client.get("/api/stats/quality", headers=auth(token)).json()["data"]
    assert quality["total"] == frames_total
    assert quality["rejected"] == rejected_frames

    trend = client.get("/api/stats/trend", headers=auth(token)).json()["data"]
    today = datetime.now(UTC).date().isoformat()
    assert next(item["frames"] for item in trend["items"] if item["date"] == today) == frames_total


def test_the_loader_names_the_reason_it_cannot_build_a_detector(client):
    """The sentence in the 501 comes from here, and each one names something to act on."""
    from app.detector import load_online

    factory = client.app.state.session_factory
    settings = get_settings()

    detector, reason = load_online(factory, settings)
    assert detector is None
    assert "没有在线模型版本" in reason

    register_fake_model(client)  # its weight_path is weights/fake.pt, which is not on disk
    detector, reason = load_online(factory, settings)
    assert detector is None
    assert "权重文件不存在" in reason

    register_fake_model(client)  # two online rows break the one-online rule: refuse, do not guess
    detector, reason = load_online(factory, settings)
    assert detector is None
    assert "拒绝猜测" in reason


def test_detect_frame_reports_a_failing_model_and_leaves_a_failed_task(client):
    token = sign_in(client)
    _, frame = capture_one(client, token)
    model_id = register_fake_model(client)

    class BrokenDetector(FakeDetector):
        def predict(self, asset, conf_thr=0.5, iou_thr=0.45, max_det=100):
            raise RuntimeError("weight tensor is truncated")

    client.app.state.detector = BrokenDetector(model_id)
    response = client.post(f"/api/detect/frames/{frame['frame_id']}", headers=auth(token))

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == 50001
    assert body["data"] is None
    assert "weight tensor is truncated" in body["message"]

    with client.app.state.session_factory() as session:
        task = session.scalar(select(DetectTask).order_by(DetectTask.task_id.desc()).limit(1))
        assert task.status == 3
        assert "weight tensor is truncated" in (task.error_msg or "")
        assert session.scalar(select(func.count(DetectObject.object_id))) == 0
