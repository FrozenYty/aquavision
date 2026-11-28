"""A report's figures equal the dashboard's for the same seven operating days (AC-22, FR-M5-04).

The P3-07 review found `_figures` re-spelling the dashboard's queries and ending its window one
instant late: it counted `captured_at <= end` while the dashboard counts `<` the next local midnight.
This test freezes the clock and seeds frames on both sides of the window - one at the window's first
instant, one at the last microsecond of the last day, one exactly at the exclusive upper bound
(tomorrow's local midnight), and one after it - so a re-spelled query or an inclusive bound answers a
different number. Both surfaces are read back through the API, and the assertions are on the figures
the operator sees, not on the SQL that produced them.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from app import timebase
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.models import DetectObject, DetectTask, MediaAsset, SpeciesDict, SysUser
from app.security import hash_password
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

SHANGHAI = ZoneInfo("Asia/Shanghai")
#: 10:00 on 21 November local: `recent_days(7)` is 15-21 November, and the dashboard window ends at
#: the next local midnight.
NOW_LOCAL = datetime(2026, 11, 21, 10, 0, 0, tzinfo=SHANGHAI)
#: The window's first instant, inclusive in both surfaces.
WINDOW_START = datetime(2026, 11, 15, 0, 0, 0, tzinfo=SHANGHAI)
#: The instant after the window's last day: the dashboard's exclusive upper bound.
WINDOW_END = datetime(2026, 11, 22, 0, 0, 0, tzinfo=SHANGHAI)
#: Noon on the seventh previous local day: inside the old rolling window, outside this one.
BEFORE_WINDOW = datetime(2026, 11, 14, 12, 0, 0, tzinfo=SHANGHAI)
#: The last microsecond of the last day: inside the window, and counted only when the report's
#: exclusive bound is derived from the day rather than the inclusive value `report_bounds` returns.
LAST_INSTANT = datetime(2026, 11, 21, 23, 59, 59, 999999, tzinfo=SHANGHAI)
#: A passed frame with a modified box, inside the window.
INSIDE = datetime(2026, 11, 16, 12, 0, 0, tzinfo=SHANGHAI)
#: A rejected frame carrying a rejected box: counted only on the raw basis.
LATER = datetime(2026, 11, 17, 9, 0, 0, tzinfo=SHANGHAI)
#: After the window entirely, so an unbounded upper end would show up as extra frames.
AFTER_WINDOW = datetime(2026, 11, 23, 0, 0, 0, tzinfo=SHANGHAI)

SPECIES = {"holothurian": "海参", "sea_urchin": "海胆"}
REVIEWED_SPECIES = {"海参": 3}
RAW_SPECIES = {"海参": 3, "海胆": 1}
#: The seven operating days as the operator picks them: calendar dates, whole days in AV_TIMEZONE.
PERIOD = {"period_start": "2026-11-15", "period_end": "2026-11-21"}
#: The same half-open window named as its two instants. The API's `date | datetime` query types read
#: a midnight-exact timestamp as a date (pydantic's date parser accepts a datetime whose time is
#: midnight), so the window is spelled in UTC, where neither instant is a local midnight; the UTC
#: instant is what the dashboard's own bounds are stored as (ADR 14).
INSTANT_PERIOD = {
    "period_start": WINDOW_START.astimezone(UTC).isoformat(),
    "period_end": WINDOW_END.astimezone(UTC).isoformat(),
}


def utc(moment: datetime) -> datetime:
    """The naive UTC a `captured_at` or `created_at` column stores."""
    return moment.astimezone(UTC).replace(tzinfo=None)


@contextmanager
def _client(tmp_path, monkeypatch):
    """The app on a temporary SQLite database, with the clock frozen at NOW_LOCAL."""
    dsn = f"sqlite:///{(tmp_path / 'report-agree.db').as_posix()}"
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
        for class_code, cn_name in SPECIES.items():
            session.add(SpeciesDict(class_code=class_code, cn_name=cn_name, category=1))
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


def get_data(client: TestClient, token: str, path: str, **params) -> dict:
    body = client.get(path, params=params or None, headers=auth(token)).json()
    assert body["code"] == 0, body
    return body["data"]


def seed_rows(client: TestClient) -> None:
    """Seven frames: four in the window, one before it, one at its exclusive end, one after it.

    WINDOW_START, LAST_INSTANT and WINDOW_END are the three instants an inclusive end gets wrong.
    The first must be counted by both surfaces, the last microsecond of the last day must be counted
    by both, and the frame at tomorrow's local midnight must be counted by neither.
    """
    rows = [
        (BEFORE_WINDOW, "holothurian", 3, 1),
        (WINDOW_START, "holothurian", 0, 0),
        (INSIDE, "holothurian", 2, 0),
        (LATER, "sea_urchin", 3, 1),
        (LAST_INSTANT, "holothurian", 0, 0),
        (WINDOW_END, "holothurian", 0, 0),
        (AFTER_WINDOW, "sea_urchin", 0, 0),
    ]
    with client.app.state.session_factory() as session:
        task = DetectTask(task_code="DT261121-0001", task_type=2, asset_count=len(rows))
        session.add(task)
        session.flush()
        for index, (moment, class_code, review_status, quality_flag) in enumerate(rows):
            frame_id = f"{moment:%Y%m%dT%H%M%S%f}-{index:04d}"
            asset = MediaAsset(
                frame_id=frame_id,
                session_id="s-report-agree",
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
                    class_code=class_code,
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


def species_by_name(client: TestClient, token: str, basis: str) -> dict[str, int]:
    """The dashboard's per-class counts, named the way the report names them (`cn_name`)."""
    card = get_data(client, token, f"/api/stats/species?basis={basis}&days=7")
    with client.app.state.session_factory() as session:
        names = {row.class_code: row.cn_name for row in session.scalars(select(SpeciesDict)).all()}
    return {
        names.get(item["class_code"], item["class_code"]): item["count"] for item in card["items"]
    }


