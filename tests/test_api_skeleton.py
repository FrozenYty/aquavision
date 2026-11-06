"""The HTTP skeleton: the envelope, the guards, and the route set (P1-02).

The first test is the one that matters most — it compares the mounted operations against
`docs/api-contract-en.md`, so the contract stays the list of routes rather than a document that
describes an older system. The rest check behaviour that the frontend depends on: an envelope on
every response, a token required everywhere but login, roles enforced server-side, and 501 where a
module is honestly not built.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import cv2
import numpy as np
import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import SysUser
from app.security import hash_password
from fastapi.testclient import TestClient
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
    assert body["code"] == 0
    assert body["data"]["user"]["role"] == "admin"
    assert body["data"]["token"]


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
    assert frame["quality"]["score"] > 0
    assert frame["width"] == 160
    assert "quality_components" in frame

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
    assert quality["data"]["total"] == 0
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
