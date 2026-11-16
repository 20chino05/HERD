"""Frame-to-frame tracking: keep the same id on the same person.

The default settings mirror ``firmware/stm32/App/tracker.c`` and ``app_config.h`` so that what we
measure on the laptop is what the board will do:

- positions are in thousandths of the frame (0 = left/top, 1000 = right/bottom);
- each detection is matched, in order, to the nearest not-yet-claimed track within ``match_dist``
  (TRACK_MATCH_DIST = 200);
- unmatched detections start a new track while a slot is free (TRACK_MAX = 8);
- a track unseen for more than ``drop_ms`` is forgotten (TRACK_DROP_MS = 1000);
- ids count up from 1 and never use 0 ("nobody").

Two optional improvements can be switched on to measure their value: ``predict=True`` matches
against where the person should be given their last speed, and ``match="iou"`` uses box overlap
instead of center distance.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MAX_ID = 65535


@dataclass(frozen=True)
class Detection:
    cx: int
    cy: int
    w: int
    h: int
    score: int  # percent

    def xyxy(self) -> tuple[float, float, float, float]:
        return self.cx - self.w / 2, self.cy - self.h / 2, self.cx + self.w / 2, self.cy + self.h / 2


@dataclass
class Track:
    id: int
    cx: int
    cy: int
    w: int
    h: int
    vx: int  # thousandths of the frame per second
    vy: int
    first_seen_ms: int
    last_seen_ms: int
    hits: int = 1

    def xyxy(self) -> tuple[float, float, float, float]:
        return self.cx - self.w / 2, self.cy - self.h / 2, self.cx + self.w / 2, self.cy + self.h / 2


def detections_from_pixels(boxes_xyxy, scores, width: int, height: int) -> list[Detection]:
    """Pixel boxes from the detector -> the board's thousandths-of-frame representation."""
    out = []
    for (x1, y1, x2, y2), s in zip(np.asarray(boxes_xyxy, dtype=np.float64).reshape(-1, 4), np.asarray(scores)):
        out.append(
            Detection(
                cx=int(round((x1 + x2) / 2 / width * 1000)),
                cy=int(round((y1 + y2) / 2 / height * 1000)),
                w=int(round((x2 - x1) / width * 1000)),
                h=int(round((y2 - y1) / height * 1000)),
                score=int(round(float(s) * 100)),
            )
        )
    return out


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


class NearestTracker:
    def __init__(
        self,
        match_dist: int = 200,
        drop_ms: int = 1000,
        max_tracks: int = 8,
        predict: bool = False,
        match: str = "centroid",
        min_iou: float = 0.3,
    ):
        if match not in ("centroid", "iou"):
            raise ValueError(f"match must be 'centroid' or 'iou', got {match!r}")
        self.match_dist = match_dist
        self.drop_ms = drop_ms
        self.max_tracks = max_tracks
        self.predict = predict
        self.match = match
        self.min_iou = min_iou
        self._tracks: list[Track] = []
        self._next_id = 1

    @property
    def tracks(self) -> list[Track]:
        return list(self._tracks)

    def _predicted_center(self, t: Track, time_ms: int) -> tuple[float, float]:
        if not self.predict:
            return float(t.cx), float(t.cy)
        dt = (time_ms - t.last_seen_ms) / 1000.0
        return t.cx + t.vx * dt, t.cy + t.vy * dt

    def _best_match(self, d: Detection, time_ms: int, claimed: set[int]) -> Track | None:
        best, best_score = None, None
        for t in self._tracks:
            if t.id in claimed:
                continue
            px, py = self._predicted_center(t, time_ms)
            if self.match == "centroid":
                d2 = (d.cx - px) ** 2 + (d.cy - py) ** 2
                if d2 <= self.match_dist**2 and (best is None or d2 < best_score):
                    best, best_score = t, d2
            else:
                pbox = (px - t.w / 2, py - t.h / 2, px + t.w / 2, py + t.h / 2)
                iou = _iou(d.xyxy(), pbox)
                if iou >= self.min_iou and (best is None or iou > best_score):
                    best, best_score = t, iou
        return best

    def update(self, dets: list[Detection], time_ms: int) -> list[Track]:
        """Feed one frame's detections; returns the active tracks afterwards."""
        claimed: set[int] = set()
        for d in dets:
            t = self._best_match(d, time_ms, claimed)
            if t is not None:
                dt = time_ms - t.last_seen_ms
                if dt > 0:
                    t.vx = int((d.cx - t.cx) * 1000 / dt)
                    t.vy = int((d.cy - t.cy) * 1000 / dt)
                t.cx, t.cy, t.w, t.h = d.cx, d.cy, d.w, d.h
                t.last_seen_ms = time_ms
                t.hits += 1
                claimed.add(t.id)
            elif len(self._tracks) < self.max_tracks:
                t = Track(self._next_id, d.cx, d.cy, d.w, d.h, 0, 0, time_ms, time_ms)
                self._next_id = self._next_id + 1 if self._next_id < MAX_ID else 1
                self._tracks.append(t)
                claimed.add(t.id)
        self._tracks = [t for t in self._tracks if time_ms - t.last_seen_ms <= self.drop_ms]
        return list(self._tracks)
