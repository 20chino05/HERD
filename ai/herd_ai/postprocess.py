"""Decode raw model output into pixel-space person boxes.

ST's YOLOv8n person models (``yolov8n_*_quant_pc_uf_od_coco-person.tflite``) output one float32 tensor of
shape (1, 5, F): rows are cx, cy, w, h (normalized 0..1 in model-input space) and the person score;
F is the number of anchor cells over the three feature maps. No NMS is applied inside the model, so we do
it here, the same way the firmware post-processing library does on the board.
"""

from __future__ import annotations

import numpy as np

from herd_ai.boxes import iou_matrix
from herd_ai.preprocess import PreprocessMeta


def decode_yolov8(raw: np.ndarray, score_thresh: float) -> tuple[np.ndarray, np.ndarray]:
    """(5, F) or (1, 5, F) raw output -> (boxes xyxy normalized (K, 4), scores (K,)) above threshold."""
    arr = np.asarray(raw, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr[0]
    if arr.ndim != 2 or arr.shape[0] < 5:
        raise ValueError(f"expected (5, F) or (1, 5, F) output, got shape {arr.shape}")

    cx, cy, w, h = arr[0], arr[1], arr[2], arr[3]
    scores = arr[4] if arr.shape[0] == 5 else arr[4:].max(axis=0)
    keep = scores >= score_thresh
    boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)[keep]
    return boxes.astype(np.float64), scores[keep].astype(np.float64)


def nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float, max_det: int = 100) -> np.ndarray:
    """Greedy class-agnostic NMS. Returns indices of kept boxes, highest score first."""
    boxes = np.asarray(boxes, dtype=np.float64).reshape(-1, 4)
    scores = np.asarray(scores, dtype=np.float64).reshape(-1)
    order = np.argsort(-scores, kind="stable")
    keep: list[int] = []
    while order.size > 0 and len(keep) < max_det:
        i = int(order[0])
        keep.append(i)
        rest = order[1:]
        if rest.size == 0:
            break
        ious = iou_matrix(boxes[i : i + 1], boxes[rest])[0]
        order = rest[ious <= iou_thresh]
    return np.array(keep, dtype=np.int64)


def boxes_to_pixels(boxes_norm: np.ndarray, meta: PreprocessMeta) -> np.ndarray:
    """Map normalized model-space xyxy boxes back to original-image pixels, clipped to the image."""
    b = np.asarray(boxes_norm, dtype=np.float64).reshape(-1, 4) * meta.size
    b[:, [0, 2]] = (b[:, [0, 2]] - meta.pad_x) / meta.scale_x
    b[:, [1, 3]] = (b[:, [1, 3]] - meta.pad_y) / meta.scale_y
    b[:, [0, 2]] = np.clip(b[:, [0, 2]], 0, meta.orig_w)
    b[:, [1, 3]] = np.clip(b[:, [1, 3]], 0, meta.orig_h)
    return b
