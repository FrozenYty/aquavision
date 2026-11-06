"""Database engine and the declarative base (P1-01).

The DSN comes from the DB_DSN environment variable — architecture §8 puts every
environment-dependent value in .env, read through pydantic-settings once P1-02
builds the settings module. Until then this module is the single place that
knows the variable's name; no path, port or DSN is hardcoded anywhere else.

Usage: engine_from_dsn("postgresql://...") or engine_from_dsn("sqlite:///path").
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase

DSN_ENV = "DB_DSN"

# A fallback for dev machines where neither --dsn nor DB_DSN is set, so the
# script runs out of the box. data/ is gitignored, so the file never reaches
# the repository. Production always sets DB_DSN.
DEFAULT_DSN = "sqlite:///data/app.db"


def dsn_from_env() -> str:
    """The configured DSN, or the dev default when the environment is silent."""
    return os.environ.get(DSN_ENV, DEFAULT_DSN)


def engine_from_dsn(dsn: str) -> Engine:
    """Build an engine.

    Pool settings stay at SQLAlchemy's defaults: the load is one team on one
    rig, and tuning a pool before there is traffic is guesswork.
    """
    return create_engine(dsn)


class Base(DeclarativeBase):
    """Shared declarative base; every table in the data model derives from it."""
