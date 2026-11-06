"""Training experiments and the baseline comparison (FR-M6-03, AC-25).

The list is real: `train_experiment` records what was run, with which snapshot and which metrics, and
the comparison table is a projection of those rows. The per-frame comparison answers 501 — it needs
two loaded models and a frame that both were run on, and neither exists yet.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app import serializers
from app.deps import SessionDep, get_current_user
from app.envelope import not_built, ok
from app.models import TrainExperiment

router = APIRouter(prefix="/api", tags=["models"], dependencies=[Depends(get_current_user)])


@router.get("/experiments")
def list_experiments(db: SessionDep) -> dict[str, object]:
    rows = db.scalars(select(TrainExperiment).order_by(TrainExperiment.exp_id)).all()
    baseline = next((row for row in rows if row.is_baseline), None)
    base_map = float(baseline.map50) if baseline and baseline.map50 is not None else None

    items = []
    for row in rows:
        map50 = float(row.map50) if row.map50 is not None else None
        items.append(
            {
                "exp_id": row.exp_id,
                "exp_name": row.exp_name,
                "dataset_snapshot": row.dataset_snapshot,
                "split_ratio": row.split_ratio,
                "seed": row.seed,
                "epochs": row.epochs,
                "map50": map50,
                "map50_95": float(row.map50_95) if row.map50_95 is not None else None,
                "recall_avg": float(row.recall_avg) if row.recall_avg is not None else None,
                "fps": float(row.fps) if row.fps is not None else None,
                "is_baseline": bool(row.is_baseline),
                # The delta against the baseline is what the comparison table is for; computed here
                # so the frontend never has to guess which row is the reference.
                "delta_map50": round(map50 - base_map, 4)
                if map50 is not None and base_map
                else None,
                "created_at": serializers.iso(row.created_at),
            }
        )
    return ok(
        {"items": items, "baseline": baseline.exp_name if baseline else None, "total": len(items)}
    )


@router.post("/compare/frames/{frame_id}")
def compare_frame(frame_id: str) -> dict[str, object]:
    raise not_built(f"同帧对比 {frame_id}（等待两个模型版本同时可加载）")
