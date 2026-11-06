"""Dataset snapshots (FR-M4-04, AC-18).

Both routes answer 501, and the reason is a gap rather than missing effort: **the nine-table data
model has no dataset table**. A snapshot is currently only a string on `train_experiment`, so there is
nowhere to record `DS-V3`, its split, its seed or the list of frames it contains. Returning a made-up
snapshot would let the export page look finished while destroying the reproducibility AC-18 asks for.

Raising this instead of inventing storage: the fix is a tenth table, which belongs to the data model
owner, not to a skeleton PR.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.envelope import not_built

router = APIRouter(
    prefix="/api/datasets", tags=["datasets"], dependencies=[Depends(get_current_user)]
)

REASON = "数据集快照（数据模型中还没有 dataset 表）"


@router.get("")
def list_datasets() -> dict[str, object]:
    raise not_built(REASON)


@router.post("")
def export_dataset() -> dict[str, object]:
    raise not_built(REASON)
