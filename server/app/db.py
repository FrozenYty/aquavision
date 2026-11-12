"""Database engine and the declarative base (P1-01).

The DSN comes from the DB_DSN environment variable — architecture §8 puts every
environment-dependent value in .env, read through pydantic-settings once P1-02
builds the settings module. Until then this module is the single place that
knows the variable's name; no path, port or DSN is hardcoded anywhere else.

Usage: engine_from_dsn("postgresql://...") or engine_from_dsn("sqlite:///path").
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.schema import MetaData

log = logging.getLogger("aquavision.db")

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


def add_missing_columns(
    engine: Engine, metadata: MetaData | None = None
) -> tuple[list[str], list[str]]:
    """Add the columns `create_all` cannot, so a populated database survives a schema change (P3-25).

    `create_all` issues `CREATE TABLE IF NOT EXISTS`: a new *table* appears on an existing database, a
    new **column** does not, and the application then fails every query that selects it - which is
    exactly what happened when `sys_user.token_epoch` was added, and every developer had to run the
    `ALTER TABLE` by hand.

    The rule this implements is deliberately narrow: **add, never rewrite**. A column the models
    declare and the table lacks is added with the default the model gives it; nothing is dropped,
    nothing is retyped, and no row is touched. A column the models no longer have stays where it is -
    an unused column costs a few bytes, a wrong `DROP` costs data.

    Returns `(added, refused)`, both as `table.column` strings. A column that is NOT NULL with no
    server default, or whose default the database rejects, lands in `refused` with the reason: it
    cannot be added to a table that already has rows, and saying so is better than a half-upgraded
    schema.
    """
    metadata = metadata if metadata is not None else Base.metadata
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    quote = engine.dialect.identifier_preparer.quote
    added: list[str] = []
    refused: list[str] = []

    for table in metadata.sorted_tables:
        if table.name not in existing_tables:
            # create_all has already built it in full.
            continue
        live = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            label = f"{table.name}.{column.name}"
            if column.name in live:
                continue
            default = str(column.server_default.arg) if column.server_default is not None else None
            if not column.nullable and default is None:
                refused.append(f"{label}: NOT NULL without a server default")
                continue
            statement = (
                f"ALTER TABLE {quote(table.name)} ADD COLUMN {quote(column.name)} "
                f"{column.type.compile(engine.dialect)}"
            )
            if default is not None:
                statement += f" DEFAULT {default}"
            if not column.nullable:
                statement += " NOT NULL"
            try:
                with engine.begin() as connection:
                    connection.execute(text(statement))
            except SQLAlchemyError as err:  # e.g. SQLite refuses a non-constant default
                refused.append(f"{label}: {type(err).__name__}: {err}")
                log.warning("could not add %s: %s", label, err)
            else:
                added.append(label)

    return added, refused
