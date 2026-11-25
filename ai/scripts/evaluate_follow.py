"""Week 9: the follow law (pantilt.c) driving a virtual pan camera over labeled pedestrian video.

Each labeled person is one episode: the camera starts at home, the person enters the home view, and
the firmware's tracker + follow law try to keep them centered until their track ends. Labeled boxes
are the detections (perfect detector) so the sweep measures the control law alone; --detector then
runs the real detector on the camera's crop at the chosen settings to see what detection misses add.

    python scripts/evaluate_follow.py                 # sweep gain x speed x deadband on three sequences
    python scripts/evaluate_follow.py --detector      # add the real-detector run on PETS

Writes results/follow/summary.md, results/follow/<seq>.json and results/follow/<seq>_episode.png.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd_ai.followsim import Episode, SimConfig, VirtualCamera, episode_ids, run_episode, summarize  # noqa: E402
from herd_ai.mot import load_mot_gt, load_seqinfo  # noqa: E402
from herd_ai.paths import DATA_DIR, RESULTS_DIR  # noqa: E402

MOT = DATA_DIR / "mot15" / "MOT15Labels" / "train"
VIDEOS = {
    "PETS09-S2L1": DATA_DIR / "mot15" / "PETS09-S2L1-raw.mp4",
    "TUD-Stadtmitte": DATA_DIR / "mot15" / "TUD-Stadtmitte-raw.mp4",
    "ADL-Rundle-6": DATA_DIR / "mot15" / "ADL-Rundle-6-raw.mp4",
}
GAINS = [15, 30, 50, 80]
SPEEDS = [60, 120, 240]
DEADBANDS = [0, 40]
FPS_VARIANTS = [10.0, 5.0]
MAX_REVERSALS_PER_MIN = 30.0  # more than this and the servos visibly twitch


def sweep_configs(args) -> list[SimConfig]:
    cfgs = [SimConfig(follow_gain_pct=0)]  # fixed camera baseline
    for g in args.gains:
        for s in args.speeds:
            for d in args.deadbands:
                cfgs.append(SimConfig(follow_gain_pct=g, max_speed_dps=s, follow_deadband=d))
    return cfgs


def run_seq(seq: str, cfgs: list[SimConfig], min_seconds: float) -> tuple[dict, dict[str, list[Episode]]]:
    info = load_seqinfo(MOT / seq / "seqinfo.ini")
    gt = load_mot_gt(MOT / seq / "gt" / "gt.txt")
    ids = episode_ids(gt, info["frame_rate"], min_seconds)
    results, episodes = {}, {}
    for cfg in cfgs:
        eps = [run_episode(seq, gt, info["width"], info["height"], info["frame_rate"], i, cfg) for i in ids]
        episodes[cfg.label()] = [e for e in eps if e is not None]
        results[cfg.label()] = dict(summarize(eps), config=cfg.__dict__)
    return {"sequence": seq, "fps": info["frame_rate"], "width": info["width"], "height": info["height"], "people": len(ids), "results": results}, episodes


def choose(all_results: list[dict], labels: list[str]) -> str:
    """Best label by frames-weighted centered fraction, among settings that do not twitch."""
    best, best_v = None, -1.0
    for lab in labels:
        frames = sum(r["results"][lab]["frames"] for r in all_results)
        if not frames:
            continue
        rev = max(r["results"][lab]["reversals_per_min"] for r in all_results)
        v = sum(r["results"][lab]["in_band_frac"] * r["results"][lab]["frames"] for r in all_results) / frames
        if rev <= MAX_REVERSALS_PER_MIN and v > best_v:
            best, best_v = lab, v
    return best or labels[0]


class _FrameReader:
    def __init__(self, video: Path):
        import cv2

        self.cv2 = cv2
        self.cap = cv2.VideoCapture(str(video))
        if not self.cap.isOpened():
            raise FileNotFoundError(video)
        self.next_index = 1

    def get(self, f: int):
        if f != self.next_index:
            self.cap.set(self.cv2.CAP_PROP_POS_FRAMES, f - 1)
        ok, bgr = self.cap.read()
        self.next_index = f + 1
        return self.cv2.cvtColor(bgr, self.cv2.COLOR_BGR2RGB) if ok else None


def detector_run(seq: str, cfg: SimConfig, model: Path, min_seconds: float, score_thresh: float) -> tuple[dict, list[Episode]]:
    from herd_ai.detector import PersonDetector
    from herd_ai.tracker import detections_from_pixels

    info = load_seqinfo(MOT / seq / "seqinfo.ini")
    gt = load_mot_gt(MOT / seq / "gt" / "gt.txt")
    det = PersonDetector(model, score_thresh)
    reader = _FrameReader(VIDEOS[seq])
    probe = reader.get(1)
    vid_h, vid_w = probe.shape[:2]
    scale = vid_w / info["width"]  # labels are in the original resolution; the video may be smaller
    gt = {f: [type(b)(b.frame, b.track_id, b.x1 * scale, b.y1 * scale, b.x2 * scale, b.y2 * scale) for b in boxes] for f, boxes in gt.items()}
    cam = VirtualCamera(vid_w, vid_h, cfg)

    def detect_fn(f: int, x0: int, x1: int):
        rgb = reader.get(f)
        if rgb is None:
            return []
        res = det.detect(rgb[:, x0:x1])
        dets = detections_from_pixels(res.boxes, res.scores, cam.vw, vid_h)
        return sorted(dets, key=lambda d: -d.score)[:8]

    ids = episode_ids(gt, info["frame_rate"], min_seconds)
    eps = [run_episode(seq, gt, vid_w, vid_h, info["frame_rate"], i, cfg, detect_fn) for i in ids]
    eps = [e for e in eps if e is not None]
    return dict(summarize(eps), config=cfg.__dict__, model=model.name), eps


def episode_png(seq: str, chosen: Episode, baseline: Episode | None, cfg_label: str, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 5.6), sharex=True)
    t = [p[0] / 1000 for p in chosen.trace]
    a1.plot(t, [p[2] / 10 for p in chosen.trace], color="#15202B", lw=2, label=f"person {chosen.gt_id} (labeled position)")
    a1.plot(t, [p[1] / 10 for p in chosen.trace], color="#D98A00", lw=2, label=f"camera pan, {cfg_label}")
    a1.set_ylabel("degrees from home")
    a1.legend(loc="best", fontsize=8, frameon=False)
    a1.grid(color="#E3E7EC")
    a2.axhspan(500 - 150, 500 + 150, color="#1F8F57", alpha=0.12, lw=0, label="centered band")
    a2.plot(t, [p[3] for p in chosen.trace], color="#D98A00", lw=2, label="following")
    if baseline is not None:
        tb = [p[0] / 1000 for p in baseline.trace]
        a2.plot(tb, [p[3] for p in baseline.trace], color="#8A94A3", lw=2, ls="--", label="fixed camera")
    a2.set_ylim(-50, 1050)
    a2.set_ylabel("where the person is in the view")
    a2.set_xlabel("seconds")
    a2.legend(loc="best", fontsize=8, frameon=False)
    a2.grid(color="#E3E7EC")
    fig.suptitle(f"{seq}: one person followed by the virtual camera")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    plt.close(fig)


def _row(seq: str, lab: str, r: dict) -> str:
    return (f"| {seq} | {lab} | {r['episodes']} | {r['frames']} | {100 * r['in_band_frac']:.0f} % | {100 * r['visible_frac']:.0f} % | "
            f"{r['mean_abs_err']:.0f} | {r['lost']} | {r['handoff_ready']} | {r['reversals_per_min']:.1f} |")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seqs", nargs="*", default=list(VIDEOS))
    ap.add_argument("--gains", type=int, nargs="*", default=GAINS)
    ap.add_argument("--speeds", type=int, nargs="*", default=SPEEDS)
    ap.add_argument("--deadbands", type=int, nargs="*", default=DEADBANDS)
    ap.add_argument("--min-seconds", type=float, default=3.0, help="shortest labeled track to use")
    ap.add_argument("--detector", action="store_true", help="also run the real detector on PETS at the chosen settings")
    ap.add_argument("--model", type=Path, default=None)
    ap.add_argument("--score-thresh", type=float, default=0.25)
    ap.add_argument("--out", type=Path, default=RESULTS_DIR / "follow")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    cfgs = sweep_configs(args)
    labels = [c.label() for c in cfgs]
    per_seq, per_seq_eps = [], {}
    for seq in args.seqs:
        res, eps = run_seq(seq, cfgs, args.min_seconds)
        per_seq.append(res)
        per_seq_eps[seq] = eps
        print(f"{seq}: {res['people']} people, {res['fps']:g} fps")
        for lab in labels:
            r = res["results"][lab]
            print(f"  {lab:28s} centered {100 * r['in_band_frac']:5.1f} %  in view {100 * r['visible_frac']:5.1f} %  lost {r['lost']:2d}  "
                  f"handoff-ready {r['handoff_ready']:2d}  reversals/min {r['reversals_per_min']:5.1f}")

    chosen = choose(per_seq, labels[1:])
    default = SimConfig().label()
    print(f"\nchosen: {chosen} (default firmware: {default})")

    # frame-rate variants of the default and the chosen setting
    fps_rows = []
    for base_lab in dict.fromkeys([default, chosen]):
        base = next(c for c in cfgs if c.label() == base_lab)
        for fps in FPS_VARIANTS:
            cfg = SimConfig(**dict(base.__dict__, fps=fps))
            for res in per_seq:
                seq = res["sequence"]
                if fps >= res["fps"]:
                    continue
                r2, eps2 = run_seq(seq, [cfg], args.min_seconds)
                res["results"][cfg.label()] = r2["results"][cfg.label()]
                fps_rows.append((seq, cfg.label(), r2["results"][cfg.label()]))

    det_row = None
    if args.detector and "PETS09-S2L1" in args.seqs:
        from herd_ai.models import DEFAULT_MODEL, model_path

        model = args.model or model_path(DEFAULT_MODEL.filename)
        cfg = next(c for c in cfgs if c.label() == chosen)
        r, eps = detector_run("PETS09-S2L1", cfg, model, args.min_seconds, args.score_thresh)
        det_row = ("PETS09-S2L1", f"{chosen} + real detector", r)
        next(x for x in per_seq if x["sequence"] == "PETS09-S2L1")["results"][f"{chosen}+detector"] = r
        print(f"real detector on PETS: centered {100 * r['in_band_frac']:.1f} %, in view {100 * r['visible_frac']:.1f} %, lost {r['lost']}")

    for res in per_seq:
        seq = res["sequence"]
        eps = per_seq_eps[seq]
        longest = max(eps[chosen], key=lambda e: e.frames) if eps.get(chosen) else None
        if longest is not None:
            base = next((e for e in eps[labels[0]] if e.gt_id == longest.gt_id), None)
            episode_png(seq, longest, base, chosen, args.out / f"{seq}_episode.png")
        res["episodes"] = {lab: [{"gt_id": e.gt_id, "frames": e.frames, "in_band_frac": e.in_band_frac, "visible_frac": e.visible_frac,
                                 "lost_ms": e.lost_ms, "hit_limit": e.hit_limit, "handoff_ready_ms": e.handoff_ready_ms,
                                 "reversals": e.reversals, "followed_ms": e.followed_ms} for e in eps[lab]] for lab in (labels[0], chosen)}
        (args.out / f"{seq}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")

    head = "| sequence | setting | people | frames | centered | in view | mean error (/1000) | lost | handoff-ready | reversals / min |"
    sep = "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    lines = [
        "# Week 9: following with the servos, simulated on labeled video",
        "",
        f"Date: {date.today().isoformat()}. The camera sees half the frame width ({SimConfig().hfov_deg} deg), pans at most to the frame edges,",
        f"runs the follow law from pantilt.c with the firmware tracker, applies each box {SimConfig().latency_ms} ms after its frame and",
        f"steps the servos every {SimConfig().loop_ms} ms. 'centered' = the labeled person within +-{SimConfig().band}/1000 of the view center;",
        "'lost' = target gone for 1.5 s before reaching a pan limit; 'handoff-ready' = reached the edge of the view at the pan limit",
        "(where unit_fsm.c sends \"heading your way\"); reversals = pan direction changes per minute of following.",
        "",
        f"Chosen setting: **{chosen}** (default firmware: {default}).",
        "",
        "## Fixed camera, firmware default, chosen setting",
        "",
        head, sep,
    ]
    for res in per_seq:
        for lab in dict.fromkeys([labels[0], default, chosen]):
            lines.append(_row(res["sequence"], lab, res["results"][lab]))
    if det_row:
        lines.append(_row(*det_row))
    lines += ["", "## Frame rate", "", head, sep]
    for seq, lab, r in fps_rows:
        lines.append(_row(seq, lab, r))
    lines += ["", "## Full sweep", "", head, sep]
    for res in per_seq:
        for lab in labels[1:]:
            lines.append(_row(res["sequence"], lab, res["results"][lab]))
    (args.out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
