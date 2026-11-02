"""Catalog of ST's ready-made person-detection models and the numbers ST publishes for them.

AP is ST's own COCO-person AP at IoU 0.5 (score threshold 0.001, NMS 0.5, max 100 detections).
Inference times are ST's measurements on the STM32N6570-DK (NPU + MCU) with STEdgeAI Core 4.0.0.
Sources: the yolov8n and st_yoloxn READMEs in github.com/STMicroelectronics/stm32ai-modelzoo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from herd_ai.paths import MODELS_DIR

_YOLOV8_BASE = (
    "https://raw.githubusercontent.com/stm32-hotspot/ultralytics/main/"
    "examples/YOLOv8-STEdgeAI/stedgeai_models/object_detection/"
)
_YOLOX_BASE = (
    "https://media.githubusercontent.com/media/STMicroelectronics/stm32ai-modelzoo/main/"
    "object_detection/st_yoloxn/ST_pretrainedmodel_public_dataset/coco_2017_person/"
)


@dataclass(frozen=True)
class ModelInfo:
    family: str
    input_size: int
    filename: str
    url: str
    st_ap50_percent: float | None  # ST's published AP@0.5 on COCO-person (None for non-detectors)
    st_n6_ms: float | None  # ST's published inference time on STM32N6570-DK, ms

    @property
    def stem(self) -> str:
        return Path(self.filename).stem


_OSNET_BASE = (
    "https://media.githubusercontent.com/media/STMicroelectronics/stm32ai-modelzoo/main/"
    "re_identification/osnet/ST_pretrainedmodel_public_dataset/DeepSportradar/"
)


def _yolov8(size: int, ap: float, ms: float) -> ModelInfo:
    fn = f"yolov8n_{size}_quant_pc_uf_od_coco-person.tflite"
    return ModelInfo("yolov8n", size, fn, _YOLOV8_BASE + fn, ap, ms)


def _yolox(size: int, ap: float, ms: float) -> ModelInfo:
    d = f"st_yoloxn_d033_w025_{size}"
    fn = f"{d}_int8.tflite"
    return ModelInfo("st_yoloxn", size, fn, f"{_YOLOX_BASE}{d}/{fn}", ap, ms)


def _osnet(alpha: str, ms: float) -> ModelInfo:
    """ST's person re-identification models (model zoo v4.0), 256x128 input, trained on DeepSportradar.

    Not detectors: AP is None. Timing is ST's on the STM32N6570-DK with STEdgeAI Core 3.0.0.
    """
    d = f"osnet_a{alpha}_256_128_tfs"
    fn = f"{d}_int8.tflite"
    return ModelInfo("osnet", 256, fn, f"{_OSNET_BASE}{d}/{fn}", None, ms)


MODEL_CATALOG: tuple[ModelInfo, ...] = (
    _yolov8(192, 53.58, 16.33),
    _yolov8(256, 58.40, 23.83),
    _yolov8(320, 61.86, 29.93),
    _yolov8(416, 64.79, 54.67),
    _yolox(256, 44.85, 9.42),
    _yolox(320, 51.17, 13.29),
    _yolox(416, 54.80, 21.30),
    _osnet("025", 3.53),
    _osnet("100", 13.44),
)

DEFAULT_MODEL = MODEL_CATALOG[1]  # yolov8n at 256: fits internal RAM, ~24 ms on the N6

_SIZE_RE = re.compile(r"_(\d{3})(?=_|\.|$)")


def input_size_from_name(name: str) -> int:
    """Pull the input resolution out of an ST model file name, e.g. ``..._256_...`` -> 256."""
    m = _SIZE_RE.search(Path(name).name)
    if not m:
        raise ValueError(f"no input size found in model name {name!r}")
    return int(m.group(1))


def model_path(filename: str) -> Path:
    return MODELS_DIR / filename


def catalog_entry(path_or_name: str | Path) -> ModelInfo | None:
    name = Path(path_or_name).name
    return next((m for m in MODEL_CATALOG if m.filename == name), None)
