"""Week 5 deliverable: measure person-detection accuracy and speed against COCO val2017 ground truth.

    python scripts/evaluate.py                                   # yolov8n 256 on all 5000 val images
    python scripts/evaluate.py --models models/yolov8n_*_coco-person.tflite --pycocotools
    python scripts/evaluate.py --n-with-person 300 --n-without 100   # quick run on a fixed subset

Uses ST's evaluation settings so the numbers are comparable to the model zoo README:
IoU 0.5 for a match, NMS 0.5, score threshold 0.001, at most 100 detections per image.
Writes results/<model>/metrics.json and pr_curve.png, and a cross-model results/summary.md.
"""

from __future__ import annotations

import argparse
import contextlib
import glob
import io
import json
import platform
import statistics
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd_ai.coco import ImageGT, load_person_gt, select_images  # noqa: E402
from herd_ai.detector import PersonDetector  # noqa: E402
from herd_ai.metrics import average_precision, match_image, precision_recall_at  # noqa: E402
from herd_ai.models import DEFAULT_MODEL, catalog_entry, model_path  # noqa: E402
from herd_ai.paths import ANNOTATIONS_FILE, IMAGES_DIR, RESULTS_DIR  # noqa: E402

REPORT_THRESHOLDS = (0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


def _load_rgb(path: Path) -> np.ndarray:
    bgr = cv2.imread(str(path))
    if bgr is None:
        raise FileNotFoundError(path)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def evaluate_model(det: PersonDetector, gts: dict[int, ImageGT], image_ids: list[int], images_dir: Path, iou: float) -> dict:
    all_scores, all_tp, n_gt = [], [], 0
    latencies, totals = [], []
    coco_results = []

    for iid in tqdm(image_ids, desc=det.name, unit="img", leave=False):
        gt = gts[iid]
        res = det.detect(_load_rgb(images_dir / gt.file_name))
        scores, tp = match_image(res.boxes, res.scores, gt.boxes, gt.crowd, iou)
        all_scores.append(scores)
        all_tp.append(tp)
        n_gt += gt.boxes.shape[0]
        latencies.append(res.latency_ms)
        totals.append(res.total_ms)
        for (x1, y1, x2, y2), s in zip(res.boxes, res.scores):
            coco_results.append(
                {"image_id": iid, "category_id": 1, "bbox": [float(x1), float(y1), float(x2 - x1), float(y2 - y1)], "score": float(s)}
            )

    scores = np.concatenate(all_scores) if all_scores else np.zeros(0)
    tp = np.concatenate(all_tp) if all_tp else np.zeros(0, dtype=bool)
    ap50, precision, recall = average_precision(scores, tp, n_gt)

    at_threshold = {}
    for t in REPORT_THRESHOLDS:
        p, r, f1 = precision_recall_at(scores, tp, n_gt, t)
        at_threshold[f"{t:g}"] = {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}
    best_t = max(at_threshold, key=lambda k: at_threshold[k]["f1"])

    lat = np.array(latencies)
    return {
        "ap50": round(ap50, 4),
        "n_images": len(image_ids),
        "n_gt_boxes": int(n_gt),
        "n_detections_scored": int(scores.size),
        "at_threshold": at_threshold,
        "best_f1_threshold": float(best_t),
        "latency_ms": {
            "mean": round(float(lat.mean()), 2),
            "median": round(float(np.median(lat)), 2),
            "p95": round(float(np.percentile(lat, 95)), 2),
            "min": round(float(lat.min()), 2),
            "max": round(float(lat.max()), 2),
        },
        "end_to_end_ms_mean": round(statistics.fmean(totals), 2),
        "_curve": (precision, recall),
        "_coco_results": coco_results,
    }


def pycocotools_ap50(annotations: Path, image_ids: list[int], results: list[dict]) -> float | None:
    """Independent cross-check of our evaluator with the official COCO API. Returns AP@0.5 or None."""
    if not results:
        return 0.0
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    with contextlib.redirect_stdout(io.StringIO()):
        coco_gt = COCO(str(annotations))
        coco_dt = coco_gt.loadRes(results)
        ev = COCOeval(coco_gt, coco_dt, iouType="bbox")
        ev.params.catIds = [1]
        ev.params.imgIds = image_ids
        ev.evaluate()
        ev.accumulate()
        ev.summarize()
    return round(float(ev.stats[1]), 4)  # stats[1] is AP at IoU=0.50, area=all, maxDets=100


def plot_pr_curve(precision: np.ndarray, recall: np.ndarray, title: str, ap50: float, dest: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5, 4), dpi=120)
    ax.plot(recall, precision, lw=1.5)
    ax.set_xlabel("recall")
    ax.set_ylabel("precision")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.3)
    ax.set_title(f"{title}\nAP@0.5 = {ap50:.3f}", fontsize=9)
    fig.tight_layout()
    fig.savefig(dest)
    plt.close(fig)


