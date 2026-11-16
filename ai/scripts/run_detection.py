"""Week 4 deliverable: run ST's ready-made person detector on photos (or the webcam) on the laptop.

    python scripts/run_detection.py                               # yolov8n 256 on ai/samples/
    python scripts/run_detection.py --images path/to/photos --score-thresh 0.4
    python scripts/run_detection.py --model models/yolov8n_320_quant_pc_uf_od_coco-person.tflite
    python scripts/run_detection.py --webcam 0                    # live preview, press q to quit

Writes annotated JPEGs plus detections.json (boxes, scores, per-image latency) to --out.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd_ai.detector import PersonDetector  # noqa: E402
from herd_ai.draw import draw_detections  # noqa: E402
from herd_ai.models import DEFAULT_MODEL, model_path  # noqa: E402
from herd_ai.paths import OUTPUTS_DIR, SAMPLES_DIR  # noqa: E402

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


def _collect_images(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files.extend(sorted(q for q in p.iterdir() if q.suffix.lower() in IMAGE_SUFFIXES))
        elif p.suffix.lower() in IMAGE_SUFFIXES:
            files.append(p)
    return files


def _load_rgb(path: Path) -> np.ndarray:
    bgr = cv2.imread(str(path))
    if bgr is None:
        raise FileNotFoundError(f"could not read image {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def run_on_images(det: PersonDetector, images: list[Path], out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    print(f"{'image':<28}{'people':>7}{'invoke ms':>11}{'total ms':>10}  scores")
    for path in images:
        img = _load_rgb(path)
        res = det.detect(img)
        annotated = draw_detections(img, res.boxes, res.scores)
        cv2.imwrite(str(out / path.name), cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR))
        entries.append(
            {
                "image": path.name,
                "width": int(img.shape[1]),
                "height": int(img.shape[0]),
                "detections": [
                    {"box": [round(float(v), 1) for v in b], "score": round(float(s), 4)}
                    for b, s in zip(res.boxes, res.scores)
                ],
                "latency_ms": round(res.latency_ms, 2),
                "total_ms": round(res.total_ms, 2),
            }
        )
        scores = " ".join(f"{s:.2f}" for s in res.scores)
        print(f"{path.name:<28}{len(res):>7}{res.latency_ms:>11.1f}{res.total_ms:>10.1f}  {scores}")

    lat = [e["latency_ms"] for e in entries]
    tot = [e["total_ms"] for e in entries]
    summary = {
        "n_images": len(entries),
        "n_detections": sum(len(e["detections"]) for e in entries),
        "mean_latency_ms": round(statistics.fmean(lat), 2) if lat else 0.0,
        "median_latency_ms": round(statistics.median(lat), 2) if lat else 0.0,
        "mean_total_ms": round(statistics.fmean(tot), 2) if tot else 0.0,
    }
    print(
        f"\n{summary['n_images']} images, {summary['n_detections']} people found, "
        f"invoke {summary['mean_latency_ms']:.1f} ms mean / {summary['median_latency_ms']:.1f} ms median, "
        f"end-to-end {summary['mean_total_ms']:.1f} ms mean"
    )
    return {"images": entries, "summary": summary}


def run_webcam(det: PersonDetector, index: int) -> None:
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"could not open webcam {index}")
    print("press q to quit")
    fps_hist: list[float] = []
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        t0 = time.perf_counter()
        res = det.detect(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        fps_hist.append(1.0 / max(time.perf_counter() - t0, 1e-6))
        fps_hist = fps_hist[-30:]
        shown = cv2.cvtColor(draw_detections(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), res.boxes, res.scores), cv2.COLOR_RGB2BGR)
        hud = f"{det.name}  {len(res)} people  invoke {res.latency_ms:.1f} ms  {statistics.fmean(fps_hist):.1f} fps"
        cv2.putText(shown, hud, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.imshow("Open Herd - person detection", shown)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, default=model_path(DEFAULT_MODEL.filename))
    ap.add_argument("--images", type=Path, nargs="*", default=[SAMPLES_DIR], help="image files and/or folders")
    ap.add_argument("--webcam", type=int, nargs="?", const=0, default=None, metavar="INDEX", help="live webcam instead of files")
    ap.add_argument("--out", type=Path, default=None, help="output folder (default outputs/run_<model>_<time>)")
    ap.add_argument("--score-thresh", type=float, default=0.25, help="operating point from the COCO sweep; see results/summary.md")
    ap.add_argument("--iou-thresh", type=float, default=0.5)
    ap.add_argument("--mode", choices=("fit", "letterbox"), default="fit")
    ap.add_argument("--threads", type=int, default=None)
    args = ap.parse_args(argv)

    if not args.model.exists():
        print(f"model not found: {args.model}\nrun: python scripts/download_models.py", file=sys.stderr)
        return 2
    det = PersonDetector(args.model, args.score_thresh, args.iou_thresh, mode=args.mode, num_threads=args.threads)
    print(f"model {det.name}  input {det.input_size}x{det.input_size}  score>={args.score_thresh}  nms {args.iou_thresh}  resize {args.mode}\n")

    if args.webcam is not None:
        run_webcam(det, args.webcam)
        return 0

    images = _collect_images(args.images)
    if not images:
        print(f"no images found in {args.images}", file=sys.stderr)
        return 2
    out = args.out or OUTPUTS_DIR / f"run_{det.name}_{datetime.now():%Y%m%d_%H%M%S}"
    result = run_on_images(det, images, out)
    log = {
        "model": det.name,
        "model_path": str(args.model),
        "input_size": det.input_size,
        "score_thresh": args.score_thresh,
        "iou_thresh": args.iou_thresh,
        "mode": args.mode,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **result,
    }
    (out / "detections.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"annotated images and detections.json written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
