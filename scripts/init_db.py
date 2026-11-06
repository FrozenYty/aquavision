"""Create the nine tables and seed the species dictionary (P1-01).

Acceptance (PLAN.md P1-01): the script runs on an empty database and four
classes are seeded. It is idempotent — safe to re-run on a database that
already has the tables and rows.

The DSN comes from --dsn, then the DB_DSN environment variable, then the dev
default (sqlite under data/, gitignored). Every path lives in configuration,
never in the code (architecture §8).

Usage: python scripts/init_db.py [--dsn postgresql://...]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The script runs from anywhere; the app package lives two levels up.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from app.db import Base, dsn_from_env, engine_from_dsn  # noqa: E402
from app.models import EXPECTED_COLUMNS, SpeciesDict  # noqa: E402
from app.seed import SPECIES_SEED, seed_species  # noqa: E402
from sqlalchemy import inspect, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


def init_db(dsn: str) -> None:
    """Create all tables and seed the species dictionary on the given database."""
    engine = engine_from_dsn(dsn)

    # The model is the DDL: create_all issues CREATE TABLE IF NOT EXISTS for
    # each of the nine tables, so an existing schema is left alone.
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        inserted = seed_species(session)

        # The acceptance check, run where the work happens: the dictionary must
        # hold the four classes, in labels.txt order, nothing more.
        rows = session.scalars(select(SpeciesDict).order_by(SpeciesDict.species_id)).all()
        codes = [row.class_code for row in rows]

    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    print(f"database: {engine.url.render_as_string(hide_password=True)}")
    print(f"tables ({len(tables)}): {', '.join(tables)}")
    print(f"species seeded: {inserted} new, {len(codes)} total")

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
    if problems:
        for problem in problems:
            print(f"  mismatch: {problem}", file=sys.stderr)
        raise SystemExit(1)

    print("OK: nine tables, four classes in labels.txt order")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=None,
        help="database DSN; defaults to $DB_DSN, then sqlite:///data/app.db",
    )
    args = parser.parse_args()
    init_db(args.dsn or dsn_from_env())


if __name__ == "__main__":
    main()
