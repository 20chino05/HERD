"""The C the board runs (tracker.c + behavior.c) and the Python mirrors give identical output on
real pedestrian data. Skipped without a C compiler or the MOT15 labels."""

from pathlib import Path

import pytest

from herd_ai import parity
from herd_ai.mot import load_mot_gt, load_seqinfo
from herd_ai.paths import DATA_DIR

MOT = DATA_DIR / "mot15" / "MOT15Labels" / "train"
GCC = parity.find_gcc()

pytestmark = pytest.mark.skipif(GCC is None or not MOT.exists(), reason="needs a C compiler and the MOT15 labels")


@pytest.fixture(scope="module")
def trace_tool(tmp_path_factory) -> Path:
    return parity.build_trace_tool(tmp_path_factory.mktemp("trace"), GCC)


def _stream(seq: str, max_frames: int | None = None):
    info = load_seqinfo(MOT / seq / "seqinfo.ini")
    gt = load_mot_gt(MOT / seq / "gt" / "gt.txt")
    return parity.gt_to_trace(gt, info["width"], info["height"], info["frame_rate"], max_frames=max_frames)


def test_trace_tool_builds_from_the_real_firmware_sources(trace_tool: Path):
    assert trace_tool.exists()


@pytest.mark.parametrize("seq,max_frames", [("PETS09-S2L1", 300), ("TUD-Stadtmitte", None)])
def test_c_and_python_agree_frame_for_frame(trace_tool: Path, seq: str, max_frames):
    stream = _stream(seq, max_frames)
    res = parity.compare(trace_tool, stream)
    assert res["c_lines"] == res["py_lines"] == res["frames"]
    assert res["mismatches"] == [], f"first mismatch at frame {res['mismatches'][0][0]}:\n{res['mismatches'][0][1]}\n{res['mismatches'][0][2]}"
    assert res["identical"]


def test_the_guards_match_too_when_switched_on(tmp_path: Path):
    defines = {"LINGER_REQUIRE_MOTION": 1, "LINGER_MIN_SCORE": 40}
    exe = parity.build_trace_tool(tmp_path, GCC, defines)
    res = parity.compare(exe, _stream("PETS09-S2L1", 400), defines)
    assert res["identical"], res["mismatches"][:1]
    assert parity.firmware_config(defines)["LINGER_REQUIRE_MOTION"] == 1
    assert parity.firmware_config()["LINGER_REQUIRE_MOTION"] == 0, "the firmware as committed keeps the guard off"


def test_the_stream_has_people_and_the_rule_fires_on_pets(trace_tool: Path):
    stream = _stream("PETS09-S2L1", 300)
    assert any(dets for _, dets in stream)
    lines = parity.run_c(trace_tool, stream)
    assert any(" L=0" not in ln for ln in lines), "someone in PETS should linger within 300 frames (43 s)"
