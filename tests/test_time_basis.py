"""The time basis ADR 14 decides: one configured zone answers every calendar question.

Storage keeps `captured_at` naive UTC, so a capture taken just after local midnight is stored under the
previous UTC date. These tests seed the three instants around a local day - 00:00:00, 23:59:59 and the
next 00:00:00 - and assert both halves of the defect: the date filter means the operator's day, and an
emitted timestamp carries the configured offset. The last test runs the same rows with
`AV_TIMEZONE=UTC`, which proves the setting is consulted rather than a `+08:00` baked into the code.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import MediaAsset, SysUser
from app.security import hash_password
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

SHANGHAI = ZoneInfo("Asia/Shanghai")
FRAME_DAY = "2026-11-02"
FIRST_ID = "20261102T000000-0001"
LAST_ID = "20261102T235959-0002"
NEXT_ID = "20261103T000000-0003"


def local(year: int, month: int, day: int, hour: int, minute: int, second: int) -> datetime:
    """An instant expressed in the zone the default configuration uses."""
    return datetime(year, month, day, hour, minute, second, tzinfo=SHANGHAI)


@contextmanager
def _app_client(tmp_path, monkeypatch, timezone: str):
    dsn = f"sqlite:///{(tmp_path / 'timebase.db').as_posix()}"
    monkeypatch.setenv("DB_DSN", dsn)
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    monkeypatch.setenv("AV_TIMEZONE", timezone)
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    engine = engine_from_dsn(dsn)
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    with app.state.session_factory() as session:
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

    # The capture routes accept only the local machine (FR-M1-02, P3-20), so this client says
    # where it is instead of relying on the test runner's default address.
    with TestClient(app, client=("127.0.0.1", 50000)) as test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
def client(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "Asia/Shanghai") as test_client:
        yield test_client


@pytest.fixture
def utc_client(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "UTC") as test_client:
        yield test_client


def sign_in(client: TestClient) -> str:
    body = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password123"}
    ).json()
    assert body["code"] == 0, body
    return body["data"]["token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def seed_frame(client: TestClient, frame_id: str, moment: datetime) -> None:
    """Store one frame; `moment` is the instant as the operator experienced it (offset-aware)."""
    with client.app.state.session_factory() as session:
        session.add(
            MediaAsset(
                frame_id=frame_id,
                session_id="s-local",
                point_code="A3",
                file_path=f"frames/A3/{frame_id}.jpg",
                file_size=1024,
                file_hash=(frame_id.replace("-", "") + "0" * 64)[:64],
                captured_at=moment.astimezone(UTC).replace(tzinfo=None),
                width=640,
                height=480,
                quality_score=80,
                quality_flag=0,
                is_retake=0,
            )
        )
        session.commit()


def seed_the_local_day_boundaries(client: TestClient) -> None:
    """The instants on either side of the local day, stored as the naive UTC the column holds."""
    seed_frame(client, FIRST_ID, local(2026, 11, 2, 0, 0, 0))
    seed_frame(client, LAST_ID, local(2026, 11, 2, 23, 59, 59))
    seed_frame(client, NEXT_ID, local(2026, 11, 3, 0, 0, 0))


def list_frames(client: TestClient, token: str, **params) -> dict:
    body = client.get("/api/frames", params=params, headers=auth(token)).json()
    assert body["code"] == 0, body
    return body["data"]


def frame_ids(page: dict) -> list[str]:
    return [item["frame_id"] for item in page["items"]]


def test_a_frame_at_local_midnight_is_in_its_own_day(client):
    seed_the_local_day_boundaries(client)
    page = list_frames(client, sign_in(client), start=FRAME_DAY, end=FRAME_DAY)
    assert set(frame_ids(page)) == {FIRST_ID, LAST_ID}
    assert page["total"] == 2


def test_a_frame_at_the_last_local_second_is_in_the_same_day(client):
    seed_the_local_day_boundaries(client)
    page = list_frames(client, sign_in(client), start=FRAME_DAY, end=FRAME_DAY)
    assert LAST_ID in frame_ids(page)


def test_local_midnight_of_the_next_day_is_not_in_this_day(client):
    seed_the_local_day_boundaries(client)
    page = list_frames(client, sign_in(client), start=FRAME_DAY, end=FRAME_DAY)
    assert NEXT_ID not in frame_ids(page)


def test_an_emitted_captured_at_carries_the_configured_offset(client):
    seed_the_local_day_boundaries(client)
    token = sign_in(client)
    page = list_frames(client, token, start=FRAME_DAY, end=FRAME_DAY)
    by_id = {item["frame_id"]: item for item in page["items"]}
    # The exact string, not merely something that parses: the contract's own example shape.
    assert by_id[LAST_ID]["captured_at"] == "2026-11-02T23:59:59.000+08:00"

    # The sessions list derives `started_at` from the same column and must agree.
    sessions = client.get("/api/capture/sessions", headers=auth(token)).json()["data"]
    assert sessions["items"][0]["started_at"] == "2026-11-02T00:00:00.000+08:00"


def test_other_outbound_timestamps_use_the_same_converter(client):
    """The token expiry and the monitor's reading are timestamps too; they share serializers/timebase."""
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password123"}
    ).json()["data"]
    assert login["expires_at"].endswith("+08:00")

    monitor = client.get("/api/monitor", headers=auth(login["token"])).json()["data"]
    assert monitor["at"].endswith("+08:00")


def test_the_same_rows_fall_on_utc_days_when_the_zone_is_utc(utc_client):
    seed_the_local_day_boundaries(utc_client)
    token = sign_in(utc_client)
    page = list_frames(utc_client, token, start=FRAME_DAY, end=FRAME_DAY)
    # 00:00+08:00 is 16:00Z on 1 November, so under a UTC day it moves to the previous date; the
    # 23:59:59 local frame and the next local midnight both fall inside 2 November UTC.
    assert set(frame_ids(page)) == {LAST_ID, NEXT_ID}
    by_id = {item["frame_id"]: item for item in page["items"]}
    assert by_id[NEXT_ID]["captured_at"] == "2026-11-02T16:00:00.000+00:00"
