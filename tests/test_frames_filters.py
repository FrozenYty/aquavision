"""The frame search filters (AC-08, FR-M2-04).

AC-08 asks that "four filters combine correctly", so these tests do not check that GET /api/frames
answers 200: they seed frames that differ in exactly one attribute each and assert that every filter
alone keeps the right rows, that the four together intersect instead of piling up, and that the
returned total describes the filtered set rather than the page.

One boundary is pinned here deliberately: ADR 14 decides that the date filters mean the operator's
local day in `AV_TIMEZONE`, not the UTC day `captured_at` is stored under.
`test_the_date_range_is_the_operators_local_day` states that boundary, including the frames just
outside it, so a regression to UTC-day filtering fails on purpose.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import MediaAsset, SysUser
from app.security import hash_password
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client(tmp_path, monkeypatch):
    """An app over a throwaway database, with the one account these requests need."""
    dsn = f"sqlite:///{(tmp_path / 'frames.db').as_posix()}"
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
        yield test_client
    get_settings.cache_clear()


def sign_in(client: TestClient) -> str:
    body = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password123"}
    ).json()
    assert body["code"] == 0, body
    return body["data"]["token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def seed_frame(
    client: TestClient,
    frame_id: str,
    *,
    session_id: str,
    site: str,
    captured_at: datetime,
    quality_flag: int = 0,
) -> None:
    """One stored frame, with only the attributes the filters look at differing between calls."""
    factory = client.app.state.session_factory
    with factory() as session:
        session.add(
            MediaAsset(
                frame_id=frame_id,
                session_id=session_id,
                point_code=site,
                file_path=f"frames/{site}/{frame_id}.jpg",
                file_size=1024,
                file_hash=(frame_id.replace("-", "") + "0" * 64)[:64],
                captured_at=captured_at,
                width=640,
                height=480,
                quality_score=80 if quality_flag == 0 else 40,
                quality_flag=quality_flag,
                is_retake=quality_flag,
            )
        )
        session.commit()


def list_frames(client: TestClient, token: str, **params) -> dict:
    body = client.get("/api/frames", params=params, headers=auth(token)).json()
    assert body["code"] == 0, body
    return body["data"]


def frame_ids(page: dict) -> list[str]:
    return [item["frame_id"] for item in page["items"]]


def seed_four_frames(client: TestClient) -> None:
    """A 2x2: two capture sessions, two sites, ok-retake, and four different local days.

    A = s-1 / A3 / ok       / 2026-11-01
    B = s-1 / B1 / retake   / 2026-11-02
    C = s-2 / A3 / ok       / 2026-11-03
    D = s-2 / B1 / retake   / 2026-11-04
    """
    seed_frame(
        client,
        "20261101T100000-0001",
        session_id="s-1",
        site="A3",
        captured_at=datetime(2026, 11, 1, 10, 0),
    )
    seed_frame(
        client,
        "20261102T100000-0002",
        session_id="s-1",
        site="B1",
        captured_at=datetime(2026, 11, 2, 10, 0),
        quality_flag=1,
    )
    seed_frame(
        client,
        "20261103T100000-0003",
        session_id="s-2",
        site="A3",
        captured_at=datetime(2026, 11, 3, 10, 0),
    )
    seed_frame(
        client,
        "20261104T100000-0004",
        session_id="s-2",
        site="B1",
        captured_at=datetime(2026, 11, 4, 10, 0),
        quality_flag=1,
    )


def test_the_session_filter_narrows_to_one_capture_run(client):
    seed_four_frames(client)
    page = list_frames(client, sign_in(client), session="s-1")
    assert set(frame_ids(page)) == {"20261101T100000-0001", "20261102T100000-0002"}
    assert page["total"] == 2


def test_the_site_filter_narrows_to_one_monitoring_point(client):
    seed_four_frames(client)
    page = list_frames(client, sign_in(client), site="A3")
    assert set(frame_ids(page)) == {"20261101T100000-0001", "20261103T100000-0003"}
    assert page["total"] == 2


def test_the_quality_filter_splits_retakes_from_accepted_frames(client):
    seed_four_frames(client)
    token = sign_in(client)
    accepted = list_frames(client, token, quality="ok")
    retakes = list_frames(client, token, quality="retake")
    assert set(frame_ids(accepted)) == {"20261101T100000-0001", "20261103T100000-0003"}
    assert set(frame_ids(retakes)) == {"20261102T100000-0002", "20261104T100000-0004"}
    assert (accepted["total"], retakes["total"]) == (2, 2)


def test_the_date_range_is_inclusive_on_both_ends(client):
    seed_four_frames(client)
    token = sign_in(client)
    # A single day as both ends: the frame captured on that local day is included by both bounds.
    assert frame_ids(list_frames(client, token, start="2026-11-02", end="2026-11-02")) == [
        "20261102T100000-0002"
    ]
    # Two days: both edge days are included, nothing before or after.
    assert set(frame_ids(list_frames(client, token, start="2026-11-02", end="2026-11-03"))) == {
        "20261102T100000-0002",
        "20261103T100000-0003",
    }
    # One-sided ranges still cut at the boundary they name.
    assert set(frame_ids(list_frames(client, token, start="2026-11-03"))) == {
        "20261103T100000-0003",
        "20261104T100000-0004",
    }
    assert set(frame_ids(list_frames(client, token, end="2026-11-02"))) == {
        "20261101T100000-0001",
        "20261102T100000-0002",
    }


def test_the_four_filters_combine_as_an_intersection(client):
    seed_four_frames(client)
    token = sign_in(client)
    # Each added filter can only narrow the result: s-2 gives C and D, A3 removes D, ok keeps C, and
    # the date pins it to C's day.
    page = list_frames(
        client,
        token,
        session="s-2",
        site="A3",
        quality="ok",
        start="2026-11-03",
        end="2026-11-03",
    )
    assert frame_ids(page) == ["20261103T100000-0003"]
    assert page["total"] == 1
    # A combination that matches nothing is an empty page, not the unfiltered list.
    empty = list_frames(
        client,
        token,
        session="s-1",
        site="A3",
        quality="retake",
        start="2026-11-01",
        end="2026-11-01",
    )
    assert empty["items"] == []
    assert empty["total"] == 0


def test_the_total_counts_the_filtered_set_not_the_page(client):
    seed_four_frames(client)
    page = list_frames(client, sign_in(client), session="s-1", size=1)
    assert len(frame_ids(page)) == 1
    assert page["total"] == 2, "total must describe all matching frames, not the returned page"


def test_the_date_range_is_the_operators_local_day(client):
    """ADR 14: a day runs 00:00:00-23:59:59.999999 in the configured zone, not the stored UTC day.

    `captured_at` is naive UTC, so a capture at local 2026-11-02 03:00 on a UTC+8 machine is stored as
    2026-11-01T19:00Z. It must still count as 2 November; the frames either side - one at local
    1 November 23:00 and one at local 3 November 00:00 - are the day next door.
    """
    seed_frame(
        client,
        "20261101T150000-0004",
        session_id="s-3",
        site="A3",
        captured_at=datetime(2026, 11, 1, 15, 0),  # local 2026-11-01 23:00
    )
    seed_frame(
        client,
        "20261101T190000-0005",
        session_id="s-3",
        site="A3",
        captured_at=datetime(2026, 11, 1, 19, 0),  # local 2026-11-02 03:00
    )
    seed_frame(
        client,
        "20261102T100000-0006",
        session_id="s-3",
        site="A3",
        captured_at=datetime(2026, 11, 2, 10, 0),  # local 2026-11-02 18:00
    )
    seed_frame(
        client,
        "20261102T160000-0007",
        session_id="s-3",
        site="A3",
        captured_at=datetime(2026, 11, 2, 16, 0),  # local 2026-11-03 00:00
    )
    token = sign_in(client)
    on_the_second = frame_ids(list_frames(client, token, start="2026-11-02", end="2026-11-02"))
    assert set(on_the_second) == {"20261101T190000-0005", "20261102T100000-0006"}
