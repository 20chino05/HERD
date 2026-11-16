"""Person re-identification: Market-1501 file names, the standard rank/mAP protocol, pair thresholds,
and the "which of k people is the one I was told about" test. Pure-math tests run always; the
embedder tests need ST's OSNet file."""

import numpy as np
import pytest

from herd_ai.models import MODELS_DIR
from herd_ai.reid import (
    PersonEmbedder,
    cosine_distance_matrix,
    crop_person,
    parse_market_name,
    prepare_crop,
)
from herd_ai.reid_metrics import evaluate_rank, nearest_of_k, pair_distances, pick_threshold, threshold_table

OSNET = MODELS_DIR / "osnet_a025_256_128_tfs_int8.tflite"
needs_osnet = pytest.mark.skipif(not OSNET.exists(), reason="OSNet model not downloaded")


def test_market_file_names_give_person_and_camera_ids():
    assert parse_market_name("0001_c1s1_001051_00.jpg") == (1, 1)
    assert parse_market_name("1501_c6s4_001877_01.jpg") == (1501, 6)
    assert parse_market_name("-1_c3s2_000123_00.jpg") == (-1, 3)  # junk
    assert parse_market_name("0000_c2s1_000005_01.jpg") == (0, 2)  # distractor


def test_prepare_crop_stretches_to_256_by_128_uint8():
    crop = np.full((300, 90, 3), 200, dtype=np.uint8)
    tensor = prepare_crop(crop)
    assert tensor.shape == (1, 256, 128, 3)
    assert tensor.dtype == np.uint8
    assert int(tensor[0, 128, 64, 0]) == 200


def test_crop_person_clips_to_the_image_and_can_add_margin():
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    crop = crop_person(img, (150.0, 20.0, 260.0, 90.0))
    assert crop.shape == (70, 50, 3)
    wide = crop_person(img, (100.0, 40.0, 120.0, 60.0), margin=0.5)
    assert wide.shape == (40, 40, 3)
    with pytest.raises(ValueError):
        crop_person(img, (300.0, 0.0, 310.0, 10.0))


def test_cosine_distance_matrix_on_unit_vectors():
    a = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    b = np.array([[1.0, 0.0], [np.sqrt(0.5), np.sqrt(0.5)]], dtype=np.float32)
    d = cosine_distance_matrix(a, b)
    assert d.shape == (2, 2)
    assert d[0, 0] == pytest.approx(0.0, abs=1e-6)
    assert d[1, 0] == pytest.approx(1.0, abs=1e-6)
    assert d[0, 1] == pytest.approx(1 - np.sqrt(0.5), abs=1e-6)


# --- rank / mAP protocol ------------------------------------------------------------------------

# Two queries, five gallery images. Rows are distances, smaller is more similar.
# query 0: person 1 seen by camera 1. query 1: person 2 seen by camera 2.
G_PIDS = np.array([1, 1, 2, 0, -1])  # 0 = distractor (stays), -1 = junk (removed)
G_CAMS = np.array([1, 2, 1, 3, 2])
Q_PIDS = np.array([1, 2])
Q_CAMS = np.array([1, 2])
DIST = np.array(
    [
        [0.05, 0.40, 0.30, 0.20, 0.01],  # q0: same-cam copy (removed), true match at 0.40 behind 0.30 and 0.20
        [0.60, 0.70, 0.10, 0.50, 0.00],  # q1: true match is nearest
    ]
)


def test_evaluate_rank_removes_same_camera_and_junk_then_scores_cmc_and_map():
    res = evaluate_rank(DIST, Q_PIDS, Q_CAMS, G_PIDS, G_CAMS, max_rank=5)
    # q0 valid gallery after removing [same pid+cam] and [junk]: idx 1 (0.40), 2 (0.30), 3 (0.20)
    # ranked: 3, 2, 1 -> the true match is third -> rank-1 miss, rank-3 hit, AP = 1/3
    # q1 valid gallery: idx 0, 1, 2, 3 -> ranked 2 first -> rank-1 hit, AP = 1
    assert res.n_valid_queries == 2
    assert res.cmc[0] == pytest.approx(0.5)
    assert res.cmc[2] == pytest.approx(1.0)
    assert res.map == pytest.approx((1 / 3 + 1.0) / 2)


