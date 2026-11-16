"""Week 7 deliverable (laptop side): run the person detector + tracker on a video and measure it.

    python scripts/track_sequence.py --video data/mot15/PETS09-S2L1-raw.mp4 --gt data/mot15/MOT15Labels/train/PETS09-S2L1
    python scripts/track_sequence.py --video ... --gt ... --tracker iou --predict --save-video
    python scripts/track_sequence.py --webcam                      # live, press q to quit

With --gt (a MOTChallenge sequence folder holding gt/gt.txt and seqinfo.ini) it scores the result:
recall / precision / id switches / MOTA overall and split by how many people were in the frame
(1-2, 3-4, 5+), plus milliseconds per frame per stage. The tracker defaults mirror the firmware
skeleton (firmware/stm32/App/tracker.c): nearest center within 200/1000 of the frame, drop after 1 s.
Writes results/tracking/<name>/metrics.json (+ annotated .mp4 with --save-video) and
results/tracking/summary.md.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd_ai.detector import PersonDetector  # noqa: E402
from herd_ai.draw import draw_tracks  # noqa: E402
from herd_ai.models import DEFAULT_MODEL, model_path  # noqa: E402
from herd_ai.mot import MOTAccumulator, load_mot_gt, load_seqinfo  # noqa: E402
from herd_ai.paths import RESULTS_DIR  # noqa: E402
from herd_ai.tracker import NearestTracker, detections_from_pixels  # noqa: E402

CROWD_BINS = (("1-2", 1, 2), ("3-4", 3, 4), ("5+", 5, 10**6))


def _pct(x: list[float], q: float) -> float:
    return float(np.percentile(x, q)) if x else 0.0


def _stats(x: list[float]) -> dict:
    return {"mean": statistics.fmean(x), "median": statistics.median(x), "p95": _pct(x, 95)} if x else {}


def make_tracker(args) -> NearestTracker:
    return NearestTracker(
        match_dist=args.match_dist,
        drop_ms=args.drop_ms,
        max_tracks=args.max_tracks,
        predict=args.predict,
        match=args.tracker,
        min_iou=args.min_iou,
    )


def _to_pixels(xyxy_thousandths, width: int, height: int) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = xyxy_thousandths
    return x1 / 1000 * width, y1 / 1000 * height, x2 / 1000 * width, y2 / 1000 * height


def run_video(det: PersonDetector, args) -> tuple[dict, list[dict]]:
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise RuntimeError(f"could not open {args.video}")
    fps = args.fps or cap.get(cv2.CAP_PROP_FPS) or 25.0
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    gt = seqinfo = None
    scale = 1.0
    if args.gt:
        seqinfo = load_seqinfo(args.gt / "seqinfo.ini") if (args.gt / "seqinfo.ini").exists() else None
        scale = width / seqinfo["width"] if seqinfo else 1.0
        gt = load_mot_gt(args.gt / "gt" / "gt.txt", scale=scale)
        if seqinfo and abs(seqinfo["frame_rate"] - fps) > 0.5 and not args.fps:
            print(f"note: video reports {fps:.1f} fps, seqinfo says {seqinfo['frame_rate']}; using seqinfo")
            fps = seqinfo["frame_rate"]

    tracker = make_tracker(args)
    acc_track, acc_det = MOTAccumulator(0.5), MOTAccumulator(0.5)
    writer = None
    if args.save_video:
        writer = cv2.VideoWriter(str(args.out / "tracked.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

    invoke_ms: list[float] = []
    detect_ms: list[float] = []
    track_ms: list[float] = []
    people_per_frame: list[int] = []
    frames_out: list[dict] = []
    frame_idx = 0
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        frame_idx += 1
        time_ms = int(round((frame_idx - 1) * 1000.0 / fps))
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        res = det.detect(rgb)
        t0 = time.perf_counter()
        dets = detections_from_pixels(res.boxes, res.scores, width, height)
        tracks = tracker.update(dets, time_ms)
        track_ms.append((time.perf_counter() - t0) * 1000.0)
        invoke_ms.append(res.latency_ms)
        detect_ms.append(res.total_ms)

        seen = [t for t in tracks if t.last_seen_ms == time_ms]
        hyps = [(t.id, *_to_pixels(t.xyxy(), width, height)) for t in seen]
        frames_out.append(
            {
                "frame": frame_idx,
                "time_ms": time_ms,
                "tracks": [{"id": t.id, "box": [round(v, 1) for v in h[1:]]} for t, h in zip(seen, hyps)],
            }
        )
        if gt is not None:
            gt_boxes = gt.get(frame_idx, [])
            people_per_frame.append(len(gt_boxes))
            acc_track.update(frame_idx, gt_boxes, hyps)
            acc_det.update(frame_idx, gt_boxes, [(i, *b) for i, b in enumerate(res.boxes.tolist())])
        else:
            people_per_frame.append(len(dets))

        if writer is not None:
            shown = draw_tracks(rgb, seen)
            hud = f"frame {frame_idx}  {len(seen)} tracked"
            cv2.putText(shown, hud, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)
            writer.write(cv2.cvtColor(shown, cv2.COLOR_RGB2BGR))
    cap.release()
    if writer is not None:
        writer.release()

    per_frame_ms = [a + b for a, b in zip(detect_ms, track_ms)]
    timing_by_people = {}
    for key, lo, hi in CROWD_BINS:
        sel = [m for m, n in zip(per_frame_ms, people_per_frame) if lo <= n <= hi]
        if sel:
            med = statistics.median(sel)
            timing_by_people[key] = {"n_frames": len(sel), "ms_per_frame_median": med, "fps_laptop": 1000.0 / med}

    result = {
        "video": str(args.video),
        "frames": frame_idx,
        "fps_source": fps,
        "resolution": [width, height],
        "timing_ms": {
            "invoke": _stats(invoke_ms),
            "detect_total": _stats(detect_ms),
            "tracker": _stats(track_ms),
            "per_frame": _stats(per_frame_ms),
        },
        "timing_by_people_in_frame": timing_by_people,
        "people_per_frame_max": max(people_per_frame) if people_per_frame else 0,
    }
    if gt is not None:
        det_summary = acc_det.summary()
        result["tracking"] = acc_track.summary()
        result["tracking_by_crowd"] = acc_track.summary_by_crowd()
        result["detection_only"] = {k: det_summary[k] for k in ("n_gt", "tp", "fp", "fn", "recall", "precision")}
        result["gt"] = {"folder": str(args.gt), "seqinfo": seqinfo, "scale_applied": scale}
    return result, frames_out


def run_webcam(det: PersonDetector, args) -> None:
    cap = cv2.VideoCapture(args.webcam)
    if not cap.isOpened():
        raise RuntimeError(f"could not open webcam {args.webcam}")
    tracker = make_tracker(args)
    print("press q to quit")
    t_start = time.perf_counter()
    hist: list[float] = []
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        t0 = time.perf_counter()
        now_ms = int((t0 - t_start) * 1000)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        res = det.detect(rgb)
        h, w = rgb.shape[:2]
        tracks = tracker.update(detections_from_pixels(res.boxes, res.scores, w, h), now_ms)
        hist = (hist + [1.0 / max(time.perf_counter() - t0, 1e-6)])[-30:]
        shown = draw_tracks(rgb, [t for t in tracks if t.last_seen_ms == now_ms])
        hud = f"{len(tracks)} tracked  {statistics.fmean(hist):.1f} fps"
        cv2.putText(shown, hud, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.imshow("Open Herd - tracking", cv2.cvtColor(shown, cv2.COLOR_RGB2BGR))
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()


def write_summary(root: Path) -> None:
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(root.glob("*/metrics.json"))]
    if not rows:
        return
    lines = [
        "# Detector + tracker on MOT15 sequences (laptop)",
        "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M} by scripts/track_sequence.py. MOTA = 1 - (misses + false alarms + id switches) / people;",
        "a match is IoU >= 0.5. 'det recall' is the detector alone (no ids), so the gap to 'recall' is the tracker's. ms/frame is this",
        "laptop's CPU (detector + tracker), only useful relative to other rows.",
        "",
        "| run | frames | people max | det recall / precision | recall | precision | id switches | MOTA | mostly tracked | ms/frame 1-2 / 3-4 / 5+ people |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        tr, d, tb = r.get("tracking", {}), r.get("detection_only", {}), r.get("timing_by_people_in_frame", {})
        ms = " / ".join(f"{tb[k]['ms_per_frame_median']:.1f}" if k in tb else "-" for k in ("1-2", "3-4", "5+"))
        if tr:
            lines.append(
                f"| {r['name']} | {r['frames']} | {r['people_per_frame_max']} | {d['recall']:.2f} / {d['precision']:.2f} | "
                f"{tr['recall']:.2f} | {tr['precision']:.2f} | {tr['idsw']} | {tr['mota']:.2f} | "
                f"{tr['mostly_tracked']} / {tr['n_gt_tracks']} | {ms} |"
            )
        else:
            lines.append(f"| {r['name']} | {r['frames']} | {r['people_per_frame_max']} | - | - | - | - | - | - | {ms} |")
    (root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, default=model_path(DEFAULT_MODEL.filename))
    ap.add_argument("--video", type=Path, default=None)
    ap.add_argument("--gt", type=Path, default=None, help="MOTChallenge sequence folder with gt/gt.txt and seqinfo.ini")
    ap.add_argument("--webcam", type=int, nargs="?", const=0, default=None, metavar="INDEX")
    ap.add_argument("--fps", type=float, default=None, help="override the video's frame rate for timestamps")
    ap.add_argument("--score-thresh", type=float, default=0.25)
    ap.add_argument("--iou-thresh", type=float, default=0.5, help="NMS")
    ap.add_argument("--tracker", choices=("centroid", "iou"), default="centroid")
    ap.add_argument("--match-dist", type=int, default=200, help="TRACK_MATCH_DIST, thousandths of the frame")
    ap.add_argument("--min-iou", type=float, default=0.3, help="for --tracker iou")
    ap.add_argument("--drop-ms", type=int, default=1000, help="TRACK_DROP_MS")
    ap.add_argument("--max-tracks", type=int, default=8, help="TRACK_MAX")
    ap.add_argument("--predict", action="store_true", help="match against the position predicted from the last speed")
    ap.add_argument("--save-video", action="store_true")
    ap.add_argument("--name", default=None, help="results folder name (default <video>__<model size>__<tracker settings>)")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--results-root", type=Path, default=RESULTS_DIR / "tracking")
    ap.add_argument("--threads", type=int, default=None)
    args = ap.parse_args(argv)

    if not args.model.exists():
        print(f"model not found: {args.model}\nrun: python scripts/download_models.py", file=sys.stderr)
        return 2
    det = PersonDetector(args.model, args.score_thresh, args.iou_thresh, num_threads=args.threads)

    if args.webcam is not None:
        run_webcam(det, args)
        return 0
    if args.video is None or not args.video.exists():
        print(f"video not found: {args.video}", file=sys.stderr)
        return 2

    match_tag = f"centroid{args.match_dist}" if args.tracker == "centroid" else f"iou{int(args.min_iou * 100)}"
    settings = f"{match_tag}_drop{args.drop_ms}{'_pred' if args.predict else ''}"
    name = args.name or f"{args.video.stem.replace('-raw', '')}__{det.input_size}__{settings}"
    args.out = args.out or args.results_root / name
    args.out.mkdir(parents=True, exist_ok=True)

    print(f"model {det.name}  score>={args.score_thresh}  tracker {settings}  video {args.video.name}")
    result, frames_out = run_video(det, args)
    result.update(
        {
            "name": name,
            "model": det.name,
            "input_size": det.input_size,
            "tracker": {
                "match": args.tracker,
                "match_dist": args.match_dist,
                "min_iou": args.min_iou,
                "drop_ms": args.drop_ms,
                "max_tracks": args.max_tracks,
                "predict": args.predict,
            },
            "score_thresh": args.score_thresh,
            "environment": {
                "python": platform.python_version(),
                "machine": platform.machine(),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            },
        }
    )
    (args.out / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (args.out / "tracks.json").write_text(json.dumps(frames_out), encoding="utf-8")
    write_summary(args.results_root)

    t = result.get("tracking")
    tm = result["timing_ms"]
    print(
        f"{result['frames']} frames, up to {result['people_per_frame_max']} people; "
        f"invoke {tm['invoke']['median']:.1f} ms, tracker {tm['tracker']['median']:.2f} ms median"
    )
    if t:
        d = result["detection_only"]
        print(
            f"detector alone: recall {d['recall']:.2f} precision {d['precision']:.2f}\n"
            f"with tracker:   recall {t['recall']:.2f} precision {t['precision']:.2f} id switches {t['idsw']} "
            f"MOTA {t['mota']:.2f} mostly tracked {t['mostly_tracked']}/{t['n_gt_tracks']}"
        )
        for b, s in sorted(result["tracking_by_crowd"].items()):
            print(f"  {b:>4} people in frame: {s['n_frames']:4d} frames  recall {s['recall']:.2f}  idsw {s['idsw']}  MOTA {s['mota']:.2f}")
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
