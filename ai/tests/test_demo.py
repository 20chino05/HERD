"""The local showcase: the page is built from the committed results, and the live stream runs the
real detector + tracker on the PETS video."""

from pathlib import Path

import pytest

from herd_ai.demo import SOURCES, LiveTracker, load_results, render_page
from herd_ai.paths import MODELS_DIR, RESULTS_DIR

YOLO = MODELS_DIR / "yolov8n_256_quant_pc_uf_od_coco-person.tflite"


def test_results_load_from_the_committed_files():
    r = load_results()
    assert r["week5"], "week 5 metrics should be committed"
    assert {m["input_size"] for m in r["week5"]} >= {256, 320}
    assert r["week7"]["defaults"], "week 7 default runs should be committed"
    assert any(row["name"].startswith("PETS09") for row in r["week7"]["defaults"])


def test_page_renders_every_week_with_real_numbers():
    html = render_page(load_results(), reid_demo=[])
    for heading in ("Week 4", "Week 5", "Week 6", "Week 7", "Week 8", "Week 9", "Live"):
        assert heading in html
    assert "0.577" in html  # week 5 AP of the 256 model
    assert "PETS09-S2L1" in html
    assert "<table" in html and "/stream/pets" in html
    assert "/results/linger/PETS09-S2L1_timeline.png" in html and "/results/follow/PETS09-S2L1_episode.png" in html
    assert "FOLLOW_DEADBAND" in html


def test_results_include_weeks_8_and_9():
    r = load_results()
    assert r["week8"] and r["week8"]["default"] == "120x8000"
    assert set(r["week9"]) >= {"PETS09-S2L1", "TUD-Stadtmitte"}
    assert r["parity"] and "identical" in r["parity"]


@pytest.mark.skipif(not (YOLO.exists() and SOURCES["pets"].exists()), reason="model or PETS video missing")
def test_live_stream_yields_jpeg_frames_with_tracking():
    live = LiveTracker(YOLO)
    frames = []
    for jpeg, info in live.frames("pets", keep_going=lambda: len(frames) < 3, pace=False):
        frames.append((jpeg, info))
    assert len(frames) == 3
    for jpeg, info in frames:
        assert jpeg[:2] == b"\xff\xd8"
        assert info["frame"] >= 1 and info["ms"] > 0
    assert frames[2][1]["frame"] == 3
