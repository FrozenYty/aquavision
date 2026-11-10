"""Prepare the AquaVision training dataset from the raw DUO release (P0-01).

Reads the COCO files under data/raw/DUO/DUO/, cleans them, groups near-identical
frames so they never cross split boundaries, and writes a YOLO dataset,
data/dataset-stats.json and the frozen test manifest.

DUO ships without video or sequence ids and renames frames to 1.jpg..N.jpg, so
"split by video" is implemented with perceptual hashing: frames within a small
hamming distance are treated as one group and always stay in the same split.
The official DUO test set is kept untouched (1111 images >= the required 500).
The remaining 6671 images are dealt 85:15 into train/validation by group; --seed
decides the group order, so the same seed reproduces the same split. The test
manifest lists `filename md5` for the frozen 1111 images; the images stay out of
git.

Usage: python scripts/prepare_dataset.py [--seed 42]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import cv2

# Contract with species_dict (docs/data-model-en.md): order must match labels.txt.
CLASS_CODES = ["holothurian", "strongylocentrotus", "chlamys", "asterias"]
DUO_TO_INDEX = {"holothurian": 0, "echinus": 1, "scallop": 2, "starfish": 3}

VAL_RATIO = 0.15
DEFAULT_SEED = 42
MIN_TEST_IMAGES = 500
HAMMING_MAX = 3  # frames this close are treated as one group
HASH_BANDS = 4  # 64-bit hash split into 16-bit bands for fast lookup


def dhash64(path: Path) -> int:
    """64-bit difference hash of an image."""
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    img = cv2.resize(img, (9, 8))
    bits = (img[:, 1:] > img[:, :-1]).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def group_frames(hashes: dict[str, int]) -> list[list[str]]:
    """Union-find clustering of frames whose hashes differ by <= HAMMING_MAX."""
    parent = {name: name for name in hashes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    bands: list[dict[int, list[str]]] = [defaultdict(list) for _ in range(HASH_BANDS)]
    for name, value in hashes.items():
        for i in range(HASH_BANDS):
            bands[i][(value >> (i * 16)) & 0xFFFF].append(name)

    for band in bands:
        for members in band.values():
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, b = members[i], members[j]
                    if hamming(hashes[a], hashes[b]) <= HAMMING_MAX:
                        ra, rb = find(a), find(b)
                        if ra != rb:
                            parent[rb] = ra

    groups: dict[str, list[str]] = defaultdict(list)
    for name in hashes:
        groups[find(name)].append(name)
    return list(groups.values())


def clean_boxes(annotations: list[dict], width: int, height: int) -> tuple[list[dict], int]:
    """Drop ignored/crowd boxes, clamp to image bounds, drop degenerate boxes."""
    kept, dropped = [], 0
    for ann in annotations:
        if ann.get("ignore") or ann.get("iscrowd"):
            dropped += 1
            continue
        x, y, w, h = ann["bbox"]
        x, y = max(0.0, x), max(0.0, y)
        w, h = min(w, width - x), min(h, height - y)
        if w <= 1 or h <= 1:
            dropped += 1
            continue
        kept.append({"category_id": ann["category_id"], "bbox": [x, y, w, h]})
    return kept, dropped


def load_split(raw: Path, split: str, image_dir: Path):
    """Load one COCO split; return per-image records with cleaned boxes."""
    data = json.loads((raw / "annotations" / f"instances_{split}.json").read_text("utf-8"))
    cat_map = {c["id"]: DUO_TO_INDEX[c["name"]] for c in data["categories"]}
    by_image: dict[int, list[dict]] = defaultdict(list)
    for ann in data["annotations"]:
        by_image[ann["image_id"]].append(ann)

    records, dropped_ann, unreadable = [], 0, 0
    for image in data["images"]:
        path = image_dir / image["file_name"]
        if cv2.imread(str(path)) is None:
            unreadable += 1
            continue
        boxes, dropped = clean_boxes(by_image[image["id"]], image["width"], image["height"])
        dropped_ann += dropped
        records.append(
            {
                "file_name": image["file_name"],
                "path": path,
                "width": image["width"],
                "height": image["height"],
                "boxes": [
                    {"class_index": cat_map[b["category_id"]], "bbox": b["bbox"]} for b in boxes
                ],
            }
        )
    return records, dropped_ann, unreadable


def split_groups(groups: list[list[str]], target: int, seed: int) -> set[str]:
    """Deal whole hash groups into validation until the target is reached.

    The seed shuffles groups within each size bucket. Largest groups still go first, so a big sequence
    stays atomic and the target is not overshot by a small group; the seed decides the ties, which is
    what makes the split reproducible without fixing it to one arbitrary input order.
    """
    buckets: dict[int, list[list[str]]] = defaultdict(list)
    for group in groups:
        buckets[len(group)].append(group)
    rng = random.Random(seed)
    order: list[list[str]] = []
    for size in sorted(buckets, reverse=True):
        bucket = buckets[size]
        rng.shuffle(bucket)
        order.extend(bucket)

    val_names: set[str] = set()
    for group in order:
        if len(val_names) >= target:
            break
        val_names.update(group)
    return val_names


def split_train_val(
    records: list[dict], seed: int = DEFAULT_SEED
) -> tuple[list[dict], list[dict], list[list[str]]]:
    """Group by hash, then deal whole groups into val until VAL_RATIO is reached."""
    hashes = {r["file_name"]: dhash64(r["path"]) for r in records}
    groups = group_frames(hashes)
    target = int(len(records) * VAL_RATIO)
    val_names = split_groups(groups, target, seed)

    train = [r for r in records if r["file_name"] not in val_names]
    val = [r for r in records if r["file_name"] in val_names]
    return train, val, groups


def write_split(records: list[dict], out: Path, name: str) -> dict:
    """Copy images and write YOLO label files; return per-class box counts."""
    img_dir, lbl_dir = out / name / "images", out / name / "labels"
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)
    counts: Counter[int] = Counter()
    for rec in records:
        stem = Path(rec["file_name"]).stem
        shutil.copy(rec["path"], img_dir / f"{name}-{stem}.jpg")
        lines = []
        for box in rec["boxes"]:
            x, y, w, h = box["bbox"]
            cx, cy = (x + w / 2) / rec["width"], (y + h / 2) / rec["height"]
            lines.append(
                f"{box['class_index']} {cx:.6f} {cy:.6f} {w / rec['width']:.6f} {h / rec['height']:.6f}"
            )
            counts[box["class_index"]] += 1
        (lbl_dir / f"{name}-{stem}.txt").write_text("\n".join(lines), encoding="utf-8")
    return {
        "images": len(records),
        "boxes": sum(counts.values()),
        "per_class_boxes": {CLASS_CODES[i]: counts.get(i, 0) for i in range(len(CLASS_CODES))},
    }


def write_test_manifest(records: list[dict], out: Path, path: Path) -> int:
    """Write `filename md5` for the frozen test split, one line per image.

    The filenames are the ones written under `<out>/test/images`, so the manifest is checked against
    the files the evaluation reads. The images themselves stay out of git.
    """
    lines = []
    for rec in sorted(records, key=lambda r: r["file_name"]):
        name = f"test-{Path(rec['file_name']).stem}.jpg"
        digest = hashlib.md5((out / "test" / "images" / name).read_bytes()).hexdigest()
        lines.append(f"{name} {digest}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def write_dataset_yaml(out: Path) -> None:
    names = "\n".join(f"  {i}: {code}" for i, code in enumerate(CLASS_CODES))
    (out / "dataset.yaml").write_text(
        f"path: {out.resolve().as_posix()}\n"
        "train: train/images\nval: val/images\ntest: test/images\n"
        f"names:\n{names}\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path("data/raw/DUO/DUO"))
    parser.add_argument("--out", type=Path, default=Path("data/dataset"))
    parser.add_argument("--stats", type=Path, default=Path("data/dataset-stats.json"))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--manifest", type=Path, default=Path("test-manifest.txt"))
    args = parser.parse_args()

    train_all, dropped_ann, unreadable = load_split(
        args.raw, "train", args.raw / "images" / "train"
    )
    test, dropped_ann_t, unreadable_t = load_split(args.raw, "test", args.raw / "images" / "test")
    if len(test) < MIN_TEST_IMAGES:
        raise SystemExit(f"test set has {len(test)} images, need >= {MIN_TEST_IMAGES}")

    train, val, groups = split_train_val(train_all, seed=args.seed)
    stats = {
        "source": "DUO (github.com/chongweiliu/DUO), COCO instances",
        "class_codes": CLASS_CODES,
        "split": {
            "rule": "85:15 over the non-test images; official test frozen",
            "seed": args.seed,
        },
        "splits": {
            "train": write_split(train, args.out, "train"),
            "val": write_split(val, args.out, "val"),
            "test": write_split(test, args.out, "test"),
        },
        "cleaning": {
            "unreadable_images_dropped": unreadable + unreadable_t,
            "ignored_or_degenerate_boxes_dropped": dropped_ann + dropped_ann_t,
        },
        "grouping": {
            "method": f"dhash64, hamming <= {HAMMING_MAX}",
            "groups": len(groups),
            "largest_group": max(len(g) for g in groups),
        },
        "manifest": {
            "path": str(args.manifest),
            "lines": write_test_manifest(test, args.out, args.manifest),
        },
    }
    stats["total_images"] = sum(split["images"] for split in stats["splits"].values())
    write_dataset_yaml(args.out)
    args.stats.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    print(f"Wrote {args.manifest}")
    print(f"Wrote {args.stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
