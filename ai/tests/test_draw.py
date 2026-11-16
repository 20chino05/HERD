import numpy as np

from herd_ai.draw import draw_detections


def test_draw_detections_returns_a_new_annotated_copy():
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    boxes = np.array([[10.0, 20.0, 60.0, 80.0]])
    scores = np.array([0.87])
    out = draw_detections(img, boxes, scores)
    assert out.shape == img.shape and out.dtype == np.uint8
    assert img.sum() == 0  # input untouched
    assert out[20, 10:60].sum() > 0  # top edge of the box was drawn
    assert out[50, 15:55].sum() == 0  # interior left alone


def test_draw_detections_with_no_boxes_is_a_plain_copy():
    img = np.full((20, 30, 3), 7, dtype=np.uint8)
    out = draw_detections(img, np.zeros((0, 4)), np.zeros((0,)))
    assert (out == img).all() and out is not img
