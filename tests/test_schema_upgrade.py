"""A schema change reaches a populated database without a wipe (P3-25, ADR 08).

`create_all` issues `CREATE TABLE IF NOT EXISTS`: a new *table* appears on an existing database, a new
**column** does not, and the application then fails every query that selects it. That is not a theory -
adding `sys_user.token_epoch` in `P3-20` made every development database on every machine answer
`no such column`, and the fix was a hand-written `ALTER TABLE` that nobody wrote down.

The previous schema is reconstructed by dropping the newest column, which is what the release before
the catch-up really had. The upgrade runs through the documented command - `scripts/init_db.py` - so
the test covers the route an operator takes, not just a helper.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.db import Base, add_missing_columns, engine_from_dsn
from app.models import SysLog, SysUser
from sqlalchemy import Column, Integer, MetaData, Table, inspect, select, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent.parent


def _previous_schema(path: Path) -> str:
    """A populated database as the release before this one left it: every table, one column short."""
    dsn = f"sqlite:///{path.as_posix()}"
    engine = engine_from_dsn(dsn)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        # SQLite has supported DROP COLUMN since 3.35; this is the previous release's shape.
        connection.execute(text("ALTER TABLE sys_user DROP COLUMN token_epoch"))
    # Raw SQL on purpose: the ORM knows the column this database does not have yet, and an INSERT
    # through the models is the very query that fails before the upgrade exists.
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO sys_user (username, phone, password_hash, salt, role_code, real_name,"
                " status, fail_count) VALUES ('old-account', '13800000007', 'unused', 'unused',"
                " 'analyst', 'Old Account', 1, 0)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO sys_log (module, action, target_type, target_id)"
                " VALUES ('auth', 'login', 'sys_user', '1')"
            )
        )
    engine.dispose()
    return dsn


def _run_init_db(dsn: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "init_db.py"), "--dsn", dsn],
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_column_added_to_the_models_reaches_a_populated_database(tmp_path: Path) -> None:
    dsn = _previous_schema(tmp_path / "old.db")

    engine = engine_from_dsn(dsn)
    assert "token_epoch" not in {
        column["name"] for column in inspect(engine).get_columns("sys_user")
    }
    engine.dispose()

    result = _run_init_db(dsn)
    assert result.returncode == 0, result.stderr
    assert "schema upgraded: sys_user.token_epoch" in result.stdout, result.stdout

    engine = engine_from_dsn(dsn)
    try:
        columns = {column["name"]: column for column in inspect(engine).get_columns("sys_user")}
        assert "token_epoch" in columns
        # The query the application makes is the real acceptance: it used to raise here.
        with Session(engine) as session:
            row = session.scalar(select(SysUser).where(SysUser.username == "old-account"))
            assert row is not None, "the upgrade lost the row"
            assert (row.phone, row.real_name, row.role_code, row.status) == (
                "13800000007",
                "Old Account",
                "analyst",
                1,
            )
            # The documented default applies to the row that existed before the column did.
            assert row.token_epoch == 0
            assert session.scalar(select(SysLog).where(SysLog.action == "login")) is not None
    finally:
        engine.dispose()

    # A second run changes nothing: the route is safe to repeat, which is what an operator needs.
    again = _run_init_db(dsn)
    assert again.returncode == 0, again.stderr
    assert "schema upgraded" not in again.stdout, again.stdout


def test_the_script_still_reports_a_schema_it_could_not_upgrade(tmp_path: Path) -> None:
    """A refusal is a failure, not a warning: the first query selecting the column would 500."""
    dsn = _previous_schema(tmp_path / "old.db")
    engine = engine_from_dsn(dsn)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE sys_user DROP COLUMN real_name"))
    engine.dispose()

    result = _run_init_db(dsn)
    assert result.returncode == 1, result.stdout
    assert "not upgraded: sys_user.real_name: NOT NULL without a server default" in result.stderr


def test_a_column_that_cannot_be_added_is_refused_rather_than_half_added(tmp_path: Path) -> None:
    """The rule is add-only: what SQL cannot do to a table with rows is named, not guessed at."""
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'probe.db').as_posix()}")
    metadata = MetaData()
    Table(
        "probe",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("with_default", Integer, nullable=False, server_default="0"),
        Column("needs_a_value", Integer, nullable=False),
    )
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE probe (id INTEGER PRIMARY KEY)"))

    added, refused = add_missing_columns(engine, metadata)
    assert added == ["probe.with_default"]
    assert refused == ["probe.needs_a_value: NOT NULL without a server default"]

    with engine.begin() as connection:
        names = [row[1] for row in connection.execute(text("PRAGMA table_info(probe)")).fetchall()]
    assert names == ["id", "with_default"], "nothing is added when the row set cannot take it"
    engine.dispose()
