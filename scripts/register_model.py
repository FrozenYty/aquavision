"""Register the exploratory baseline weights in `model_version` (P2-06c).

The training run writes `metrics.json` next to the weights; this script turns that file into a
`model_version` row. It can leave the row as a candidate (`--no-activate`) or make it the online
version; the activation rule is the same one the API route uses: exactly one online row.

Usage:
    python scripts/register_model.py
    python scripts/register_model.py --no-activate
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

        row.weight_path = str(weights)
        row.labels_path = str(labels)
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
        "--metrics",
        type=Path,
        default=Path("runs/detect/data/models/baseline-e0/metrics.json"),
    )
    parser.add_argument("--weights", type=Path, default=None)
    parser.add_argument("--labels", type=Path, default=Path("data/dataset/dataset.yaml"))
    parser.add_argument("--version-name", default="v8n-E0-exploratory")
    parser.add_argument("--dataset-ref", default="DUO-85:15-subset-1800")
    parser.add_argument("--no-activate", action="store_true")
    parser.add_argument("--dsn", default=None)
    args = parser.parse_args()

    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    weights = args.weights or Path(metrics["weights"])
    model_id = register_model(
        args.dsn or dsn_from_env(),
        version_name=args.version_name,
        weights=weights,
        labels=args.labels,
        dataset_ref=args.dataset_ref,
        metrics=metrics,
        activate=not args.no_activate,
    )
    print(f"model_version {model_id}: {args.version_name} -> {weights}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
