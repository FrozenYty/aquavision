"""Load the online weights and run one frame through them (P2-05b).

**Why the torch import lives inside the functions.** `requirements.txt` pins ultralytics, which pulls
torch, but the server must stay startable on a machine without the training stack: CI installs
neither package, and a deployment may serve the API only. A module-level import would turn "torch is
absent" into "the API does not start"; a lazy one turns it into one route answering a stated reason,
which is the honest failure for a missing capability.

**Which weights.** The model comes from the single `model_version` row with `is_online = 1`; no
weight path is written in this file. One process loads one model at start-up, and switching the
online version takes a restart — the decision P2-06c records.

**What a failure looks like.** `load_online` returns either a detector or a sentence saying why none
could be built: no online row, no weight file, no torch, an unreadable file, or a class order that
disagrees with `species_dict`. Nothing here invents a box when the model cannot run.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.models import MediaAsset, ModelVersion, SpeciesDict

log = logging.getLogger("aquavision.detector")

#: Defaults from data model §3.4. The batch route carries its own values per task.
CONF_THRESHOLD = 0.5
IOU_THRESHOLD = 0.45
MAX_DET = 100
IMG_SIZE = 640


class Detector:
    """The online model, loaded once and shared by the route and the queue worker."""

    def __init__(
        self,
        weights: Path,
        *,
        model_version_id: int,
        version_name: str,
        data_dir: Path,
        device: str | None = None,
        imgsz: int = IMG_SIZE,
    ):
        # Imported here, not at module scope: see the module docstring.
        from ultralytics import YOLO

        self.model_version_id = model_version_id
        self.version_name = version_name
        self._data_dir = Path(data_dir)
        self._imgsz = imgsz
        self._device = device or _pick_device()
        self._model = YOLO(str(weights))
        # Ultralytics models are not thread-safe; the queue pool calls this from several threads.
        self._lock = threading.Lock()

    @property
    def class_names(self) -> list[str]:
        """The class codes the weights were trained with, in index order."""
        names = self._model.names
        return [str(names[index]) for index in sorted(names)]

    def predict(
        self,
        asset: MediaAsset,
        conf_thr: float = CONF_THRESHOLD,
        iou_thr: float = IOU_THRESHOLD,
        max_det: int = MAX_DET,
    ) -> list[dict[str, Any]]:
        """Run one image and return boxes in the serialiser's normalised top-left convention."""
        image = self._data_dir / asset.file_path
        # Ultralytics answers an unreadable source with an empty result. An empty result here would
        # be a fabricated one: the frame was never looked at. Fail instead.
        if not image.is_file():
            raise FileNotFoundError(f"帧文件不存在：{image}")

        with self._lock:
            result = self._model.predict(
                source=str(image),
                conf=float(conf_thr),
                iou=float(iou_thr),
                max_det=int(max_det),
                imgsz=self._imgsz,
                device=self._device,
                verbose=False,
            )[0]

        boxes = []
        names = self._model.names
        for box in result.boxes:
            x1, y1, x2, y2 = (float(value) for value in box.xyxyn[0].tolist())
            # Clip to the image: a coordinate outside 0..1 would fail the contract's normalisation.
            x = min(max(x1, 0.0), 1.0)
            y = min(max(y1, 0.0), 1.0)
            boxes.append(
                {
                    "class_code": str(names[int(box.cls)]),
                    "confidence": float(box.conf),
                    "x": x,
                    "y": y,
                    "w": max(0.0, min(max(x2, 0.0), 1.0) - x),
                    "h": max(0.0, min(max(y2, 0.0), 1.0) - y),
                }
            )
        return boxes

    def __call__(self, asset: MediaAsset) -> list[dict[str, Any]]:
        """The queue worker's callable shape."""
        return self.predict(asset)


def load_online(session_factory, settings) -> tuple[Detector | None, str | None]:
    """Return the online detector, or `None` and a sentence saying why it could not be built."""
    with session_factory() as session:
        online = list(session.scalars(select(ModelVersion).where(ModelVersion.is_online == 1)))
        species_codes = list(
            session.scalars(select(SpeciesDict.class_code).order_by(SpeciesDict.species_id))
        )

    if not online:
        return None, "没有在线模型版本：请先注册权重并把它设为在线"
    if len(online) > 1:
        # P3-03 promises exactly one online row. Two means the state is broken; guessing is worse.
        return None, f"model_version 有 {len(online)} 行标记为在线，拒绝猜测使用哪一个"

    row = online[0]
    if not row.weight_path:
        return None, f"在线模型 {row.version_name} 没有登记权重路径"
    weights = Path(row.weight_path)
    if not weights.is_absolute():
        weights = Path.cwd() / weights
    if not weights.is_file():
        return None, f"在线模型 {row.version_name} 的权重文件不存在：{weights}"

    try:
        detector = Detector(
            weights,
            model_version_id=row.model_id,
            version_name=row.version_name,
            data_dir=Path(settings.data_dir),
        )
    except ImportError as exc:
        missing = exc.name or "torch"
        return None, f"运行环境缺少推理依赖 {missing}，无法加载在线模型 {row.version_name}"
    except Exception as exc:  # noqa: BLE001 - the reason belongs in the response
        return None, (f"在线模型 {row.version_name} 的权重无法加载：{type(exc).__name__}: {exc}")

    problem = _class_order_problem(detector.class_names, species_codes)
    if problem:
        return None, problem
    return detector, None


def _class_order_problem(names: list[str], species_codes: list[str]) -> str | None:
    """The data model makes the class order a contract; a mismatch would mislabel every box."""
    if not species_codes:
        return "species_dict 为空，无法校验模型类别顺序，拒绝推理"
    if names != species_codes:
        return f"模型类别顺序 {names} 与 species_dict {species_codes} 不一致，拒绝加载"
    return None


def _pick_device() -> str:
    """CPU is always valid; a CUDA build uses the first GPU when one is visible."""
    try:
        import torch

        return "0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"
