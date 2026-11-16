"""Turn an RGB image into the uint8 NxNx3 tensor the ST models expect.

Two resize modes:

- ``fit``: stretch the whole image to NxN, ignoring aspect ratio. This is what the ST model zoo
  evaluation uses and what the board does when it downscales the camera frame in hardware, so it is the
  default and the mode whose accuracy numbers are comparable to ST's published figures.
- ``letterbox``: scale to fit the longer side and pad the rest with gray (114). Keeps aspect ratio.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

PAD_VALUE = 114
MODES = ("fit", "letterbox")


@dataclass(frozen=True)
class PreprocessMeta:
    """Everything needed to map a box in model-input space back to original-image pixels."""

    orig_w: int
    orig_h: int
    size: int
    mode: str
    scale_x: float  # model-space pixels per original pixel, x
    scale_y: float  # model-space pixels per original pixel, y
    pad_x: int  # left padding in model-space pixels (letterbox only)
    pad_y: int  # top padding in model-space pixels (letterbox only)


def prepare_input(img: np.ndarray, size: int, mode: str = "fit") -> tuple[np.ndarray, PreprocessMeta]:
    """Resize an HxWx3 uint8 RGB image to a (1, size, size, 3) uint8 tensor."""
    if img.ndim != 3 or img.shape[2] != 3:
        raise ValueError(f"expected an HxWx3 RGB image, got shape {img.shape}")
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")

    h, w = img.shape[:2]
    if mode == "fit":
        out = cv2.resize(img, (size, size), interpolation=cv2.INTER_LINEAR)
        meta = PreprocessMeta(w, h, size, mode, size / w, size / h, 0, 0)
    else:
        scale = size / max(w, h)
        new_w, new_h = round(w * scale), round(h * scale)
        content = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        pad_x, pad_y = (size - new_w) // 2, (size - new_h) // 2
        out = np.full((size, size, 3), PAD_VALUE, dtype=np.uint8)
        out[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = content
        meta = PreprocessMeta(w, h, size, mode, new_w / w, new_h / h, pad_x, pad_y)

    return out[np.newaxis].astype(np.uint8, copy=False), meta
