"""MOTChallenge ground truth and a small tracking scorecard.

``gt.txt`` rows are ``frame, id, left, top, width, height, conf, x, y, z`` (MOT15); rows with
``conf`` 0 are not evaluated. The scorecard follows the CLEAR MOT definitions: a track box matches a
ground-truth box at IoU >= 0.5, an id switch is counted when a ground-truth person is matched to a
different track id than last time, and MOTA = 1 - (misses + false alarms + id switches) / ground truth.
"""

from __future__ import annotations

import configparser
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from herd_ai.boxes import iou_matrix


@dataclass(frozen=True)
class GTBox:
    frame: int
    track_id: int
    x1: float
    y1: float
    x2: float
    y2: float


def load_mot_gt(path: str | Path, scale: float = 1.0) -> dict[int, list[GTBox]]:
    """Flagged ground-truth boxes per frame, in pixels (multiplied by ``scale`` if the video was resized)."""
    gt: dict[int, list[GTBox]] = defaultdict(list)
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(",")
        if len(parts) < 6:
            continue
        frame, tid = int(parts[0]), int(parts[1])
        x, y, w, h = (float(v) * scale for v in parts[2:6])
        conf = float(parts[6]) if len(parts) > 6 else 1.0
        if conf == 0:
            continue
        gt[frame].append(GTBox(frame, tid, x, y, x + w, y + h))
    return dict(gt)


def load_seqinfo(path: str | Path) -> dict:
    """``seqinfo.ini`` -> {name, frame_rate, seq_length, width, height}."""
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")
    s = cp["Sequence"]
    return {
        "name": s.get("name"),
        "frame_rate": float(s.get("frameRate")),
        "seq_length": int(s.get("seqLength")),
        "width": int(s.get("imWidth")),
        "height": int(s.get("imHeight")),
    }


def count_people_per_frame(gt: dict[int, list[GTBox]]) -> dict[int, int]:
    return {f: len(boxes) for f, boxes in gt.items()}


def crowd_bin(n: int) -> str:
    if n <= 0:
        return "0"
    if n <= 2:
        return "1-2"
    if n <= 4:
        return "3-4"
    return "5+"


class MOTAccumulator:
    def __init__(self, iou_thresh: float = 0.5):
        self.iou_thresh = iou_thresh
        self._rows: list[dict] = []
        self._last_hyp: dict[int, int] = {}
        self._gt_frames: Counter = Counter()
        self._gt_matched: Counter = Counter()

    def update(self, frame: int, gt_boxes: list[GTBox], hyps: list[tuple]) -> None:
        """``hyps`` are ``(track_id, x1, y1, x2, y2)`` in the same pixel space as the ground truth."""
        n_gt, n_h = len(gt_boxes), len(hyps)
        pairs: list[tuple[int, int]] = []
        if n_gt and n_h:
            g = np.array([[b.x1, b.y1, b.x2, b.y2] for b in gt_boxes], dtype=np.float64)
            h = np.array([list(hp[1:5]) for hp in hyps], dtype=np.float64)
            iou = iou_matrix(g, h)
            used_g, used_h = set(), set()
            for gi, hi in sorted(zip(*np.nonzero(iou >= self.iou_thresh)), key=lambda p: -iou[p[0], p[1]]):
                if gi in used_g or hi in used_h:
                    continue
                used_g.add(gi)
                used_h.add(hi)
                pairs.append((int(gi), int(hi)))

        idsw = 0
        for gi, hi in pairs:
            gt_id, hyp_id = gt_boxes[gi].track_id, int(hyps[hi][0])
            if gt_id in self._last_hyp and self._last_hyp[gt_id] != hyp_id:
                idsw += 1
            self._last_hyp[gt_id] = hyp_id
            self._gt_matched[gt_id] += 1
        for b in gt_boxes:
            self._gt_frames[b.track_id] += 1

        tp = len(pairs)
        self._rows.append(
            {"frame": frame, "bin": crowd_bin(n_gt), "n_gt": n_gt, "tp": tp, "fp": n_h - tp, "fn": n_gt - tp, "idsw": idsw}
        )

    @staticmethod
    def _totals(rows: list[dict]) -> dict:
        n_gt = sum(r["n_gt"] for r in rows)
        tp = sum(r["tp"] for r in rows)
        fp = sum(r["fp"] for r in rows)
        fn = sum(r["fn"] for r in rows)
        idsw = sum(r["idsw"] for r in rows)
        return {
            "n_frames": len(rows),
            "n_gt": n_gt,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "idsw": idsw,
            "mota": 1.0 - (fn + fp + idsw) / n_gt if n_gt else float("nan"),
            "recall": tp / n_gt if n_gt else float("nan"),
            "precision": tp / (tp + fp) if (tp + fp) else float("nan"),
        }

    def summary(self) -> dict:
        s = self._totals(self._rows)
        s["n_gt_tracks"] = len(self._gt_frames)
        s["mostly_tracked"] = sum(1 for tid, n in self._gt_frames.items() if self._gt_matched[tid] / n >= 0.8)
        s["mostly_lost"] = sum(1 for tid, n in self._gt_frames.items() if self._gt_matched[tid] / n < 0.2)
        return s

    def summary_by_crowd(self) -> dict[str, dict]:
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in self._rows:
            groups[r["bin"]].append(r)
        return {b: self._totals(rows) for b, rows in groups.items()}
