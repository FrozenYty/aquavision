"""Restore drill for the SQLite development database (P4-17, runbook section 5).

The runbook says how to back up and restore; this command is that page executed. It takes a
consistent copy of the database (`VACUUM INTO`, not a file copy), opens both the source and the copy
read-only, and proves they answer the same: the row counts of `sys_user`, `detect_object` and
`detect_task`, and the totals `/api/stats` computes. One line per comparison, then `PASS` or `FAIL`.

The source is opened through a `file:...?mode=ro` URI, so a drill cannot damage what it proves. The
copy is written under the data root by default (`data/drill/app-backup.db`); an existing copy is
refused unless `--force`, and nothing outside that scratch path is ever deleted.

A PostgreSQL deployment is **not covered**: when `DB_DSN` does not name a SQLite file the command
says so and exits without pretending to pass. The frame archive is the other half of a restore and
is copied separately, as runbook section 5 says.

Usage:
    python scripts/drill_restore.py
    python scripts/drill_restore.py --source data/app.db --scratch data/drill/backup.db --force
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

# The script runs from anywhere; the app package lives two levels up.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from app.config import get_settings  # noqa: E402
from app.db import PROJECT_ROOT, dsn_from_env  # noqa: E402
from app.models import DetectObject, DetectTask, SysUser  # noqa: E402
from app.routers import stats  # noqa: E402
from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

#: The row counts the drill compares. These are the tables `/api/stats` reads; a restore that loses
#: a row of any of them is not a restore, whatever the other figures say.
ROW_TABLES: tuple[tuple[str, type], ...] = (
    ("sys_user", SysUser),
    ("detect_object", DetectObject),
    ("detect_task", DetectTask),
)

#: The window the `/api/stats` pages ask for by default. The handler signature defaults are `Query`
#: objects, not values, so a direct call must pass the values the route would have passed.
STATS_DAYS = 7


@dataclass(frozen=True)
class Figure:
    """One figure compared, both values kept so a difference names itself."""

    label: str
    source: int
    restored: int

    @property
    def same(self) -> bool:
        return self.source == self.restored


@dataclass(frozen=True)
class Report:
    """What one comparison found; the command prints it and the tests read it."""

    source: Path
    scratch: Path
    figures: list[Figure]

    @property
    def ok(self) -> bool:
        return all(figure.same for figure in self.figures)

    @property
    def differences(self) -> list[Figure]:
        return [figure for figure in self.figures if not figure.same]


def read_only_uri(path: Path) -> str:
    """The URI a database is opened through; `mode=ro` is the promise that it cannot be written."""
    return f"{path.resolve().as_uri()}?mode=ro"


def _read_only_engine(path: Path) -> Engine:
    """An engine over `path` whose every connection is read-only.

    `create_engine("sqlite://")` with a creator is deliberate: the query-string form
    `sqlite:///file:...?mode=ro&uri=true` has to be assembled differently for a path with spaces,
    while the SQLite URI built here already carries the mode and the encoding.
    """
    uri = read_only_uri(path)
    return create_engine(
        "sqlite://", creator=lambda: sqlite3.connect(uri, uri=True), poolclass=StaticPool
    )


def take_backup(source: Path, scratch: Path) -> None:
    """Write a consistent copy of `source` to `scratch`, as runbook section 5 prescribes.

    `VACUUM INTO` is the runbook's form: it writes a transaction-consistent snapshot rather than the
    pages a file copy could capture while the service is writing. It reads through the read-only
    URI, so the drill cannot modify the database it is proving. `scratch` must not exist yet;
    `VACUUM INTO` refuses to overwrite, which is the second half of that guarantee.
    """
    scratch.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(read_only_uri(source), uri=True)
    try:
        connection.execute("VACUUM INTO ?", (str(scratch),))
    finally:
        connection.close()


def _row_counts(session: Session) -> dict[str, int]:
    return {
        label: session.scalar(select(func.count()).select_from(model)) or 0
        for label, model in ROW_TABLES
    }


def stats_totals(session: Session) -> dict[str, int]:
    """The `/api/stats` totals, computed by the route functions themselves.

    The handlers are called with a session and the values the pages pass, so this compares the
    API's own computation and nothing here re-spells an aggregate: a change to a route changes the
    drill with it. `trend` is not a total - it is per-day buckets - and is left to `/api/stats`
    callers rather than repeated here.
    """
    reviewed = stats.species_composition(session, basis="reviewed", days=STATS_DAYS)["data"]
    raw = stats.species_composition(session, basis="raw", days=STATS_DAYS)["data"]
    quality = stats.quality_rejection(session, days=STATS_DAYS)["data"]
    corrections = stats.corrections(session, days=STATS_DAYS)["data"]
    return {
        "/api/stats/species total (reviewed)": reviewed["total"],
        "/api/stats/species total (raw)": raw["total"],
        "/api/stats/quality total": quality["total"],
        "/api/stats/corrections total": corrections["total"],
    }


def compare(source: Path, scratch: Path) -> Report:
    """Open the source and the restored copy read-only and compare every figure."""
    source_engine = _read_only_engine(source)
    scratch_engine = _read_only_engine(scratch)
    try:
        with Session(source_engine) as source_session, Session(scratch_engine) as scratch_session:
            source_rows = _row_counts(source_session)
            restored_rows = _row_counts(scratch_session)
            source_stats = stats_totals(source_session)
            restored_stats = stats_totals(scratch_session)
    finally:
        source_engine.dispose()
        scratch_engine.dispose()

    figures = [
        Figure(label, source_rows[label], restored_rows[label]) for label, _model in ROW_TABLES
    ]
    figures += [Figure(label, source_stats[label], restored_stats[label]) for label in source_stats]
    return Report(source=source, scratch=scratch, figures=figures)


def print_report(report: Report) -> None:
    """One line per comparison, then the verdict."""
    print(f"drill restore: {report.source} -> {report.scratch}")
    print("backup: VACUUM INTO (consistent copy; the source was opened read-only)")
    for figure in report.figures:
        if figure.same:
            print(f"  {figure.label}: {figure.source} = {figure.restored}")
        else:
            print(f"  {figure.label}: source {figure.source} != restored {figure.restored}")
    print("PASS" if report.ok else "FAIL")


def sqlite_file_from_dsn(dsn: str) -> Path | None:
    """The SQLite file `dsn` names, or None when it names anything else.

    `dsn_from_env` has already anchored a relative default to the repository root, so this only
    strips the prefix; an in-memory database is not a file and is as uncovered as PostgreSQL.
    """
    prefix = "sqlite:///"
    if not dsn.startswith(prefix):
        return None
    path = Path(dsn[len(prefix) :])
    if path.name == ":memory:":
        return None
    return path


def _data_root() -> Path:
    """The data root, anchored the way `db.py` anchors a relative SQLite path."""
    root = Path(get_settings().data_dir)
    return root if root.is_absolute() else PROJECT_ROOT / root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Back up the SQLite database and prove the copy restores to the same totals"
    )
    parser.add_argument(
        "--source",
        default=None,
        help="SQLite database to drill; defaults to the file DB_DSN names, then data/app.db",
    )
    parser.add_argument(
        "--scratch",
        default=None,
        help="scratch copy to write; defaults to <data root>/drill/app-backup.db",
    )
    parser.add_argument("--force", action="store_true", help="overwrite an existing scratch copy")
    args = parser.parse_args(argv)

    if args.source:
        source = Path(args.source)
    else:
        configured = sqlite_file_from_dsn(dsn_from_env())
        if configured is None:
            print(
                "drill restore: not covered - this drill drills the SQLite development database "
                "only, and the configured DB_DSN is not a SQLite file, so PostgreSQL is not "
                "covered and nothing was proved",
                file=sys.stderr,
            )
            return 3
        source = configured
    if not source.is_file():
        print(f"drill restore: no database at {source}", file=sys.stderr)
        return 2

    scratch = Path(args.scratch) if args.scratch else _data_root() / "drill" / "app-backup.db"
    if scratch.resolve() == source.resolve():
        print("drill restore: the scratch copy must not be the source database", file=sys.stderr)
        return 2
    if scratch.is_dir():
        print(f"drill restore: the scratch path is a directory: {scratch}", file=sys.stderr)
        return 2
    if scratch.exists():
        if not args.force:
            print(
                f"drill restore: {scratch} already exists; pass --force to overwrite it",
                file=sys.stderr,
            )
            return 2
        scratch.unlink()

    try:
        take_backup(source, scratch)
        report = compare(source, scratch)
    except (OSError, sqlite3.Error, SQLAlchemyError) as err:
        print(f"drill restore: {type(err).__name__}: {err}", file=sys.stderr)
        return 2

    print_report(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
