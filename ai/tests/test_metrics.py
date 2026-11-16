import numpy as np
import pytest

from herd_ai.metrics import average_precision, iou_matrix, match_image, precision_recall_at


def test_iou_matrix_basic_cases():
    a = np.array([[0, 0, 2, 2], [0, 0, 1, 1]], dtype=float)
    b = np.array([[0, 0, 2, 2], [5, 5, 6, 6], [1, 0, 3, 2]], dtype=float)
    iou = iou_matrix(a, b)
    assert iou.shape == (2, 3)
    assert iou[0, 0] == pytest.approx(1.0)
    assert iou[0, 1] == pytest.approx(0.0)
    assert iou[0, 2] == pytest.approx(2 / 6)  # intersection 2, union 4+4-2


def test_match_image_marks_tp_and_fp_in_score_order():
    dets = np.array([[0, 0, 10, 10], [50, 50, 60, 60], [1, 1, 10, 10]], dtype=float)
    scores = np.array([0.9, 0.8, 0.7])
    gts = np.array([[0, 0, 10, 10]], dtype=float)
    out_scores, tp = match_image(dets, scores, gts, crowd_boxes=np.zeros((0, 4)), iou_thresh=0.5)
    assert out_scores.tolist() == [0.9, 0.8, 0.7]
    assert tp.tolist() == [True, False, False]  # second hit on the same GT is a duplicate -> FP


def test_match_image_ignores_detections_on_crowd_regions():
    dets = np.array([[0, 0, 10, 10], [100, 100, 110, 110]], dtype=float)
    scores = np.array([0.9, 0.8])
    gts = np.zeros((0, 4))
    crowd = np.array([[0, 0, 12, 12]], dtype=float)
    out_scores, tp = match_image(dets, scores, gts, crowd_boxes=crowd, iou_thresh=0.5)
    assert out_scores.tolist() == [0.8]  # the crowd-covered detection is dropped, not counted
    assert tp.tolist() == [False]


def test_match_image_with_no_detections_returns_empty():
    out_scores, tp = match_image(
        np.zeros((0, 4)), np.zeros((0,)), np.array([[0, 0, 1, 1.0]]), np.zeros((0, 4)), 0.5
    )
    assert out_scores.shape == (0,) and tp.shape == (0,)


def test_average_precision_perfect_detector_is_one():
    ap, _, _ = average_precision(np.array([0.9, 0.8]), np.array([True, True]), n_gt=2)
    assert ap == pytest.approx(1.0)


def test_average_precision_all_false_is_zero():
    ap, _, _ = average_precision(np.array([0.9, 0.8]), np.array([False, False]), n_gt=2)
    assert ap == pytest.approx(0.0)


def test_average_precision_coco_101_point_interpolation():
    # 2 GT; detections ordered by score: TP, FP, TP
    # recall 0.5 reached at precision 1.0; recall 1.0 reached at precision 2/3
    scores = np.array([0.9, 0.8, 0.7])
    tp = np.array([True, False, True])
    ap, precision, recall = average_precision(scores, tp, n_gt=2)
    expected = (51 * 1.0 + 50 * (2 / 3)) / 101
    assert ap == pytest.approx(expected, abs=1e-6)
    np.testing.assert_allclose(recall, [0.5, 0.5, 1.0])
    np.testing.assert_allclose(precision, [1.0, 0.5, 2 / 3])


def test_average_precision_sorts_by_score_before_accumulating():
    # same detections as above but given out of order; result must not change
    scores = np.array([0.7, 0.9, 0.8])
    tp = np.array([True, True, False])
    ap, _, _ = average_precision(scores, tp, n_gt=2)
    assert ap == pytest.approx((51 * 1.0 + 50 * (2 / 3)) / 101, abs=1e-6)


def test_average_precision_with_no_ground_truth_is_zero():
    ap, _, _ = average_precision(np.zeros((0,)), np.zeros((0,), dtype=bool), n_gt=0)
    assert ap == 0.0


def test_precision_recall_at_threshold():
    scores = np.array([0.9, 0.8, 0.7, 0.3])
    tp = np.array([True, False, True, True])
    p, r, f1 = precision_recall_at(scores, tp, n_gt=4, score_thresh=0.5)
    assert p == pytest.approx(2 / 3)
    assert r == pytest.approx(2 / 4)
    assert f1 == pytest.approx(2 * (2 / 3) * 0.5 / ((2 / 3) + 0.5))


def test_precision_recall_at_threshold_with_no_detections_is_zero_not_nan():
    p, r, f1 = precision_recall_at(np.array([0.1]), np.array([True]), n_gt=1, score_thresh=0.5)
    assert (p, r, f1) == (0.0, 0.0, 0.0)
