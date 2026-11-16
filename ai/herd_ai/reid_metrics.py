"""Scoring a re-identification model.

``evaluate_rank`` is the standard Market-1501 protocol (CMC rank-k and mAP) so our numbers compare
with published ones. The other functions answer the project's own questions: how far apart are
"same person" and "different person" embeddings across cameras, what distance threshold should a
unit use, and how often does it pick the right person when k people walk in together.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

JUNK_PID = -1


@dataclass
class RankResult:
    cmc: np.ndarray  # cmc[k-1] = fraction of queries whose true match is within the top k
    map: float
    n_valid_queries: int


def _cross_camera_mask(q_cam: int, g_camids: np.ndarray, g_pids: np.ndarray) -> np.ndarray:
    return (g_camids != q_cam) & (g_pids != JUNK_PID)


def evaluate_rank(distmat, q_pids, q_camids, g_pids, g_camids, max_rank: int = 10) -> RankResult:
    """CMC and mAP over all queries. For each query, gallery images of the same person from the same
    camera and junk images (pid -1) are removed, as in the Market-1501 evaluation code."""
    distmat = np.asarray(distmat, dtype=np.float64)
    q_pids, q_camids = np.asarray(q_pids), np.asarray(q_camids)
    g_pids, g_camids = np.asarray(g_pids), np.asarray(g_camids)
    n_q, n_g = distmat.shape
    max_rank = min(max_rank, n_g)

    order_all = np.argsort(distmat, axis=1)
    cmcs: list[np.ndarray] = []
    aps: list[float] = []
    for qi in range(n_q):
        order = order_all[qi]
        remove = ((g_pids[order] == q_pids[qi]) & (g_camids[order] == q_camids[qi])) | (g_pids[order] == JUNK_PID)
        matches = (g_pids[order] == q_pids[qi])[~remove]
        if not matches.any():
            continue
        hit = np.minimum(np.cumsum(matches), 1)
        cmc = hit[:max_rank]
        if len(cmc) < max_rank:
            cmc = np.concatenate([cmc, np.full(max_rank - len(cmc), cmc[-1])])
        cmcs.append(cmc.astype(np.float64))
        precision_at = np.cumsum(matches) / (np.arange(len(matches)) + 1)
        aps.append(float((precision_at * matches).sum() / matches.sum()))

    if not aps:
        return RankResult(np.full(max_rank, np.nan), float("nan"), 0)
    return RankResult(np.mean(cmcs, axis=0), float(np.mean(aps)), len(aps))


def pair_distances(distmat, q_pids, q_camids, g_pids, g_camids) -> tuple[np.ndarray, np.ndarray]:
    """All cross-camera query/gallery distances, split into same-person and different-person pairs."""
    distmat = np.asarray(distmat)
    q_pids, q_camids = np.asarray(q_pids), np.asarray(q_camids)
    g_pids, g_camids = np.asarray(g_pids), np.asarray(g_camids)
    valid = (q_camids[:, None] != g_camids[None, :]) & (g_pids[None, :] != JUNK_PID)
    same = q_pids[:, None] == g_pids[None, :]
    return distmat[valid & same], distmat[valid & ~same]


def threshold_table(pos, neg, thresholds) -> list[dict]:
    """For each distance threshold: true-accept rate on same-person pairs and false-accept rate on
    different-person pairs (a pair is "accepted" as the same person when distance <= threshold)."""
    pos, neg = np.asarray(pos), np.asarray(neg)
    rows = []
    for t in thresholds:
        rows.append(
            {
                "threshold": float(t),
                "tpr": float(np.mean(pos <= t)) if len(pos) else float("nan"),
                "fpr": float(np.mean(neg <= t)) if len(neg) else float("nan"),
            }
        )
    return rows


def pick_threshold(pos, neg, max_fpr: float) -> float:
    """The largest distance threshold whose false-accept rate stays at or under ``max_fpr``."""
    pos, neg_sorted = np.asarray(pos, dtype=np.float64), np.sort(np.asarray(neg, dtype=np.float64))
    n = len(neg_sorted)
    allowed = int(np.floor(max_fpr * n + 1e-9))
    if allowed >= n:
        return float(max(pos.max() if len(pos) else 0.0, neg_sorted[-1] if n else 0.0))
    bound = neg_sorted[allowed]  # the first negative that must be rejected
    accepted = np.concatenate([pos, neg_sorted[:allowed]])
    below = accepted[accepted < bound]
    return float(below.max()) if len(below) else float(np.nextafter(bound, -np.inf))


def nearest_of_k(distmat, q_pids, q_camids, g_pids, g_camids, k: int = 2, rng=None, trials_per_query: int = 1) -> float:
    """``k`` people walk into the neighbor camera's view and one of them is the person we were told
    about: how often is that person the nearest embedding? Each trial draws one cross-camera image of
    the right person and ``k - 1`` of other people."""
    rng = rng if rng is not None else np.random.default_rng(0)
    distmat = np.asarray(distmat)
    q_pids, q_camids = np.asarray(q_pids), np.asarray(q_camids)
    g_pids, g_camids = np.asarray(g_pids), np.asarray(g_camids)
    hits = trials = 0
    for qi in range(distmat.shape[0]):
        cross = _cross_camera_mask(q_camids[qi], g_camids, g_pids)
        pos_idx = np.flatnonzero(cross & (g_pids == q_pids[qi]))
        neg_idx = np.flatnonzero(cross & (g_pids != q_pids[qi]))
        if len(pos_idx) == 0 or len(neg_idx) < k - 1:
            continue
        for _ in range(trials_per_query):
            p = rng.choice(pos_idx)
            others = rng.choice(neg_idx, size=k - 1, replace=False)
            hits += int(distmat[qi, p] < distmat[qi, others].min())
            trials += 1
    return hits / trials if trials else float("nan")