def test_evaluate_rank_skips_queries_with_no_cross_camera_match():
    g_pids = np.array([7, 7])
    g_cams = np.array([1, 1])
    res = evaluate_rank(np.array([[0.1, 0.2]]), np.array([7]), np.array([1]), g_pids, g_cams, max_rank=2)
    assert res.n_valid_queries == 0
    assert np.isnan(res.map)


def test_pair_distances_split_cross_camera_pairs_into_same_and_different_person():
    pos, neg = pair_distances(DIST, Q_PIDS, Q_CAMS, G_PIDS, G_CAMS)
    # q0 cross-camera: idx1 (pos 0.40), idx3 (neg 0.20); idx4 junk dropped; idx0 and idx2 same camera dropped
    # q1 cross-camera: idx0 (neg 0.60), idx2 (pos 0.10), idx3 (neg 0.50); idx1 and idx4 same camera dropped
    assert sorted(pos.tolist()) == [0.10, 0.40]
    assert sorted(neg.tolist()) == [0.20, 0.50, 0.60]


def test_threshold_table_reports_true_and_false_accept_rates():
    pos = np.array([0.1, 0.2, 0.3, 0.4])
    neg = np.array([0.35, 0.5, 0.6, 0.7])
    rows = threshold_table(pos, neg, [0.25, 0.45])
    assert rows[0]["threshold"] == 0.25
    assert rows[0]["tpr"] == pytest.approx(0.5)  # 0.1, 0.2 accepted
    assert rows[0]["fpr"] == pytest.approx(0.0)
    assert rows[1]["tpr"] == pytest.approx(1.0)
    assert rows[1]["fpr"] == pytest.approx(0.25)  # 0.35 wrongly accepted


def test_pick_threshold_is_the_largest_distance_keeping_false_accepts_under_budget():
    pos = np.array([0.1, 0.2, 0.3, 0.4])
    neg = np.array([0.35, 0.5, 0.6, 0.7])
    t = pick_threshold(pos, neg, max_fpr=0.0)
    assert t < 0.35
    assert pick_threshold(pos, neg, max_fpr=0.25) < 0.5
    assert pick_threshold(pos, neg, max_fpr=0.25) >= 0.35


def test_nearest_of_k_measures_picking_the_right_person_out_of_k_arrivals():
    rng = np.random.default_rng(0)
    # q1's true match is always nearest, q0's never is (0.40 vs the only cross-camera negative 0.20)
    acc2 = nearest_of_k(DIST, Q_PIDS, Q_CAMS, G_PIDS, G_CAMS, k=2, rng=rng, trials_per_query=20)
    assert acc2 == pytest.approx(0.5)


# --- the real model ------------------------------------------------------------------------------


@needs_osnet
def test_embedder_returns_unit_vectors_and_zero_distance_for_identical_crops():
    emb = PersonEmbedder(OSNET)
    assert emb.input_hw == (256, 128)
    assert emb.dim == 128
    crop = (np.random.default_rng(1).random((240, 100, 3)) * 255).astype(np.uint8)
    v = emb.embed(crop)
    assert v.shape == (128,)
    assert v.dtype == np.float32
    assert np.linalg.norm(v) == pytest.approx(1.0, abs=1e-4)
    d = cosine_distance_matrix(v[None], emb.embed_batch([crop, 255 - crop]))
    assert d[0, 0] == pytest.approx(0.0, abs=1e-5)
    assert d[0, 1] > d[0, 0]
    assert emb.last_latency_ms > 0
