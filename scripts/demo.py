"""Run the AquaVision slice end to end on a throwaway database (P4-12).

A rehearsal used to be a person clicking through thirteen pages from memory, and the numbers in the
metrics table came from whoever remembered to write them down. One command now does the slice and
prints the numbers: create a fresh database through `scripts/init_db.py`, register the delivered
version under `models/`, sign in, capture one frame through the real capture route, run it through the
real detection route, generate one report and read one statistics figure. Every step is timed.

The camera belongs to the client, so the driver supplies the image. A camera is used when one answers;
otherwise a recorded frame from `data/frames/`; otherwise one generated in memory. Which of the three
it was is printed, so the output never implies a live shot that was not taken.

Detection needs ultralytics and torch. Without them the driver says so plainly and leaves the box
counts absent - it never invents a number, and the rest of the slice still runs.

The development database is never touched: the run gets a fresh one under `data/tmp/`, and the path is
printed so the numbers can be checked afterwards.

Usage:
    .venv-infer\\Scripts\\python.exe scripts/demo.py
    python scripts/demo.py
"""

from __future__ import annotations

import base64
import importlib.util
import json
import logging
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parent.parent
# The application package and the seeding/registration scripts route through these two directories.
sys.path.insert(0, str(REPO / "server"))
sys.path.insert(0, str(REPO / "scripts"))

POINT_CODE = "A3"
ADMIN = "admin"
#: A throwaway database on the operator's own machine, so the password is not a secret worth copying.
ADMIN_PASSWORD = "demo-password"
RECORDED_FRAMES = REPO / "data" / "frames"


class StepFailed(RuntimeError):
    """A step produced no number. The driver prints no table and exits non-zero."""


def scratch_directory() -> Path:
    """A fresh tree under the runtime data root, never the development database.

    `data/` is gitignored and already the runtime data root. It is also inside the workspace, which
    the confined shells this repository is developed in allow writing to - the system temp root is not.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = REPO / "data" / "tmp" / f"demo-{stamp}-{os.getpid()}"
    path.mkdir(parents=True)
    return path


def relative(path: Path) -> str:
    """Paths are printed relative to the repository root, so the output stays portable."""
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def inference_available() -> bool:
    """Whether this interpreter can load a model, checked without importing torch."""
    return importlib.util.find_spec("ultralytics") is not None


def create_database(dsn: str) -> None:
    """Create the schema and seed it through the real `scripts/init_db.py`, not a copy of it."""
    script = REPO / "scripts" / "init_db.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--dsn", dsn, "--admin-password", ADMIN_PASSWORD],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    print(completed.stdout.rstrip())
    if completed.returncode != 0:
        print(completed.stderr.rstrip(), file=sys.stderr)
        raise StepFailed(f"scripts/init_db.py exited {completed.returncode}")


def register_version(dsn: str) -> str:
    """Register the delivered version with the helper `scripts/register_model.py` provides."""
    import register_model

    delivered = register_model.delivered_versions()
    if not delivered:
        raise StepFailed(
            "models/ holds no delivered version (one directory with best.pt, labels.txt, metrics.json)"
        )
    register_model.register_delivered(dsn, delivered[0], activate=True)
    return delivered[0].name


def choose_frame(camera_index: int) -> tuple[str, str, bytes]:
    """The frame the client would have captured: (statement, kind, JPEG bytes)."""
    from app.vision.capture import CameraSource, CaptureError

    source = CameraSource(index=camera_index)
    try:
        source.open()
    except CaptureError:
        pass
    else:
        try:
            width, height = source.size
            frame = source.read()
        except CaptureError as err:
            print(f"camera {camera_index} opened but delivered no frame: {err}")
        else:
            encoded, buffer = cv2.imencode(".jpg", frame)
            if not encoded:
                raise StepFailed("the camera frame could not be encoded as JPEG")
            return (
                f"camera {camera_index} (live grab, {width}x{height})",
                "camera",
                buffer.tobytes(),
            )
        finally:
            source.close()

    recorded = sorted(
        RECORDED_FRAMES.rglob("*.jpg"), key=lambda path: path.stat().st_mtime, reverse=True
    )
    if recorded:
        return f"recorded frame {relative(recorded[0])}", "recorded", recorded[0].read_bytes()

    texture = np.random.default_rng(0).integers(40, 200, (480, 640, 3), dtype=np.uint8)
    encoded, buffer = cv2.imencode(".jpg", texture)
    if not encoded:
        raise StepFailed("the generated frame could not be encoded as JPEG")
    return (
        "generated in memory (no camera answered, data/frames holds no .jpg)",
        "generated",
        buffer.tobytes(),
    )


def call(client, method: str, path: str, *, token: str | None = None, **kwargs) -> dict:
    """One API call; a non-zero envelope is a failed step, carrying the server's own message."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = client.request(method, path, headers=headers, **kwargs)
    try:
        body = response.json()
    except ValueError:
        raise StepFailed(f"{method} {path}: HTTP {response.status_code}, not an envelope") from None
    if response.status_code >= 400 or body.get("code") != 0:
        raise StepFailed(f"{method} {path}: {body.get('code')} {body.get('message')}")
    return body["data"]


