"""Tests for the model-version registration script (P2-06c)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from app.db import engine_from_dsn
from app.models import ModelVersion
from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import register_model as register  # noqa: E402

METRICS = {
    "map50": 0.5,
    "map50_95": 0.3,
    "recall_avg": 0.6,
    "fps": 30.0,
    "params_m": 3.2,
}


def test_activation_keeps_exactly_one_online_row(tmp_path: Path) -> None:
    dsn = f"sqlite:///{(tmp_path / 'models.db').as_posix()}"

    first = register.register_model(
        dsn,
        version_name="v1",
        weights=Path("a.pt"),
        labels=Path("labels.txt"),
        dataset_ref="S",
        metrics=METRICS,
        activate=True,
    )
    second = register.register_model(
        dsn,
        version_name="v2",
        weights=Path("b.pt"),
        labels=Path("labels.txt"),
        dataset_ref="S",
        metrics=METRICS,
        activate=True,
    )

    assert first != second
    engine = engine_from_dsn(dsn)
    with Session(engine) as session:
        rows = {row.version_name: row for row in session.scalars(select(ModelVersion)).all()}
        assert rows["v1"].is_online == 0
        assert rows["v1"].status == 2
        assert rows["v2"].is_online == 1
        assert rows["v2"].status == 1
        assert float(rows["v2"].map50) == pytest.approx(0.5)
        assert float(rows["v2"].map50_95) == pytest.approx(0.3)
        assert float(rows["v2"].recall_avg) == pytest.approx(0.6)
        assert float(rows["v2"].fps) == pytest.approx(30.0)
        assert float(rows["v2"].params_m) == pytest.approx(3.2)


def test_registration_is_idempotent_and_can_stay_candidate(tmp_path: Path) -> None:
    dsn = f"sqlite:///{(tmp_path / 'models.db').as_posix()}"

    first = register.register_model(
        dsn,
        version_name="v1",
        weights=Path("a.pt"),
        labels=Path("labels.txt"),
        dataset_ref="S",
        metrics=METRICS,
        activate=False,
    )
    second = register.register_model(
        dsn,
        version_name="v1",
        weights=Path("a.pt"),
        labels=Path("labels.txt"),
        dataset_ref="S",
        metrics=METRICS,
        activate=False,
    )

    assert first == second
    engine = engine_from_dsn(dsn)
    with Session(engine) as session:
        row = session.scalar(select(ModelVersion).where(ModelVersion.version_name == "v1"))
        assert row.is_online == 0
        assert row.status == 0
