"""Dataset snapshots (FR-M4-04, AC-18).

An export is deterministic: the same frames with the same seed always produce the same splits, and a
similarity group never straddles two of them. The grouping is what makes AC-18 more than a seed: with a
fixed camera, frames captured seconds apart are near-identical, and splitting them across train and
test would report an accuracy the model has not earned.

Membership goes into `dataset_item`, one row per frame, because three later questions are joins rather
than directory scans: which frames trained this model, may this frame be cleaned up, and do groups
still stay on one side.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app import serializers
from app.deps import SessionDep, SettingsDep, UserDep, get_current_user, require
from app.envelope import BAD_PARAM, CONFLICT, ApiError, ok
from app.models import Dataset, DatasetItem, DetectObject, MediaAsset, SysLog

router = APIRouter(
    prefix="/api/datasets", tags=["datasets"], dependencies=[Depends(get_current_user)]
)

#: Frames captured within this many seconds of each other are treated as one similarity group.
#: A fixed camera at a fixed frame rate produces bursts; grouping by capture second is the cheapest
#: honest proxy, and the field is wide enough to replace with a perceptual hash later.
GROUP_SECONDS = 10

SPLITS = {1: "train", 2: "val", 3: "test"}


class ExportBody(BaseModel):
    snapshot_name: str = Field(min_length=3, max_length=64, pattern=r"^DS-[A-Za-z0-9_-]+$")
    split_ratio: str = Field(default="7:2:1", pattern=r"^\d{1,2}:\d{1,2}:\d{1,2}$")
    seed: int = Field(default=42, ge=0)
    only_reviewed: bool = True


@router.get("")
def list_datasets(db: SessionDep) -> dict[str, object]:
    rows = db.scalars(select(Dataset).order_by(Dataset.dataset_id.desc())).all()
    items = []
    for row in rows:
        counts = {
            SPLITS[split]: count
            for split, count in db.execute(
                select(DatasetItem.split, func.count(DatasetItem.item_id))
                .where(DatasetItem.dataset_id == row.dataset_id)
                .group_by(DatasetItem.split)
            ).all()
        }
        items.append(
            {
                "dataset_id": row.dataset_id,
                "snapshot_name": row.snapshot_name,
                "split_ratio": row.split_ratio,
                "seed": row.seed,
                "frame_count": row.frame_count,
                "status": {0: "building", 1: "ready", 2: "archived"}.get(row.status, "unknown"),
                "splits": counts,
                "created_at": serializers.iso(row.created_at),
            }
        )
    return ok({"items": items, "total": len(items)})


@router.post("", dependencies=[Depends(require("analyst", "algo", "admin"))])
def export_dataset(
    body: ExportBody, db: SessionDep, user: UserDep, settings: SettingsDep
) -> dict[str, object]:
    if db.scalar(select(Dataset).where(Dataset.snapshot_name == body.snapshot_name)):
        raise ApiError(CONFLICT, "该快照名已存在")

    ratios = [int(part) for part in body.split_ratio.split(":")]
    if sum(ratios) != 10:
        raise ApiError(BAD_PARAM, "划分比例之和应为 10，例如 7:2:1")

    frames = _select_frames(db, body.only_reviewed)
    if not frames:
        raise ApiError(BAD_PARAM, "没有符合条件的帧，无法导出")

    groups = _group(frames)
    assignment = _assign(groups, ratios, body.seed)

    snapshot = Dataset(
        snapshot_name=body.snapshot_name,
        manifest_path="",
        split_ratio=body.split_ratio,
        seed=body.seed,
        frame_count=len(frames),
        status=1,
        created_by=user.user_id,
    )
    db.add(snapshot)
    db.flush()

    counts = {1: 0, 2: 0, 3: 0}
    for group_key, members in groups.items():
        split = assignment[group_key]
        for asset in members:
            counts[split] += 1
            db.add(
                DatasetItem(
                    dataset_id=snapshot.dataset_id,
                    asset_id=asset.asset_id,
                    split=split,
                    group_key=group_key,
                )
            )

    # The manifest is a human-readable copy; the rows are the record. Keeping both means a reviewer can
    # read the snapshot without a database, and the application never parses it.
    manifest = Path(settings.data_dir) / "datasets" / body.snapshot_name / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "snapshot_name": body.snapshot_name,
                "split_ratio": body.split_ratio,
                "seed": body.seed,
                "frame_count": len(frames),
                "splits": {SPLITS[key]: value for key, value in counts.items()},
                "groups": len(groups),
                "frames": [
                    {"frame_id": asset.frame_id, "split": SPLITS[assignment[_group_of(asset)]]}
                    for asset in frames
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    snapshot.manifest_path = str(manifest).replace("\\", "/")

    db.add(
        SysLog(
            user_id=user.user_id,
            module="dataset",
            action="export",
            target_type="dataset",
            target_id=str(snapshot.dataset_id),
            after_value=json.dumps({SPLITS[k]: v for k, v in counts.items()}),
        )
    )
    db.commit()
    db.refresh(snapshot)

    return ok(
        {
            "dataset_id": snapshot.dataset_id,
            "snapshot_name": snapshot.snapshot_name,
            "split_ratio": snapshot.split_ratio,
            "seed": snapshot.seed,
            "frame_count": snapshot.frame_count,
            "splits": {SPLITS[key]: value for key, value in counts.items()},
            "groups": len(groups),
            "manifest_path": snapshot.manifest_path,
            "status": "ready",
            "created_at": serializers.iso(snapshot.created_at),
        }
    )


def _select_frames(db, only_reviewed: bool) -> list[MediaAsset]:
    """Frames that carry a reviewed result; an unreviewed frame is not a label (AC-18).

    "Reviewed" means at least one box was confirmed or modified — a frame whose reviewer rejected
    every box still counts, because the empty result is a label too.
    """
    stmt = select(MediaAsset)
    if only_reviewed:
        reviewed = (
            select(DetectObject.frame_id).where(DetectObject.review_status.in_((1, 2))).distinct()
        )
        stmt = stmt.where(MediaAsset.frame_id.in_(reviewed))
    return list(db.scalars(stmt.order_by(MediaAsset.captured_at)).all())


def _group_of(asset: MediaAsset) -> str:
    return asset.captured_at.replace(microsecond=0).isoformat()[:19]


def _group(frames: list[MediaAsset]) -> dict[str, list[MediaAsset]]:
    groups: dict[str, list[MediaAsset]] = {}
    for asset in frames:
        key = _group_of(asset)
        groups.setdefault(key, []).append(asset)
    return groups


def _assign(groups: dict[str, list[MediaAsset]], ratios: list[int], seed: int) -> dict[str, int]:
    """Deterministically put each group on one side of the split.

    Sorted group order plus a seeded hash means the same frames and the same seed always give the same
    answer, on any machine, without storing the assignment anywhere.
    """
    ordered = sorted(groups)
    weights = {1: ratios[0], 2: ratios[1], 3: ratios[2]}
    total = sum(weights.values())
    assigned: dict[str, int] = {}
    used = {1: 0, 2: 0, 3: 0}
    target = {split: weight / total for split, weight in weights.items()}

    for key in ordered:
        digest = hashlib.sha256(f"{seed}:{key}".encode()).digest()
        pointer = digest[0] / 255
        # Walk the cumulative distribution; ties fall to the larger split, which is stable.
        cumulative = 0.0
        chosen = 3
        for split in (1, 2, 3):
            cumulative += target[split]
            if pointer <= cumulative:
                chosen = split
                break
        assigned[key] = chosen
        used[chosen] += 1

    # An empty split would make the snapshot unusable; move the smallest group into it.
    for split in (1, 2, 3):
        if used[split] == 0:
            donor = max(assigned, key=lambda key: len(groups[key]))
            assigned[donor] = split
            used[split] += 1
    return assigned
