"""Statistics for the dashboard (FR-M5-01, FR-M5-03, FR-M2-03, FR-M4-02).

Every figure is computed from rows, never from a fixed list. The basis question matters: a count over
`detect_object` includes rejected boxes unless it filters them, and a viewer comparing two numbers
taken on different bases will conclude the wrong thing — so the basis is returned with the figures.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app import timebase
from app.deps import SessionDep, get_current_user
from app.envelope import ok
from app.models import DetectObject, MediaAsset, SpeciesDict

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(get_current_user)])


def _window(days: int) -> tuple[datetime, datetime]:
    """The one local-day window every statistics route counts over (ADR 14).

    The last `days` local calendar days ending today in `AV_TIMEZONE`, from the start of the oldest
    day (inclusive) to the start of tomorrow (exclusive), both expressed as the naive UTC the columns
    store. A rolling `now - days * 24h` window cuts the first local day at the current clock time, so
    two cards labelled "近 7 日" count different frames - the defect this helper removes.
    """
    recent = timebase.recent_days(days)
    lower, upper = timebase.day_bounds(recent[0].isoformat(), recent[-1].isoformat())
    assert lower is not None and upper is not None
    return lower, upper


@router.get("/species")
def species_composition(
    db: SessionDep,
    basis: str = Query(default="reviewed", pattern="^(reviewed|raw)$"),
    days: int = Query(default=7, ge=1, le=90),
) -> dict[str, object]:
    since, until = _window(days)
    stmt = (
        select(DetectObject.class_code, func.count(DetectObject.object_id))
        .join(MediaAsset, MediaAsset.frame_id == DetectObject.frame_id)
        .where(MediaAsset.captured_at >= since, MediaAsset.captured_at < until)
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
    since, until = _window(days)
    total = (
        db.scalar(
            select(func.count(MediaAsset.asset_id)).where(
                MediaAsset.captured_at >= since, MediaAsset.captured_at < until
            )
        )
        or 0
    )
    rejected = (
        db.scalar(
            select(func.count(MediaAsset.asset_id)).where(
                MediaAsset.captured_at >= since,
                MediaAsset.captured_at < until,
                MediaAsset.quality_flag == 1,
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
    """Frames per local day (ADR 14). Days with no capture are present with a zero, so the line has
    no gaps that read as missing data rather than as a quiet day."""
    items = []
    for day in timebase.recent_days(days):
        lower, upper = timebase.day_bounds(day.isoformat(), day.isoformat())
        frames = (
            db.scalar(
                select(func.count(MediaAsset.asset_id)).where(
                    MediaAsset.captured_at >= lower,
                    MediaAsset.captured_at < upper,
                )
            )
            or 0
        )
        items.append({"date": str(day), "frames": frames})
    return ok({"days": days, "items": items})


@router.get("/corrections")
def corrections(db: SessionDep, days: int = Query(default=7, ge=1, le=90)) -> dict[str, object]:
    """How reviewers changed the automatic result: rejected, relabelled, and drawn by hand."""
    since, until = _window(days)
    rejected = (
        db.scalar(
            select(func.count(DetectObject.object_id)).where(
                DetectObject.review_status == 3,
                DetectObject.created_at >= since,
                DetectObject.created_at < until,
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
                DetectObject.created_at < until,
            )
        )
        or 0
    )
    added = (
        db.scalar(
            select(func.count(DetectObject.object_id)).where(
                DetectObject.is_manual == 1,
                DetectObject.created_at >= since,
                DetectObject.created_at < until,
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
