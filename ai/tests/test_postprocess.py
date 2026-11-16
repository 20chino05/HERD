import numpy as np

from herd_ai.postprocess import boxes_to_pixels, decode_yolov8, nms
from herd_ai.preprocess import PreprocessMeta


def test_decode_yolov8_converts_cxcywh_to_xyxy_and_filters_by_score():
    # columns: cx, cy, w, h, score (normalized 0..1), shape (5, F)
    raw = np.array(
        [
            [0.5, 0.5, 0.2, 0.4, 0.9],
            [0.1, 0.1, 0.1, 0.1, 0.2],
            [0.8, 0.2, 0.2, 0.2, 0.6],
        ]
    ).T
    boxes, scores = decode_yolov8(raw, score_thresh=0.5)
    assert boxes.shape == (2, 4)
    np.testing.assert_allclose(boxes[0], [0.4, 0.3, 0.6, 0.7], atol=1e-6)
    np.testing.assert_allclose(boxes[1], [0.7, 0.1, 0.9, 0.3], atol=1e-6)
    np.testing.assert_allclose(scores, [0.9, 0.6])


def test_decode_yolov8_accepts_batch_dimension():
    raw = np.array([[[0.5], [0.5], [0.2], [0.2], [0.8]]])  # (1, 5, 1)
    boxes, scores = decode_yolov8(raw, score_thresh=0.1)
    assert boxes.shape == (1, 4)
    assert scores.shape == (1,)


def test_decode_yolov8_returns_empty_arrays_when_nothing_passes():
    raw = np.zeros((5, 10))
    boxes, scores = decode_yolov8(raw, score_thresh=0.5)
    assert boxes.shape == (0, 4)
    assert scores.shape == (0,)


def test_nms_suppresses_overlapping_lower_score_box_and_orders_by_score():
    boxes = np.array(
        [
            [0.0, 0.0, 1.0, 1.0],  # score 0.7, overlaps box 1 heavily
            [0.05, 0.05, 1.0, 1.0],  # score 0.9, keep
            [2.0, 2.0, 3.0, 3.0],  # score 0.5, disjoint, keep
        ]
    )
    scores = np.array([0.7, 0.9, 0.5])
    keep = nms(boxes, scores, iou_thresh=0.5)
    assert keep.tolist() == [1, 2]


def test_nms_respects_max_det():
    boxes = np.array([[i, 0.0, i + 0.5, 1.0] for i in range(5)], dtype=float)
    scores = np.linspace(0.9, 0.5, 5)
    keep = nms(boxes, scores, iou_thresh=0.5, max_det=2)
    assert keep.tolist() == [0, 1]


def test_nms_on_empty_input_returns_empty():
    keep = nms(np.zeros((0, 4)), np.zeros((0,)), iou_thresh=0.5)
    assert keep.shape == (0,)


def test_boxes_to_pixels_fit_mode_scales_by_original_size_and_clips():
    meta = PreprocessMeta(
        orig_w=640, orig_h=480, size=256, mode="fit", scale_x=256 / 640, scale_y=256 / 480, pad_x=0, pad_y=0
    )
    boxes_norm = np.array([[0.25, 0.5, 0.75, 1.2]])
    px = boxes_to_pixels(boxes_norm, meta)
    np.testing.assert_allclose(px, [[160, 240, 480, 480]])


def test_boxes_to_pixels_letterbox_mode_removes_padding_and_scale():
    # 640x480 image letterboxed into 256: scale = 0.4, content 256x192, pad_y = 32
    meta = PreprocessMeta(orig_w=640, orig_h=480, size=256, mode="letterbox", scale_x=0.4, scale_y=0.4, pad_x=0, pad_y=32)
    # normalized box covering model-space x 0..256, y 32..224 -> whole original image
    boxes_norm = np.array([[0.0, 32 / 256, 1.0, 224 / 256]])
    px = boxes_to_pixels(boxes_norm, meta)
    np.testing.assert_allclose(px, [[0, 0, 640, 480]], atol=1e-6)
