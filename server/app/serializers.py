"""One place that turns a row into the JSON the contract describes.

Serialisers live together because drift between endpoints is the usual defect: two handlers each build
their own dict and one of them forgets a field six months later.
"""

from __future__ import annotations

from typing import Any

from app.models import DetectObject, DetectTask, MediaAsset, ModelVersion, SpeciesDict, SysUser

#: Task status codes, from the data model §3.4 comment.
TASK_STATUS = {0: "queued", 1: "running", 2: "done", 3: "failed", 4: "cancelled"}

#: Review status codes, from the data model §3.5 comment.
REVIEW_STATUS = {0: "pending", 1: "confirmed", 2: "modified", 3: "rejected"}


def iso(value: Any) -> str | None:
    """A naive UTC datetime as ISO 8601 with an explicit offset, as the contract requires."""
    if value is None:
        return None
    return value.replace(tzinfo=None).isoformat(timespec="seconds") + "+00:00"


def frame(asset: MediaAsset) -> dict[str, object]:
    return {
        "frame_id": asset.frame_id,
        "session_id": asset.session_id,
        "point_code": asset.point_code,
        "captured_at": iso(asset.captured_at),
        "quality": {
            "score": asset.quality_score,
            "verdict": "retake" if asset.quality_flag else "ok",
        },
        "is_retake": bool(asset.is_retake),
        "env": {"turbidity_rel": asset.turbidity_rel},
        "width": asset.width,
        "height": asset.height,
    }


def box(obj: DetectObject) -> dict[str, object]:
    return {
        "object_id": obj.object_id,
        "class_code": obj.class_code,
        "confidence": float(obj.confidence),
        "x": float(obj.x),
        "y": float(obj.y),
        "w": float(obj.w),
        "h": float(obj.h),
        "is_manual": obj.is_manual,
        "review_status": obj.review_status,
    }


def task(row: DetectTask) -> dict[str, object]:
    return {
        "task_id": row.task_id,
        "task_code": row.task_code,
        "type": "live" if row.task_type == 1 else "batch",
        "status": TASK_STATUS.get(row.status, "unknown"),
        "progress": row.progress,
        "asset_count": row.asset_count,
        "obj_count": row.obj_count,
        "model_version_id": row.model_version_id,
        "error_msg": row.error_msg,
        "created_at": iso(row.created_at),
        "finished_at": iso(row.finished_at),
    }


def model_version(row: ModelVersion) -> dict[str, object]:
    return {
        "model_id": row.model_id,
        "version_name": row.version_name,
        "dataset_ref": row.dataset_ref,
        "map50": float(row.map50) if row.map50 is not None else None,
        "map50_95": float(row.map50_95) if row.map50_95 is not None else None,
        "recall_avg": float(row.recall_avg) if row.recall_avg is not None else None,
        "fps": float(row.fps) if row.fps is not None else None,
        "params_m": float(row.params_m) if row.params_m is not None else None,
        "is_online": bool(row.is_online),
        "status": row.status,
        "created_at": iso(row.created_at),
    }


def species(row: SpeciesDict) -> dict[str, object]:
    return {
        "class_code": row.class_code,
        "cn_name": row.cn_name,
        "latin_name": row.latin_name,
        "category": row.category,
        "conf_thr": float(row.conf_thr),
        "in_stat": bool(row.in_stat),
        "status": row.status,
    }


def user(row: SysUser) -> dict[str, object]:
    return {
        "user_id": row.user_id,
        "username": row.username,
        "real_name": row.real_name,
        "role": row.role_code,
        "status": row.status,
        "last_login_at": iso(row.last_login_at),
    }
