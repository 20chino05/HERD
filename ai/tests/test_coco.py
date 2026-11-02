import json

import numpy as np

from herd_ai.coco import load_person_gt, select_images

PERSON = 1
DOG = 18


def _write_fixture(tmp_path):
    data = {
        "images": [
            {"id": 10, "file_name": "a.jpg", "width": 640, "height": 480},
            {"id": 20, "file_name": "b.jpg", "width": 320, "height": 240},
            {"id": 30, "file_name": "c.jpg", "width": 100, "height": 100},
        ],
        "annotations": [
            {"id": 1, "image_id": 10, "category_id": PERSON, "bbox": [10, 20, 30, 40], "iscrowd": 0},
            {"id": 2, "image_id": 10, "category_id": PERSON, "bbox": [100, 100, 50, 50], "iscrowd": 1},
            {"id": 3, "image_id": 10, "category_id": DOG, "bbox": [0, 0, 5, 5], "iscrowd": 0},
            {"id": 4, "image_id": 20, "category_id": DOG, "bbox": [0, 0, 5, 5], "iscrowd": 0},
        ],
        "categories": [{"id": PERSON, "name": "person"}, {"id": DOG, "name": "dog"}],
    }
    p = tmp_path / "instances.json"
    p.write_text(json.dumps(data))
    return p


def test_load_person_gt_converts_xywh_to_xyxy_and_splits_crowd(tmp_path):
    gts = load_person_gt(_write_fixture(tmp_path))
    assert set(gts) == {10, 20, 30}
    a = gts[10]
    assert a.file_name == "a.jpg" and a.width == 640 and a.height == 480
    np.testing.assert_allclose(a.boxes, [[10, 20, 40, 60]])
    np.testing.assert_allclose(a.crowd, [[100, 100, 150, 150]])
    assert gts[20].boxes.shape == (0, 4)  # dog-only image has no person boxes
    assert gts[30].boxes.shape == (0, 4)  # image with no annotations at all


def test_select_images_takes_requested_counts_deterministically(tmp_path):
    gts = load_person_gt(_write_fixture(tmp_path))
    chosen = select_images(gts, n_with_person=1, n_without=1, seed=0)
    assert chosen[0] == 10 and chosen[1] in (20, 30)
    assert select_images(gts, n_with_person=1, n_without=1, seed=0) == chosen


def test_select_images_none_means_all(tmp_path):
    gts = load_person_gt(_write_fixture(tmp_path))
    assert sorted(select_images(gts)) == [10, 20, 30]
