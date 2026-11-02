"""Single-class detection metrics: greedy matching, COCO-style AP@IoU, precision/recall at a threshold."""

from __future__ import annotations

import numpy as np

from herd_ai.boxes import intersection_over_area, iou_matrix

__all__ = ["iou_matrix", "match_image", "average_precision", "precision_recall_at"]


def match_image(
    det_boxes: np.ndarray,
    det_scores: np.ndarray,
    gt_boxes: np.ndarray,
    crowd_boxes: np.ndarray,
    iou_thresh: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Match one image's detections to its ground truth.

    Detections are visited highest score first. Each is a true positive if it overlaps an unmatched GT
    box at IoU >= ``iou_thresh`` (taking the best such GT), otherwise a false positive. A detection that
    matches nothing but lies mostly on an ``iscrowd`` region is ignored, as in the COCO evaluator.

    Returns (scores, is_tp) for the detections that were counted, in score order.
    """
    det_boxes = np.asarray(det_boxes, dtype=np.float64).reshape(-1, 4)
    det_scores = np.asarray(det_scores, dtype=np.float64).reshape(-1)
    gt_boxes = np.asarray(gt_boxes, dtype=np.float64).reshape(-1, 4)
    crowd_boxes = np.asarray(crowd_boxes, dtype=np.float64).reshape(-1, 4)

    ious = iou_matrix(det_boxes, gt_boxes)
    crowd_cover = intersection_over_area(det_boxes, crowd_boxes)
    gt_used = np.zeros(gt_boxes.shape[0], dtype=bool)

    out_scores: list[float] = []
    out_tp: list[bool] = []
    for i in np.argsort(-det_scores, kind="stable"):
        candidates = np.flatnonzero(~gt_used & (ious[i] >= iou_thresh))
        if candidates.size:
            gt_used[candidates[np.argmax(ious[i, candidates])]] = True
            out_scores.append(det_scores[i])
            out_tp.append(True)
            continue
        if crowd_cover.shape[1] and crowd_cover[i].max() >= iou_thresh:
            continue  # on a crowd region: neither TP nor FP
        out_scores.append(det_scores[i])
        out_tp.append(False)

    return np.array(out_scores, dtype=np.float64), np.array(out_tp, dtype=bool)


def average_precision(scores: np.ndarray, is_tp: np.ndarray, n_gt: int) -> tuple[float, np.ndarray, np.ndarray]:
    """COCO-style AP: precision envelope sampled at 101 recall points.

    Returns (ap, precision, recall) where precision/recall are the raw cumulative curves in score order.
    """
    scores = np.asarray(scores, dtype=np.float64).reshape(-1)
    is_tp = np.asarray(is_tp, dtype=bool).reshape(-1)
    if n_gt == 0 or scores.size == 0:
        return 0.0, np.zeros(0), np.zeros(0)

    order = np.argsort(-scores, kind="stable")
    tp = is_tp[order]
    tp_cum = np.cumsum(tp)
    fp_cum = np.cumsum(~tp)
    recall = tp_cum / n_gt
    precision = tp_cum / (tp_cum + fp_cum)

    envelope = np.maximum.accumulate(precision[::-1])[::-1]
    recall_points = np.linspace(0.0, 1.0, 101)
    idx = np.searchsorted(recall, recall_points, side="left")
    sampled = np.zeros(recall_points.shape)
    valid = idx < envelope.size
    sampled[valid] = envelope[idx[valid]]
    return float(sampled.mean()), precision, recall


def precision_recall_at(scores: np.ndarray, is_tp: np.ndarray, n_gt: int, score_thresh: float) -> tuple[float, float, float]:
    """Precision, recall and F1 when only detections with score >= ``score_thresh`` are kept."""
    scores = np.asarray(scores, dtype=np.float64).reshape(-1)
    is_tp = np.asarray(is_tp, dtype=bool).reshape(-1)
    selected = scores >= score_thresh
    n_det = int(selected.sum())
    n_tp = int(is_tp[selected].sum())
    p = n_tp / n_det if n_det else 0.0
    r = n_tp / n_gt if n_gt else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return float(p), float(r), float(f1)
