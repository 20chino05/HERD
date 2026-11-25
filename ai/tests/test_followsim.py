"""The virtual pan camera and the follow law on a made-up scene: one person walking across a wide
frame at a steady speed while another stands still."""

from herd_ai.followsim import SimConfig, VirtualCamera, episode_ids, run_episode, summarize
from herd_ai.mot import GTBox

W, H, FPS = 1200, 600, 10.0  # the camera sees the middle 600 px at home and can pan +-30 deg (300 px)


def walking_scene(speed_px_per_s: float = 50.0, seconds: float = 12.0, start_x: float = 450.0, stop_x: float = 880.0):
    """Person 1 walks right from start_x and stops at stop_x; person 2 stands still at x = 350."""
    gt = {}
    for i in range(int(seconds * FPS)):
        x = min(start_x + speed_px_per_s * i / FPS, stop_x)
        boxes = [GTBox(i + 1, 2, 320, 150, 380, 450)]
        if x + 30 < W:
            boxes.append(GTBox(i + 1, 1, x - 30, 150, x + 30, 450))
        gt[i + 1] = boxes
    return gt


def test_camera_window_and_angles():
    cam = VirtualCamera(W, H, SimConfig(hfov_deg=60, view_frac=0.5))
    assert cam.vw == 600 and cam.px_per_deg == 10.0 and cam.pan_limit_deg == 30
    assert cam.window(0) == (300, 900)
    assert cam.window(100) == (400, 1000)   # +10 deg -> 100 px right
    assert cam.window(900) == (600, 1200)   # clamped at the frame edge
    assert cam.angle_x10_of(700) == 100
    d = cam.to_view(GTBox(1, 1, 570, 150, 630, 450), 300)
    assert (d.cx, d.cy, d.w, d.h) == (500, 500, 100, 500)
    assert cam.to_view(GTBox(1, 1, 950, 150, 1010, 450), 300) is None  # outside the window


def test_following_keeps_the_walker_centered_and_a_fixed_camera_does_not():
    gt = walking_scene()
    assert episode_ids(gt, FPS) == [1, 2]
    follow = run_episode("toy", gt, W, H, FPS, 1, SimConfig(follow_gain_pct=30, max_speed_dps=120))
    fixed = run_episode("toy", gt, W, H, FPS, 1, SimConfig(follow_gain_pct=0))
    assert follow.frames == fixed.frames == 120
    assert follow.in_band_frac > 0.9, follow.in_band_frac
    assert fixed.visible_frac == 1.0 and fixed.in_band_frac < 0.5  # in view, but centered only while passing the middle
    assert follow.lost_ms is None and not follow.hit_limit


def test_walking_out_of_range_reaches_the_pan_limit_and_the_handoff_condition():
    gt = walking_scene(speed_px_per_s=60.0, stop_x=10_000)
    ep = run_episode("toy", gt, W, H, FPS, 1, SimConfig())
    assert ep.hit_limit and ep.handoff_ready_ms is not None
    assert ep.visible_frac > 0.8  # followed all the way to the limit


def test_summary_aggregates_episodes():
    gt = walking_scene()
    eps = [run_episode("toy", gt, W, H, FPS, i, SimConfig()) for i in episode_ids(gt, FPS)]
    s = summarize(eps)
    assert s["episodes"] == 2 and s["frames"] == sum(e.frames for e in eps if e)
    assert 0.0 <= s["in_band_frac"] <= 1.0 and s["followed_s"] > 0


def test_resampling_to_a_lower_frame_rate_keeps_the_person_tracked():
    gt = walking_scene()
    slow = run_episode("toy", gt, W, H, FPS, 1, SimConfig(fps=5))
    assert slow is not None and slow.frames == 60 and slow.in_band_frac > 0.8
