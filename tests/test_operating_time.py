"""The interface keeps supplied offsets and reports accept operating calendar dates."""

import os
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path

import pytest
from app import timebase
from app.config import get_settings
from test_time_basis import _app_client, auth, seed_the_local_day_boundaries, sign_in


@pytest.mark.parametrize("timezone", ["UTC", "America/New_York", "Asia/Tokyo"])
def test_frontend_time_is_independent_of_host_zone(timezone):
    node = shutil.which("node")
    assert node, "Node is required for operating time tests"
    subprocess.run(
        [node, str(Path(__file__).with_name("operating_time.mjs"))],
        env=os.environ | {"TZ": timezone},
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_report_dates_include_the_whole_operating_day(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "Asia/Shanghai") as client:
        seed_the_local_day_boundaries(client)
        response = client.post(
            "/api/reports",
            headers=auth(sign_in(client)),
            json={
                "period_start": "2026-11-02",
                "period_end": "2026-11-02",
                "basis": "raw",
            },
        )
        assert response.status_code == 200, response.text
        report = response.json()["data"]
        assert report["period_start"] == "2026-11-02T00:00:00.000+08:00"
        assert report["period_end"] == "2026-11-02T23:59:59.999+08:00"
        document = Path(report["file_path"]).read_text(encoding="utf-8")
        assert "2 帧" in document


def test_report_dates_respect_a_day_with_a_clock_change(monkeypatch):
    monkeypatch.setenv("AV_TIMEZONE", "America/New_York")
    get_settings.cache_clear()
    try:
        start, end = timebase.report_bounds(date(2026, 3, 8), date(2026, 3, 8))
        assert start == datetime(2026, 3, 8, 5)
        assert end == datetime(2026, 3, 9, 3, 59, 59, 999999)
    finally:
        get_settings.cache_clear()
