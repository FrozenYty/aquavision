"""Review versions and rollback (P3-16, FR-M4-02, AC-16).

The storage already existed: every submission writes a `sys_log` row with the complete before/after box
lists. These tests drive the two routes that read that history and replay one entry from it, through
the API, and check the restored boxes by class and coordinate rather than by count alone.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import DetectObject, DetectTask, MediaAsset, SysUser
from app.security import hash_password
from app.seed import seed_species
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

FRAME = "20261111T120000-0001"
OTHER_FRAME = "20261111T120000-0002"
EMPTY_FRAME = "20261111T120000-0003"
CAPTURED_AT = datetime(2026, 11, 11, 12, 0, 0)


@pytest.fixture
def client(tmp_path, monkeypatch):
    """An app over a throwaway database, with the three roles these routes talk about."""
    dsn = f"sqlite:///{(tmp_path / 'review.db').as_posix()}"
    monkeypatch.setenv("DB_DSN", dsn)
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
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
        for username, role in (
            ("admin", "admin"),
            ("observer", "observer"),
            ("analyst", "analyst"),
        ):
            hashed, salt = hash_password("password123")
            session.add(
                SysUser(
                    username=username,
                    password_hash=hashed,
                    salt=salt,
                    role_code=role,
                    real_name=username,
                    status=1,
                    fail_count=0,
                )
            )
        session.commit()

    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def sign_in(client: TestClient, username: str = "admin") -> str:
    body = client.post(
        "/api/auth/login", json={"username": username, "password": "password123"}
    ).json()
    assert body["code"] == 0, body
    return body["data"]["token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def box(
    class_code: str,
    x: float,
    y: float,
    w: float = 0.1,
    h: float = 0.1,
    confidence: float = 0.9,
) -> dict:
    return {"class_code": class_code, "confidence": confidence, "x": x, "y": y, "w": w, "h": h}


def seed_frame(client: TestClient, frame_id: str, specs: list[dict]) -> list[int]:
    """A captured frame with a finished detection task and the given automatic boxes."""
    factory = client.app.state.session_factory
    with factory() as session:
        asset = MediaAsset(
            frame_id=frame_id,
            session_id="s-review",
            point_code="A3",
            file_path=f"frames/{frame_id}.jpg",
            file_size=1024,
            file_hash=(frame_id.replace("-", "") + "0" * 64)[:64],
            captured_at=CAPTURED_AT,
            width=640,
            height=480,
            quality_score=80,
            quality_flag=0,
            is_retake=0,
        )
        session.add(asset)
        session.flush()
        if not specs:
            session.commit()
            return []

        task = DetectTask(
            task_code=f"DT-{frame_id[-4:]}",
            task_type=2,
            asset_count=1,
            status=2,
            progress=100,
        )
        session.add(task)
        session.flush()
        object_ids = []
        for spec in specs:
            row = DetectObject(
                task_id=task.task_id,
                asset_id=asset.asset_id,
                frame_id=frame_id,
                class_code=spec["class_code"],
                confidence=spec["confidence"],
                x=spec["x"],
                y=spec["y"],
                w=spec["w"],
                h=spec["h"],
                is_manual=0,
                review_status=0,
                version_no=1,
            )
            session.add(row)
            session.flush()
            object_ids.append(row.object_id)
        session.commit()
        return object_ids


def review(client: TestClient, headers: dict, frame_id: str, objects: list[dict]) -> dict:
    body = client.post(
        f"/api/review/frames/{frame_id}", json={"objects": objects}, headers=headers
    ).json()
    assert body["code"] == 0, body
    return body["data"]


def versions(client: TestClient, headers: dict, frame_id: str) -> dict:
    body = client.get(f"/api/review/frames/{frame_id}/versions", headers=headers).json()
    assert body["code"] == 0, body
    return body["data"]


def objects(client: TestClient, headers: dict, frame_id: str) -> list[dict]:
    body = client.get(f"/api/frames/{frame_id}/objects", headers=headers).json()
    assert body["code"] == 0, body
    return body["data"]["items"]


def two_reviews(client: TestClient) -> tuple[dict, dict, int, int, int, int]:
    """Two submissions that a rollback can distinguish: the first set, the second, and both log ids.

    The first keeps both automatic boxes and adds one; the second moves one box, drops two and adds
    one, so the accepted set is smaller than the version before it.
    """
    analyst = auth(sign_in(client, "analyst"))
    admin = auth(sign_in(client, "admin"))
    first_id, second_id = seed_frame(
        client,
        FRAME,
        [box("holothurian", 0.10, 0.10, 0.2, 0.2), box("chlamys", 0.50, 0.50)],
    )
    review(
        client,
        analyst,
        FRAME,
        [
            {"object_id": first_id, **box("holothurian", 0.10, 0.10, 0.2, 0.2)},
            {"object_id": second_id, **box("chlamys", 0.50, 0.50)},
            box("starfish", 0.30, 0.30),
        ],
    )
    review(
        client,
        admin,
        FRAME,
        [
            {"object_id": first_id, **box("holothurian", 0.15, 0.15, 0.2, 0.2)},
            box("asterias", 0.60, 0.60),
        ],
    )
    history = versions(client, admin, FRAME)["items"]
    assert [entry["action"] for entry in history] == ["submit", "submit"]
    return analyst, admin, first_id, second_id, history[1]["log_id"], history[0]["log_id"]


def test_two_submissions_appear_newest_first_with_their_counts_and_authors(client):
    _, admin, _, _, first_log, second_log = two_reviews(client)

    data = versions(client, admin, FRAME)
    assert data["frame_id"] == FRAME
    items = data["items"]
    assert [item["log_id"] for item in items] == [second_log, first_log]
    assert [item["action"] for item in items] == ["submit", "submit"]

    newest, oldest = items
    assert newest["author"] == "admin"
    assert oldest["author"] == "analyst"
    assert newest["before_count"] == 3 and newest["after_count"] == 2
    assert oldest["before_count"] == 2 and oldest["after_count"] == 3
    for item in items:
        assert isinstance(item["created_at"], str)
        assert item["created_at"].endswith("+00:00")

    # The counts come from the stored JSON, not from the current boxes: the frame has two accepted
    # boxes now, while the first submission's entry says three.
    accepted = [item for item in objects(client, admin, FRAME) if item["review_status"] != 3]
    assert len(accepted) == 2
    assert oldest["after_count"] == 3


def test_rollback_restores_the_target_box_set_as_a_new_version(client):
    analyst, admin, first_id, second_id, first_log, _ = two_reviews(client)

    body = client.post(
        f"/api/review/frames/{FRAME}/rollback", json={"log_id": first_log}, headers=analyst
    ).json()
    assert body["code"] == 0, body
    restored = body["data"]
    assert restored["log_id"] == first_log
    assert restored["frame_id"] == FRAME
    assert restored["object_count"] == 3
    assert restored["rejected"] == 1  # the box added by the second submission
    assert restored["added"] == 0
    assert isinstance(restored["version_no"], int)
    assert isinstance(restored["hard_sample"], bool)

    # The accepted set is the target set, box by box: class and geometry, not only the count.
    accepted = [item for item in objects(client, admin, FRAME) if item["review_status"] != 3]
    assert [
        (item["class_code"], item["x"], item["y"], item["w"], item["h"]) for item in accepted
    ] == [
        ("holothurian", 0.10, 0.10, 0.2, 0.2),
        ("chlamys", 0.50, 0.50, 0.1, 0.1),
        ("starfish", 0.30, 0.30, 0.1, 0.1),
    ]
    by_id = {item["object_id"]: item for item in accepted}
    # The moved box is back at its old coordinates and is marked modified; the untouched boxes are
    # confirmed again, and the restored manual box is no longer rejected.
    assert by_id[first_id]["x"] == 0.10 and by_id[first_id]["review_status"] == 2
    assert by_id[second_id]["review_status"] == 1


def test_rollback_marks_removed_boxes_rejected_instead_of_deleting_them(client):
    analyst, admin, first_id, second_id, first_log, _ = two_reviews(client)

    before = objects(client, admin, FRAME)
    client.post(f"/api/review/frames/{FRAME}/rollback", json={"log_id": first_log}, headers=analyst)

    # The box the rollback dropped is still a row, marked rejected: AC-15 keeps the record, and every
    # statistic that reads `review_status` can tell it apart from an accepted one.
    after = objects(client, admin, FRAME)
    assert len(after) == len(before)
    dropped = next(item for item in after if item["class_code"] == "asterias")
    assert dropped["review_status"] == 3
    with client.app.state.session_factory() as session:
        rows = session.scalars(select(DetectObject).where(DetectObject.frame_id == FRAME)).all()
        assert len(rows) == len(before)
        assert any(row.class_code == "asterias" and row.review_status == 3 for row in rows)


def test_the_rollback_is_itself_an_entry_in_the_history(client):
    analyst, admin, _, _, first_log, _ = two_reviews(client)

    client.post(f"/api/review/frames/{FRAME}/rollback", json={"log_id": first_log}, headers=analyst)

    items = versions(client, admin, FRAME)["items"]
    assert [item["action"] for item in items] == ["rollback", "submit", "submit"]
    newest = items[0]
    assert newest["author"] == "analyst"
    # Every stored box at that moment, the rejected ones included.
    assert newest["before_count"] == 4
    assert newest["after_count"] == 3
    assert newest["log_id"] > items[1]["log_id"]


def test_a_rollback_to_the_current_set_is_refused_as_a_no_op(client):
    analyst, admin, _, _, _, second_log = two_reviews(client)

    body = client.post(
        f"/api/review/frames/{FRAME}/rollback", json={"log_id": second_log}, headers=analyst
    ).json()
    assert body["code"] == 40901
    assert body["data"] is None
    # Refused before writing, so the timeline did not gain an entry that says nothing changed.
    assert len(versions(client, admin, FRAME)["items"]) == 2


def test_an_unknown_log_id_is_refused(client):
    headers = auth(sign_in(client, "analyst"))
    seed_frame(client, FRAME, [box("holothurian", 0.10, 0.10, 0.2, 0.2)])

    body = client.post(
        f"/api/review/frames/{FRAME}/rollback", json={"log_id": 999999}, headers=headers
    ).json()
    assert body["code"] == 40401
    assert body["data"] is None


def test_a_log_belonging_to_another_frame_is_refused(client):
    admin = auth(sign_in(client, "admin"))
    first_box = seed_frame(client, FRAME, [box("holothurian", 0.10, 0.10, 0.2, 0.2)])[0]
    other_box = seed_frame(client, OTHER_FRAME, [box("chlamys", 0.50, 0.50)])[0]
    review(
        client,
        admin,
        OTHER_FRAME,
        [{"object_id": other_box, **box("chlamys", 0.50, 0.50)}],
    )
    other_log = versions(client, admin, OTHER_FRAME)["items"][0]["log_id"]

    body = client.post(
        f"/api/review/frames/{FRAME}/rollback", json={"log_id": other_log}, headers=admin
    ).json()
    assert body["code"] == 40901
    assert body["data"] is None
    # The frame it was aimed at was not touched.
    assert objects(client, admin, FRAME)[0]["object_id"] == first_box


def test_a_rollback_is_refused_for_an_observer(client):
    admin = auth(sign_in(client, "admin"))
    observer = auth(sign_in(client, "observer"))
    frame_id = seed_frame(client, FRAME, [box("holothurian", 0.10, 0.10, 0.2, 0.2)])[0]
    review(
        client,
        admin,
        FRAME,
        [{"object_id": frame_id, **box("holothurian", 0.10, 0.10, 0.2, 0.2)}],
    )
    log_id = versions(client, admin, FRAME)["items"][0]["log_id"]

    response = client.post(
        f"/api/review/frames/{FRAME}/rollback", json={"log_id": log_id}, headers=observer
    )
    assert response.status_code == 403
    assert response.json()["code"] == 40301


def test_a_frame_with_no_reviews_answers_an_empty_list(client):
    admin = auth(sign_in(client, "admin"))
    seed_frame(client, EMPTY_FRAME, [])

    data = versions(client, admin, EMPTY_FRAME)
    assert data["frame_id"] == EMPTY_FRAME
    assert data["items"] == []

    missing = client.get("/api/review/frames/no-such-frame/versions", headers=admin).json()
    assert missing["code"] == 40401