def print_table(rows: list[tuple[str, str, float]], total: float) -> None:
    width_step = max(len(step) for step, _, _ in rows)
    width_result = max(len(result) for _, result, _ in rows)
    print(f"{'step':<{width_step}}  {'result':<{width_result}}  elapsed")
    print(f"{'-' * width_step}  {'-' * width_result}  -------")
    for step, result, seconds in rows:
        print(f"{step:<{width_step}}  {result:<{width_result}}  {seconds:5.2f}s")
    print(f"{'total':<{width_step}}  {'':<{width_result}}  {total:5.2f}s")


def main() -> int:
    scratch = scratch_directory()
    data_dir = scratch / "data"
    database = scratch / "demo.db"
    dsn = f"sqlite:///{database.as_posix()}"

    # Set before anything imports app.config: get_settings caches on its first read.
    os.environ["DB_DSN"] = dsn
    os.environ["AV_DATA_DIR"] = str(data_dir)
    # The detection route is synchronous; a background pool would only add timing noise.
    os.environ["AV_WORKER_ENABLED"] = "0"

    print("AquaVision demo driver (P4-12)")
    print(f"scratch:  {relative(scratch)}")
    print(f"database: {relative(database)}  (throwaway; the development database is not touched)")
    print()

    from app.config import get_settings
    from app.main import create_app
    from fastapi.testclient import TestClient

    # The driver reports the slice's numbers, not a request log; httpx's INFO lines would drown them.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    settings = get_settings()
    rows: list[tuple[str, str, float]] = []
    started_all = time.perf_counter()

    try:
        started = time.perf_counter()
        create_database(dsn)
        rows.append(
            ("create schema and seed", "scripts/init_db.py: OK", time.perf_counter() - started)
        )

        started = time.perf_counter()
        version = register_version(dsn)
        rows.append(
            ("register model version", f"{version} (online)", time.perf_counter() - started)
        )

        started = time.perf_counter()
        client = TestClient(create_app(), client=("127.0.0.1", 50000))
        client.__enter__()
        try:
            detector = client.app.state.detector
            rows.append(
                (
                    "start the API",
                    f"model loaded: {detector.version_name}" if detector else "no model loaded",
                    time.perf_counter() - started,
                )
            )

            started = time.perf_counter()
            body = call(
                client,
                "POST",
                "/api/auth/login",
                json={"username": ADMIN, "password": ADMIN_PASSWORD},
            )
            token = body["token"]
            rows.append(("sign in", ADMIN, time.perf_counter() - started))

            started = time.perf_counter()
            session_id = call(client, "POST", "/api/capture/sessions", token=token)["session_id"]
            rows.append(("open capture session", session_id, time.perf_counter() - started))

            started = time.perf_counter()
            statement, source_kind, image = choose_frame(settings.camera_index)
            print(f"frame source: {statement}")
            frame = call(
                client,
                "POST",
                f"/api/capture/sessions/{session_id}/frames",
                token=token,
                json={
                    "point_code": POINT_CODE,
                    "image_b64": base64.b64encode(image).decode("ascii"),
                },
            )
            frames = 1
            frame_id = frame["frame_id"]
            rows.append(
                (
                    "post one frame",
                    f"quality {frame['quality']['score']}, "
                    f"{'queued' if frame['queued'] else 'quality-rejected'}, "
                    f"{len(image) // 1024} KiB",
                    time.perf_counter() - started,
                )
            )

            started = time.perf_counter()
            if inference_available():
                if detector is None:
                    raise StepFailed(
                        f"the online model did not load: {client.app.state.detector_error}"
                    )
                detected = call(client, "POST", f"/api/detect/frames/{frame_id}", token=token)
                classes = Counter(box["class_code"] for box in detected["boxes"])
                boxes, class_counts = len(detected["boxes"]), dict(classes)
                model_version = detected["model_version"]
                names = ", ".join(f"{code} {count}" for code, count in sorted(classes.items()))
                rows.append(
                    (
                        "detect the frame",
                        f"{boxes} boxes ({names or 'none'}), {detected['latency_ms']} ms",
                        time.perf_counter() - started,
                    )
                )
            else:
                print(
                    "detection unavailable: ultralytics is not installed in this interpreter; "
                    "box counts will be absent."
                )
                boxes, class_counts, model_version = None, {}, None
                rows.append(
                    (
                        "detect the frame",
                        "not measured (ultralytics is not installed)",
                        time.perf_counter() - started,
                    )
                )

            started = time.perf_counter()
            now = datetime.now(UTC)
            report = call(
                client,
                "POST",
                "/api/reports",
                token=token,
                json={
                    "period_start": (now - timedelta(hours=1)).isoformat(),
                    "period_end": (now + timedelta(hours=1)).isoformat(),
                },
            )
            rows.append(
                (
                    "generate report",
                    f"{report['report_code']} ({report['status']})",
                    time.perf_counter() - started,
                )
            )

            started = time.perf_counter()
            statistics = call(client, "GET", "/api/stats/species?days=1", token=token)
            stats_total = statistics["total"]
            rows.append(
                (
                    "read statistics",
                    f"{stats_total} objects, {len(statistics['items'])} classes",
                    time.perf_counter() - started,
                )
            )
            if boxes is not None and stats_total != boxes:
                raise StepFailed(
                    f"the statistics total {stats_total} contradicts the {boxes} boxes detection "
                    "returned"
                )
        finally:
            client.__exit__(None, None, None)

        total = time.perf_counter() - started_all
    except StepFailed as err:
        print(file=sys.stderr)
        print(f"FAILED: {err}", file=sys.stderr)
        print(f"no table printed; the throwaway tree stays at {relative(scratch)}", file=sys.stderr)
        return 1

    per_class = (
        ", ".join(f"{code} {count}" for code, count in sorted(class_counts.items())) or "none"
    )
    boxes_shown = "absent (ultralytics is not installed)" if boxes is None else str(boxes)
    print()
    print_table(rows, total)
    print()
    print(f"frames captured {frames}")
    print(f"boxes drawn {boxes_shown}")
    print(f"per-class {per_class}")
    print(f"statistics total {stats_total}")
    print()
    print(
        "demo summary: "
        + json.dumps(
            {
                "scratch": relative(scratch),
                "database": relative(database),
                "frame_source": statement,
                "frame_source_kind": source_kind,
                "frame_id": frame_id,
                "frames": frames,
                "boxes": boxes,
                "class_counts": dict(sorted(class_counts.items())),
                "stats_total": stats_total,
                "model_version": model_version,
                "report_code": report["report_code"],
                "report_file": relative(Path(report["file_path"])),
                "detection": "ok"
                if boxes is not None
                else "unavailable: ultralytics is not installed",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
