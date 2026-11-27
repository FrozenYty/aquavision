"""Retention cleanup for the data root (P3-08, FR-M2-05, AC-09).

Two kinds of file are intermediate, and both are cleanup candidates once their mtime is older than
`retention_days`:

- a thumbnail a `media_asset` row still points at through `thumb_path`. The file and the reference are
  removed together, or the row would point at a file that is gone;
- a scratch frame `/ws/capture` wrote under `frames/live/` and a killed process never removed. No row
  ever names one, so there is no reference to null.

**Originals are never deleted.** `media_asset.file_path` names the captured frame; every file it names
survives this script, and no option removes one - `docs/data-model-en.md` section 6 and FR-M2-05 both say
originals are not auto-deleted, and the column is NOT NULL, so the database cannot describe a frame
without a file.

The default is a dry run that prints the cleanup list, because a deleted intermediate cannot be rebuilt:
read it, then pass `--apply`. The cutoff is calendar arithmetic in `AV_TIMEZONE` (ADR 14), and
`retention_days` is read when the run starts - the `sys_param` value when a row exists, otherwise
`AV_RETENTION_DAYS` (ADR 15).

    python scripts/cleanup_retention.py
    python scripts/cleanup_retention.py --apply
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

# The script runs from anywhere; the app package lives two levels up.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from app import timebase  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import dsn_from_env, engine_from_dsn  # noqa: E402
from app.models import MediaAsset  # noqa: E402
from app.params import effective  # noqa: E402
from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

#: Where the live socket writes its scratch frame; `live.py` deletes it after each inference, and a
#: killed process does not. It is a pseudo-site no capture session uses.
LIVE_SCRATCH = Path("frames") / "live"


@dataclass
class Report:
    """What one run did, or would do; the command prints it and the tests read it."""

    cutoff: datetime
    retention_days: int
    deleted: list[tuple[str, int]] = field(default_factory=list)
    nulled: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    dry_run: bool = True

    @property
    def freed_bytes(self) -> int:
        return sum(size for _relative, size in self.deleted)


def _inside(root: Path, path: Path) -> bool:
    """True when `path` resolves under the data root; a row cannot name a file outside it."""
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _older_than(path: Path, cutoff_timestamp: float) -> bool:
    try:
        return path.stat().st_mtime < cutoff_timestamp
    except OSError:
        return False


def _human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"


def cleanup(
    data_root: str | Path,
    session_factory: sessionmaker,
    retention_days: int,
    *,
    apply: bool = False,
    now: datetime | None = None,
) -> Report:
    """Build the cleanup list and, with `apply`, carry it out."""
    root = Path(data_root)
    cutoff = (now or timebase.now()) - timedelta(days=retention_days)
    report = Report(cutoff=cutoff, retention_days=retention_days, dry_run=not apply)

    with session_factory() as session:
        rows = session.execute(
            select(MediaAsset.asset_id, MediaAsset.thumb_path).where(
                MediaAsset.thumb_path.is_not(None)
            )
        ).all()

    null_asset_ids: list[int] = []
    for asset_id, thumb_path in rows:
        path = root / thumb_path
        if not _inside(root, path):
            report.skipped.append(f"{thumb_path} (outside the data root)")
            continue
        if not path.exists():
            # The file is already gone; the stale reference is what is left to clean.
            report.nulled.append(thumb_path)
            null_asset_ids.append(asset_id)
            continue
        if not _older_than(path, cutoff.timestamp()):
            report.kept.append(thumb_path)
            continue
        size = path.stat().st_size
        if apply:
            try:
                path.unlink()
            except OSError as err:
                report.failed.append((thumb_path, f"{type(err).__name__}: {err}"))
                continue
            null_asset_ids.append(asset_id)
        else:
            report.nulled.append(thumb_path)
        report.deleted.append((thumb_path, size))

    scratch = root / LIVE_SCRATCH
    if scratch.is_dir():
        for path in sorted(scratch.glob("*.jpg")):
            if not _older_than(path, cutoff.timestamp()):
                continue
            size = path.stat().st_size
            relative = path.relative_to(root).as_posix()
            if apply:
                try:
                    path.unlink()
                except OSError as err:
                    report.failed.append((relative, f"{type(err).__name__}: {err}"))
                    continue
            report.deleted.append((relative, size))

    if apply and null_asset_ids:
        with session_factory() as session:
            session.execute(
                update(MediaAsset)
                .where(MediaAsset.asset_id.in_(null_asset_ids))
                .values(thumb_path=None)
            )
            session.commit()

    return report


def print_report(report: Report, data_root: Path) -> None:
    """The operator's cleanup list: one line per file, then the totals."""
    mode = "dry run - nothing is changed (pass --apply to delete)" if report.dry_run else "apply"
    print(f"cleanup: {mode}")
    print(f"data root: {data_root}")
    print(f"retention: {report.retention_days} days, cutoff {timebase.iso(report.cutoff)}")

    verb = "would delete" if report.dry_run else "deleted"
    for relative, size in report.deleted:
        print(f"  {verb}: {relative} ({_human(size)})")
    null_verb = "would null" if report.dry_run else "nulled"
    for relative in report.nulled:
        print(f"  {null_verb}: media_asset.thumb_path = {relative}")
    for relative in report.kept:
        print(f"  kept (younger than the cutoff): {relative}")
    for relative in report.skipped:
        print(f"  skipped: {relative}", file=sys.stderr)
    for relative, reason in report.failed:
        print(f"  could not delete: {relative} ({reason})", file=sys.stderr)

    print(f"{verb}: {len(report.deleted)} file(s), {_human(report.freed_bytes)}")
    print(f"{null_verb}: {len(report.nulled)} reference(s)")
    if report.failed:
        print(f"failed: {len(report.failed)} file(s)", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Remove intermediate files older than retention_days"
    )
    parser.add_argument(
        "--apply", action="store_true", help="delete the files and null the references"
    )
    parser.add_argument(
        "--data-dir", default=None, help="data root; defaults to AV_DATA_DIR, then data/"
    )
    parser.add_argument(
        "--dsn", default=None, help="database DSN; defaults to $DB_DSN, then sqlite:///data/app.db"
    )
    parser.add_argument(
        "--retention-days", type=int, default=None, help="override retention_days for this run"
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    data_root = Path(args.data_dir or settings.data_dir)
    if not data_root.is_dir():
        print(f"data root does not exist: {data_root}", file=sys.stderr)
        return 2

    engine = engine_from_dsn(args.dsn or dsn_from_env())
    factory = sessionmaker(bind=engine)
    try:
        days = (
            args.retention_days
            if args.retention_days is not None
            else effective(factory, "retention_days", settings)
        )
        if days < 1:
            print("retention days must be at least 1", file=sys.stderr)
            return 2
        report = cleanup(data_root, factory, days, apply=args.apply)
    finally:
        engine.dispose()

    print_report(report, data_root)
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
