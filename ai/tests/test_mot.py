"""MOTChallenge ground truth and the tracking scorecard (recall, precision, ID switches, MOTA)."""

from pathlib import Path

import pytest

from herd_ai.mot import GTBox, MOTAccumulator, count_people_per_frame, crowd_bin, load_mot_gt

GT_TEXT = """1,1,10,20,50,100,1,-1,-1,-1
1,2,200,20,50,100,1,-1,-1,-1
2,1,12,20,50,100,1,-1,-1,-1
2,2,205,20,50,100,1,-1,-1,-1
2,3,400,20,50,100,0,-1,-1,-1
3,1,14,20,50,100,1,-1,-1,-1
"""


def test_load_mot_gt_keeps_flagged_rows_as_pixel_boxes_per_frame(tmp_path: Path):
    p = tmp_path / "gt.txt"
    p.write_text(GT_TEXT)
    gt = load_mot_gt(p)
    assert sorted(gt) == [1, 2, 3]
    assert gt[1][0] == GTBox(frame=1, track_id=1, x1=10.0, y1=20.0, x2=60.0, y2=120.0)
    assert [b.track_id for b in gt[2]] == [1, 2]  # conf 0 row dropped


def test_people_per_frame_and_crowd_bins(tmp_path: Path):
    p = tmp_path / "gt.txt"
    p.write_text(GT_TEXT)
    gt = load_mot_gt(p)
    assert count_people_per_frame(gt) == {1: 2, 2: 2, 3: 1}
    assert crowd_bin(1) == "1-2" and crowd_bin(2) == "1-2"
    assert crowd_bin(3) == "3-4" and crowd_bin(4) == "3-4"
    assert crowd_bin(5) == "5+" and crowd_bin(9) == "5+"


def _gt(frame, tid, x):
    return GTBox(frame, tid, x, 0.0, x + 50.0, 100.0)


def test_perfect_tracking_scores_mota_one_and_no_switches():
    acc = MOTAccumulator(iou_thresh=0.5)
    for f in range(1, 4):
        acc.update(f, [_gt(f, 1, 0.0), _gt(f, 2, 300.0)], [(7, 0.0, 0.0, 50.0, 100.0), (8, 300.0, 0.0, 350.0, 100.0)])
    s = acc.summary()
    assert s["n_gt"] == 6 and s["tp"] == 6 and s["fp"] == 0 and s["fn"] == 0
    assert s["idsw"] == 0
    assert s["mota"] == pytest.approx(1.0)
    assert s["recall"] == pytest.approx(1.0) and s["precision"] == pytest.approx(1.0)
    assert s["mostly_tracked"] == 2 and s["n_gt_tracks"] == 2


def test_swapping_ids_counts_switches_and_misses_and_false_alarms():
    acc = MOTAccumulator(iou_thresh=0.5)
    acc.update(1, [_gt(1, 1, 0.0), _gt(1, 2, 300.0)], [(7, 0.0, 0.0, 50.0, 100.0), (8, 300.0, 0.0, 350.0, 100.0)])
    acc.update(2, [_gt(2, 1, 0.0), _gt(2, 2, 300.0)], [(8, 0.0, 0.0, 50.0, 100.0), (7, 300.0, 0.0, 350.0, 100.0)])
    acc.update(3, [_gt(3, 1, 0.0), _gt(3, 2, 300.0)], [(8, 0.0, 0.0, 50.0, 100.0), (9, 600.0, 0.0, 650.0, 100.0)])
    s = acc.summary()
    assert s["idsw"] == 2  # both people changed id in frame 2
    assert s["fn"] == 1  # person 2 missed in frame 3
    assert s["fp"] == 1  # box at x=600 matches nobody
    assert s["mota"] == pytest.approx(1 - (1 + 1 + 2) / 6)


def test_summary_can_be_split_by_how_many_people_were_in_the_frame():
    acc = MOTAccumulator(iou_thresh=0.5)
    acc.update(1, [_gt(1, 1, 0.0)], [(7, 0.0, 0.0, 50.0, 100.0)])
    acc.update(2, [_gt(2, i, 100.0 * i) for i in range(5)], [(i + 10, 100.0 * i, 0.0, 100.0 * i + 50.0, 100.0) for i in range(4)])
    by_bin = acc.summary_by_crowd()
    assert by_bin["1-2"]["n_gt"] == 1 and by_bin["1-2"]["fn"] == 0
    assert by_bin["5+"]["n_gt"] == 5 and by_bin["5+"]["fn"] == 1
    assert "3-4" not in by_bin
