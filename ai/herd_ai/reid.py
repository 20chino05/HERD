"""Person re-identification with ST's OSNet models (model zoo v4.0).

A person crop goes in at 256x128 (uint8 RGB), an int8 embedding comes out. We dequantize it,
L2-normalize it and compare embeddings by cosine distance (0 = identical, 1 = unrelated).
The same recipe will run on the board, where the embedding is what one unit would send to its
neighbor along with "heading your way".
"""

from __future__ import annotations

import re
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
from ai_edge_litert.interpreter import Interpreter

MODEL_INPUT_HW = (256, 128)  # height, width

_MARKET_RE = re.compile(r"^(-?\d+)_c(\d)")


def parse_market_name(name: str) -> tuple[int, int]:
    """Market-1501 file names look like ``0001_c1s1_001051_00.jpg``: person 1 seen by camera 1.

    Person id -1 marks junk crops (ignored by the protocol) and 0 marks distractors (count as
    negatives).
    """
    m = _MARKET_RE.match(Path(name).name)
    if not m:
        raise ValueError(f"not a Market-1501 file name: {name!r}")
    return int(m.group(1)), int(m.group(2))


def crop_person(img_rgb: np.ndarray, box_xyxy, margin: float = 0.0) -> np.ndarray:
    """Cut a person out of a frame. ``margin`` adds that fraction of the box size on every side.

    The box is clipped to the image; a box entirely outside it raises ``ValueError``.
    """
    h, w = img_rgb.shape[:2]
    x1, y1, x2, y2 = (float(v) for v in box_xyxy)
    if margin:
        mx, my = (x2 - x1) * margin, (y2 - y1) * margin
        x1, x2, y1, y2 = x1 - mx, x2 + mx, y1 - my, y2 + my
    xi1, yi1 = max(0, int(round(x1))), max(0, int(round(y1)))
    xi2, yi2 = min(w, int(round(x2))), min(h, int(round(y2)))
    if xi2 <= xi1 or yi2 <= yi1:
        raise ValueError(f"box {box_xyxy} lies outside the {w}x{h} image")
    return img_rgb[yi1:yi2, xi1:xi2]


def prepare_crop(crop_rgb: np.ndarray, hw: tuple[int, int] = MODEL_INPUT_HW) -> np.ndarray:
    """Stretch a crop to the model's height x width and add the batch axis: (1, H, W, 3) uint8."""
    if crop_rgb.ndim != 3 or crop_rgb.shape[2] != 3:
        raise ValueError(f"expected an HxWx3 image, got {crop_rgb.shape}")
    h, w = hw
    resized = cv2.resize(crop_rgb, (w, h), interpolation=cv2.INTER_NEAREST)  # ST trains with nearest
    return np.ascontiguousarray(resized, dtype=np.uint8)[None]


def _unit(v: np.ndarray) -> np.ndarray:
    v = v.astype(np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def cosine_distance_matrix(a, b) -> np.ndarray:
    """Pairwise cosine distance between rows of ``a`` and rows of ``b`` (both already unit length)."""
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    return np.clip(1.0 - a @ b.T, 0.0, 2.0)


class PersonEmbedder:
    """Wraps ``osnet_a025_256_128_tfs_int8.tflite`` (128-d) or ``osnet_a100_...`` (512-d)."""

    def __init__(self, model_path: str | Path, num_threads: int | None = None, warmup: bool = True):
        self.path = Path(model_path)
        self.name = self.path.stem
        kwargs = {"num_threads": num_threads} if num_threads else {}
        self._interp = Interpreter(model_path=str(self.path), **kwargs)
        self._interp.allocate_tensors()

        inp = self._interp.get_input_details()[0]
        outs = self._interp.get_output_details()
        if inp["dtype"] != np.uint8 or len(inp["shape"]) != 4 or inp["shape"][3] != 3:
            raise ValueError(f"expected a (1, H, W, 3) uint8 input, got {inp['shape']} {inp['dtype']}")
        if len(outs) != 1 or len(outs[0]["shape"]) != 2:
            raise NotImplementedError(f"expected one (1, D) embedding output, got {[tuple(o['shape']) for o in outs]}")
        self.input_hw = (int(inp["shape"][1]), int(inp["shape"][2]))
        self.dim = int(outs[0]["shape"][1])
        self._in_index = inp["index"]
        self._out_index = outs[0]["index"]
        scale, zero_point = outs[0]["quantization"]
        self._scale = float(scale) if scale else 1.0
        self._zero_point = int(zero_point)
        self.last_latency_ms = 0.0

        if warmup:
            self.embed(np.zeros((*self.input_hw, 3), dtype=np.uint8))

    def embed(self, crop_rgb: np.ndarray) -> np.ndarray:
        """One unit-length float32 embedding for one person crop."""
        self._interp.set_tensor(self._in_index, prepare_crop(crop_rgb, self.input_hw))
        t0 = perf_counter()
        self._interp.invoke()
        self.last_latency_ms = (perf_counter() - t0) * 1000.0
        raw = self._interp.get_tensor(self._out_index)[0]
        if raw.dtype != np.float32:
            raw = (raw.astype(np.float32) - self._zero_point) * self._scale
        return _unit(raw)

    def embed_batch(self, crops) -> np.ndarray:
        return np.stack([self.embed(c) for c in crops]) if len(crops) else np.zeros((0, self.dim), np.float32)
