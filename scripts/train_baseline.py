"""Train the exploratory baseline on the DUO split (P2-06b).

The official E0–E4 experiments stay at P4 on the frozen dataset; this run is the exploratory
baseline that gives the dashboard real numbers. It samples a reproducible subset of the 5671/1000
split, trains YOLOv8n for 30 epochs, evaluates the best weights on the frozen 1111-image test set,
and writes every metric into `train_experiment`.

The subset lists and the data YAML live under data/, which is gitignored; the script and its tests
are the reproducible part. The run needs the CUDA training environment, not the CPU runtime
environment.

Usage:
    python scripts/train_baseline.py
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from app.db import Base, dsn_from_env, engine_from_dsn  # noqa: E402
from app.models import TrainExperiment  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

CLASS_CODES = ["holothurian", "strongylocentrotus", "chlamys", "asterias"]


def select_subset(images: list[Path], limit: int, seed: int) -> list[Path]:
    """Choose `limit` images deterministically; the result is sorted."""
    if limit >= len(images):
        return sorted(images)
    rng = random.Random(seed)
    return sorted(rng.sample(sorted(images), limit))


def write_data_yaml(
    path: Path,
    root: Path,
    train_images: list[Path],
    val_images: list[Path],
    test_dir: Path,
) -> Path:
    """Write the YOLO data file and the two image lists; return the data file's path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    train_list = path.parent / "baseline-train.txt"
    val_list = path.parent / "baseline-val.txt"
    train_list.write_text(
        "\n".join(p.resolve().as_posix() for p in train_images) + "\n", encoding="utf-8"
    )
    val_list.write_text(
        "\n".join(p.resolve().as_posix() for p in val_images) + "\n", encoding="utf-8"
    )
    names = "\n".join(f"  {index}: {code}" for index, code in enumerate(CLASS_CODES))
    path.write_text(
        f"path: {root.resolve().as_posix()}\n"
        f"train: {train_list.resolve().as_posix()}\n"
        f"val: {val_list.resolve().as_posix()}\n"
        f"test: {test_dir.resolve().as_posix()}\n"
        f"names:\n{names}\n",
        encoding="utf-8",
    )
    return path


def record_experiment(
    dsn: str,
    *,
    experiment: str,
    snapshot: str,
    split_ratio: str,
    seed: int,
    epochs: int,
    batch_size: int,
    lr: float,
    metrics: dict,
    note: str,
) -> int:
    """Insert one baseline row with every metric column filled; return its id."""
    engine = engine_from_dsn(dsn)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        row = TrainExperiment(
            exp_name=experiment,
            dataset_snapshot=snapshot,
            split_ratio=split_ratio,
            seed=seed,
            epochs=epochs,
            batch_size=batch_size,
            lr=lr,
            augment_json=json.dumps(
                {"imgsz": metrics.get("imgsz"), "optimizer": "auto"}, sort_keys=True
            ),
            map50=metrics["map50"],
            map50_95=metrics["map50_95"],
            recall_avg=metrics["recall_avg"],
            fps=metrics["fps"],
            params_m=metrics["params_m"],
            is_baseline=1,
            note=note,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.exp_id


def train_and_record(args: argparse.Namespace) -> dict:
    from ultralytics import YOLO

    dataset = Path(args.dataset)
    train_images = sorted((dataset / "train" / "images").glob("*.jpg"))
    val_images = sorted((dataset / "val" / "images").glob("*.jpg"))
    if not train_images or not val_images:
        raise SystemExit(f"no images under {dataset}/train or /val")

    train_subset = select_subset(train_images, args.train_limit, args.seed)
    val_subset = select_subset(val_images, args.val_limit, args.seed)
    data_yaml = write_data_yaml(
        Path(args.data), dataset, train_subset, val_subset, dataset / "test" / "images"
    )

    model = YOLO(args.model)
    model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        seed=args.seed,
        device=args.device,
        workers=args.workers,
        project=args.project,
        name=args.name,
        exist_ok=True,
        pretrained=True,
        patience=args.epochs,
        verbose=True,
    )

    best = Path(args.project) / args.name / "weights" / "best.pt"
    if best.exists():
        model = YOLO(str(best))
    metrics_obj = model.val(
        data=str(data_yaml),
        split="test",
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=f"{args.name}-test",
        exist_ok=True,
    )
    inference_ms = float(metrics_obj.speed.get("inference", 0.0))
    metrics = {
        "map50": float(metrics_obj.box.map50),
        "map50_95": float(metrics_obj.box.map),
        "recall_avg": float(metrics_obj.box.mr),
        "fps": 1000.0 / inference_ms if inference_ms else 0.0,
        "params_m": sum(p.numel() for p in model.model.parameters()) / 1_000_000,
        "inference_ms": inference_ms,
        "imgsz": args.imgsz,
        "train_images": len(train_subset),
        "val_images": len(val_subset),
        "test_images": len(list((dataset / "test" / "images").glob("*.jpg"))),
        "epochs": args.epochs,
        "batch_size": args.batch,
        "seed": args.seed,
        "weights": best.resolve().as_posix(),
    }
    run_dir = Path(args.project) / args.name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    note = (
        f"exploratory baseline; {len(train_subset)} train / {len(val_subset)} val; "
        "frozen test only for reporting; official E0-E4 stay at P4"
    )
    metrics["exp_id"] = record_experiment(
        args.dsn or dsn_from_env(),
        experiment=args.experiment,
        snapshot=args.snapshot,
        split_ratio=args.split_ratio,
        seed=args.seed,
        epochs=args.epochs,
        batch_size=args.batch,
        lr=args.lr0,
        metrics=metrics,
        note=note,
    )
    print(json.dumps(metrics, indent=2))
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/dataset"))
    parser.add_argument("--data", type=Path, default=Path("data/baseline.yaml"))
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--train-limit", type=int, default=1800)
    parser.add_argument("--val-limit", type=int, default=200)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lr0", type=float, default=0.01)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--project", type=Path, default=Path("data/models"))
    parser.add_argument("--name", default="baseline-e0")
    parser.add_argument("--experiment", default="E0-exploratory")
    parser.add_argument("--snapshot", default="DUO-85:15-subset-1800")
    parser.add_argument("--split-ratio", default="85:15")
    parser.add_argument("--dsn", default=None)
    args = parser.parse_args()
    train_and_record(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
