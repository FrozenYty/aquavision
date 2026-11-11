"""Demo mode: one action that returns the system to the state a rehearsal starts from (P3-06, AC-36).

A rehearsal has to begin from the same place every time: no frames, no tasks, no reports, and a model
still online. This is the backend half of that. The setting is what keeps the route out of a deployed
system, and the refusal when it is off is `404`, not `403` - a data-wiping endpoint should not answer
"forbidden", which tells a prober that it exists.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select

from app.deps import SessionDep, SettingsDep, get_current_user, require
from app.envelope import NOT_FOUND, ApiError, ok
from app.models import (
    Dataset,
    DatasetItem,
    DetectObject,
    DetectTask,
    DetectTaskItem,
    MediaAsset,
    ModelVersion,
    Report,
    SysLog,
    SysMessage,
    TrainExperiment,
)

router = APIRouter(prefix="/api/demo", tags=["demo"], dependencies=[Depends(get_current_user)])

#: The business rows a reset removes, child before parent so a database that enforces foreign keys
#: accepts each delete. The order is also the order the response reports.
DELETED_TABLES = (
    DetectObject,
    DetectTaskItem,
    DetectTask,
    Report,
    DatasetItem,
    Dataset,
    TrainExperiment,
    SysMessage,
    SysLog,
    MediaAsset,
)


def demo_gate(settings: SettingsDep) -> None:
    """Refuse unless the deployment turned the mode on. Not-found on purpose: see the module docstring."""
    if not settings.demo_enabled:
        raise ApiError(NOT_FOUND, "演示模式未开启")


@router.post("/reset", dependencies=[Depends(demo_gate), Depends(require("admin"))])
def reset(db: SessionDep, settings: SettingsDep) -> dict[str, object]:
    """Delete the business rows and the stored frames, and report what went.

    Kept on purpose:
    - `model_version` - a rehearsal whose first capture answers "模型权重未注册" is not the state a
      rehearsal starts from, it is the opposite of it;
    - `species_dict` - detection validates the model's class order against it, so removing it would
      break the first inference of the session;
    - `sys_user` and `sys_param` - deleting the caller's own account mid-request is a lockout, not a
      reset, and the configuration is part of the environment a rehearsal is meant to reuse.
    Every other business table is emptied; each count is reported so an operator can see the reset
    happened instead of trusting a boolean.
    """
    deleted: dict[str, int] = {}
    for model in DELETED_TABLES:
        result = db.execute(delete(model))
        deleted[model.__tablename__] = result.rowcount or 0
    db.commit()

    frames_dir = Path(settings.data_dir) / "frames"
    removed = 0
    if frames_dir.is_dir():
        # Count the unlinks that succeeded, not the files that were there: the DB part of the reset is
        # already committed, so a file another process still holds must not fail it - but it must not
        # be reported as removed either.
        for path in frames_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
        shutil.rmtree(frames_dir, ignore_errors=True)

    online = db.scalar(select(ModelVersion.version_name).where(ModelVersion.is_online == 1))
    return ok({"deleted": deleted, "frame_files_removed": removed, "model_online": online})
