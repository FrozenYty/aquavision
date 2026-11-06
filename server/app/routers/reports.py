"""Inspection reports (FR-M5-04, AC-22).

Both routes answer 501 for the same reason as datasets: **there is no report table**. A report has a
period, a template, a basis, a model version, a generated file and a status — six facts with nowhere to
live. Generating a PDF and forgetting it would satisfy the demo and lose the history the requirement
calls for, so the honest answer is that the storage comes first.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.envelope import not_built

router = APIRouter(
    prefix="/api/reports", tags=["reports"], dependencies=[Depends(get_current_user)]
)

REASON = "巡检报告（数据模型中还没有 report 表）"


@router.get("")
def list_reports() -> dict[str, object]:
    raise not_built(REASON)


@router.post("")
def create_report() -> dict[str, object]:
    raise not_built(REASON)
