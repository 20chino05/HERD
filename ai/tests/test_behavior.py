"""The lingering rule, mirrored from firmware/stm32/App/behavior.c: a person who stays within
LINGER_RADIUS of one spot for LINGER_TIME_MS is reported once per stay."""

from herd_ai.behavior import LingerDetector
from herd_ai.tracker import Track


def _track(id_, x, y, now_ms, first_ms=0):
    return Track(id=id_, cx=x, cy=y, w=120, h=400, vx=0, vy=0, first_seen_ms=first_ms, last_seen_ms=now_ms)


def _feed(det, positions, step_ms=100, start_ms=0):
    """positions: list of lists of (id, x, y) per frame. Returns the (frame_time, id) of every report."""
    out = []
    t = start_ms
    for frame in positions:
        got = det.update([_track(i, x, y, t) for i, x, y in frame], t)
        if got:
            out.append((t, got))
        t += step_ms
    return out


def test_standing_still_is_reported_once_after_the_time():
    det = LingerDetector(radius=120, time_ms=8000)
    frames = [[(1, 500, 500)]] * 120  # 12 s at 10 fps
    reports = _feed(det, frames)
    assert reports == [(8000, 1)]
    assert det.is_lingering(1)


def test_small_moves_inside_the_radius_do_not_reset_the_timer():
    det = LingerDetector(radius=120, time_ms=8000)
    frames = [[(1, 500 + (i % 3) * 30, 500 - (i % 2) * 40)] for i in range(100)]
    assert _feed(det, frames) == [(8000, 1)]


def test_walking_away_resets_the_anchor_and_allows_a_new_report_later():
    det = LingerDetector(radius=120, time_ms=8000)
    stand = [[(1, 500, 500)]] * 70       # 7 s, not yet
    walk = [[(1, 500 + 150 * (i + 1), 500)] for i in range(3)]  # jumps of 150 > radius
    stand2 = [[(1, 950, 500)]] * 90      # 9 s at the new spot
    reports = _feed(det, stand + walk + stand2)
    assert reports == [(7200 + 8000, 1)]  # timed from the last jump (frame 72 at 7.2 s)


def test_two_people_lingering_in_the_same_frame_are_reported_one_per_frame():
    det = LingerDetector(radius=120, time_ms=8000)
    frames = [[(1, 300, 500), (2, 700, 500)]] * 90
    assert _feed(det, frames) == [(8000, 1), (8100, 2)]


def test_a_forgotten_track_frees_its_slot_and_a_new_id_starts_fresh():
    det = LingerDetector(radius=120, time_ms=8000)
    _feed(det, [[(1, 500, 500)]] * 50)        # 5 s standing
    _feed(det, [[]] * 3, start_ms=5000)        # tracker dropped them
    reports = _feed(det, [[(2, 500, 500)]] * 90, start_ms=5300)
    assert reports == [(5300 + 8000, 2)]
    assert not det.is_lingering(1)


def test_slots_are_limited_like_the_firmware():
    det = LingerDetector(radius=120, time_ms=1000, max_slots=2)
    frames = [[(1, 100, 500), (2, 400, 500), (3, 700, 500)]] * 15
    reports = _feed(det, frames)
    assert [r[1] for r in reports] == [1, 2]  # no slot for the third person


def test_standing_ms_reports_how_long_they_have_been_at_the_anchor():
    det = LingerDetector(radius=120, time_ms=8000)
    _feed(det, [[(1, 500, 500)]] * 31)  # last update at 3000 ms
    assert det.standing_ms(1, 3000) == 3000
    assert det.standing_ms(1, 3450) == 3450
    assert det.standing_ms(9, 3000) is None


def test_require_motion_ignores_someone_who_never_walked_in():
    det = LingerDetector(radius=120, time_ms=8000, require_motion=True)
    assert _feed(det, [[(1, 500, 500)]] * 100) == []  # a static false detection never moves
    walk = [[(1, 100 + 50 * i, 500)] for i in range(10)]  # 100 -> 550 in 1 s, then stands
    stand = [[(1, 560, 500)]] * 100
    reports = _feed(det, walk + stand)
    assert len(reports) == 1 and reports[0][1] == 1


def test_min_score_holds_the_report_until_the_detection_is_confident():
    det = LingerDetector(radius=120, time_ms=1000, min_score=50)
    weak = [Track(id=1, cx=500, cy=500, w=100, h=400, vx=0, vy=0, first_seen_ms=0, last_seen_ms=0, score=30)]
    strong = [Track(id=1, cx=500, cy=500, w=100, h=400, vx=0, vy=0, first_seen_ms=0, last_seen_ms=0, score=70)]
    for t in range(0, 1500, 100):
        assert det.update(weak, t) == 0
    assert det.update(strong, 1500) == 1
