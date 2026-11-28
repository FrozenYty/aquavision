"""Inspection reports (FR-M5-04, AC-22).

A report is generated as a Markdown document. The format is the one open question: the SRS asks for
Word or PDF, and neither can be produced without a rendering dependency, so the same row shape will
serve a later export step. What is already real is the part AC-22 checks — the figures come from the
same queries the dashboard uses, and the footer carries the model version and the basis.

The row is what makes the history queryable by period, template and basis; the file is the document.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app import serializers, timebase
from app.deps import SessionDep, SettingsDep, UserDep, get_current_user, require
from app.envelope import BAD_PARAM, CONFLICT, INTERNAL, NOT_FOUND, ApiError, ok
from app.models import (
    DetectObject,
    MediaAsset,
    ModelVersion,
    Report,
    SpeciesDict,
    SysLog,
)
from app.notify import LEVEL_INFO, notify

router = APIRouter(
    prefix="/api/reports", tags=["reports"], dependencies=[Depends(get_current_user)]
)

STATUS = {0: "generating", 1: "ready", 2: "failed"}
TEMPLATES = ("standard", "brief")
BASES = ("reviewed", "raw")


class ReportBody(BaseModel):
    period_start: date | datetime
    period_end: date | datetime
    template: str = Field(default="standard", pattern="^(standard|brief)$")
    basis: str = Field(default="reviewed", pattern="^(reviewed|raw)$")
    preview_token: str | None = Field(default=None, min_length=64, max_length=64)


@router.get("/preview")
def preview_report(
    db: SessionDep,
    period_start: date | datetime,
    period_end: date | datetime,
    basis: str = Query(default="reviewed", pattern="^(reviewed|raw)$"),
) -> dict[str, object]:
    start, end = timebase.report_bounds(period_start, period_end)
    if end <= start:
        raise ApiError(BAD_PARAM, "结束日期不能早于开始日期")
    online = db.scalar(select(ModelVersion).where(ModelVersion.is_online == 1))
    figures = _figures(db, start, end, basis)
    return ok(
        {
            "preview_token": _preview_token(start, end, basis, figures, online),
            "period_start": serializers.iso(start),
            "period_end": serializers.iso(end),
            "basis": basis,
            "model_version": online.version_name if online else None,
            "figures": figures,
        }
    )


@router.get("")
def list_reports(
    db: SessionDep,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=24, ge=1, le=100),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    template: str | None = Query(default=None, pattern="^(standard|brief)$"),
    basis: str | None = Query(default=None, pattern="^(reviewed|raw)$"),
) -> dict[str, object]:
    """The archive, newest first, narrowed by the filters the history page offers.

    The period filter is an overlap test on the report's own period, decided on the stored UTC
    instants: a day range is converted once (`day_bounds`), never compared as a rendered string, so a
    report that ends just after local midnight still belongs to its operating day (ADR 14). `total`
    is the size of the filtered set, and `page`/`size` walk that set rather than the whole archive.
    """
    try:
        lower, upper = timebase.day_bounds(date_from, date_to)
    except ValueError as err:
        raise ApiError(BAD_PARAM, f"参数有误：日期须为 YYYY-MM-DD（{err.args[0]}）") from err
    if lower is not None and upper is not None and upper <= lower:
        raise ApiError(BAD_PARAM, "结束日期不能早于开始日期")

    conditions = []
    if lower is not None:
        conditions.append(Report.period_end >= lower)
    if upper is not None:
        conditions.append(Report.period_start < upper)
    if template:
        conditions.append(Report.template == template)
    if basis:
        conditions.append(Report.basis == basis)

    rows = db.scalars(
        select(Report)
        .where(*conditions)
        .order_by(Report.report_id.desc())
        .limit(size)
        .offset((page - 1) * size)
    ).all()
    total = db.scalar(select(func.count(Report.report_id)).where(*conditions)) or 0
    return ok({"items": [_report(row) for row in rows], "total": total, "page": page, "size": size})


@router.get("/{report_code}/file")
def download_report(report_code: str, db: SessionDep, settings: SettingsDep) -> FileResponse:
    """The generated document itself, as a download (FR-M5-04, AC-22, TM-096).

    The row records where `_render` wrote the Markdown, so the route serves that file rather than
    regenerating it: a downloaded report must be the one the figures were checked against. The
    database is trusted, but a stored path is still resolved and refused unless it stays inside the
    data root - a path is data, and data can be wrong. A report whose state cannot have a document
    yet is answered with the state, not with a server error.
    """
    row = db.scalar(select(Report).where(Report.report_code == report_code))
    if row is None:
        raise ApiError(NOT_FOUND, "报告不存在")
    if row.status == 0:
        # The document is being written: retrying later is the correct action, so this is a conflict
        # with the state rather than an absent resource.
        raise ApiError(CONFLICT, "报告正在生成，请稍后再试")
    if row.status != 1 or not row.file_path:
        reason = row.error_msg or "没有留下原因"
        raise ApiError(NOT_FOUND, f"报告生成失败（{reason}），没有可下载的文件")

    root = Path(settings.data_dir).resolve()
    path = (root / row.file_path).resolve()
    if not path.is_relative_to(root):
        raise ApiError(NOT_FOUND, "报告文件的记录不在数据目录内，拒绝下载")
    if not path.is_file():
        raise ApiError(NOT_FOUND, "报告文件已丢失，请重新生成")
    return FileResponse(path, media_type="text/markdown", filename=f"{row.report_code}.md")


@router.post("", dependencies=[Depends(require("analyst", "admin"))])
def create_report(
    body: ReportBody, request: Request, db: SessionDep, user: UserDep, settings: SettingsDep
) -> dict[str, object]:
    # Calendar dates use the operating zone; existing offset-aware clients keep their instants.
    start, end = timebase.report_bounds(body.period_start, body.period_end)
    if end <= start:
        raise ApiError(BAD_PARAM, "结束日期不能早于开始日期")
    body = body.model_copy(
        update={"period_start": timebase.to_zone(start), "period_end": timebase.to_zone(end)}
    )

    serial = (db.scalar(select(func.count(Report.report_id))) or 0) + 1
    code = f"RP{timebase.now().strftime('%y%m%d')}-{serial:03d}"
    if db.scalar(select(Report).where(Report.report_code == code)):
        raise ApiError(CONFLICT, "报告编号冲突，请重试")

    online = db.scalar(select(ModelVersion).where(ModelVersion.is_online == 1))
    figures = _figures(db, start, end, body.basis)
    if body.preview_token and body.preview_token != _preview_token(
        start, end, body.basis, figures, online
    ):
        raise ApiError(CONFLICT, "数据或模型已更新，请刷新预览后重新生成")

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
    # The third event FR-M8-02 names, after the report is really stored: the file and the row exist,
    # so the message cannot point at something that failed to generate.
    notify(
        request.app.state.session_factory,
        msg_type="report_done",
        level=LEVEL_INFO,
        title=f"报告 {row.report_code} 已生成",
        content=f"{serializers.iso(row.period_start)} 至 {serializers.iso(row.period_end)}",
        ref_type="report",
        ref_id=str(row.report_id),
    )
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
    model = online.version_name if online else "未上线"
    basis = "复核后结果" if body.basis == "reviewed" else "原始识别结果"
    lines = [
        f"# 巡检报告 {code}",
        "",
        f"- 统计周期：{timebase.to_zone(body.period_start):%Y-%m-%d} 至 "
        f"{timebase.to_zone(body.period_end):%Y-%m-%d}",
        f"- 模板：{body.template}",
        f"- 统计口径：{basis}",
    ]
    # The brief template keeps the period, the species composition and the footer; the standard one
    # adds the capture-quality and model sections that make the full inspection record.
    if body.template == "standard":
        lines += [
            f"- 模型版本：{model}",
            "",
            "## 采集与质量",
            "",
            f"- 采集成像：{figures['frames']} 帧",
            f"- 质量拦截：{figures['rejected']} 帧，拦截率 {figures['rate']:.2%}",
        ]
    lines += [
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
        f"生成于 {timebase.iso(timebase.now())} · 模型版本 {model} · 口径 "
        f"{'复核后' if body.basis == 'reviewed' else '原始'}",
        "",
        "> 演示阶段报告以 Markdown 生成；Word 与 PDF 由同一份数据在导出环节渲染。",
        "",
    ]
    return "\n".join(lines)


def _preview_token(start, end, basis, figures, online) -> str:
    values = [
        start.isoformat(),
        end.isoformat(),
        basis,
        figures,
        online.version_name if online else None,
    ]
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode("utf-8")).hexdigest()
