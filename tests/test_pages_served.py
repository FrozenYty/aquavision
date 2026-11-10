"""The backend serves the pages as well as the API (P2-19).

Why this exists: until this change the FastAPI process mounted routers only, the pages were served by a
separate ``python -m http.server``, and every ``/api`` call from a page went to that other port and came
back as "interface not found". A proxy was assumed and never committed. This test is what keeps one
origin true - without it, a refactor that drops the mount would look like a frontend bug for a week.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base, engine_from_dsn


@pytest.fixture
def client(tmp_path, monkeypatch):
    """An app over a throwaway database, built the same way `test_api_skeleton.py` builds it."""
    dsn = f"sqlite:///{(tmp_path / 'pages.db').as_posix()}"
    monkeypatch.setenv("DB_DSN", dsn)
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    get_settings.cache_clear()

    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()
    engine = engine_from_dsn(dsn)
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_root_redirects_to_the_sign_in_page(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/templates/login.html"


def test_the_sign_in_page_is_served(client):
    response = client.get("/templates/login.html")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>" in response.text


def test_static_assets_are_served(client):
    for path in ("/static/css/app.css", "/static/css/tokens.css", "/static/js/api.js"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert len(response.text) > 500, path


def test_the_api_still_wins_over_the_catch_all_mount(client):
    """The static mount is registered last, so every /api route must answer before it."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["data"]["database"] == "ok"
