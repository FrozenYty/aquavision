"""Inspection reports (FR-M5-04, AC-22).

A report is generated as a Markdown document. The format is the one open question: the SRS asks for
Word or PDF, and neither can be produced without a rendering dependency, so the same row shape will
serve a later export step. What is already real is the part AC-22 checks — the figures come from the
same queries the dashboard uses, and the footer carries the model version and the basis.

The row is what makes the history queryable by period, template and basis; the file is the document.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app import serializers, timebase
from app.deps import SessionDep, SettingsDep, UserDep, get_current_user, require
from app.envelope import BAD_PARAM, CONFLICT, INTERNAL, ApiError, ok
from app.models import (
    DetectObject,
    MediaAsset,
    ModelVersion,
    Report,
    SpeciesDict,
    SysLog,
)

router = APIRouter(
    prefix="/api/reports", tags=["reports"], dependencies=[Depends(get_current_user)]
)

STATUS = {0: "generating", 1: "ready", 2: "failed"}
TEMPLATES = ("standard", "brief")
BASES = ("reviewed", "raw")


class ReportBody(BaseModel):
    period_start: datetime
    period_end: datetime
    template: str = Field(default="standard", pattern="^(standard|brief)$")
    basis: str = Field(default="reviewed", pattern="^(reviewed|raw)$")


@router.get("")
def list_reports(
    db: SessionDep,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=24, ge=1, le=100),
) -> dict[str, object]:
    rows = db.scalars(
        select(Report).order_by(Report.report_id.desc()).limit(size).offset((page - 1) * size)
    ).all()
    total = db.scalar(select(func.count(Report.report_id))) or 0
    return ok({"items": [_report(row) for row in rows], "total": total, "page": page, "size": size})


@router.post("", dependencies=[Depends(require("analyst", "admin"))])
def create_report(
    body: ReportBody, db: SessionDep, user: UserDep, settings: SettingsDep
) -> dict[str, object]:
    # ADR 14: the period arrives with its offset; storage keeps the instant as naive UTC.
    start = timebase.as_utc(body.period_start)
    end = timebase.as_utc(body.period_end)
    if end <= start:
        raise ApiError(BAD_PARAM, "结束日期不能早于开始日期")

    serial = (db.scalar(select(func.count(Report.report_id))) or 0) + 1
    code = f"RP{timebase.now().strftime('%y%m%d')}-{serial:03d}"
    if db.scalar(select(Report).where(Report.report_code == code)):
        raise ApiError(CONFLICT, "报告编号冲突，请重试")

    online = db.scalar(select(ModelVersion).where(ModelVersion.is_online == 1))
    figures = _figures(db, start, end, body.basis)

    row = Report(
        report_code=code,
        period_start=start,
        period_end=end,
        template=body.template,
        basis=body.basis,
        model_version_id=online.model_id if online else None,
        status=0,
        created_by=user.user_id,
    )
    db.add(row)
    db.flush()

    path = Path(settings.data_dir) / "reports" / f"{code}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(_render(code, body, figures, online), encoding="utf-8")
    except OSError as err:
        row.status = 2
        row.error_msg = f"写入文件失败：{type(err).__name__}"
        db.commit()
        raise ApiError(INTERNAL, "报告文件写入失败") from err

    row.file_path = str(path).replace("\\", "/")
    row.status = 1
    db.add(
        SysLog(
            user_id=user.user_id,
            module="report",
            action="generate",
            target_type="report",
            target_id=str(row.report_id),
            after_value=body.basis,
        )
    )
    db.commit()
    db.refresh(row)
    return ok(_report(row))


def _report(row: Report) -> dict[str, object]:
    return {
        "report_id": row.report_id,
        "report_code": row.report_code,
        "period_start": serializers.iso(row.period_start),
        "period_end": serializers.iso(row.period_end),
        "template": row.template,
        "basis": row.basis,
        "model_version_id": row.model_version_id,
        "status": STATUS.get(row.status, "unknown"),
        "error_msg": row.error_msg,
        "file_path": row.file_path,
        "created_at": serializers.iso(row.created_at),
    }


def _figures(db, start: datetime, end: datetime, basis: str) -> dict[str, object]:
    """The same numbers the dashboard shows, computed with the same filters."""
    frames = (
        db.scalar(
            select(func.count(MediaAsset.asset_id)).where(
                MediaAsset.captured_at >= start, MediaAsset.captured_at <= end
            )
        )
        or 0
    )
    rejected = (
        db.scalar(
            select(func.count(MediaAsset.asset_id)).where(
                MediaAsset.captured_at >= start,
                MediaAsset.captured_at <= end,
                MediaAsset.quality_flag == 1,
            )
        )
        or 0
    )

    stmt = (
        select(DetectObject.class_code, func.count(DetectObject.object_id))
        .join(MediaAsset, MediaAsset.frame_id == DetectObject.frame_id)
        .where(MediaAsset.captured_at >= start, MediaAsset.captured_at <= end)
        .group_by(DetectObject.class_code)
    )
    if basis == "reviewed":
        stmt = stmt.where(DetectObject.review_status != 3)
    counts = {code: count for code, count in db.execute(stmt).all()}
    names = {row.class_code: row.cn_name for row in db.scalars(select(SpeciesDict)).all()}
    total = sum(counts.values()) or 1

    return {
        "frames": frames,
        "rejected": rejected,
        "rate": round(rejected / frames, 4) if frames else 0.0,
        "species": [
            {"name": names.get(code, code), "count": count, "share": round(count / total, 4)}
            for code, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
        ],
    }


def _render(code: str, body: ReportBody, figures: dict[str, object], online) -> str:
    lines = [
        f"# 巡检报告 {code}",
        "",
        f"- 统计周期：{timebase.to_zone(body.period_start):%Y-%m-%d} 至 "
        f"{timebase.to_zone(body.period_end):%Y-%m-%d}",
        f"- 模板：{body.template}",
        f"- 统计口径：{'复核后结果' if body.basis == 'reviewed' else '原始识别结果'}",
        f"- 模型版本：{online.version_name if online else '未上线'}",
        "",
        "## 采集与质量",
        "",
        f"- 采集成像：{figures['frames']} 帧",
        f"- 质量拦截：{figures['rejected']} 帧，拦截率 {figures['rate']:.2%}",
        "",
        "## 物种组成",
        "",
        "| 物种 | 目标数 | 占比 |",
        "|---|---|---|",
    ]
    species = figures["species"]
    if species:
        lines += [f"| {row['name']} | {row['count']} | {row['share']:.2%} |" for row in species]
    else:
        lines.append("| 无数据 | 0 | 0% |")

    lines += [
        "",
        "---",
        "",
        f"生成于 {timebase.iso(timebase.now())} · 模型版本 "
        f"{online.version_name if online else '未上线'} · 口径 "
        f"{'复核后' if body.basis == 'reviewed' else '原始'}",
        "",
        "> 演示阶段报告以 Markdown 生成；Word 与 PDF 由同一份数据在导出环节渲染。",
        "",
    ]
    return "\n".join(lines)
