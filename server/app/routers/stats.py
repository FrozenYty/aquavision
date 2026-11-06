"""Statistics for the dashboard (FR-M5-01, FR-M5-03, FR-M2-03, FR-M4-02).

Every figure is computed from rows, never from a fixed list. The basis question matters: a count over
`detect_object` includes rejected boxes unless it filters them, and a viewer comparing two numbers
taken on different bases will conclude the wrong thing — so the basis is returned with the figures.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.deps import SessionDep, get_current_user
from app.envelope import ok
from app.models import DetectObject, MediaAsset, SpeciesDict

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(get_current_user)])


@router.get("/species")
def species_composition(
    db: SessionDep,
    basis: str = Query(default="reviewed", pattern="^(reviewed|raw)$"),
    days: int = Query(default=7, ge=1, le=90),
) -> dict[str, object]:
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
    stmt = (
        select(DetectObject.class_code, func.count(DetectObject.object_id))
        .join(MediaAsset, MediaAsset.frame_id == DetectObject.frame_id)
        .where(MediaAsset.captured_at >= since)
        .group_by(DetectObject.class_code)
    )
    if basis == "reviewed":
        stmt = stmt.where(DetectObject.review_status != 3)

    counts = {row[0]: row[1] for row in db.execute(stmt).all()}
    names = {row.class_code: row.cn_name for row in db.scalars(select(SpeciesDict)).all()}
    total = sum(counts.values()) or 1
    items = [
        {
            "class_code": code,
            "cn_name": names.get(code, code),
            "count": count,
            "share": round(count / total, 4),
        }
        for code, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
    ]
    return ok({"basis": basis, "days": days, "items": items, "total": sum(counts.values())})


@router.get("/quality")
def quality_rejection(
    db: SessionDep, days: int = Query(default=7, ge=1, le=90)
) -> dict[str, object]:
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
    total = (
        db.scalar(select(func.count(MediaAsset.asset_id)).where(MediaAsset.captured_at >= since))
        or 0
    )
    rejected = (
        db.scalar(
            select(func.count(MediaAsset.asset_id)).where(
                MediaAsset.captured_at >= since, MediaAsset.quality_flag == 1
            )
        )
        or 0
    )
    return ok(
        {
            "days": days,
            "total": total,
            "rejected": rejected,
            "rate": round(rejected / total, 4) if total else 0.0,
        }
    )


@router.get("/trend")
def capture_trend(db: SessionDep, days: int = Query(default=7, ge=1, le=90)) -> dict[str, object]:
    """Frames per day. Days with no capture are present with a zero, so the line has no gaps that
    read as missing data rather than as a quiet day."""
    today = datetime.now(UTC).replace(tzinfo=None).date()
    start = today - timedelta(days=days - 1)
    rows = db.execute(
        select(func.date(MediaAsset.captured_at), func.count(MediaAsset.asset_id))
        .where(MediaAsset.captured_at >= datetime.combine(start, datetime.min.time()))
        .group_by(func.date(MediaAsset.captured_at))
    ).all()
    seen = {str(day): count for day, count in rows}
    items = [
        {
            "date": str(start + timedelta(days=offset)),
            "frames": seen.get(str(start + timedelta(days=offset)), 0),
        }
        for offset in range(days)
    ]
    return ok({"days": days, "items": items})


@router.get("/corrections")
def corrections(db: SessionDep, days: int = Query(default=7, ge=1, le=90)) -> dict[str, object]:
    """How reviewers changed the automatic result: rejected, relabelled, and drawn by hand."""
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
    rejected = (
        db.scalar(
            select(func.count(DetectObject.object_id)).where(
                DetectObject.review_status == 3, DetectObject.created_at >= since
            )
        )
        or 0
    )
    modified = (
        db.scalar(
            select(func.count(DetectObject.object_id)).where(
                DetectObject.review_status == 2,
                DetectObject.is_manual == 0,
                DetectObject.created_at >= since,
            )
        )
        or 0
    )
    added = (
        db.scalar(
            select(func.count(DetectObject.object_id)).where(
                DetectObject.is_manual == 1, DetectObject.created_at >= since
            )
        )
        or 0
    )
    return ok(
        {
            "days": days,
            "rejected": rejected,
            "modified": modified,
            "added": added,
            "total": rejected + modified + added,
        }
    )
