"""End-to-end checks against the real ST model and real COCO images. Skipped when either is missing."""

from pathlib import Path

import numpy as np
import pytest

from herd_ai.boxes import iou_matrix
from herd_ai.coco import load_person_gt
from herd_ai.detector import PersonDetector
from herd_ai.paths import ANNOTATIONS_FILE, IMAGES_DIR, MODELS_DIR

MODEL = MODELS_DIR / "yolov8n_256_quant_pc_uf_od_coco-person.tflite"

needs_model = pytest.mark.skipif(not MODEL.exists(), reason="model not downloaded; run scripts/download_models.py")
needs_data = pytest.mark.skipif(
    not (ANNOTATIONS_FILE.exists() and IMAGES_DIR.exists()), reason="COCO val2017 not downloaded"
)


def _load_rgb(path: Path) -> np.ndarray:
    import cv2

    bgr = cv2.imread(str(path))
    assert bgr is not None, path
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _typical_single_person_images(n: int = 8):
    """The first ``n`` val2017 images (by id) with exactly one upright person covering 20-50% of the frame.

    Single odd images are avoided on purpose: the one whose person fills the whole frame (id 500716)
    scores only 0.50, and a lying-down subject (id 581206) scores 0.24 despite a 0.97 IoU box.
    """
    gts = load_person_gt(ANNOTATIONS_FILE)
    chosen = []
    for g in sorted(gts.values(), key=lambda g: g.image_id):
        if g.boxes.shape[0] != 1 or g.crowd.shape[0]:
            continue
        x1, y1, x2, y2 = g.boxes[0]
        frac = (x2 - x1) * (y2 - y1) / (g.width * g.height)
        if 0.2 <= frac <= 0.5 and (y2 - y1) > (x2 - x1):
            chosen.append(g)
        if len(chosen) == n:
            break
    return chosen


@needs_model
def test_detector_reports_input_size_and_name_from_model():
    det = PersonDetector(MODEL)
    assert det.input_size == 256
    assert det.name == "yolov8n_256_quant_pc_uf_od_coco-person"


@needs_model
def test_detector_returns_no_boxes_on_a_blank_image():
    det = PersonDetector(MODEL, score_thresh=0.5)
    result = det.detect(np.full((480, 640, 3), 128, dtype=np.uint8))
    assert result.boxes.shape == (0, 4)
    assert result.scores.shape == (0,)
    assert result.latency_ms > 0


@needs_model
@needs_data
def test_detector_localizes_typical_single_people_in_coco_images():
    """Boxes land on the person (IoU >= 0.5) for most typical photos: proves decode + rescale are right."""
    det = PersonDetector(MODEL, score_thresh=0.25)
    localized, top_scores = 0, []
    cohort = _typical_single_person_images()
    assert len(cohort) == 8
    for gt in cohort:
        result = det.detect(_load_rgb(IMAGES_DIR / gt.file_name))
        assert (result.boxes >= 0).all()
        assert (result.boxes[:, [0, 2]] <= gt.width).all() and (result.boxes[:, [1, 3]] <= gt.height).all()
        if len(result) and iou_matrix(result.boxes, gt.boxes).max() >= 0.5:
            localized += 1
            top_scores.append(result.scores.max())
    assert localized >= 6, f"only {localized} of 8 single-person images were localized at IoU 0.5"
    assert max(top_scores) >= 0.8
