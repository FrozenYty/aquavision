"""Tests for scripts/prepare_dataset.py (P0-01).

The one rule that must never break: frames in the same hash group may never
land in different splits.
"""

import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import prepare_dataset as prep


def make_image(path: Path, seed: int) -> None:
    """Write a deterministic random image so hashes are reproducible."""
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 255, (64, 64, 3), dtype=np.uint8)
    cv2.imwrite(str(path), img)


def test_identical_frames_stay_in_one_group(tmp_path: Path) -> None:
    a, b = tmp_path / "a.jpg", tmp_path / "b.jpg"
    make_image(a, seed=1)
    shutil.copy(a, b)  # same content, different file
    hashes = {"a.jpg": prep.dhash64(a), "b.jpg": prep.dhash64(b)}
    assert len(prep.group_frames(hashes)) == 1


def test_distinct_frames_form_separate_groups(tmp_path: Path) -> None:
    a, b = tmp_path / "a.jpg", tmp_path / "b.jpg"
    make_image(a, seed=1)
    make_image(b, seed=2)
    hashes = {"a.jpg": prep.dhash64(a), "b.jpg": prep.dhash64(b)}
    assert len(prep.group_frames(hashes)) == 2


def test_clean_boxes_drops_ignore_crowd_and_degenerate() -> None:
    anns = [
        {"bbox": [10, 10, 20, 20], "category_id": 1},
        {"bbox": [10, 10, 20, 20], "category_id": 1, "ignore": 1},
        {"bbox": [10, 10, 20, 20], "category_id": 1, "iscrowd": 1},
        {"bbox": [10, 10, 0, 20], "category_id": 1},
    ]
    kept, dropped = prep.clean_boxes(anns, width=100, height=100)
    assert len(kept) == 1
    assert dropped == 3


def test_clean_boxes_clamps_to_image_bounds() -> None:
    anns = [{"bbox": [90, 90, 50, 50], "category_id": 1}]
    kept, dropped = prep.clean_boxes(anns, width=100, height=100)
    assert dropped == 0
    assert kept[0]["bbox"] == [90.0, 90.0, 10.0, 10.0]


def test_groups_never_cross_train_val_boundary(tmp_path: Path) -> None:
    """Ten distinct frames plus five identical pairs; pairs must stay atomic."""
    records = []
    for i in range(10):
        path = tmp_path / f"solo-{i}.jpg"
        make_image(path, seed=100 + i)
        records.append(
            {"file_name": path.name, "path": path, "width": 64, "height": 64, "boxes": []}
        )
    for i in range(5):
        path = tmp_path / f"pair-{i}a.jpg"
        make_image(path, seed=200 + i)
        records.append(
            {"file_name": path.name, "path": path, "width": 64, "height": 64, "boxes": []}
        )
        twin = tmp_path / f"pair-{i}b.jpg"
        shutil.copy(path, twin)
        records.append(
            {"file_name": twin.name, "path": twin, "width": 64, "height": 64, "boxes": []}
        )

    train, val, groups = prep.split_train_val(records)
    train_names = {r["file_name"] for r in train}
    val_names = {r["file_name"] for r in val}
    assert train_names.isdisjoint(val_names)
    for group in groups:
        members = set(group)
        assert not (members & train_names and members & val_names), group


def test_write_dataset_yaml_keeps_class_code_order(tmp_path: Path) -> None:
    """labels order is a contract with species_dict; the yaml must follow CLASS_CODES."""
    prep.write_dataset_yaml(tmp_path)
    text = (tmp_path / "dataset.yaml").read_text(encoding="utf-8")
    for index, code in enumerate(prep.CLASS_CODES):
        assert f"  {index}: {code}" in text
