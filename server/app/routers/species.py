"""The species dictionary (FR-M6-04, AC-26).

`class_code` order is a contract with the model's `labels.txt`: codes cannot be added, renamed or
reordered through the API, only their thresholds and display properties can change. Allowing an add
here would silently desynchronise the index a detection result uses as a class.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import serializers
from app.deps import SessionDep, UserDep, get_current_user, require
from app.envelope import NOT_FOUND, ApiError, ok
from app.models import SpeciesDict, SysLog

router = APIRouter(
    prefix="/api/species", tags=["species"], dependencies=[Depends(get_current_user)]
)


class PatchBody(BaseModel):
    conf_thr: float | None = Field(default=None, ge=0.0, le=1.0)
    in_stat: bool | None = None
    cn_name: str | None = Field(default=None, min_length=1, max_length=32)


@router.get("")
def list_species(db: SessionDep) -> dict[str, object]:
    rows = db.scalars(select(SpeciesDict).order_by(SpeciesDict.species_id)).all()
    return ok({"items": [serializers.species(row) for row in rows], "total": len(rows)})


@router.patch("/{class_code}", dependencies=[Depends(require("analyst", "algo", "admin"))])
def update(class_code: str, body: PatchBody, db: SessionDep, user: UserDep) -> dict[str, object]:
    row = db.scalar(select(SpeciesDict).where(SpeciesDict.class_code == class_code))
    if row is None:
        raise ApiError(NOT_FOUND, "类别不存在")

    before = serializers.species(row)
    if body.conf_thr is not None:
        row.conf_thr = body.conf_thr
    if body.in_stat is not None:
        row.in_stat = 1 if body.in_stat else 0
    if body.cn_name is not None:
        row.cn_name = body.cn_name
    after = serializers.species(row)

    db.add(
        SysLog(
            user_id=user.user_id,
            module="species",
            action="update",
            target_type="species_dict",
            target_id=class_code,
            before_value=str(before),
            after_value=str(after),
        )
    )
    db.commit()
    return ok(after)