def write_summary(rows: list[dict], dest: Path) -> None:
    lines = [
        "# Person detection on COCO val2017 (laptop run)",
        "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M}. AP@0.5 uses ST's settings (NMS 0.5, score 0.001, max 100 dets).",
        "Laptop times are LiteRT on CPU and only indicate relative cost; the board column is ST's published NPU time.",
        "",
        "| model | input | images | GT boxes | AP50 ours | AP50 pycocotools | AP50 ST published | P / R / F1 @0.5 | best F1 (thr) | laptop invoke ms mean / p95 | ST N6 ms |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        t = r["at_threshold"]["0.5"]
        bt = f"{r['best_f1_threshold']:g}"
        best = r["at_threshold"][bt]["f1"]
        pc = f"{r['pycocotools_ap50']:.3f}" if r.get("pycocotools_ap50") is not None else "-"
        st_ap = f"{r['st_ap50_percent'] / 100:.3f}" if r.get("st_ap50_percent") else "-"
        st_ms = f"{r['st_n6_ms']:.1f}" if r.get("st_n6_ms") else "-"
        lines.append(
            f"| {r['model']} | {r['input_size']} | {r['n_images']} | {r['n_gt_boxes']} | {r['ap50']:.3f} | {pc} | {st_ap} | "
            f"{t['precision']:.2f} / {t['recall']:.2f} / {t['f1']:.2f} | {best:.2f} ({bt}) | "
            f"{r['latency_ms']['mean']:.1f} / {r['latency_ms']['p95']:.1f} | {st_ms} |"
        )
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=[str(model_path(DEFAULT_MODEL.filename))], help="model files (globs ok)")
    ap.add_argument("--annotations", type=Path, default=ANNOTATIONS_FILE)
    ap.add_argument("--images-dir", type=Path, default=IMAGES_DIR)
    ap.add_argument("--n-with-person", type=int, default=None, help="limit images containing people (default all)")
    ap.add_argument("--n-without", type=int, default=None, help="limit images without people (default all)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--iou", type=float, default=0.5, help="IoU for a detection to count as correct")
    ap.add_argument("--nms", type=float, default=0.5)
    ap.add_argument("--score-thresh", type=float, default=0.001)
    ap.add_argument("--max-det", type=int, default=100)
    ap.add_argument("--mode", choices=("fit", "letterbox"), default="fit")
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument("--out", type=Path, default=RESULTS_DIR)
    ap.add_argument("--pycocotools", action="store_true", help="also compute AP@0.5 with the official COCO API")
    args = ap.parse_args(argv)

    model_files = sorted({Path(p) for pat in args.models for p in (glob.glob(pat) or [pat])})
    missing = [m for m in model_files if not m.exists()]
    if missing:
        print(f"model files not found: {missing}", file=sys.stderr)
        return 2
    if not args.annotations.exists() or not args.images_dir.exists():
        print(f"COCO data not found at {args.annotations} / {args.images_dir}", file=sys.stderr)
        return 2

    gts = load_person_gt(args.annotations)
    image_ids = select_images(gts, args.n_with_person, args.n_without, args.seed)
    print(f"{len(image_ids)} images ({sum(gts[i].has_person for i in image_ids)} with people), "
          f"{sum(gts[i].boxes.shape[0] for i in image_ids)} person boxes, IoU {args.iou}, resize {args.mode}")

    env = {
        "machine": platform.node(),
        "cpu": platform.processor(),
        "python": platform.python_version(),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    rows = []
    for mf in model_files:
        det = PersonDetector(mf, args.score_thresh, args.nms, args.max_det, args.mode, args.threads)
        m = evaluate_model(det, gts, image_ids, args.images_dir, args.iou)
        precision, recall = m.pop("_curve")
        coco_results = m.pop("_coco_results")
        m["pycocotools_ap50"] = pycocotools_ap50(args.annotations, image_ids, coco_results) if args.pycocotools else None

        info = catalog_entry(mf)
        m.update(
            {
                "model": det.name,
                "model_path": str(mf),
                "input_size": det.input_size,
                "st_ap50_percent": info.st_ap50_percent if info else None,
                "st_n6_ms": info.st_n6_ms if info else None,
                "config": {"iou": args.iou, "nms": args.nms, "score_thresh": args.score_thresh, "max_det": args.max_det,
                           "mode": args.mode, "seed": args.seed, "n_with_person": args.n_with_person, "n_without": args.n_without},
                "environment": env,
            }
        )
        out_dir = args.out / det.name
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "metrics.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
        plot_pr_curve(precision, recall, det.name, m["ap50"], out_dir / "pr_curve.png")
        rows.append(m)

        t = m["at_threshold"]["0.5"]
        extra = f"  pycocotools {m['pycocotools_ap50']:.3f}" if m["pycocotools_ap50"] is not None else ""
        st = f"  ST published {m['st_ap50_percent'] / 100:.3f}" if m["st_ap50_percent"] else ""
        print(f"{det.name}: AP50 {m['ap50']:.3f}{extra}{st}  P/R/F1@0.5 {t['precision']:.2f}/{t['recall']:.2f}/{t['f1']:.2f}  "
              f"invoke {m['latency_ms']['mean']:.1f} ms mean")

    args.out.mkdir(parents=True, exist_ok=True)
    write_summary(rows, args.out / "summary.md")
    print(f"\nwrote {args.out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
