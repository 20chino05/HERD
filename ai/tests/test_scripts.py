"""Smoke tests for the command-line scripts. They run the real model on real files and are skipped
when the model or the COCO data has not been downloaded."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from herd_ai.paths import AI_ROOT, ANNOTATIONS_FILE, IMAGES_DIR, MODELS_DIR, SAMPLES_DIR

SCRIPTS = AI_ROOT / "scripts"
MODEL = MODELS_DIR / "yolov8n_256_quant_pc_uf_od_coco-person.tflite"

needs_model = pytest.mark.skipif(not MODEL.exists(), reason="model not downloaded")
needs_data = pytest.mark.skipif(
    not (ANNOTATIONS_FILE.exists() and IMAGES_DIR.exists()), reason="COCO val2017 not downloaded"
)


def _venv_python() -> str:
    """The interpreter of the active virtual environment (sys.executable may point at the base install)."""
    candidate = Path(sys.prefix) / "Scripts" / "python.exe"
    return str(candidate) if candidate.exists() else sys.executable


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    cmd = [_venv_python(), str(SCRIPTS / script), *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=AI_ROOT, timeout=600)


@needs_model
def test_run_detection_annotates_samples_and_logs_detections(tmp_path: Path):
    out = tmp_path / "out"
    proc = _run("run_detection.py", "--model", str(MODEL), "--images", str(SAMPLES_DIR), "--out", str(out))
    assert proc.returncode == 0, proc.stderr

    jpgs = sorted(p.name for p in out.glob("*.jpg"))
    assert jpgs == sorted(p.name for p in SAMPLES_DIR.glob("*.jpg"))

    log = json.loads((out / "detections.json").read_text())
    by_name = {entry["image"]: entry for entry in log["images"]}
    assert len(by_name["three_people.jpg"]["detections"]) >= 2
    assert by_name["no_person.jpg"]["detections"] == []
    assert by_name["one_person.jpg"]["latency_ms"] > 0
    assert log["model"].endswith("coco-person")
    assert log["summary"]["mean_latency_ms"] > 0


@needs_model
@needs_data
def test_evaluate_writes_metrics_and_summary_for_a_small_subset(tmp_path: Path):
    out = tmp_path / "results"
    proc = _run(
        "evaluate.py",
        "--models", str(MODEL),
        "--n-with-person", "20",
        "--n-without", "5",
        "--out", str(out),
        "--pycocotools",
    )
    assert proc.returncode == 0, proc.stderr

    metrics = json.loads((out / MODEL.stem / "metrics.json").read_text())
    assert metrics["n_images"] == 25
    assert metrics["n_gt_boxes"] > 0
    assert 0.0 <= metrics["ap50"] <= 1.0
    assert 0.0 <= metrics["pycocotools_ap50"] <= 1.0
    assert metrics["latency_ms"]["mean"] > 0
    assert "0.5" in metrics["at_threshold"] and set(metrics["at_threshold"]["0.5"]) == {"precision", "recall", "f1"}
    assert (out / MODEL.stem / "pr_curve.png").exists()
    assert "ap50" in (out / "summary.md").read_text().lower()


def test_download_models_skips_files_that_already_exist():
    proc = _run("download_models.py", "--only", "yolov8n_256")
    assert proc.returncode == 0, proc.stderr
    assert "already present" in proc.stdout
