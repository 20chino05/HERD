"""A virtual pan camera on a wide video, driven by the firmware's follow law.

The video frame is the world. The camera sees a window `view_frac` of the frame wide (the full
height); its pan angle slides the window sideways at `hfov_deg` per window width, so the window
hits the frame edges at the pan limit. Each frame: crop the window, detect (labeled boxes as perfect
detections, or the real detector on the crop), run the firmware tracker, hand the target's box to
the follow law (`pantilt.py`, a mirror of pantilt.c) after `latency_ms`, and step the servos every
`loop_ms` until the next frame, like app_loop() does.

One episode follows one labeled person from the first frame they are inside the home window until
their track ends or the target is lost. The error that matters is where the *labeled* person is in
the view, not where the tracked box is, so an id switch onto someone else counts against the law.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .mot import GTBox
from .pantilt import LEFT, RIGHT, PanTilt
from .tracker import Detection, NearestTracker

MAX_BOXES = 8


@dataclass(frozen=True)
class SimConfig:
    hfov_deg: int = 60
    vfov_deg: int = 45
    view_frac: float = 0.5
    follow_gain_pct: int = 30
    max_speed_dps: int = 120
    follow_deadband: int = 0
    loop_ms: int = 5
    latency_ms: int = 30
    fps: float | None = None  # resample the labels to this frame rate (None = the video's)
    match_dist: int = 200
    drop_ms: int = 1000
    target_lost_ms: int = 1500
    band: int = 150  # "centered" = within this many thousandths of the middle
    edge_margin: int = 120  # FRAME_EDGE_MARGIN

    def label(self) -> str:
        s = f"gain{self.follow_gain_pct}_speed{self.max_speed_dps}_dead{self.follow_deadband}"
        return s + (f"_{self.fps:g}fps" if self.fps else "")


class VirtualCamera:
    def __init__(self, width: int, height: int, cfg: SimConfig):
        self.W, self.H = width, height
        self.vw = int(round(width * cfg.view_frac))
        self.px_per_deg = self.vw / cfg.hfov_deg
        self.pan_limit_deg = int(((width - self.vw) / 2) / self.px_per_deg)

    def window(self, pan_x10: int) -> tuple[int, int]:
        cx = self.W / 2 + pan_x10 / 10 * self.px_per_deg
        x0 = int(round(cx - self.vw / 2))
        x0 = max(0, min(self.W - self.vw, x0))
        return x0, x0 + self.vw

    def to_view(self, b: GTBox, x0: int, score: int = 90) -> Detection | None:
        cx, cy = (b.x1 + b.x2) / 2 - x0, (b.y1 + b.y2) / 2
        if cx < 0 or cx >= self.vw:
            return None
        return Detection(int(round(cx / self.vw * 1000)), int(round(cy / self.H * 1000)),
                         int(round((b.x2 - b.x1) / self.vw * 1000)), int(round((b.y2 - b.y1) / self.H * 1000)), score)

    def view_x(self, x_px: float, x0: int) -> int:
        """A world x in pixels -> thousandths of the current view (may be outside 0..1000)."""
        return int(round((x_px - x0) / self.vw * 1000))

    def angle_x10_of(self, x_px: float) -> int:
        return int(round((x_px - self.W / 2) / self.px_per_deg * 10))


@dataclass
class Episode:
    seq: str
    gt_id: int
    start_ms: int
    end_ms: int
    frames: int = 0  # frames where the labeled person was still in the scene
    in_band: int = 0  # ... and inside the center band of the view
    visible: int = 0  # ... and anywhere inside the view
    abs_err_sum: float = 0.0
    reversals: int = 0
    moves: int = 0
    lost_ms: int | None = None
    hit_limit: bool = False
    handoff_ready_ms: int | None = None
    trace: list = field(default_factory=list)  # (t_ms, pan_x10, person_angle_x10, person_view_x)

    @property
    def followed_ms(self) -> int:
        return (self.lost_ms if self.lost_ms is not None else self.end_ms) - self.start_ms

    @property
    def in_band_frac(self) -> float:
        return self.in_band / self.frames if self.frames else 0.0

    @property
    def visible_frac(self) -> float:
        return self.visible / self.frames if self.frames else 0.0

    @property
    def mean_abs_err(self) -> float:
        return self.abs_err_sum / self.frames if self.frames else 0.0


def _center_x(b: GTBox) -> float:
    return (b.x1 + b.x2) / 2


def resampled_frames(gt: dict[int, list[GTBox]], native_fps: float, fps: float | None) -> list[int]:
    frames = sorted(gt)
    if fps and fps < native_fps:
        step = max(1, int(round(native_fps / fps)))
        frames = frames[::step]
    return frames


def run_episode(seq: str, gt: dict[int, list[GTBox]], width: int, height: int, native_fps: float, gt_id: int,
                cfg: SimConfig, detect_fn=None) -> Episode | None:
    """detect_fn(frame_index, x0, x1) -> list[Detection] in view thousandths; None = perfect labeled boxes."""
    cam = VirtualCamera(width, height, cfg)
    frames = resampled_frames(gt, native_fps, cfg.fps)
    by_frame = {f: {b.track_id: b for b in gt[f]} for f in frames}
    h0, h1 = cam.window(0)
    start = next((f for f in frames if gt_id in by_frame[f] and h0 <= _center_x(by_frame[f][gt_id]) < h1), None)
    if start is None:
        return None
    end = max(f for f in frames if gt_id in by_frame[f])
    t_of = lambda f: int(round((f - 1) * 1000.0 / native_fps))  # noqa: E731

    pt = PanTilt(hfov_deg=cfg.hfov_deg, vfov_deg=cfg.vfov_deg, pan_min_deg=-cam.pan_limit_deg, pan_max_deg=cam.pan_limit_deg,
                 follow_gain_pct=cfg.follow_gain_pct, max_speed_dps=cfg.max_speed_dps, follow_deadband=cfg.follow_deadband)
    tracker = NearestTracker(match_dist=cfg.match_dist, drop_ms=cfg.drop_ms)
    ep = Episode(seq, gt_id, t_of(start), t_of(end))
    t_prev = t_of(start)
    pt.update(t_prev)
    target_id = None
    last_seen = t_prev
    pending = None  # (due_ms, x, y)
    last_dir = 0

    for f in frames:
        if f < start:
            continue
        if f > end:
            break
        t = t_of(f)
        s = t_prev + cfg.loop_ms
        while s <= t:
            if pending is not None and pending[0] <= s:
                pt.follow(pending[1], pending[2])
                pending = None
            before = pt.pan_x10
            pt.update(s)
            d = (pt.pan_x10 > before) - (pt.pan_x10 < before)
            if d:
                ep.moves += 1
                if last_dir and d != last_dir:
                    ep.reversals += 1
                last_dir = d
            s += cfg.loop_ms
        t_prev = t

        x0, x1 = cam.window(pt.pan_x10)
        if detect_fn is not None:
            dets = detect_fn(f, x0, x1)
        else:
            dets = [d for d in (cam.to_view(b, x0) for b in sorted(gt[f], key=lambda b: b.track_id)) if d is not None][:MAX_BOXES]
        tracks = tracker.update(dets, t)
        gt_box = by_frame[f].get(gt_id)
        if gt_box is None:
            continue
        person_vx = cam.view_x(_center_x(gt_box), x0)
        ep.frames += 1
        ep.visible += 0 <= person_vx < 1000
        ep.in_band += abs(person_vx - 500) <= cfg.band
        ep.abs_err_sum += abs(person_vx - 500)
        ep.trace.append((t, pt.pan_x10, cam.angle_x10_of(_center_x(gt_box)), person_vx))

        if target_id is None:
            near = [tr for tr in tracks if tr.last_seen_ms == t and abs(tr.cx - person_vx) <= 100]
            if not near:
                continue
            target_id = min(near, key=lambda tr: abs(tr.cx - person_vx)).id
            last_seen = t
        tr = next((x for x in tracks if x.id == target_id), None)
        if tr is None or tr.last_seen_ms != t:
            if t - last_seen > cfg.target_lost_ms:
                ep.lost_ms = t
                break
            continue
        last_seen = t
        pending = (t + cfg.latency_ms, tr.cx, tr.cy)
        if (tr.cx >= 1000 - cfg.edge_margin and pt.at_limit(RIGHT)) or (tr.cx <= cfg.edge_margin and pt.at_limit(LEFT)):
            ep.hit_limit = True
            if ep.handoff_ready_ms is None:
                ep.handoff_ready_ms = t
    return ep


def episode_ids(gt: dict[int, list[GTBox]], native_fps: float, min_seconds: float = 3.0) -> list[int]:
    length: dict[int, int] = {}
    for boxes in gt.values():
        for b in boxes:
            length[b.track_id] = length.get(b.track_id, 0) + 1
    return sorted(i for i, n in length.items() if n >= min_seconds * native_fps)


def summarize(episodes: list[Episode]) -> dict:
    eps = [e for e in episodes if e is not None and e.frames > 0]
    frames = sum(e.frames for e in eps)
    followed_s = sum(e.followed_ms for e in eps) / 1000
    return {
        "episodes": len(eps),
        "frames": frames,
        "in_band_frac": sum(e.in_band for e in eps) / frames if frames else 0.0,
        "visible_frac": sum(e.visible for e in eps) / frames if frames else 0.0,
        "mean_abs_err": sum(e.abs_err_sum for e in eps) / frames if frames else 0.0,
        "lost": sum(1 for e in eps if e.lost_ms is not None and not e.hit_limit),
        "handoff_ready": sum(1 for e in eps if e.handoff_ready_ms is not None),
        "reversals_per_min": sum(e.reversals for e in eps) / followed_s * 60 if followed_s else 0.0,
        "followed_s": followed_s,
    }
