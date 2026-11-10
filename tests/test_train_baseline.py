"""Tests for the exploratory baseline script (P2-06b).

The training run itself needs a GPU and the CUDA environment; these tests cover the reproducible
parts: the subset is deterministic, the data file points at the three splits, and the experiment row
is written with every metric column filled.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from app.db import engine_from_dsn
from app.models import TrainExperiment
from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import train_baseline as train  # noqa: E402


def test_select_subset_is_deterministic_and_sorted() -> None:
    images = [Path(f"{index:02d}.jpg") for index in range(20)]

    first = train.select_subset(images, limit=7, seed=42)
    second = train.select_subset(images, limit=7, seed=42)

    assert first == second
    assert len(first) == 7
    assert first == sorted(first)
    assert set(first) <= set(images)
    assert train.select_subset(images, limit=50, seed=42) == images


def test_write_data_yaml_writes_absolute_lists_and_names(tmp_path: Path) -> None:
    data = tmp_path / "data" / "baseline.yaml"
    train_images = [tmp_path / "train" / "images" / "a.jpg"]
    val_images = [tmp_path / "val" / "images" / "b.jpg"]
    test_dir = tmp_path / "test" / "images"

    train.write_data_yaml(data, tmp_path, train_images, val_images, test_dir)

    text = data.read_text(encoding="utf-8")
    assert f"path: {tmp_path.resolve().as_posix()}" in text
    assert f"test: {test_dir.resolve().as_posix()}" in text
    for code in train.CLASS_CODES:
        assert code in text
    train_list = (tmp_path / "data" / "baseline-train.txt").read_text(encoding="utf-8")
    val_list = (tmp_path / "data" / "baseline-val.txt").read_text(encoding="utf-8")
    assert train_images[0].resolve().as_posix() in train_list
    assert val_images[0].resolve().as_posix() in val_list


def test_record_experiment_fills_every_metric(tmp_path: Path) -> None:
    dsn = f"sqlite:///{(tmp_path / 'exp.db').as_posix()}"
    metrics = {
        "map50": 0.5,
        "map50_95": 0.3,
        "recall_avg": 0.6,
        "fps": 30.0,
        "params_m": 3.2,
        "imgsz": 640,
    }

    exp_id = train.record_experiment(
        dsn,
        experiment="E0-test",
        snapshot="S",
        split_ratio="85:15",
        seed=42,
        epochs=30,
        batch_size=16,
        lr=0.01,
        metrics=metrics,
        note="test note",
    )

    engine = engine_from_dsn(dsn)
    with Session(engine) as session:
        row = session.scalar(select(TrainExperiment).where(TrainExperiment.exp_id == exp_id))
        assert row.exp_name == "E0-test"
        assert row.dataset_snapshot == "S"
        assert row.split_ratio == "85:15"
        assert row.seed == 42
        assert row.epochs == 30
        assert row.batch_size == 16
        assert float(row.lr) == pytest.approx(0.01)
        assert float(row.map50) == pytest.approx(0.5)
        assert float(row.map50_95) == pytest.approx(0.3)
        assert float(row.recall_avg) == pytest.approx(0.6)
        assert float(row.fps) == pytest.approx(30.0)
        assert float(row.params_m) == pytest.approx(3.2)
        assert row.is_baseline == 1
        assert row.note == "test note"
