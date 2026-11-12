"""A cached parameter belongs to the database it was read from (P3-19, ADR 15)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app import params
from app.db import Base, engine_from_dsn
from app.models import SysParam
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture(autouse=True)
def _clean_cache() -> Iterator[None]:
    params.forget()
    yield
    params.forget()


def _database(path: Path) -> sessionmaker:
    engine = engine_from_dsn(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _store(factory: sessionmaker, key: str, value: str) -> None:
    with Session(factory.kw["bind"]) as session:
        session.add(SysParam(param_key=key, param_value=value, value_type="int"))
        session.commit()


def test_two_databases_do_not_share_a_cached_value(tmp_path: Path) -> None:
    """No `forget()` between the reads: the point is that the cache cannot leak across databases."""
    first = _database(tmp_path / "first.db")
    second = _database(tmp_path / "second.db")
    _store(first, "max_concurrency", "1")
    _store(second, "max_concurrency", "7")

    assert params.effective(first, "max_concurrency") == 1
    assert params.effective(second, "max_concurrency") == 7
