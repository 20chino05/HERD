"""The lingering rule, a line-for-line mirror of firmware/stm32/App/behavior.c.

A person is lingering when they stay within `radius` (thousandths of the frame) of one spot for
`time_ms`. Each stay is reported once, by the id the tracker gave the person. Moving further than
the radius from the spot starts the clock again from the new spot. One id is reported per update,
the next one on the next frame, exactly as the C does. Slots are limited to TRACK_MAX like the
firmware: a ninth person is simply not watched.

Two optional guards, measured in week 8 (off = the firmware as merged):
- `require_motion`: only someone who has moved more than the radius since first seen can be
  reported, which silences a detector false positive on a static object (it never moves);
- `min_score`: the last detection score (percent) must be at least this.
"""

from __future__ import annotations

from dataclasses import dataclass

from .tracker import Track


@dataclass
class _Slot:
    used: bool = False
    anchored: bool = False
    reported: bool = False
    moved: bool = False
    id: int = 0
    anchor_x: int = 0
    anchor_y: int = 0
    since_ms: int = 0


class LingerDetector:
    def __init__(self, radius: int = 120, time_ms: int = 8000, max_slots: int = 8, require_motion: bool = False, min_score: int = 0):
        self.radius = int(radius)
        self.time_ms = int(time_ms)
        self.require_motion = require_motion
        self.min_score = int(min_score)
        self._slots = [_Slot() for _ in range(max_slots)]

    def _slot_for(self, track_id: int) -> _Slot | None:
        for s in self._slots:
            if s.used and s.id == track_id:
                return s
        for s in self._slots:
            if not s.used:
                s.used, s.anchored, s.reported, s.moved = True, False, False, False
                s.id, s.anchor_x, s.anchor_y, s.since_ms = track_id, 0, 0, 0
                return s
        return None

    def update(self, tracks: list[Track], now_ms: int) -> int:
        """Call once per frame with the tracker's active tracks. Returns the id of someone who just
        started lingering, or 0."""
        active = {t.id for t in tracks}
        for s in self._slots:
            if s.used and s.id not in active:
                s.used = False
        r2 = self.radius * self.radius
        lingering = 0
        for t in tracks:
            s = self._slot_for(t.id)
            if s is None:
                continue
            x, y = int(t.cx), int(t.cy)
            dx, dy = x - s.anchor_x, y - s.anchor_y
            if not s.anchored or dx * dx + dy * dy > r2:
                if s.anchored:
                    s.moved = True
                s.anchored, s.anchor_x, s.anchor_y, s.since_ms, s.reported = True, x, y, int(now_ms), False
                continue
            if s.reported or lingering != 0 or int(now_ms) - s.since_ms < self.time_ms:
                continue
            if (self.require_motion and not s.moved) or t.score < self.min_score:
                continue
            s.reported = True
            lingering = t.id
        return lingering

    def _find(self, track_id: int) -> _Slot | None:
        for s in self._slots:
            if s.used and s.id == track_id:
                return s
        return None

    def is_lingering(self, track_id: int) -> bool:
        s = self._find(track_id)
        return bool(s and s.reported)

    def standing_ms(self, track_id: int, now_ms: int) -> int | None:
        """How long this person has been within the radius of their current spot, or None."""
        s = self._find(track_id)
        if s is None or not s.anchored:
            return None
        return int(now_ms) - s.since_ms

    def anchor(self, track_id: int) -> tuple[int, int] | None:
        s = self._find(track_id)
        return (s.anchor_x, s.anchor_y) if s and s.anchored else None
