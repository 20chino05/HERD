"""Draw detection boxes on an RGB image."""

from __future__ import annotations

import cv2
import numpy as np

GREEN = (0, 255, 0)


def draw_detections(
    img_rgb: np.ndarray,
    boxes: np.ndarray,
    scores: np.ndarray,
    color: tuple[int, int, int] = GREEN,
    thickness: int = 2,
    label: str = "person",
) -> np.ndarray:
    """Return a copy of ``img_rgb`` with one labelled rectangle per box."""
    out = np.ascontiguousarray(img_rgb.copy())
    for (x1, y1, x2, y2), score in zip(np.asarray(boxes).reshape(-1, 4), np.asarray(scores).reshape(-1)):
        p1 = (int(round(x1)), int(round(y1)))
        p2 = (int(round(x2)), int(round(y2)))
        cv2.rectangle(out, p1, p2, color, thickness)
        text = f"{label} {score:.2f}"
        cv2.putText(out, text, (p1[0], max(p1[1] - 6, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    return out
