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


def ensure_sqlite_directory(dsn: str) -> None:
    """Create the directory a file-backed SQLite database lives in, when it is missing.

    `data/` is git-ignored, so a fresh clone has none and SQLite refuses to create the database file
    itself: `sqlite3.OperationalError: unable to open database file`. Creating the parent here, where
    every caller builds its engine, makes the documented commands work from a clone as written.
    Only `sqlite:///` file DSNs are touched; `:memory:` and every server database are left alone.
    """
    prefix = "sqlite:///"
    if not dsn.startswith(prefix):
        return
    location = dsn[len(prefix) :]
    if not location or location.startswith(":memory:"):
        return
    parent = Path(location).parent
    if parent.exists():
        # A file where the directory should be is a broken path somebody may be probing on purpose:
        # leave it to SQLite, which reports it when the connection is opened.
        return
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Report what cannot be created through the connection error, not earlier and differently.
        return


def dsn_from_env() -> str:
    """The configured DSN, or the dev default when the environment is silent."""
    return resolve_dsn(os.environ.get(DSN_ENV, DEFAULT_DSN))


def engine_from_dsn(dsn: str) -> Engine:
    """Build an engine.

    SQLite connections are opened with check_same_thread=False because the detection worker uses the
    same engine from a background thread. Pool settings stay at SQLAlchemy's defaults: the load is one
    team on one rig, and tuning a pool before there is traffic is guesswork.

    A file-backed SQLite DSN gets its parent directory created first, so a clone without the
    git-ignored `data/` directory still starts.
    """
    ensure_sqlite_directory(dsn)
    connect_args = {"check_same_thread": False} if dsn.startswith("sqlite") else {}
    return create_engine(dsn, connect_args=connect_args)


class Base(DeclarativeBase):
    """Shared declarative base; every table in the data model derives from it."""


#: Columns a previous release created and the models no longer declare. **Dropping is deliberately not
#: automatic**: "the models do not mention it" is also what a rename looks like from the database's side,
#: and a wrong DROP costs data. Each entry here is a reviewed decision - table, column, and why - and it
#: is the only thing `drop_obsolete_columns` will ever remove.
OBSOLETE_COLUMNS: tuple[tuple[str, str, str], ...] = (
    (
        "media_asset",
        "turbidity_rel",
        "the capture request stopped sending it and no reader consumed it; every stored value was NULL",
    ),
)


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


def drop_obsolete_columns(
    engine: Engine, obsolete: tuple[tuple[str, str, str], ...] = OBSOLETE_COLUMNS
) -> tuple[list[str], list[str]]:
    """Drop the columns declared in `OBSOLETE_COLUMNS`, and nothing else.

    The pair to `add_missing_columns`, with the opposite default: that one acts on its own because
    adding a column cannot lose anything, and this one acts only on what a person wrote down and
    reviewed. `create_all` and the models give no signal that distinguishes "dropped on purpose" from
    "renamed by accident", so the list is the signal.

    Returns `(dropped, refused)` for the same reason the add path does: a column that cannot be
    dropped - an older SQLite without `ALTER TABLE ... DROP COLUMN`, or one an index still names -
    must stop the upgrade loudly rather than leave a schema half-migrated.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    quote = engine.dialect.identifier_preparer.quote
    dropped: list[str] = []
    refused: list[str] = []

    for table, column, reason in obsolete:
        if table not in existing_tables:
            continue
        if column not in {live["name"] for live in inspector.get_columns(table)}:
            continue
        try:
            with engine.begin() as connection:
                connection.execute(text(f"ALTER TABLE {quote(table)} DROP COLUMN {quote(column)}"))
        except SQLAlchemyError as err:
            refused.append(f"{table}.{column}: {type(err).__name__}: {err}")
            log.warning("could not drop %s.%s: %s", table, column, err)
        else:
            dropped.append(f"{table}.{column} ({reason})")
            log.info("dropped %s.%s: %s", table, column, reason)

    return dropped, refused
