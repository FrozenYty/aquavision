"""Dataset export (AC-18, FR-M3-04).

AC-18 is about a snapshot, not a download: similar frames must not be split across train and val, or the
validation number is measured on images the model has already seen. These tests assert the grouping rule,
the counts that follow from it, and the manifest a reviewer would open — not that the route answers 200.

The route had no test before this file: `P2-09` closed AC-18 with a *page*, and a page-side claim left the
export itself unasserted. `only_reviewed` is tested in the negative — a database with no reviewed object
must refuse the export rather than produce an empty snapshot — which needs no foreign-key chain to seed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import MediaAsset, SysUser
from app.security import hash_password
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client(tmp_path, monkeypatch):
    """An app over a throwaway database and a throwaway data root."""
    dsn = f"sqlite:///{(tmp_path / 'datasets.db').as_posix()}"
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
        session.commit()

    with TestClient(app) as test_client:
        yield test_client, factory, Path(get_settings().data_dir)
    get_settings.cache_clear()


def sign_in(client: TestClient) -> dict[str, str]:
    body = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password123"}
    ).json()
    assert body["code"] == 0, body
    return {"Authorization": f"Bearer {body['data']['token']}"}


def seed_frame(factory, frame_id: str, captured_at: datetime, index: int) -> None:
    """One captured frame with an image on disk — the shape `_select_frames` looks at."""
    with factory() as session:
        session.add(
            MediaAsset(
                frame_id=frame_id,
                session_id="s-datasets",
                point_code="A3",
                file_path=f"{frame_id}.jpg",
                file_size=4,
                file_hash=frame_id.ljust(64, "0")[:64],
                captured_at=captured_at.astimezone(UTC).replace(tzinfo=None),
                width=640,
                height=480,
                quality_score=90,
                quality_flag=0,
                is_retake=0,
            )
        )
        session.commit()
    del index


def test_a_snapshot_keeps_a_burst_out_of_two_splits(client) -> None:
    """The rule AC-18 exists for: frames taken together must not straddle two sets."""
    test_client, factory, _root = client
    headers = sign_in(test_client)
    base = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
    for index in range(2):
        seed_frame(factory, f"burst-{index}", base + timedelta(microseconds=index), index)

    response = test_client.post(
        "/api/datasets",
        headers=headers,
        json={"snapshot_name": "DS-burst", "only_reviewed": False},
    )
    body = response.json()
    assert response.status_code == 200, body

    manifest = json.loads(
        (Path(get_settings().data_dir) / "datasets" / "DS-burst" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    by_id = {entry["frame_id"]: entry["split"] for entry in manifest["frames"]}
    assert by_id["burst-0"] == by_id["burst-1"], "one burst was split across two sets"
    assert manifest["frame_count"] == 2
    assert sum(body["data"]["splits"].values()) == 2


def test_the_export_is_listed_with_the_counts_the_manifest_carries(client) -> None:
    """The page reads the list, so the two must agree rather than each be plausible on its own."""
    test_client, factory, _root = client
    headers = sign_in(test_client)
    seed_frame(factory, "listed-1", datetime(2026, 11, 2, 9, 0, tzinfo=UTC), 0)

    exported = test_client.post(
        "/api/datasets",
        headers=headers,
        json={"snapshot_name": "DS-listed", "only_reviewed": False},
    ).json()
    listed = test_client.get("/api/datasets", headers=headers).json()["data"]["items"]

    assert [item["snapshot_name"] for item in listed] == ["DS-listed"]
    # The two views differ in shape and the difference is real: the export answers all three split names
    # including the empty ones, while the list only answers the splits that have rows. A page rendering a
    # train/val/test table therefore cannot show a zero row. Asserted here as agreement on what they do
    # report, so the inconsistency is visible rather than papered over.
    for split, count in listed[0]["splits"].items():
        assert exported["data"]["splits"][split] == count
    assert sum(listed[0]["splits"].values()) == sum(exported["data"]["splits"].values()) == 1
    assert listed[0]["frame_count"] == exported["data"]["frame_count"] == 1
    assert listed[0]["status"] == "ready"
    assert (Path(get_settings().data_dir) / "datasets" / "DS-listed" / "manifest.json").is_file()


def test_an_impossible_snapshot_is_refused_with_its_reason(client) -> None:
    """A ratio that cannot sum to ten, a name already used, and nothing to export."""
    test_client, factory, _root = client
    headers = sign_in(test_client)
    seed_frame(factory, "refused-1", datetime(2026, 11, 2, 8, 0, tzinfo=UTC), 0)

    bad_ratio = test_client.post(
        "/api/datasets",
        headers=headers,
        json={"snapshot_name": "DS-ratio", "split_ratio": "7:2:2", "only_reviewed": False},
    )
    assert bad_ratio.status_code == 400
    assert "10" in bad_ratio.json()["message"]

    # No detect_object rows exist here, so a reviewed-only export has nothing to label.
    nothing_reviewed = test_client.post(
        "/api/datasets", headers=headers, json={"snapshot_name": "DS-unreviewed"}
    )
    assert nothing_reviewed.status_code == 400
    assert "帧" in nothing_reviewed.json()["message"]

    first = test_client.post(
        "/api/datasets",
        headers=headers,
        json={"snapshot_name": "DS-twice", "only_reviewed": False},
    )
    assert first.status_code == 200
    repeated = test_client.post(
        "/api/datasets",
        headers=headers,
        json={"snapshot_name": "DS-twice", "only_reviewed": False},
    )
    assert repeated.status_code == 409
