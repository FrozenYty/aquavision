"""Register a model version in `model_version` (P2-06c, P2-06d).

A delivered version is a directory under `models/` holding `best.pt`, `labels.txt` and
`metrics.json` (ADR 13), and that directory is what the positional argument names — with one
delivered version present, running the script with no argument registers it. The flag form
(`--metrics`, `--weights`) stays for a training run whose files are still under `runs/`.

The weight and label paths are stored relative to the repository root whenever the file is inside
it, because ADR 13 makes that column portable: the row is read on whichever machine serves the
database, and an absolute path would silently work on only the one that wrote it.

Usage:
    python scripts/register_model.py [models/<version_name>]
    python scripts/register_model.py [models/<version_name>] --no-activate
    python scripts/register_model.py --metrics runs/.../metrics.json --weights runs/.../best.pt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from app.db import Base, dsn_from_env, engine_from_dsn  # noqa: E402
from app.models import ModelVersion  # noqa: E402
from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

#: SRS section 4 delivers these together, and ADR 13 tracks exactly these three.
DELIVERED_FILES = ("best.pt", "labels.txt", "metrics.json")

#: The exploratory baseline's subset; a delivered `metrics.json` may name its own.
DEFAULT_DATASET_REF = "DUO-85:15-subset-1800"


def portable_path(path: Path) -> str:
    """A file inside the repository is stored relative to its root; anything else as it was given."""
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def delivered_versions(models_dir: Path | None = None) -> list[Path]:
    """The directories under `models/` that hold all three delivered artefacts, in name order."""
    root = models_dir or REPO / "models"
    if not root.is_dir():
        return []
    return [
        entry
        for entry in sorted(root.iterdir())
        if entry.is_dir() and all((entry / name).is_file() for name in DELIVERED_FILES)
    ]


def register_delivered(dsn: str, version_dir: Path, *, activate: bool = True) -> int:
    """Register one delivered directory; the directory's name is the version name."""
    metrics = json.loads((version_dir / "metrics.json").read_text(encoding="utf-8"))
    return register_model(
        dsn,
        version_name=version_dir.name,
        weights=version_dir / "best.pt",
        labels=version_dir / "labels.txt",
        dataset_ref=str(metrics.get("dataset_ref", DEFAULT_DATASET_REF)),
        metrics=metrics,
        activate=activate,
    )


def register_model(
    dsn: str,
    *,
    version_name: str,
    weights: Path,
    labels: Path,
    dataset_ref: str,
    metrics: dict,
    activate: bool = True,
) -> int:
    """Insert or update one model row; when `activate`, make it the only online row."""
    engine = engine_from_dsn(dsn)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        row = session.scalar(select(ModelVersion).where(ModelVersion.version_name == version_name))
        if row is None:
            row = ModelVersion(version_name=version_name)
            session.add(row)

        row.weight_path = portable_path(weights)
        row.labels_path = portable_path(labels)
        row.dataset_ref = dataset_ref
        row.map50 = float(metrics["map50"])
        row.map50_95 = float(metrics["map50_95"])
        row.recall_avg = float(metrics["recall_avg"])
        row.fps = float(metrics["fps"])
        row.params_m = float(metrics["params_m"])

        if activate:
            session.flush()  # assign model_id for a new row before excluding it
            session.execute(
                update(ModelVersion)
                .where(ModelVersion.model_id != row.model_id)
                .values(is_online=0, status=2)
            )
            row.is_online = 1
            row.status = 1
        elif row.model_id is None:
            row.is_online = 0
            row.status = 0

        session.commit()
        session.refresh(row)
        return row.model_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "version_dir",
        nargs="?",
        type=Path,
        default=None,
        help="a delivered version directory; defaults to the only one under models/",
    )
    parser.add_argument("--metrics", type=Path, default=None, help="a training run's metrics.json")
    parser.add_argument("--weights", type=Path, default=None)
    parser.add_argument("--labels", type=Path, default=Path("data/dataset/dataset.yaml"))
    parser.add_argument("--version-name", default="v8n-E0-exploratory")
    parser.add_argument("--dataset-ref", default=DEFAULT_DATASET_REF)
    parser.add_argument("--no-activate", action="store_true")
    parser.add_argument("--dsn", default=None)
    args = parser.parse_args()

    dsn = args.dsn or dsn_from_env()
    target = args.version_dir
    if target is None and args.metrics is None:
        delivered = delivered_versions()
        if len(delivered) != 1:
            present = ", ".join(version.name for version in delivered) or "none"
            parser.error(f"name a version directory; models/ holds {present}")
        target = delivered[0]

    if target is not None:
        if args.metrics is not None:
            parser.error("pass either a version directory or --metrics, not both")
        model_id = register_delivered(dsn, target, activate=not args.no_activate)
        print(f"model_version {model_id}: {target.name} -> {portable_path(target / 'best.pt')}")
        return 0

    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    weights = args.weights or Path(metrics["weights"])
    model_id = register_model(
        dsn,
        version_name=args.version_name,
        weights=weights,
        labels=args.labels,
        dataset_ref=args.dataset_ref,
        metrics=metrics,
        activate=not args.no_activate,
    )
    print(f"model_version {model_id}: {args.version_name} -> {portable_path(weights)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
