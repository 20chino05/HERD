"""Smoke tests for the week 6 and 7 scripts. They run the real models on the real downloads and are
skipped when a model or dataset is missing."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from herd_ai.paths import AI_ROOT, DATA_DIR, MODELS_DIR

SCRIPTS = AI_ROOT / "scripts"
OSNET = MODELS_DIR / "osnet_a025_256_128_tfs_int8.tflite"
YOLO = MODELS_DIR / "yolov8n_256_quant_pc_uf_od_coco-person.tflite"
MARKET = DATA_DIR / "market1501" / "Market-1501-v15.09.15"
TUD_VIDEO = DATA_DIR / "mot15" / "TUD-Campus-raw.mp4"
TUD_GT = DATA_DIR / "mot15" / "MOT15Labels" / "train" / "TUD-Campus"


def _venv_python() -> str:
    candidate = Path(sys.prefix) / "Scripts" / "python.exe"
    return str(candidate) if candidate.exists() else sys.executable


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([_venv_python(), str(SCRIPTS / script), *args], capture_output=True, text=True, cwd=AI_ROOT, timeout=900)


@pytest.mark.skipif(not (OSNET.exists() and (MARKET / "query").exists()), reason="OSNet model or Market-1501 not downloaded")
def test_evaluate_reid_scores_a_small_subset_and_writes_metrics(tmp_path: Path):
    proc = _run("evaluate_reid.py", "--models", str(OSNET), "--max-query", "40", "--max-gallery", "400", "--out", str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    metrics = json.loads((tmp_path / OSNET.stem / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["dataset"]["n_query"] == 40 and metrics["dataset"]["n_gallery"] == 400
    assert metrics["embedding_dim"] == 128
    assert 0.0 <= metrics["map"] <= 1.0
    assert 0.0 <= metrics["cmc"]["rank1"] <= metrics["cmc"]["rank5"] <= metrics["cmc"]["rank10"] <= 1.0
    assert metrics["pair_separation"]["pos_median"] < metrics["pair_separation"]["neg_median"]
    assert set(metrics["nearest_of_k"]) == {"2", "3", "5"}
    assert (tmp_path / OSNET.stem / "distances.png").exists()
    assert "osnet_a025" in (tmp_path / "summary.md").read_text(encoding="utf-8")


@pytest.mark.skipif(not (YOLO.exists() and TUD_VIDEO.exists() and TUD_GT.exists()), reason="detector model or MOT15 TUD-Campus not downloaded")
def test_track_sequence_scores_tud_campus_against_ground_truth(tmp_path: Path):
    proc = _run("track_sequence.py", "--model", str(YOLO), "--video", str(TUD_VIDEO), "--gt", str(TUD_GT), "--results-root", str(tmp_path), "--name", "tud")
    assert proc.returncode == 0, proc.stderr
    m = json.loads((tmp_path / "tud" / "metrics.json").read_text(encoding="utf-8"))
    assert m["frames"] == 71
    assert m["tracking"]["n_gt"] > 0
    assert m["tracking"]["recall"] > 0.3, "the detector should find at least some of the walking people"
    assert m["tracking"]["precision"] > 0.5
    assert m["detection_only"]["recall"] >= m["tracking"]["recall"] - 1e-9
    assert "tracking_by_crowd" in m and m["timing_ms"]["tracker"]["median"] < 5.0
    frames = json.loads((tmp_path / "tud" / "tracks.json").read_text(encoding="utf-8"))
    assert len(frames) == 71 and all("tracks" in f for f in frames)
    assert "| tud |" in (tmp_path / "summary.md").read_text(encoding="utf-8")
