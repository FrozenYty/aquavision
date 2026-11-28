"""Measure the performance budget: single-frame latency and the list routes' P90 (P3-10, AC-34).

**What is measured.** Two budgets, both from the requirements:

- *Single-frame latency* - NFR-U-09 and AC-34: one frame end to end within 1,500 ms, median and P90
  over 100 timings. The frame is timed through the real route
  ``POST /api/detect/frames/{frame_id}``, so pre-processing, inference, NMS, the database writes and
  the JSON encoding all count. It needs the delivered weights under ``models/``; when no detector
  can be built the run names the reason and exits 3 instead of printing a pass.
- *List latency* - NFR-P-01: P90 within 2,000 ms on the paginated list routes
  (``/api/frames``, ``/api/tasks``, ``/api/hard-samples``, ``/api/reports``). Each route is warmed
  once and then timed over ``--requests`` calls. ``/api/datasets`` is a list route but not
  paginated, so it is named as skipped rather than measured.

**The design capacity the numbers are measured at.** NFR-P-05 defines it: a deployment designed for
100,000 image assets and 5,000,000 detected objects, with paged and filtered queries on the large
tables inside 3 s. Those are the defaults of ``--frames`` and ``--objects``; the script also seeds the
200 batch tasks of 500 frames and their 100,000 ``detect_task_item`` rows, and three sites'
``frames/<site>/<day>/`` folders. The 30-day operating envelope of one deployment - three monitoring
points x 500 accepted frames per point per day x 30 days = 45,000 frames, ~135,000 boxes - is the
smaller routine-load check: ``--frames 45000 --objects 135000``.

**How it stays offline and reproducible.** Everything runs in one process against a throwaway SQLite
database the script creates under the data root (``data/tmp/measure/`` by default), seeds with bulk
``executemany`` inserts against the schema ``app.models.Base.metadata`` declares (no hand-written
DDL), and deletes afterwards unless ``--keep`` is given. No camera, no network, no uvicorn: the routes
are called through FastAPI's ``TestClient``, which runs the application's own lifespan - the same
detector loading a deployment does. A 640x480 JPEG is generated with OpenCV under the scratch data
root, so no repository image is needed. The run prints the interpreter and
``torch.cuda.is_available()``, so a CPU measurement is never read as a GPU one.

**Percentiles** are nearest-rank: sort the samples and take the ``ceil(fraction * n)``-th smallest,
which is monotonic in the fraction. **Budgets** are compared per route and per budget, and a
``PASS``/``FAIL`` line is printed for each.

Exit codes: 0 every measured budget passes; 1 a measured budget misses or a route answers a non-zero
envelope (a failure, not a timing); 3 the environment cannot run a requested part (the reason is
named); 2 the run could not set itself up (bad arguments, an unwritable scratch path). A measured
miss (1) outranks an unavailable part (3): a red budget is actionable even when the other half cannot
run. ``--list-only`` and ``--detect-only`` measure one half; a part that was not requested is not a
missing measurement. ``--list-budget-ms`` and ``--frame-budget-ms`` override the two budgets, which is
how ``tests/test_measure_performance.py`` proves the check can fail.

Usage:
    python scripts/measure_performance.py
    python scripts/measure_performance.py --frames 45000 --objects 135000 --requests 30 --timings 100
    python scripts/measure_performance.py --list-only
    python scripts/measure_performance.py --keep
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import math
import os
import platform
import shutil
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = REPO_ROOT / "server"
SCRIPTS_DIR = REPO_ROOT / "scripts"

#: NFR-P-05's design capacity: the database a deployment is expected to carry.
DESIGN_FRAMES = 100_000
DESIGN_OBJECTS = 5_000_000

#: The 30-day operating envelope of one deployment, the smaller routine-load check.
DAYS = 30
POINTS = ("A1", "A2", "A3")
BATCH = 500
BOXES_PER_FRAME = 3
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

ADMIN = "admin"
ADMIN_PASSWORD = "measure-password"

#: The requirements' budgets (NFR-P-01, NFR-U-09) and AC-34's re-statement of them.
LIST_BUDGET_MS = 2000.0
FRAME_BUDGET_MS = 1500.0

#: Every paginated list route the contract serves. Order is the order the tables are printed in.
LIST_ROUTES = (
    ("frames", "/api/frames?page=1&size=24"),
    ("tasks", "/api/tasks?page=1&size=24"),
    ("hard samples", "/api/hard-samples?page=1&size=24"),
    ("reports", "/api/reports?page=1&size=24"),
)

#: A list route the requirement might be read to cover, but which has no page/size to measure.
SKIPPED_LIST_ROUTES = (
    (
        "/api/datasets",
        "a list route but not paginated: it returns every snapshot, so there is no page/size to time",
    ),
)

#: Written into a scratch directory this script may clear; a directory without it is left alone.
MARKER = ".measure-scratch"

SPECIES_CODES = ("holothurian", "strongylocentrotus", "chlamys", "asterias")


class SetupFailed(RuntimeError):
    """The run cannot create its throwaway database or image (exit code 2)."""


class MeasurementFailed(RuntimeError):
    """A route answered a non-zero envelope, or answered something that is not one."""


def percentile(values: list[float], fraction: float) -> float:
    """The nearest-rank percentile: monotonic in ``fraction``, no interpolation.

    ``ceil(fraction * n)`` is the rank, so the result is always one of the samples: a P90 of a
    hundred timings is the 90th slowest, which is what a reader expects and what a second
    implementation cannot disagree with.
    """
    if not values:
        raise ValueError("no measurements")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(f"fraction must be in [0, 1], got {fraction}")
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def p90(values: list[float]) -> float:
    return percentile(values, 0.9)


def median(values: list[float]) -> float:
    return percentile(values, 0.5)


def relative(path: Path) -> str:
    """Paths are printed relative to the repository root, so the output stays portable."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _frame_key(index: int) -> tuple[datetime, str, str]:
    """The (captured_at, frame_id, point_code) of the index-th seeded frame.

    The frame id follows data model §3.3, ``YYYYMMDDTHHMMSS-mmmm``. The suffix is the point number
    plus the frame's serial within its point and day, which is unique because the three components
    of ``index`` (day, point, serial) are.
    """
    today = datetime.now(UTC).date()
    day = today - timedelta(days=DAYS - 1 - index % DAYS)
    point = POINTS[(index // DAYS) % len(POINTS)]
    serial = index // (DAYS * len(POINTS))
    captured = datetime.combine(day, datetime.min.time()) + timedelta(seconds=serial * 28)
    frame_id = f"{day:%Y%m%d}T{captured:%H%M%S}-{POINTS.index(point) + 1}{serial:03d}"
    return captured, frame_id, point


def _chunks(rows, size: int = 5_000):
    """Yield the row dicts in bounded batches, so 135,000 inserts do not sit in memory at once."""
    batch: list[dict[str, object]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _insert(connection, table, rows) -> None:
    """Bulk-insert rows with one ``executemany`` per batch: the seeding must not cost an hour."""
    for batch in _chunks(rows):
        connection.execute(table.insert(), batch)


def _media_rows(frames: int, image_bytes: int):
    for index in range(frames):
        captured, frame_id, point = _frame_key(index)
        yield {
            "asset_id": index + 1,
            "frame_id": frame_id,
            "session_id": f"s-{captured:%Y%m%d}-{point}",
            "point_code": point,
            "file_path": "frame.jpg",
            "thumb_path": None,
            "file_size": image_bytes,
            "file_hash": f"{index:064x}",
            "captured_at": captured,
            "width": FRAME_WIDTH,
            "height": FRAME_HEIGHT,
            "exposure_us": 8_000,
            "gain_db": 1.5,
            "quality_score": 85,
            "quality_flag": 0,
            "is_retake": 0,
        }


def _object_rows(objects: int, frames: int):
    for index in range(objects):
        frame_index = index % frames
        _, frame_id, _ = _frame_key(frame_index)
        # The review states a 30-day archive holds: most boxes untouched, a fifth confirmed, a few
        # modified, a sliver rejected. A quarter of the modified ones is flagged as hard examples,
        # so /api/hard-samples has a pool to group.
        review = 0 if index % 100 < 70 else 1 if index % 100 < 90 else 2 if index % 100 < 97 else 3
        hard = index % 50 == 0 and review != 3
        yield {
            "task_id": frame_index // BATCH + 1,
            "asset_id": frame_index + 1,
            "frame_id": frame_id,
            "class_code": SPECIES_CODES[index % len(SPECIES_CODES)],
            "confidence": 0.5 + (index % 400) / 1000.0,
            "x": (index % 40) / 100.0,
            "y": ((index // 40) % 40) / 100.0,
            "w": 0.10 + (index % 10) / 100.0,
            "h": 0.08 + (index % 7) / 100.0,
            "track_id": None,
            "is_manual": 1 if review == 2 else 0,
            "review_status": review,
            "version_no": 2 if review in (1, 2) else 1,
            "hard_flag": 1 if hard else 0,
            "hard_reason": ("low_conf", "modified", "inconsistent")[index % 3] if hard else None,
            "reviewed_by": 1 if review in (1, 2, 3) else None,
            "reviewed_at": None,
        }


def _objects_in_task(start: int, count: int, frames: int, objects: int) -> int:
    """How many seeded boxes fall on the frames ``[start, start + count)`` of a task."""
    return sum(
        (objects - 1 - frame) // frames + 1
        for frame in range(start, min(start + count, frames))
        if frame < objects
    )


def _task_rows(frames: int, objects: int):
    tasks = math.ceil(frames / BATCH)
    created = datetime.now(UTC).replace(tzinfo=None)
    for index in range(tasks):
        start = index * BATCH
        count = min(BATCH, frames - start)
        yield {
            "task_id": index + 1,
            "task_code": f"DT{created:%y%m%d}-{index + 1:03d}",
            "task_type": 2,
            "model_version_id": None,
            "asset_count": count,
            "conf_thr": 0.5,
            "iou_thr": 0.45,
            "max_det": 100,
            "class_filter": None,
            "status": 2,
            "progress": 100,
            "obj_count": _objects_in_task(start, count, frames, objects),
            "error_msg": None,
            "created_by": 1,
            "created_at": created,
            "finished_at": created,
        }


def _task_item_rows(frames: int, objects: int):
    boxes = max(1, objects // frames)
    for frame_index in range(frames):
        captured, _, _ = _frame_key(frame_index)
        yield {
            "task_id": frame_index // BATCH + 1,
            "asset_id": frame_index + 1,
            "state": 2,
            "box_count": boxes,
            "claimed_at": captured,
            "finished_at": captured + timedelta(minutes=1),
        }


def _report_rows():
    """One report per site per operating day: 90 rows, the archive a 30-day deployment holds."""
    today = datetime.now(UTC).date()
    start_of_day = datetime.min.time()
    for index in range(DAYS * len(POINTS)):
        day = today - timedelta(days=DAYS - 1 - index // len(POINTS))
        period_start = datetime.combine(day, start_of_day) + timedelta(hours=8)
        yield {
            "report_id": index + 1,
            "report_code": f"RP{day:%y%m%d}-{index + 1:03d}",
            "period_start": period_start,
            "period_end": period_start + timedelta(hours=8),
            "template": "standard" if index % 2 else "brief",
            "basis": "reviewed" if index % 3 else "raw",
            "model_version_id": None,
            "file_path": None,
            "status": 1,
            "error_msg": None,
            "created_by": 1,
            "created_at": period_start,
        }


def _species_rows():
    from app.seed import SPECIES_SEED

    for index, row in enumerate(SPECIES_SEED):
        yield {
            "species_id": index + 1,
            "class_code": row["class_code"],
            "cn_name": row["cn_name"],
            "latin_name": row.get("latin_name"),
            "category": row["category"],
            "conf_thr": 0.5,
            "in_stat": 1,
            "status": 1,
            "remark": row.get("remark"),
        }


def _user_rows():
    from app.security import hash_password

    hashed, salt = hash_password(ADMIN_PASSWORD)
    yield {
        "user_id": 1,
        "username": ADMIN,
        "phone": None,
        "email": None,
        "password_hash": hashed,
        "salt": salt,
        "role_code": "admin",
        "real_name": "Performance Measurement",
        "status": 1,
        "fail_count": 0,
        "locked_until": None,
        "last_login_at": None,
        "token_epoch": 0,
    }


def _model_row():
    """The one online model_version row, discovered the way a deployment registers it."""
    import register_model as delivered

    versions = delivered.delivered_versions()
    if not versions:
        return None
    version = versions[0]
    metrics = json.loads((version / "metrics.json").read_text(encoding="utf-8"))
    yield {
        "model_id": 1,
        "version_name": version.name,
        "weight_path": delivered.portable_path(version / "best.pt"),
        "labels_path": delivered.portable_path(version / "labels.txt"),
        "onnx_path": None,
        "dataset_ref": metrics.get("dataset_ref"),
        "map50": metrics.get("map50"),
        "map50_95": metrics.get("map50_95"),
        "recall_avg": metrics.get("recall_avg"),
        "fps": metrics.get("fps"),
        "params_m": metrics.get("params_m"),
        "status": 1,
        "is_online": 1,
    }


def seed(engine, frames: int, objects: int, image_bytes: int, with_model: bool) -> str | None:
    """Create the schema from the models and bulk-insert one database at design capacity."""
    import app.models  # noqa: F401 - importing registers the fourteen tables on Base.metadata
    from app.db import Base

    Base.metadata.create_all(engine)
    tables = Base.metadata.tables
    started = time.perf_counter()
    online = None
    with engine.begin() as connection:
        _insert(connection, tables["species_dict"], _species_rows())
        _insert(connection, tables["sys_user"], _user_rows())
        _insert(connection, tables["media_asset"], _media_rows(frames, image_bytes))
        _insert(connection, tables["detect_task"], _task_rows(frames, objects))
        _insert(connection, tables["detect_object"], _object_rows(objects, frames))
        _insert(connection, tables["detect_task_item"], _task_item_rows(frames, objects))
        _insert(connection, tables["report"], _report_rows())
        if with_model:
            row = next(_model_row(), None)
            if row is not None:
                connection.execute(tables["model_version"].insert(), [row])
                online = str(row["version_name"])
    elapsed = time.perf_counter() - started
    print(
        f"seeded {frames:,} media_asset, {objects:,} detect_object, "
        f"{math.ceil(frames / BATCH):,} detect_task, {frames:,} detect_task_item, "
        f"{DAYS * len(POINTS)} report rows in {elapsed:.1f}s"
    )
    return online


def write_frame_image(path: Path) -> int:
    """A real 640x480 JPEG under the scratch data root; no repository image is needed."""
    import cv2
    import numpy as np

    image = np.random.default_rng(0).integers(
        0, 255, (FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8
    )
    if not cv2.imwrite(str(path), image):
        raise SetupFailed(f"OpenCV could not write {path}")
    return path.stat().st_size


def prepare(args) -> dict[str, object]:
    """Create the throwaway tree, generate the frame image, and point the application at both."""
    data_root = Path(os.environ.get("AV_DATA_DIR") or "data")
    if not data_root.is_absolute():
        data_root = REPO_ROOT / data_root
    scratch = Path(args.scratch) if args.scratch else data_root / "tmp" / "measure"
    if not scratch.is_absolute():
        scratch = REPO_ROOT / scratch
    if scratch.exists():
        entries = {entry.name for entry in scratch.iterdir()}
        if entries and MARKER not in entries:
            raise SetupFailed(
                f"refusing to clear {relative(scratch)}: it holds no {MARKER} marker, "
                "so it is not a directory this script created"
            )
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    (scratch / MARKER).write_text(
        "throwaway scratch of scripts/measure_performance.py; deleted unless --keep\n",
        encoding="utf-8",
    )
    data_dir = scratch / "data"
    data_dir.mkdir()
    image = data_dir / "frame.jpg"
    image_bytes = write_frame_image(image)

    # Set before anything imports app.config: get_settings caches on its first read.
    os.environ["DB_DSN"] = f"sqlite:///{(scratch / 'measure.db').as_posix()}"
    os.environ["AV_DATA_DIR"] = str(data_dir)
    # The routes are called synchronously and the measurement must not share the CPU with a pool.
    os.environ["AV_WORKER_ENABLED"] = "0"
    # No hardware may answer here, whatever the shell happens to export.
    os.environ["AV_RIG_PORT"] = ""
    os.environ["AV_RIG_TRANSPORT"] = "serial"

    return {
        "scratch": scratch,
        "database": scratch / "measure.db",
        "data_dir": data_dir,
        "image": image,
        "image_bytes": image_bytes,
    }


def sign_in(client) -> str:
    """Sign in once as the administrator the seed wrote; the route reads the account from the DB."""
    response = client.post("/api/auth/login", json={"username": ADMIN, "password": ADMIN_PASSWORD})
    body = _checked(response, "POST", "/api/auth/login")
    return str(body["data"]["token"])


def _checked(response, method: str, path: str) -> dict[str, object]:
    """A response that is not a zero-code envelope is a failure, never a timing."""
    try:
        body = response.json()
    except ValueError as err:
        raise MeasurementFailed(
            f"{method} {path}: HTTP {response.status_code}, not an envelope"
        ) from err
    if not isinstance(body, dict):
        raise MeasurementFailed(f"{method} {path}: HTTP {response.status_code}, not an envelope")
    code = body.get("code")
    if response.status_code >= 400 or code != 0:
        raise MeasurementFailed(
            f"{method} {path}: HTTP {response.status_code}, code {code}, {body.get('message')}"
        )
    return body


def _timed_get(client, path: str, headers: dict[str, str]) -> float:
    started = time.perf_counter()
    response = client.get(path, headers=headers)
    elapsed = (time.perf_counter() - started) * 1000
    _checked(response, "GET", path)
    return elapsed


def measure_list(client, token: str, requests: int) -> list[dict[str, object]]:
    """One warm-up request, then ``requests`` timed GETs, per paginated list route."""
    headers = {"Authorization": f"Bearer {token}"}
    results: list[dict[str, object]] = []
    for label, path in LIST_ROUTES:
        try:
            _checked(client.get(path, headers=headers), "GET", path)
            samples = [_timed_get(client, path, headers) for _ in range(requests)]
        except MeasurementFailed as err:
            results.append({"name": label, "route": path, "error": str(err)})
            continue
        results.append(
            {
                "name": label,
                "route": path,
                "requests": requests,
                "median_ms": median(samples),
                "p90_ms": p90(samples),
            }
        )
    return results


def measure_single_frame(client, token: str, frame_id: str, timings: int) -> dict[str, object]:
    """One warm-up POST, then ``timings`` end-to-end timings of the real detection route."""
    headers = {"Authorization": f"Bearer {token}"}
    path = f"/api/detect/frames/{frame_id}"
    try:
        _checked(client.post(path, headers=headers), "POST", path)
        samples: list[float] = []
        reported: list[float] = []
        for _ in range(timings):
            started = time.perf_counter()
            response = client.post(path, headers=headers)
            samples.append((time.perf_counter() - started) * 1000)
            body = _checked(response, "POST", path)
            reported.append(float(body["data"]["latency_ms"]))
    except MeasurementFailed as err:
        return {"error": str(err)}
    return {
        "route": path,
        "frame_id": frame_id,
        "timings": timings,
        "median_ms": median(samples),
        "p90_ms": p90(samples),
        "reported_median_ms": median(reported),
    }


def environment(measure_frames: bool) -> dict[str, object]:
    """The interpreter and the device, so a CPU number is never mistaken for a GPU one."""
    info: dict[str, object] = {
        "python": f"{platform.python_implementation()} {platform.python_version()}",
        "executable": sys.executable,
        "platform": platform.platform(),
    }
    if not measure_frames:
        info.update(torch=None, cuda_available=None, device="not checked (list-only)")
        return info
    try:
        import torch
    except ImportError:
        info.update(torch=None, cuda_available=None, device="cpu (torch is not installed)")
        return info
    cuda = bool(torch.cuda.is_available())
    info.update(torch=torch.__version__, cuda_available=cuda, device="cuda:0" if cuda else "cpu")
    return info


def _print_table(results: list[dict[str, object]], args) -> None:
    print()
    print(f"list endpoints (GET; {args.requests} timings after one warm-up, page=1&size=24)")
    print(f"  {'route':<38} {'median':>9} {'p90':>9} {'budget':>8}  result")
    for row in results:
        if "error" in row:
            print(f"  {row['route']:<38} {'-':>9} {'-':>9} {args.list_budget_ms:>8.0f}  FAIL")
            print(f"    {row['error']}")
            continue
        verdict = "PASS" if float(row["p90_ms"]) <= args.list_budget_ms else "FAIL"
        print(
            f"  {row['route']:<38} {float(row['median_ms']):>9.1f} "
            f"{float(row['p90_ms']):>9.1f} {args.list_budget_ms:>8.0f}  {verdict}"
        )
    for path, why in SKIPPED_LIST_ROUTES:
        print(f"  skipped {path}: {why}")


def _print_frame(frame: dict[str, object], args, info: dict[str, object]) -> None:
    print()
    print(f"single frame (POST {frame['route']}; {args.timings} timings after one warm-up)")
    if "error" in frame:
        print(f"  FAIL {frame['error']}")
        return
    print(
        f"  median {float(frame['median_ms']):.1f} ms, p90 {float(frame['p90_ms']):.1f} ms "
        f"over {frame['timings']} requests (device {info['device']})"
    )
    print(
        f"  the route's own inference timer reports a median of "
        f"{float(frame['reported_median_ms']):.1f} ms"
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        runtime = prepare(args)
    except SetupFailed as err:
        print(f"FAILED: {err}", file=sys.stderr)
        return 2

    print("AquaVision performance measurement (PLAN P3-10, AC-34)")
    print()
    print(
        f"design capacity: {args.frames:,} image assets, {args.objects:,} detect_object rows, "
        f"{math.ceil(args.frames / BATCH):,} detect_task rows, {args.frames:,} detect_task_item rows"
    )
    print(
        f"  NFR-P-05: 100,000 assets and 5,000,000 objects are the defaults; the 30-day operating"
        f" envelope ({len(POINTS)} points x {BATCH} frames/day x {DAYS} days) is"
        f" --frames {DAYS * len(POINTS) * BATCH:,} --objects"
        f" {DAYS * len(POINTS) * BATCH * BOXES_PER_FRAME:,}"
    )
    print(f"scratch: {relative(runtime['scratch'])} (throwaway; deleted unless --keep)")
    print(f"database: {relative(runtime['database'])}")
    print(f"frame image: {relative(runtime['image'])} ({FRAME_WIDTH}x{FRAME_HEIGHT}, generated)")

    code = 1
    try:
        code = _run(args, runtime)
    except Exception as err:  # noqa: BLE001 - the reason belongs in the output, not a traceback
        print(file=sys.stderr)
        print(f"FAILED: {type(err).__name__}: {err}", file=sys.stderr)
    finally:
        if args.keep:
            print()
            print(f"scratch kept: {relative(runtime['scratch'])}")
        else:
            _remove(runtime["scratch"])
            print()
            print(f"scratch removed: {relative(runtime['scratch'])}")
    return code


def _run(args, runtime: dict[str, object]) -> int:
    measure_lists = not args.detect_only
    measure_frames = not args.list_only

    # The script runs from anywhere; the application package lives under server/. Imported here, not
    # at module scope, so the interpreter's path is only touched when a run needs it.
    sys.path.insert(0, str(SERVER_DIR))
    sys.path.insert(0, str(SCRIPTS_DIR))

    from app.config import get_settings
    from app.db import engine_from_dsn

    get_settings.cache_clear()
    settings = get_settings()
    engine = engine_from_dsn(settings.db_dsn)
    try:
        seed(
            engine,
            args.frames,
            args.objects,
            int(runtime["image_bytes"]),
            with_model=measure_frames,
        )
    finally:
        engine.dispose()

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    if not measure_frames:
        # A list-only run registers no online model on purpose; the application's "detection
        # unavailable" warning is about the missing half, not about a broken environment.
        logging.getLogger("aquavision").setLevel(logging.ERROR)
    # starlette's test client warns that a future release will need `httpx2`; that is upstream's
    # packaging note, not part of the measurement, and it would be pasted into the PR with the table.
    import warnings

    warnings.filterwarnings(
        "ignore", message="Using `httpx` with `starlette.testclient` is deprecated"
    )
    from app.main import create_app
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    client.__enter__()
    try:
        detector = getattr(client.app.state, "detector", None)
        print()
        if measure_frames:
            if detector is None:
                print(f"detector: unavailable - {client.app.state.detector_error}")
            else:
                print(f"detector: {detector.version_name} (online model_version row)")
        token = sign_in(client)
        token = str(token)
        print(f"signed in as {ADMIN} (throwaway account)")

        info = environment(measure_frames)
        print()
        print(f"interpreter: {info['python']} - {info['executable']}")
        if measure_frames:
            print(
                f"torch: {info['torch'] or 'not installed'}, "
                f"torch.cuda.is_available(): {info['cuda_available']}, device: {info['device']}"
            )
            if info["cuda_available"] is False:
                print(
                    "note: no CUDA device answered, so this is a CPU measurement; AC-34 asks for "
                    "the deployment GPU, and a CPU pass is a lower bound, not the acceptance run"
                )
        else:
            print("torch: not imported (--list-only); no single-frame number is claimed")

        list_results = measure_list(client, token, args.requests) if measure_lists else None
        frame_result = None
        frame_unavailable = None
        if measure_frames:
            if detector is None:
                frame_unavailable = (
                    getattr(client.app.state, "detector_error", None)
                    or "no detector could be built"
                )
            else:
                frame_result = measure_single_frame(client, token, _frame_key(0)[1], args.timings)
    finally:
        client.__exit__(None, None, None)
        client.app.state.engine.dispose()

    failures: list[str] = []
    unavailable: list[str] = []
    list_pass = True
    frame_median_pass = True
    frame_p90_pass = True

    if list_results is not None:
        _print_table(list_results, args)
        broken = [row for row in list_results if "error" in row]
        if broken:
            list_pass = False
            failures.append(f"{len(broken)} list route(s) answered a non-zero envelope")
        else:
            worst = max(float(row["p90_ms"]) for row in list_results)
            list_pass = worst <= args.list_budget_ms
            print()
            print(
                f"{'PASS' if list_pass else 'FAIL'}  list p90 {worst:.1f} ms (worst route) "
                f"<= {args.list_budget_ms:.0f} ms  (NFR-P-01)"
            )
            if not list_pass:
                failures.append("list latency budget")

    if frame_result is not None:
        _print_frame(frame_result, args, info)
        if "error" in frame_result:
            failures.append("single-frame measurement answered a non-zero envelope")
        else:
            median_ms = float(frame_result["median_ms"])
            p90_ms = float(frame_result["p90_ms"])
            frame_median_pass = median_ms <= args.frame_budget_ms
            frame_p90_pass = p90_ms <= args.frame_budget_ms
            print()
            print(
                f"{'PASS' if frame_median_pass else 'FAIL'}  single-frame median {median_ms:.1f} ms "
                f"<= {args.frame_budget_ms:.0f} ms  (NFR-U-09)"
            )
            print(
                f"{'PASS' if frame_p90_pass else 'FAIL'}  single-frame p90 {p90_ms:.1f} ms "
                f"<= {args.frame_budget_ms:.0f} ms  (AC-34)"
            )
            if not (frame_median_pass and frame_p90_pass):
                failures.append("single-frame latency budget")
    elif frame_unavailable is not None:
        print()
        print(f"single frame: cannot run - {frame_unavailable}")
        unavailable.append(f"single-frame latency ({frame_unavailable})")

    if not measure_frames:
        print()
        print("single-frame latency: not requested (--list-only), so no budget is claimed")

    single_frame: dict[str, object] | None = frame_result
    if single_frame is None and frame_unavailable is not None:
        single_frame = {"unavailable": frame_unavailable}
    summary = {
        "capacity": {
            "frames": args.frames,
            "objects": args.objects,
            "tasks": math.ceil(args.frames / BATCH),
            "task_items": args.frames,
            "days": DAYS,
            "points": list(POINTS),
            "frames_per_point_per_day": BATCH,
        },
        "requests": args.requests,
        "timings": args.timings,
        "environment": info,
        "list": list_results,
        "single_frame": single_frame,
        "budgets_ms": {
            "list_p90": args.list_budget_ms,
            "frame_median": args.frame_budget_ms,
            "frame_p90": args.frame_budget_ms,
        },
        "pass": None,
    }

    if failures:
        code = 1
        print()
        print("summary: some measured budgets did not pass")
    elif unavailable:
        code = 3
        print()
        print(f"summary: cannot run a requested part - {'; '.join(unavailable)} (exit 3)")
    else:
        code = 0
        print()
        print("summary: every measured budget passed")
    summary["pass"] = code == 0
    summary["exit_code"] = code
    print()
    print("performance summary: " + json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return code


def _remove(directory: Path) -> None:
    """Delete the throwaway tree, waiting for a pooled SQLite handle to be released."""
    for attempt in range(6):
        try:
            shutil.rmtree(directory)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if attempt == 5:
                break
            gc.collect()
            time.sleep(0.2)
    shutil.rmtree(directory)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frames", type=int, default=DESIGN_FRAMES, help="frames to seed (100,000, NFR-P-05)"
    )
    parser.add_argument(
        "--objects",
        type=int,
        default=DESIGN_OBJECTS,
        help="detect_object rows to seed (5,000,000, NFR-P-05)",
    )
    parser.add_argument(
        "--requests", type=int, default=30, help="timed requests per list route after one warm-up"
    )
    parser.add_argument(
        "--timings", type=int, default=100, help="timed detections after one warm-up"
    )
    parser.add_argument(
        "--scratch",
        default=None,
        help="throwaway directory; defaults to <data root>/tmp/measure",
    )
    parser.add_argument(
        "--keep", action="store_true", help="keep the scratch database and frame image"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list-only", action="store_true", help="measure only the list endpoints")
    mode.add_argument(
        "--detect-only", action="store_true", help="measure only single-frame latency"
    )
    parser.add_argument(
        "--list-budget-ms", type=float, default=LIST_BUDGET_MS, help="list p90 budget (2,000 ms)"
    )
    parser.add_argument(
        "--frame-budget-ms", type=float, default=FRAME_BUDGET_MS, help="frame median/p90 budget"
    )
    args = parser.parse_args(argv)
    if args.frames < 1:
        parser.error("--frames must be at least 1")
    if args.objects < 1:
        parser.error("--objects must be at least 1")
    if args.requests < 1:
        parser.error("--requests must be at least 1")
    if args.timings < 1:
        parser.error("--timings must be at least 1")
    if args.list_budget_ms <= 0 or args.frame_budget_ms <= 0:
        parser.error("budgets must be positive")
    return args


if __name__ == "__main__":
    raise SystemExit(main())
