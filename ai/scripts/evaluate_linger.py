"""Week 8: does the lingering rule (behavior.c) flag the right people at the right time?

"Ground-truth stays" are the same rule applied to the labeled tracks with their perfect ids. The
pipeline is detector -> firmware tracker -> rule, run on the video. A pipeline report is a hit when
the person it points at really had been standing that long (within 1 s of the rule's time), a repeat
when that stay was already reported (an id switch restarted the clock), and otherwise a false alarm,
which is sorted into: "ghost" (no labeled person near the report: a detector false positive that
never moves), "occupied spot" (people were at that spot the whole time, but not the same labeled
person: a group shuffling about), or "early" (someone there, but not for long enough). A labeled
stay nobody reported within 5 s is a miss; each miss says how many times the pipeline's id for that
person restarted during the stay.

    python scripts/evaluate_linger.py                       # all sequences, radius x time sweep + guards
    python scripts/evaluate_linger.py --seqs PETS09-S2L1 --radius 120 --time 8000

Writes results/linger/<seq>.json, results/linger/summary.md and results/linger/<seq>_timeline.png.
Detections are cached in outputs/linger/ so re-running a sweep does not re-run the detector.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd_ai.behavior import LingerDetector  # noqa: E402
from herd_ai.detector import PersonDetector  # noqa: E402
from herd_ai.models import DEFAULT_MODEL, model_path  # noqa: E402
from herd_ai.mot import GTBox, load_mot_gt, load_seqinfo  # noqa: E402
from herd_ai.paths import DATA_DIR, OUTPUTS_DIR, RESULTS_DIR  # noqa: E402
from herd_ai.tracker import Detection, NearestTracker, Track, detections_from_pixels  # noqa: E402

MOT = DATA_DIR / "mot15" / "MOT15Labels" / "train"
VIDEOS = {
    "PETS09-S2L1": DATA_DIR / "mot15" / "PETS09-S2L1-raw.mp4",
    "TUD-Stadtmitte": DATA_DIR / "mot15" / "TUD-Stadtmitte-raw.mp4",
    "TUD-Campus": DATA_DIR / "mot15" / "TUD-Campus-raw.mp4",
    "ADL-Rundle-6": DATA_DIR / "mot15" / "ADL-Rundle-6-raw.mp4",
}
MAX_BOXES = 8  # DETECT_MAX on the board
MATCH_RADIUS = 150  # a report counts for the labeled person whose center is this close (thousandths)
HIT_SLACK_MS = 1000
MISS_WINDOW_MS = 5000
OCCUPIED_FRAC = 0.9

# guard variants measured at the default radius x time
VARIANTS = [
    ("as merged", dict()),
    ("drop 2000 ms", dict(drop_ms=2000)),
    ("drop 3000 ms", dict(drop_ms=3000)),
    ("require motion", dict(require_motion=True)),
    ("score >= 40", dict(min_score=40)),
    ("score >= 50", dict(min_score=50)),
    ("motion + score >= 40", dict(require_motion=True, min_score=40)),
    ("motion + score >= 40 + drop 2000", dict(require_motion=True, min_score=40, drop_ms=2000)),
]


def frame_time_ms(index0: int, fps: float) -> int:
    return int(round(index0 * 1000.0 / fps))


def gt_tracks(boxes: list[GTBox], width: int, height: int, now_ms: int) -> list[Track]:
    out = []
    for b in sorted(boxes, key=lambda b: b.track_id):
        cx, cy = (b.x1 + b.x2) / 2 / width * 1000, (b.y1 + b.y2) / 2 / height * 1000
        out.append(Track(b.track_id, int(round(cx)), int(round(cy)), int(round((b.x2 - b.x1) / width * 1000)),
                         int(round((b.y2 - b.y1) / height * 1000)), 0, 0, now_ms, now_ms, score=100))
    return out


def detect_video(det: PersonDetector, video: Path, cache: Path, max_frames: int | None) -> list[list[list[int]]]:
    """Per-frame detections in thousandths [cx, cy, w, h, score], at most MAX_BOXES by score, cached."""
    if cache.exists():
        frames = json.loads(cache.read_text(encoding="utf-8"))
        if max_frames is None or len(frames) >= max_frames:
            return frames[:max_frames] if max_frames else frames
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise FileNotFoundError(video)
    frames = []
    while max_frames is None or len(frames) < max_frames:
        ok, bgr = cap.read()
        if not ok:
            break
        h, w = bgr.shape[:2]
        res = det.detect(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        dets = detections_from_pixels(res.boxes, res.scores, w, h)
        dets = sorted(dets, key=lambda d: -d.score)[:MAX_BOXES]
        frames.append([[d.cx, d.cy, d.w, d.h, d.score] for d in dets])
    cap.release()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(frames), encoding="utf-8")
    return frames


def gt_stays(gt: dict[int, list[GTBox]], width: int, height: int, fps: float, radius: int, time_ms: int,
             n_frames: int) -> tuple[list[dict], dict[int, dict[int, int]]]:
    """Reports of the rule on perfect tracks, and standing_ms per frame per labeled id."""
    linger = LingerDetector(radius, time_ms, max_slots=64)
    events, standing = [], {}
    for i in range(n_frames):
        t = frame_time_ms(i, fps)
        tracks = gt_tracks(gt.get(i + 1, []), width, height, t)
        reported = set()
        while True:  # the rule reports one id per call; drain it for this frame
            lid = linger.update(tracks, t)
            if lid == 0 or lid in reported:
                break
            reported.add(lid)
            tr = next(x for x in tracks if x.id == lid)
            events.append({"t_ms": t, "frame": i + 1, "gt_id": lid, "x": tr.cx, "y": tr.cy})
        standing[i + 1] = {tr.id: linger.standing_ms(tr.id, t) for tr in tracks}
    return events, standing


def pipeline_events(frames: list[list[list[int]]], fps: float, radius: int, time_ms: int, match_dist: int, drop_ms: int,
                    require_motion: bool = False, min_score: int = 0) -> tuple[list[dict], dict[int, list[Track]]]:
    """Reports of the pipeline, and the active tracks per frame (for the miss diagnosis)."""
    tracker = NearestTracker(match_dist=match_dist, drop_ms=drop_ms)
    linger = LingerDetector(radius, time_ms, require_motion=require_motion, min_score=min_score)
    events, per_frame = [], {}
    for i, dets in enumerate(frames):
        t = frame_time_ms(i, fps)
        tracks = tracker.update([Detection(*d) for d in dets], t)
        per_frame[i + 1] = [Track(**tr.__dict__) for tr in tracks]
        lid = linger.update(tracks, t)
        if lid:
            tr = next(x for x in tracks if x.id == lid)
            events.append({"t_ms": t, "frame": i + 1, "track_id": lid, "x": tr.cx, "y": tr.cy, "score": tr.score})
    return events, per_frame


def _near(tracks: list[Track], x: int, y: int) -> Track | None:
    near = [t for t in tracks if (t.cx - x) ** 2 + (t.cy - y) ** 2 <= MATCH_RADIUS**2]
    return min(near, key=lambda t: (t.cx - x) ** 2 + (t.cy - y) ** 2) if near else None


def score_events(pipe: list[dict], per_frame: dict[int, list[Track]], gt_ev: list[dict], standing: dict[int, dict[int, int]],
                 gt: dict[int, list[GTBox]], width: int, height: int, fps: float, time_ms: int) -> dict:
    claimed: dict[int, int] = {}  # gt_id -> index of the GT stay already credited
    hits, repeats, false = [], [], []
    window = max(1, int(round(time_ms / 1000 * fps)))
    for e in pipe:
        tracks = gt_tracks(gt.get(e["frame"], []), width, height, e["t_ms"])
        who = _near(tracks, e["x"], e["y"])
        stood = standing.get(e["frame"], {}).get(who.id) if who else None
        e = dict(e, gt_id=who.id if who else None, gt_standing_ms=stood)
        if who is None or stood is None or stood < time_ms - HIT_SLACK_MS:
            if who is None:
                e["kind"] = "ghost"
            else:
                occupied = sum(1 for f in range(max(1, e["frame"] - window + 1), e["frame"] + 1)
                               if _near(gt_tracks(gt.get(f, []), width, height, 0), e["x"], e["y"]) is not None)
                e["kind"] = "occupied spot" if occupied >= OCCUPIED_FRAC * window else "early"
            false.append(e)
            continue
        stays = [k for k, g in enumerate(gt_ev) if g["gt_id"] == who.id and g["t_ms"] <= e["t_ms"] + HIT_SLACK_MS]
        stay = stays[-1] if stays else None
        if stay is not None and claimed.get(who.id) == stay:
            e["kind"] = "repeat"
            repeats.append(e)
        else:
            e["kind"] = "hit"
            e["delay_ms"] = e["t_ms"] - gt_ev[stay]["t_ms"] if stay is not None else None
            if stay is not None:
                claimed[who.id] = stay
            hits.append(e)
    missed = []
    for g in gt_ev:
        ok = any(h.get("gt_id") == g["gt_id"] and -HIT_SLACK_MS <= h["t_ms"] - g["t_ms"] <= MISS_WINDOW_MS for h in hits)
        if ok:
            continue
        # which pipeline ids sat on this person during the stay?
        ids, seen = [], 0
        for f in range(max(1, g["frame"] - window + 1), g["frame"] + 1):
            box = next((b for b in gt.get(f, []) if b.track_id == g["gt_id"]), None)
            if box is None:
                continue
            gx, gy = int(round((box.x1 + box.x2) / 2 / width * 1000)), int(round((box.y1 + box.y2) / 2 / height * 1000))
            tr = _near([t for t in per_frame.get(f, []) if t.last_seen_ms == frame_time_ms(f - 1, fps)], gx, gy)
            if tr is not None:
                seen += 1
                if not ids or ids[-1] != tr.id:
                    ids.append(tr.id)
        missed.append(dict(g, pipeline_ids=ids, detected_frac=seen / window, why="never detected" if not ids else ("id restarted" if len(ids) > 1 else "detected too briefly")))
    delays = [h["delay_ms"] for h in hits if h.get("delay_ms") is not None]
    kinds = {k: sum(1 for e in false if e["kind"] == k) for k in ("ghost", "occupied spot", "early")}
    return {
        "gt_stays": len(gt_ev), "reports": len(pipe), "hits": len(hits), "repeats": len(repeats), "false": len(false), **{f"false_{k.replace(' ', '_')}": v for k, v in kinds.items()},
        "missed": len(missed), "missed_restarted": sum(1 for m in missed if m["why"] == "id restarted"),
        "missed_never_detected": sum(1 for m in missed if m["why"] == "never detected"),
        "delay_median_ms": statistics.median(delays) if delays else None, "delay_max_ms": max(delays) if delays else None,
        "events": hits + repeats + false, "missed_events": missed,
    }


def timeline_png(seq: str, gt_ev: list[dict], scored: dict, duration_ms: int, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ids = sorted({g["gt_id"] for g in gt_ev} | {e["gt_id"] for e in scored["events"] if e.get("gt_id") is not None})
    if not ids:
        return
    row = {g: k for k, g in enumerate(ids)}
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(ids) + 1.8))
    ax.scatter([g["t_ms"] / 1000 for g in gt_ev], [row[g["gt_id"]] for g in gt_ev], marker="|", s=220, color="#15202B", label="rule on labeled tracks")
    style = {"hit": ("#1F8F57", "o", "pipeline: hit"), "repeat": ("#D98A00", "o", "pipeline: repeat (id switch)"),
             "occupied spot": ("#D98A00", "s", "pipeline: a group was there"), "early": ("#B4382E", "x", "pipeline: too early"),
             "ghost": ("#B4382E", "x", "pipeline: nobody there")}
    for kind, (c, m, lab) in style.items():
        pts = [e for e in scored["events"] if e["kind"] == kind]
        ys = [row.get(e.get("gt_id"), len(ids)) for e in pts]
        if pts:
            ax.scatter([e["t_ms"] / 1000 for e in pts], ys, color=c, marker=m, s=46, label=lab, zorder=3)
    ax.set_yticks(range(len(ids) + 1))
    ax.set_yticklabels([f"person {g}" for g in ids] + ["nobody there"])
    ax.set_xlim(0, duration_ms / 1000)
    ax.set_xlabel("seconds")
    ax.set_title(f"{seq}: when the lingering rule fires")
    ax.grid(axis="x", color="#E3E7EC")
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    plt.close(fig)


def _strip(sc: dict) -> dict:
    return {k: v for k, v in sc.items() if k not in ("events", "missed_events")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, default=model_path(DEFAULT_MODEL.filename))
    ap.add_argument("--seqs", nargs="*", default=list(VIDEOS))
    ap.add_argument("--radius", type=int, nargs="*", default=[80, 120, 160, 200])
    ap.add_argument("--time", type=int, nargs="*", default=[4000, 6000, 8000, 10000])
    ap.add_argument("--default", default="120x8000", help="radius x time used for the headline numbers, the guards and the plot")
    ap.add_argument("--score-thresh", type=float, default=0.25)
    ap.add_argument("--match-dist", type=int, default=200)
    ap.add_argument("--drop-ms", type=int, default=1000)
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--out", type=Path, default=RESULTS_DIR / "linger")
    ap.add_argument("--threads", type=int, default=None)
    args = ap.parse_args(argv)
    d_radius, d_time = (int(v) for v in args.default.split("x"))

    det = PersonDetector(args.model, args.score_thresh, num_threads=args.threads)
    args.out.mkdir(parents=True, exist_ok=True)
    summary_rows, sweep_rows, variant_rows = [], [], []
    for seq in args.seqs:
        info = load_seqinfo(MOT / seq / "seqinfo.ini")
        gt = load_mot_gt(MOT / seq / "gt" / "gt.txt")
        fps, width, height = info["frame_rate"], info["width"], info["height"]
        frames = detect_video(det, VIDEOS[seq], OUTPUTS_DIR / "linger" / f"{seq}_{args.model.stem}.json", args.max_frames)
        n = len(frames)
        duration = frame_time_ms(n, fps)
        print(f"{seq}: {n} frames at {fps:g} fps, {duration / 1000:.0f} s")

        def run(r: int, tm: int, **kw) -> dict:
            gt_ev, standing = gt_stays(gt, width, height, fps, r, tm, n)
            opts = dict(match_dist=args.match_dist, drop_ms=args.drop_ms)
            opts.update(kw)
            pipe, per_frame = pipeline_events(frames, fps, r, tm, **opts)
            sc = score_events(pipe, per_frame, gt_ev, standing, gt, width, height, fps, tm)
            sc["gt_events"] = gt_ev
            return sc

        per_setting = {}
        for r in args.radius:
            for tm in args.time:
                sc = run(r, tm)
                per_setting[f"{r}x{tm}"] = sc
                sweep_rows.append((seq, r, tm, sc))
                print(f"  radius {r:3d} time {tm / 1000:4.1f} s: stays {sc['gt_stays']:3d} hits {sc['hits']:3d} repeats {sc['repeats']:2d} "
                      f"false {sc['false']:3d} (ghost {sc['false_ghost']}, group {sc['false_occupied_spot']}, early {sc['false_early']}) missed {sc['missed']:3d}")
        key = f"{d_radius}x{d_time}"
        if key not in per_setting:
            per_setting[key] = run(d_radius, d_time)
        head = per_setting[key]
        variants = {}
        for name, kw in VARIANTS:
            sc = per_setting[key] if not kw else run(d_radius, d_time, **kw)
            variants[name] = sc
            variant_rows.append((seq, name, sc))
            print(f"  {name:36s}: hits {sc['hits']:3d} repeats {sc['repeats']:2d} false {sc['false']:3d} (ghost {sc['false_ghost']}, "
                  f"group {sc['false_occupied_spot']}, early {sc['false_early']}) missed {sc['missed']:3d} delay {sc['delay_median_ms']}")
        timeline_png(seq, head["gt_events"], head, duration, args.out / f"{seq}_timeline.png")
        (args.out / f"{seq}.json").write_text(json.dumps({
            "sequence": seq, "fps": fps, "frames": n, "duration_ms": duration, "model": args.model.name, "default": key,
            "settings": {k: _strip({kk: vv for kk, vv in v.items() if kk != "gt_events"}) for k, v in per_setting.items()},
            "variants": {k: _strip({kk: vv for kk, vv in v.items() if kk != "gt_events"}) for k, v in variants.items()},
            "default_events": head["events"], "default_missed": head["missed_events"], "default_gt_stays": head["gt_events"],
        }, indent=1), encoding="utf-8")
        summary_rows.append((seq, fps, n, duration, head))

    def row(seq: str, name: str, sc: dict) -> str:
        dl = f"{sc['delay_median_ms'] / 1000:.1f} s / {sc['delay_max_ms'] / 1000:.1f} s" if sc["delay_median_ms"] is not None else "-"
        return (f"| {seq} | {name} | {sc['gt_stays']} | {sc['hits']} | {sc['repeats']} | {sc['false_ghost']} | {sc['false_occupied_spot']} | "
                f"{sc['false_early']} | {sc['missed']} ({sc['missed_restarted']} restarted, {sc['missed_never_detected']} never seen) | {dl} |")

    head_line = "| sequence | setting | labeled stays | hits | repeats | ghost | group there | too early | missed | delay median / max |"
    sep = "|---|---|---:|---:|---:|---:|---:|---:|---|---|"
    lines = [
        "# Week 8: the lingering rule on labeled video",
        "",
        f"Date: {date.today().isoformat()}. Detector {args.model.name}, tracker match {args.match_dist} / drop {args.drop_ms} ms.",
        "A labeled stay is the rule applied to the labeled tracks with perfect ids. A hit is a pipeline report pointing at",
        f"a person who really had been standing for the rule's time (within {HIT_SLACK_MS / 1000:g} s); a repeat is a second report of",
        "the same stay after an id switch. False alarms are split into ghost (no labeled person within 150/1000 of the",
        f"report), group there (people occupied that spot for at least {OCCUPIED_FRAC:.0%} of the time, just not one labeled id), and too",
        f"early (someone there, standing less than that). A miss is a labeled stay with no report within {MISS_WINDOW_MS / 1000:g} s.",
        "",
        f"## Default setting: radius {d_radius}, time {d_time / 1000:g} s",
        "",
        head_line, sep,
    ]
    for seq, fps, n, dur, h in summary_rows:
        lines.append(row(f"{seq} ({dur / 1000:.0f} s at {fps:g} fps)", "as merged", h))
    lines += ["", "## Guards at the default setting", "", head_line, sep]
    for seq, name, sc in variant_rows:
        lines.append(row(seq, name, sc))
    lines += ["", "## Radius x time sweep (as merged)", "", head_line, sep]
    for seq, r, tm, sc in sweep_rows:
        lines.append(row(seq, f"radius {r}, {tm / 1000:g} s", sc))
    (args.out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
