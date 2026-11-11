"""The hard-example pool (AC-17, FR-M4-03).

AC-17's defining behaviour is not that the route answers: "every sample corrected in review appears in
the pool with its origin tag; removed samples no longer appear" (SRS Table 3-18). So the tests drive a
real review correction and watch it enter the pool, keep the three origin types filterable, keep a
frame listed once however many of its boxes are hard, and check that removal empties the pool entry
while the frame and its boxes stay in the store - removal clears the flag, it does not delete evidence.
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

CAPTURED_AT = datetime(2026, 11, 11, 12, 0, 0)
ORIGINS = ("low_conf", "modified", "inconsistent")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """An app over a throwaway database, with the four classes and the roles review needs."""
    dsn = f"sqlite:///{(tmp_path / 'hard.db').as_posix()}"
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
        for username, role in (("admin", "admin"), ("observer", "observer")):
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


def box(class_code: str, x: float = 0.1) -> dict:
    return {"class_code": class_code, "confidence": 0.9, "x": x, "y": 0.2, "w": 0.1, "h": 0.1}


def seed_frame(client: TestClient, frame_id: str, specs: list[dict]) -> None:
    """A frame with a finished detection task and boxes carrying the given hard-example fields."""
    factory = client.app.state.session_factory
    with factory() as session:
        asset = MediaAsset(
            frame_id=frame_id,
            session_id="s-hard",
            point_code="A3",
            file_path=f"frames/A3/{frame_id}.jpg",
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
        task = DetectTask(
            task_code=f"DT-{frame_id[-4:]}",
            task_type=2,
            asset_count=len(specs),
            status=2,
            progress=100,
            obj_count=len(specs),
        )
        session.add(task)
        session.flush()
        for spec in specs:
            session.add(
                DetectObject(
                    task_id=task.task_id,
                    asset_id=asset.asset_id,
                    frame_id=frame_id,
                    class_code=spec["class_code"],
                    confidence=spec.get("confidence", 0.9),
                    x=spec.get("x", 0.1),
                    y=spec.get("y", 0.2),
                    w=spec.get("w", 0.1),
                    h=spec.get("h", 0.1),
                    is_manual=spec.get("is_manual", 0),
                    review_status=spec.get("review_status", 0),
                    hard_flag=spec.get("hard_flag", 0),
                    hard_reason=spec.get("hard_reason"),
                )
            )
        session.commit()


def list_pool(client: TestClient, token: str, **params) -> dict:
    body = client.get("/api/hard-samples", params=params, headers=auth(token)).json()
    assert body["code"] == 0, body
    return body["data"]


def sources(page: dict) -> dict[str, str]:
    return {item["frame_id"]: item["source"] for item in page["items"]}


def test_a_review_correction_enters_the_pool_with_its_origin(client):
    """AC-17: every corrected sample appears automatically, tagged with where it came from."""
    seed_frame(
        client,
        "20261111T120000-0001",
        [
            {"class_code": "holothurian", "x": 0.1},
            {"class_code": "chlamys", "x": 0.4},
        ],
    )
    token = sign_in(client)
    objects = client.get("/api/frames/20261111T120000-0001/objects", headers=auth(token)).json()[
        "data"
    ]["items"]
    by_class = {item["class_code"]: item for item in objects}
    # The reviewer relabels the sea cucumber as a starfish and keeps the scallop unchanged: that is a
    # correction, and the frame must join the pool with the "modified" origin.
    body = client.post(
        "/api/review/frames/20261111T120000-0001",
        json={
            "objects": [
                {**by_class["holothurian"], "class_code": "asterias"},
                by_class["chlamys"],
            ]
        },
        headers=auth(token),
    ).json()
    assert body["code"] == 0, body
    assert body["data"]["hard_sample"] is True

    page = list_pool(client, token)
    assert page["total"] == 1
    assert sources(page) == {"20261111T120000-0001": "modified"}


def test_the_pool_lists_each_frame_once_and_keeps_the_origins_filterable(client):
    """The three origins are filterable, a rejected box is not a pool entry, and a frame appears once."""
    seed_frame(
        client,
        "20261111T120000-0011",
        [{"class_code": "holothurian", "hard_flag": 1, "hard_reason": "low_conf"}],
    )
    seed_frame(
        client,
        "20261111T120000-0012",
        [{"class_code": "chlamys", "hard_flag": 1, "hard_reason": "modified"}],
    )
    seed_frame(
        client,
        "20261111T120000-0013",
        [{"class_code": "asterias", "hard_flag": 1, "hard_reason": "inconsistent"}],
    )
    # Two hard boxes on one frame: still one entry in the pool.
    seed_frame(
        client,
        "20261111T120000-0014",
        [
            {"class_code": "holothurian", "x": 0.1, "hard_flag": 1, "hard_reason": "modified"},
            {"class_code": "chlamys", "x": 0.5, "hard_flag": 1, "hard_reason": "modified"},
        ],
    )
    # A hard box the reviewer rejected, and a frame with no hard box: neither belongs in the pool.
    seed_frame(
        client,
        "20261111T120000-0015",
        [
            {
                "class_code": "holothurian",
                "hard_flag": 1,
                "hard_reason": "modified",
                "review_status": 3,
            }
        ],
    )
    seed_frame(
        client,
        "20261111T120000-0016",
        [{"class_code": "chlamys", "hard_flag": 0}],
    )

    token = sign_in(client)
    page = list_pool(client, token)
    assert page["total"] == 4
    assert sources(page) == {
        "20261111T120000-0011": "low_conf",
        "20261111T120000-0012": "modified",
        "20261111T120000-0013": "inconsistent",
        "20261111T120000-0014": "modified",
    }
    # Every item is the contract's frame object plus the origin tag.
    item = page["items"][0]
    assert {"frame_id", "session_id", "captured_at", "quality", "source"} <= set(item)

    for origin, expected in (
        ("low_conf", {"20261111T120000-0011"}),
        ("modified", {"20261111T120000-0012", "20261111T120000-0014"}),
        ("inconsistent", {"20261111T120000-0013"}),
    ):
        assert origin in ORIGINS
        filtered = list_pool(client, token, source=origin)
        assert set(sources(filtered)) == expected, origin
        assert filtered["total"] == len(expected)


def test_removal_empties_the_pool_entry_and_keeps_the_evidence(client):
    """AC-17: a removed sample no longer appears; the frame and its boxes are still there."""
    seed_frame(
        client,
        "20261111T120000-0021",
        [
            {"class_code": "holothurian", "hard_flag": 1, "hard_reason": "modified"},
            {"class_code": "chlamys", "x": 0.4},
        ],
    )
    seed_frame(
        client,
        "20261111T120000-0022",
        [{"class_code": "asterias", "hard_flag": 1, "hard_reason": "low_conf"}],
    )
    token = sign_in(client)
    assert set(sources(list_pool(client, token))) == {
        "20261111T120000-0021",
        "20261111T120000-0022",
    }

    body = client.delete("/api/hard-samples/20261111T120000-0021", headers=auth(token)).json()
    assert body["code"] == 0, body
    assert body["data"] == {"frame_id": "20261111T120000-0021", "removed": 1}

    after = list_pool(client, token)
    assert set(sources(after)) == {"20261111T120000-0022"}
    # The frame was not deleted, and its boxes are still queryable: the pool flag is cleared, not the
    # evidence (a rejected row is flagged 3; a label that left the pool is just no longer hard).
    frame = client.get("/api/frames/20261111T120000-0021", headers=auth(token)).json()
    assert frame["code"] == 0, frame
    objects = client.get("/api/frames/20261111T120000-0021/objects", headers=auth(token)).json()
    assert objects["code"] == 0
    assert len(objects["data"]["items"]) == 2

    factory = client.app.state.session_factory
    with factory() as session:
        flags = session.scalars(
            select(DetectObject.hard_flag).where(DetectObject.frame_id == "20261111T120000-0021")
        ).all()
    assert flags == [0, 0], "removal clears hard_flag on the frame's boxes"

    # Removing a frame that is not in the pool is a 404, not a silent success.
    missing = client.delete("/api/hard-samples/20261111T120000-0021", headers=auth(token)).json()
    assert missing["code"] == 40401