def test_the_report_figures_equal_the_dashboard_for_the_last_seven_operating_days(client):
    """The dashboard's `days=7` window and the report's calendar period are the same seven days."""
    seed_rows(client)
    token = sign_in(client)

    quality = get_data(client, token, "/api/stats/quality?days=7")
    figures = get_data(client, token, "/api/reports/preview", **PERIOD)["figures"]

    # Four frames: the window's first instant, two inside it, and the last microsecond of the last
    # day. The frame at tomorrow's local midnight and the two frames outside the window are counted
    # by neither surface.
    assert quality["total"] == 4, quality
    assert quality["rejected"] == 1, quality
    assert quality["rate"] == pytest.approx(0.25)
    assert figures["frames"] == quality["total"]
    assert figures["rejected"] == quality["rejected"]
    assert figures["rate"] == pytest.approx(quality["rate"])

    for basis, expected in (("reviewed", REVIEWED_SPECIES), ("raw", RAW_SPECIES)):
        report = get_data(client, token, "/api/reports/preview", **PERIOD, basis=basis)
        report_species = {item["name"]: item["count"] for item in report["figures"]["species"]}
        card = get_data(client, token, f"/api/stats/species?basis={basis}&days=7")
        assert species_by_name(client, token, basis) == expected
        assert report_species == expected
        assert card["total"] == sum(item["count"] for item in report["figures"]["species"])


def test_the_report_window_ends_where_the_dashboard_window_ends(client):
    """The same seven days named as instants: the report ends where the dashboard ends.

    This is the spelling the old inclusive bound got wrong. A client naming the window as
    `[WINDOW_START, WINDOW_END)` asks for exactly the dashboard's frames, while `_figures` counted
    `captured_at <= WINDOW_END` and so also counted the frame at tomorrow's local midnight.
    """
    seed_rows(client)
    token = sign_in(client)

    quality = get_data(client, token, "/api/stats/quality?days=7")
    instants = get_data(client, token, "/api/reports/preview", **INSTANT_PERIOD)
    dates = get_data(client, token, "/api/reports/preview", **PERIOD)["figures"]

    # Proves the instants really took the timestamp path: a date period would answer the final
    # microsecond of 21 November, as the instant 22 November local midnight is a whole-day bound.
    assert instants["period_end"] == "2026-11-22T00:00:00.000+08:00", instants["period_end"]
    figures = instants["figures"]
    assert quality["total"] == 4, quality
    assert figures["frames"] == quality["total"], (
        f"the report counted {figures['frames']} frames at the exclusive end, "
        f"the dashboard counted {quality['total']}"
    )
    assert figures["rejected"] == quality["rejected"]
    assert figures["rate"] == pytest.approx(quality["rate"])
    # One window, two spellings: the figures cannot depend on how the period was written.
    assert figures == dates
