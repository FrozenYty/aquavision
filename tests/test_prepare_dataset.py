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


def test_seeded_split_counts_and_determinism() -> None:
    """The real group sizes (6455 singles, 106 pairs, one four) deal exactly 5671 / 1000."""
    groups = []
    index = 0
    for _ in range(6455):
        groups.append([f"f-{index}"])
        index += 1
    for _ in range(106):
        groups.append([f"f-{index}", f"f-{index + 1}"])
        index += 2
    groups.append([f"f-{index + i}" for i in range(4)])
    index += 4
    assert index == 6671

    first = prep.split_groups(groups, target=1000, seed=prep.DEFAULT_SEED)
    second = prep.split_groups(groups, target=1000, seed=prep.DEFAULT_SEED)
    assert first == second, "同一 seed 必须给出同一划分"
    assert len(first) == 1000
    assert index - len(first) == 5671
    assert 5671 + 1000 + 1111 == 7782


def test_write_test_manifest_formats_and_sorts(tmp_path: Path) -> None:
    out = tmp_path / "dataset"
    images = out / "test" / "images"
    images.mkdir(parents=True)
    records = []
    for stem in ("2", "1"):
        source = tmp_path / f"{stem}.jpg"
        make_image(source, seed=int(stem))
        shutil.copy(source, images / f"test-{stem}.jpg")
        records.append(
            {"file_name": f"{stem}.jpg", "path": source, "width": 64, "height": 64, "boxes": []}
        )

    count = prep.write_test_manifest(records, out, tmp_path / "test-manifest.txt")

    assert count == 2
    lines = (tmp_path / "test-manifest.txt").read_text(encoding="utf-8").splitlines()
    assert lines == sorted(lines)
    for line in lines:
        name, digest = line.split()
        assert name in {"test-1.jpg", "test-2.jpg"}
        assert len(digest) == 32
        int(digest, 16)


def test_committed_test_manifest_is_frozen() -> None:
    manifest = Path(__file__).resolve().parent.parent / "test-manifest.txt"
    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1111
    assert lines == sorted(lines)
    names = set()
    for line in lines:
        name, digest = line.split()
        assert name.startswith("test-") and name.endswith(".jpg")
        assert len(digest) == 32
        int(digest, 16)
        names.add(name)
    assert len(names) == 1111
