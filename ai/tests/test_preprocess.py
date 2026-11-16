import numpy as np
import pytest

from herd_ai.postprocess import boxes_to_pixels
from herd_ai.preprocess import prepare_input


def test_fit_mode_stretches_to_square_uint8_batch():
    img = np.full((480, 640, 3), 200, dtype=np.uint8)
    tensor, meta = prepare_input(img, size=256, mode="fit")
    assert tensor.shape == (1, 256, 256, 3)
    assert tensor.dtype == np.uint8
    assert meta.mode == "fit"
    assert meta.orig_w == 640 and meta.orig_h == 480
    assert tensor.min() == 200 and tensor.max() == 200


def test_letterbox_mode_pads_short_side_with_gray():
    img = np.full((480, 640, 3), 200, dtype=np.uint8)
    tensor, meta = prepare_input(img, size=256, mode="letterbox")
    assert tensor.shape == (1, 256, 256, 3)
    assert meta.pad_y == 32 and meta.pad_x == 0
    # padded rows are gray 114, content rows keep the image value
    assert (tensor[0, :32] == 114).all() and (tensor[0, -32:] == 114).all()
    assert (tensor[0, 32:224] == 200).all()


def test_letterbox_round_trip_recovers_original_box():
    img = np.zeros((300, 500, 3), dtype=np.uint8)
    _, meta = prepare_input(img, size=320, mode="letterbox")
    # a box in original pixels -> model-space normalized -> back to pixels
    orig = np.array([[50.0, 60.0, 250.0, 200.0]])
    model_space = orig.copy()
    model_space[:, [0, 2]] = (orig[:, [0, 2]] * meta.scale_x + meta.pad_x) / meta.size
    model_space[:, [1, 3]] = (orig[:, [1, 3]] * meta.scale_y + meta.pad_y) / meta.size
    back = boxes_to_pixels(model_space, meta)
    np.testing.assert_allclose(back, orig, atol=1e-6)


def test_rejects_non_rgb_input():
    with pytest.raises(ValueError):
        prepare_input(np.zeros((10, 10), dtype=np.uint8), size=64)
