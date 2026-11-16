"""Box geometry helpers. All boxes are (N, 4) arrays of x1, y1, x2, y2."""

from __future__ import annotations

import numpy as np


def _as_boxes(x) -> np.ndarray:
    return np.asarray(x, dtype=np.float64).reshape(-1, 4)


def _areas(b: np.ndarray) -> np.ndarray:
    return np.clip(b[:, 2] - b[:, 0], 0, None) * np.clip(b[:, 3] - b[:, 1], 0, None)


def _intersection(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ix1 = np.maximum(a[:, None, 0], b[None, :, 0])
    iy1 = np.maximum(a[:, None, 1], b[None, :, 1])
    ix2 = np.minimum(a[:, None, 2], b[None, :, 2])
    iy2 = np.minimum(a[:, None, 3], b[None, :, 3])
    return np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)


def iou_matrix(a, b) -> np.ndarray:
    """Pairwise intersection-over-union, shape (len(a), len(b))."""
    a, b = _as_boxes(a), _as_boxes(b)
    if a.shape[0] == 0 or b.shape[0] == 0:
        return np.zeros((a.shape[0], b.shape[0]))
    inter = _intersection(a, b)
    union = _areas(a)[:, None] + _areas(b)[None, :] - inter
    out = np.zeros_like(inter)
    np.divide(inter, union, out=out, where=union > 0)
    return out


def intersection_over_area(a, b) -> np.ndarray:
    """Fraction of each box in `a` that lies inside each box in `b`, shape (len(a), len(b)).

    This is how COCO decides whether a detection falls on an `iscrowd` region.
    """
    a, b = _as_boxes(a), _as_boxes(b)
    if a.shape[0] == 0 or b.shape[0] == 0:
        return np.zeros((a.shape[0], b.shape[0]))
    inter = _intersection(a, b)
    area_a = _areas(a)[:, None]
    out = np.zeros_like(inter)
    np.divide(inter, np.broadcast_to(area_a, inter.shape), out=out, where=area_a > 0)
    return out
