"""The four statistics routes count over one window (ADR 14), not four.

The P3-02 audit found species, quality and corrections counting a rolling `now - days * 24h` while
trend counted the last local calendar days. Two cards labelled "近 7 日" then disagreed: a frame on
the seventh previous local day was in quality but not in trend. This test freezes the clock and puts
frames on both sides of the window, so a route still using the rolling window answers differently.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from app import timebase
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import DetectObject, DetectTask, MediaAsset, SpeciesDict, SysUser
from app.security import hash_password
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

SHANGHAI = ZoneInfo("Asia/Shanghai")
#: 10:00 on 21 November local. `recent_days(7)` is 15-21 November; the old rolling window started
#: seven times 24 hours earlier, at 10:00 on 14 November local.
NOW_LOCAL = datetime(2026, 11, 21, 10, 0, 0, tzinfo=SHANGHAI)
#: The window's first local day and the day after its last one, both at local midnight.
WINDOW_START = datetime(2026, 11, 15, 0, 0, 0, tzinfo=SHANGHAI)
AFTER_WINDOW = datetime(2026, 11, 22, 0, 0, 0, tzinfo=SHANGHAI)
#: Noon on the seventh previous local day: the old rolling window counted it, the local window not.
BEFORE_WINDOW = datetime(2026, 11, 14, 12, 0, 0, tzinfo=SHANGHAI)
#: Two frames inside the window, one at noon and one an hour later.
INSIDE = datetime(2026, 11, 16, 12, 0, 0, tzinfo=SHANGHAI)


def utc(moment: datetime) -> datetime:
    """The naive UTC a `captured_at` or `created_at` column stores."""
    return moment.astimezone(UTC).replace(tzinfo=None)


@contextmanager
def _client(tmp_path, monkeypatch):
    """The app on a temporary SQLite database, with the clock frozen at NOW_LOCAL."""
    dsn = f"sqlite:///{(tmp_path / 'stats-window.db').as_posix()}"
    monkeypatch.setenv("DB_DSN", dsn)
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    monkeypatch.setenv("AV_TIMEZONE", "Asia/Shanghai")
    get_settings.cache_clear()
    monkeypatch.setattr(timebase, "now", lambda: NOW_LOCAL)
    monkeypatch.setattr(timebase, "now_utc", lambda: utc(NOW_LOCAL))

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
        session.add(SpeciesDict(class_code="holothurian", cn_name="海参", category=1))
        session.commit()

    # The capture routes accept only the local machine (FR-M1-02, P3-20), so this client says
    # where it is instead of relying on the test runner's default address.
    with TestClient(app, client=("127.0.0.1", 50000)) as test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
def client(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as test_client:
        yield test_client


def sign_in(client: TestClient) -> str:
    body = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password123"}
    ).json()
    assert body["code"] == 0, body
    return body["data"]["token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def seed_rows(client: TestClient) -> None:
    """Five frames around the window, one box each.

    BEFORE_WINDOW sits at noon on the seventh previous local day - inside the old rolling window,
    outside the local one. AFTER_WINDOW is the start of the day after tomorrow, inside the old
    window's missing upper bound, outside both. WINDOW_START is the window's own first instant and
    must be included; the two INSIDE frames are the rest of the window. Only those three frames and
    their three boxes may be counted by the repaired routes.
    """
    with client.app.state.session_factory() as session:
        task = DetectTask(task_code="DT261121-0001", task_type=2, asset_count=5)
        session.add(task)
        session.flush()
        rows = [
            (BEFORE_WINDOW, 3, 1),  # rejected box, rejected frame: outside the window
            (WINDOW_START, 0, 0),  # pending box, passed frame: the inclusive first instant
            (INSIDE, 2, 0),  # modified box, passed frame: inside
            (INSIDE + timedelta(hours=1), 3, 0),  # rejected box, passed frame: inside
            (AFTER_WINDOW, 2, 1),  # modified box, rejected frame: outside
        ]
        for index, (moment, review_status, quality_flag) in enumerate(rows):
            frame_id = f"{moment:%Y%m%dT%H%M%S}-{index:04d}"
            asset = MediaAsset(
                frame_id=frame_id,
                session_id="s-window",
                point_code="A3",
                file_path=f"frames/A3/{frame_id}.jpg",
                file_size=1024,
                file_hash=f"{index:064d}",
                captured_at=utc(moment),
                width=640,
                height=480,
                quality_score=80,
                quality_flag=quality_flag,
                is_retake=quality_flag,
            )
            session.add(asset)
            session.flush()
            session.add(
                DetectObject(
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
                    review_status=review_status,
                    created_at=utc(moment),
                )
            )
        session.commit()


def get_data(client: TestClient, token: str, path: str) -> dict:
    body = client.get(path, headers=auth(token)).json()
    assert body["code"] == 0, body
    return body["data"]


def test_all_four_stats_routes_count_the_same_local_day_window(client):
    """Only the three INSIDE frames are in the window; every route must see exactly those."""
    seed_rows(client)
    token = sign_in(client)

    trend = get_data(client, token, "/api/stats/trend?days=7")
    quality = get_data(client, token, "/api/stats/quality?days=7")
    raw = get_data(client, token, "/api/stats/species?basis=raw&days=7")
    reviewed = get_data(client, token, "/api/stats/species?basis=reviewed&days=7")
    corrections = get_data(client, token, "/api/stats/corrections?days=7")

    trend_frames = sum(item["frames"] for item in trend["items"])
    assert trend_frames == 3, f"trend counted {trend['items']}"
    # The old rolling window counted the 7th-previous-day frame and the frame at tomorrow's local
    # midnight, so quality answered 5 here while trend answered 3. The cards must agree.
    assert quality["total"] == trend_frames, quality
    assert quality["rejected"] == 0, "both rejected frames are outside the window"
    # species joins boxes to frames, so the three in-window frames carry three in-window boxes.
    assert raw["total"] == 3, raw
    assert reviewed["total"] == 2, "the rejected in-window box is not on the reviewed basis"
    # corrections counts boxes by created_at over the same bounds: one rejected, one modified.
    assert corrections["rejected"] == 1, corrections
    assert corrections["modified"] == 1, corrections
    assert corrections["added"] == 0, corrections
    assert corrections["total"] == 2, corrections
    for route in (trend, quality, raw, reviewed, corrections):
        assert route["days"] == 7, "every route echoes the days it counted"
