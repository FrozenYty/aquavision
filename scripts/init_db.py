"""Create the fourteen tables, seed the species dictionary and the first account (P1-01),
and register the delivered model under `models/` (P2-06d).

Acceptance (PLAN.md P1-01): the script runs on an empty database, four classes are
seeded, and an operator can log in afterwards. It is idempotent — safe to re-run on a
database that already has the tables and rows; the account is created only when
there is none, so a changed password is never overwritten.

The model registration exists because `models/` is tracked and `data/app.db` is not: a clone has
the weights but no row naming them, so detection would answer 501 with the file sitting right
there. Every delivered version is registered; one goes online only on a fresh database and only
when it is the only one delivered, so re-running this script never overrides an operator's choice.

The DSN comes from --dsn, then the DB_DSN environment variable, then the dev
default (sqlite under data/, gitignored). Every path lives in configuration,
never in the code (architecture §8).

Usage: python scripts/init_db.py [--dsn postgresql://...]
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

# The script runs from anywhere; the app package lives two levels up.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
# And this file's own directory, for the registration logic it shares with register_model.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import register_model  # noqa: E402
from app.db import Base, add_missing_columns, dsn_from_env, engine_from_dsn  # noqa: E402
from app.models import EXPECTED_COLUMNS, ModelVersion, SpeciesDict, SysUser  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.seed import SPECIES_SEED, seed_species  # noqa: E402
from sqlalchemy import inspect, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


def ensure_first_account(session: Session, password: str | None) -> str | None:
    """Create an administrator when the table is empty, and return the password used.

    Without this the schema is correct and nobody can log in: `init_db` seeded species only, and the
    login query simply found no row, so the panel answered "wrong account or password" forever. The
    password comes from `--admin-password`, then `AV_ADMIN_PASSWORD`, and otherwise a random one that is
    printed once - a known default password on a repository this public is a worse answer than a long
    random string the operator copies from their own terminal.
    """
    if session.scalar(select(SysUser.user_id).limit(1)) is not None:
        return None

    chosen = password or os.environ.get("AV_ADMIN_PASSWORD") or secrets.token_urlsafe(12)
    hashed, salt = hash_password(chosen)
    session.add(
        SysUser(
            username="admin",
            password_hash=hashed,
            salt=salt,
            role_code="admin",
            real_name="Administrator",
            status=1,
            fail_count=0,
        )
    )
    session.commit()
    return chosen


def register_delivered_versions(dsn: str) -> list[tuple[str, str, bool]]:
    """Register the delivered versions under `models/`; return (name, weight path, online) rows.

    The activation rule is the API route's, with one restraint added for a script that is re-run:
    a version goes online only when no version is online yet and only when it is the only one
    delivered. With several delivered versions on a database that already serves one, the operator
    keeps the choice, and a fresh row stays a candidate (P3-03).
    """
    versions = register_model.delivered_versions()
    if not versions:
        return []

    engine = engine_from_dsn(dsn)
    try:
        with Session(engine) as session:
            online = (
                session.scalar(select(ModelVersion.model_id).where(ModelVersion.is_online == 1))
                is not None
            )
    finally:
        engine.dispose()

    activate = len(versions) == 1 and not online
    registered = []
    for version_dir in versions:
        register_model.register_delivered(dsn, version_dir, activate=activate)
        registered.append(
            (version_dir.name, register_model.portable_path(version_dir / "best.pt"), activate)
        )
    return registered


def init_db(dsn: str, admin_password: str | None = None) -> None:
    """Create all tables and seed the species dictionary on the given database."""
    engine = engine_from_dsn(dsn)

    # The model is the DDL: create_all issues CREATE TABLE IF NOT EXISTS for
    # each of the fourteen tables. A *table* that is missing appears here; a **column** the models
    # gained does not, and every query selecting it would fail with "no such column" (P3-25), so the
    # missing columns are added next, in place, without touching a row.
    Base.metadata.create_all(engine)
    added, refused = add_missing_columns(engine)

    with Session(engine) as session:
        inserted = seed_species(session)
        first_password = ensure_first_account(session, admin_password)

        # The acceptance check, run where the work happens: the dictionary must
        # hold the four classes, in labels.txt order, nothing more.
        rows = session.scalars(select(SpeciesDict).order_by(SpeciesDict.species_id)).all()
        codes = [row.class_code for row in rows]

    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    print(f"database: {engine.url.render_as_string(hide_password=True)}")
    print(f"tables ({len(tables)}): {', '.join(tables)}")
    print(f"species seeded: {inserted} new, {len(codes)} total")
    if added:
        print(f"schema upgraded: {', '.join(added)} (existing rows kept)")
    if refused:
        for problem in refused:
            print(f"  not upgraded: {problem}", file=sys.stderr)
    model_versions = register_delivered_versions(dsn)
    for name, path, online in model_versions:
        print(f"model version: {name} -> {path} ({'online' if online else 'candidate'})")
    if model_versions and not any(online for _name, _path, online in model_versions):
        print("no model version is online: activate one with scripts/register_model.py <directory>")
    if first_password is not None:
        print()
        print("first account created - write this down, it is not printed again")
        print("  username: admin")
        print(f"  password: {first_password}")
        print()

    expected = [str(row["class_code"]) for row in SPECIES_SEED]
    problems = []
    if codes != expected:
        problems.append(f"species order is {codes}, expected {expected}")
    for table, count in EXPECTED_COLUMNS.items():
        if table not in tables:
            problems.append(f"table {table} missing")
            continue
        actual = len(inspector.get_columns(table))
        if actual != count:
            problems.append(f"{table} has {actual} columns, the dictionary says {count}")
    problems.extend(refused)
    if problems:
        for problem in problems:
            print(f"  mismatch: {problem}", file=sys.stderr)
        raise SystemExit(1)

    print("OK: fourteen tables, four classes in labels.txt order, an account to log in with")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=None,
        help="database DSN; defaults to $DB_DSN, then sqlite:///data/app.db",
    )
    parser.add_argument(
        "--admin-password",
        default=None,
        help="password for the first account; defaults to $AV_ADMIN_PASSWORD, then a random one",
    )
    args = parser.parse_args()
    init_db(args.dsn or dsn_from_env(), args.admin_password)


if __name__ == "__main__":
    main()
