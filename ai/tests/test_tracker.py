"""The frame-to-frame tracker. The default settings mirror firmware/stm32/App/tracker.c and
app_config.h (positions in thousandths of the frame, nearest match within TRACK_MATCH_DIST,
drop after TRACK_DROP_MS), so what we measure here transfers to the board."""

import numpy as np

from herd_ai.tracker import Detection, NearestTracker, detections_from_pixels


def det(cx, cy, w=100, h=300, score=90):
    return Detection(cx, cy, w, h, score)


def test_detections_from_pixels_convert_to_thousandths_of_the_frame():
    boxes = np.array([[0.0, 0.0, 320.0, 240.0], [160.0, 60.0, 480.0, 240.0]])
    dets = detections_from_pixels(boxes, np.array([0.91, 0.5]), width=640, height=240)
    assert dets[0] == Detection(250, 500, 500, 1000, 91)
    assert dets[1] == Detection(500, 625, 500, 750, 50)


def test_same_person_keeps_the_same_id_while_moving_a_little():
    tr = NearestTracker(match_dist=200, drop_ms=1000)
    a = tr.update([det(500, 500)], 0)
    b = tr.update([det(540, 505)], 100)
    assert len(a) == 1 and len(b) == 1
    assert a[0].id == b[0].id == 1
    assert b[0].cx == 540 and b[0].vx == 400  # 40 thousandths in 0.1 s


def test_a_jump_larger_than_match_dist_starts_a_new_id():
    tr = NearestTracker(match_dist=200, drop_ms=1000)
    tr.update([det(100, 500)], 0)
    tracks = tr.update([det(400, 500)], 100)
    assert sorted(t.id for t in tracks) == [1, 2]


def test_tracks_are_dropped_after_drop_ms_without_detections():
    tr = NearestTracker(match_dist=200, drop_ms=1000)
    tr.update([det(500, 500)], 0)
    assert len(tr.update([], 900)) == 1
    assert len(tr.update([], 1001)) == 0


def test_two_people_get_two_ids_and_keep_them():
    tr = NearestTracker(match_dist=200, drop_ms=1000)
    tr.update([det(200, 500), det(800, 500)], 0)
    tracks = tr.update([det(810, 500), det(190, 500)], 100)  # detection order changes
    by_x = {t.cx: t.id for t in tracks}
    assert by_x[190] == 1 and by_x[810] == 2


def test_no_more_than_max_tracks_people_are_followed():
    tr = NearestTracker(match_dist=50, drop_ms=1000, max_tracks=2)
    tracks = tr.update([det(100, 500), det(400, 500), det(700, 500)], 0)
    assert len(tracks) == 2


def test_ids_count_up_and_skip_zero():
    tr = NearestTracker(match_dist=50, drop_ms=100)
    tr._next_id = 65535
    tr.update([det(100, 500)], 0)
    tr.update([], 500)  # dropped
    tracks = tr.update([det(900, 500)], 600)
    assert tracks[0].id == 1


def test_velocity_prediction_can_be_switched_on_for_matching():
    # Walking at 1500 thousandths/s sampled every 100 ms: the jump grows from 150 to 300.
    plain = NearestTracker(match_dist=200, drop_ms=1000)
    plain.update([det(100, 500)], 0)
    plain.update([det(250, 500)], 100)  # jump 150: same id
    plain.update([det(550, 500)], 200)  # jump 300: a new id without prediction
    assert plain._next_id == 3

    pred = NearestTracker(match_dist=200, drop_ms=1000, predict=True)
    pred.update([det(100, 500)], 0)
    pred.update([det(250, 500)], 100)
    tracks = pred.update([det(550, 500)], 200)  # predicted at 400, only 150 away: same id
    assert [t.id for t in tracks] == [1]


def test_iou_matching_is_available_as_an_alternative():
    tr = NearestTracker(match="iou", min_iou=0.3, drop_ms=1000)
    tr.update([det(500, 500, 200, 400)], 0)
    same = tr.update([det(520, 500, 200, 400)], 100)
    assert same[0].id == 1
    far = tr.update([det(900, 500, 200, 400)], 200)
    assert sorted(t.id for t in far) == [1, 2]
