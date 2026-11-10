"""Database engine and the declarative base (P1-01).

The DSN comes from the DB_DSN environment variable — architecture §8 puts every
environment-dependent value in .env, read through pydantic-settings once P1-02
builds the settings module. Until then this module is the single place that
knows the variable's name; no path, port or DSN is hardcoded anywhere else.

Usage: engine_from_dsn("postgresql://...") or engine_from_dsn("sqlite:///path").
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase

DSN_ENV = "DB_DSN"

# A fallback for dev machines where neither --dsn nor DB_DSN is set, so the
# script runs out of the box. data/ is gitignored, so the file never reaches
# the repository. Production always sets DB_DSN.
DEFAULT_DSN = "sqlite:///data/app.db"


#: The repository root, used to anchor a relative SQLite path.
#:
#: A relative `sqlite:///data/app.db` is resolved against the process working directory, so `init_db` run
#: from the root and `uvicorn` run from `server/` would build two different files - and the server would
#: start happily against an empty one, answering health checks while every query returned 500. Anchoring
#: here makes the path a property of the repository rather than of where a shell happened to be.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_dsn(dsn: str) -> str:
    """Turn a relative SQLite DSN into an absolute one; leave every other DSN alone."""
    prefix = "sqlite:///"
    if not dsn.startswith(prefix):
        return dsn
    path = Path(dsn[len(prefix) :])
    if path.is_absolute():
        return dsn
    return f"{prefix}{(PROJECT_ROOT / path).as_posix()}"


def dsn_from_env() -> str:
    """The configured DSN, or the dev default when the environment is silent."""
    return resolve_dsn(os.environ.get(DSN_ENV, DEFAULT_DSN))


def engine_from_dsn(dsn: str) -> Engine:
    """Build an engine.

    SQLite connections are opened with check_same_thread=False because the detection worker uses the
    same engine from a background thread. Pool settings stay at SQLAlchemy's defaults: the load is one
    team on one rig, and tuning a pool before there is traffic is guesswork.
    """
    connect_args = {"check_same_thread": False} if dsn.startswith("sqlite") else {}
    return create_engine(dsn, connect_args=connect_args)


class Base(DeclarativeBase):
    """Shared declarative base; every table in the data model derives from it."""
