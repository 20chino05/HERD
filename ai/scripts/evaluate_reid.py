"""Week 6 deliverable: test ST's person re-identification model on the laptop with a free
multi-camera dataset (Market-1501: 1,501 people seen by 6 cameras).

    python scripts/evaluate_reid.py                                          # OSNet 0.25, full set
    python scripts/evaluate_reid.py --models "models/osnet_*.tflite"         # both OSNet sizes
    python scripts/evaluate_reid.py --max-query 300 --max-gallery 3000       # quick run (~1 min)

For each model: embed every query and gallery crop, then report
  - CMC rank-1/5/10 and mAP with the standard Market-1501 protocol (comparable to published numbers),
  - how far apart same-person and different-person embeddings are across cameras, with the distance
    threshold that keeps false "same person" decisions under 1 % and 5 %,
  - how often the right person is nearest when k people walk into the next camera together,
  - embedding latency on this laptop (relative only; ST's board number is printed next to it).
Writes results/reid/<model>/metrics.json + distances.png and results/reid/summary.md.
"""

from __future__ import annotations

import argparse
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

from herd_ai.models import catalog_entry, model_path  # noqa: E402
from herd_ai.paths import DATA_DIR, RESULTS_DIR  # noqa: E402
from herd_ai.reid import PersonEmbedder, cosine_distance_matrix, parse_market_name  # noqa: E402
from herd_ai.reid_metrics import evaluate_rank, nearest_of_k, pair_distances, pick_threshold, threshold_table  # noqa: E402

MARKET_DIR = DATA_DIR / "market1501" / "Market-1501-v15.09.15"
ST_PUBLISHED = {  # OSNet README, DeepSportradar test split (50 queries, 910 gallery)
    "osnet_a025_256_128_tfs_int8": {"map": 70.27, "rank1": 92.0, "rank5": 96.0},
    "osnet_a100_256_128_tfs_int8": {"map": 73.84, "rank1": 90.0, "rank5": 98.0},
}
NEG_SAMPLES_PER_QUERY = 500


def _list_split(folder: Path, limit: int | None, rng: np.random.Generator) -> list[Path]:
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() == ".jpg")
    if limit and limit < len(files):
        files = [files[i] for i in sorted(rng.choice(len(files), size=limit, replace=False))]
    return files


def _embed_all(emb: PersonEmbedder, files: list[Path], desc: str) -> tuple[np.ndarray, list[float]]:
    feats = np.zeros((len(files), emb.dim), dtype=np.float32)
    lat: list[float] = []
    for i, p in enumerate(tqdm(files, desc=desc, unit="img", leave=False)):
        bgr = cv2.imread(str(p))
        if bgr is None:
            raise FileNotFoundError(p)
        feats[i] = emb.embed(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        lat.append(emb.last_latency_ms)
    return feats, lat


def _pct(x: list[float], q: float) -> float:
    return float(np.percentile(x, q)) if x else 0.0


def evaluate_model(path: Path, args, rng: np.random.Generator, q_files: list[Path], g_files: list[Path]) -> dict:
    emb = PersonEmbedder(path, num_threads=args.threads)
    print(f"\nmodel {emb.name}  input {emb.input_hw[0]}x{emb.input_hw[1]}  embedding {emb.dim}-d")

    q_feats, q_lat = _embed_all(emb, q_files, "query")
    g_feats, g_lat = _embed_all(emb, g_files, "gallery")
    lat = q_lat + g_lat
    q_ids = np.array([parse_market_name(p.name) for p in q_files])
    g_ids = np.array([parse_market_name(p.name) for p in g_files])
    q_pids, q_cams, g_pids, g_cams = q_ids[:, 0], q_ids[:, 1], g_ids[:, 0], g_ids[:, 1]

    dist = cosine_distance_matrix(q_feats, g_feats)
    rank = evaluate_rank(dist, q_pids, q_cams, g_pids, g_cams, max_rank=10)

    pos_parts, neg_parts = [], []
    for s in range(0, len(q_files), 256):
        pos, neg = pair_distances(dist[s : s + 256], q_pids[s : s + 256], q_cams[s : s + 256], g_pids, g_cams)
        pos_parts.append(pos)
        take = min(len(neg), NEG_SAMPLES_PER_QUERY * min(256, len(q_files) - s))
        neg_parts.append(rng.choice(neg, size=take, replace=False) if take < len(neg) else neg)
    pos, neg = np.concatenate(pos_parts), np.concatenate(neg_parts)
    thresholds = [round(float(t), 3) for t in np.arange(0.05, 1.0001, 0.05)]
    table = threshold_table(pos, neg, thresholds)
    recommended = {}
    for fpr in args.max_fpr:
        t = pick_threshold(pos, neg, fpr)
        recommended[f"fpr_{fpr}"] = {"threshold": round(t, 4), "tpr": float(np.mean(pos <= t)), "fpr": float(np.mean(neg <= t))}
    nearest = {str(k): nearest_of_k(dist, q_pids, q_cams, g_pids, g_cams, k=k, rng=rng, trials_per_query=3) for k in args.k}

    entry = catalog_entry(path)
    metrics = {
        "model": emb.name,
        "model_path": str(path),
        "embedding_dim": emb.dim,
        "dataset": {
            "name": "Market-1501 (query vs bounding_box_test, 6 cameras)",
            "n_query": len(q_files),
            "n_gallery": len(g_files),
            "n_identities_query": int(len(np.unique(q_pids))),
            "n_gallery_junk": int(np.sum(g_pids == -1)),
            "n_gallery_distractors": int(np.sum(g_pids == 0)),
        },
        "map": rank.map,
        "cmc": {"rank1": float(rank.cmc[0]), "rank5": float(rank.cmc[4]), "rank10": float(rank.cmc[9])},
        "n_valid_queries": rank.n_valid_queries,
        "pair_separation": {
            "n_pos": int(len(pos)),
            "n_neg_sampled": int(len(neg)),
            "pos_mean": float(pos.mean()),
            "pos_median": float(np.median(pos)),
            "neg_mean": float(neg.mean()),
            "neg_median": float(np.median(neg)),
            "thresholds": table,
            "recommended": recommended,
        },
        "nearest_of_k": nearest,
        "latency_ms": {
            "mean": statistics.fmean(lat),
            "median": statistics.median(lat),
            "p95": _pct(lat, 95),
            "min": min(lat),
            "max": max(lat),
            "n": len(lat),
        },
        "st_published": {
            **ST_PUBLISHED.get(emb.name, {}),
            "dataset": "DeepSportradar (basketball players)",
            "n6570dk_ms": entry.st_n6_ms if entry else None,
        },
        "config": {"seed": args.seed, "threads": args.threads, "max_query": args.max_query, "max_gallery": args.max_gallery},
        "environment": {"python": platform.python_version(), "machine": platform.machine(), "timestamp": datetime.now().isoformat(timespec="seconds")},
    }

    out = args.out / emb.name
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    _plot(pos, neg, recommended, out / "distances.png", emb.name)

    rec_lines = "".join(
        f"  threshold {v['threshold']:.3f}: accepts {v['tpr']:.1%} of same-person pairs at {v['fpr']:.1%} false accepts\n"
        for v in recommended.values()
    )
    nearest_line = ", ".join(f"{k}: {v:.1%}" for k, v in nearest.items())
    print(
        f"  mAP {rank.map:.3f}  rank-1 {rank.cmc[0]:.3f}  rank-5 {rank.cmc[4]:.3f}  ({rank.n_valid_queries} queries)\n"
        f"  same-person distance median {np.median(pos):.3f}, different-person median {np.median(neg):.3f}\n"
        f"{rec_lines}"
        f"  right person nearest out of {nearest_line}\n"
        f"  embed {statistics.median(lat):.1f} ms median on this CPU (ST: {entry.st_n6_ms if entry else '?'} ms on the N6570-DK)"
    )
    return metrics


def _plot(pos, neg, recommended, path: Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.5, 4))
    bins = np.linspace(0, 1, 101)
    ax.hist(pos, bins=bins, density=True, alpha=0.6, label=f"same person, other camera (n={len(pos)})")
    ax.hist(neg, bins=bins, density=True, alpha=0.6, label=f"different person (sample n={len(neg)})")
    for key, v in recommended.items():
        ax.axvline(v["threshold"], color="k", linestyle="--", linewidth=1)
        ax.text(v["threshold"], ax.get_ylim()[1] * 0.95, " " + key.replace("fpr_", "FPR "), fontsize=8, va="top")
    ax.set_xlabel("cosine distance between embeddings")
    ax.set_ylabel("density")
    ax.set_title(f"{title} on Market-1501")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _fmt(x, spec: str) -> str:
    return format(x, spec) if isinstance(x, (int, float)) and x == x else "-"


def write_summary(out_dir: Path) -> None:
    rows = [json.loads(mp.read_text(encoding="utf-8")) for mp in sorted(out_dir.glob("*/metrics.json"))]
    if not rows:
        return
    lines = [
        "# Re-identification on Market-1501 (laptop)",
        "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M} by scripts/evaluate_reid.py. Standard protocol: for each query, gallery images of the",
        "same person from the same camera are removed; rank-k = true match within the k nearest; mAP over all queries.",
        "ST's own numbers are on DeepSportradar (basketball players), a different and easier set, so they are context, not a target.",
        "",
        "| model | queries / gallery | mAP | rank-1 | rank-5 | ST mAP / rank-1 (DeepSportradar) | threshold at 1% false accepts (same-person accepted) | right one of 2 / 3 / 5 | laptop embed, median | ST N6570-DK |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        rec = r["pair_separation"]["recommended"].get("fpr_0.01", {})
        st = r["st_published"]
        n = r["nearest_of_k"]
        st_map = st.get("map")
        st_r1 = st.get("rank1")
        lines.append(
            f"| {r['model']} | {r['dataset']['n_query']:,} / {r['dataset']['n_gallery']:,} | {r['map']:.3f} | {r['cmc']['rank1']:.3f} | {r['cmc']['rank5']:.3f} | "
            f"{_fmt(st_map / 100 if st_map else None, '.3f')} / {_fmt(st_r1 / 100 if st_r1 else None, '.3f')} | "
            f"{_fmt(rec.get('threshold'), '.3f')} ({_fmt(rec.get('tpr'), '.1%')}) | "
            f"{_fmt(n.get('2'), '.1%')} / {_fmt(n.get('3'), '.1%')} / {_fmt(n.get('5'), '.1%')} | "
            f"{r['latency_ms']['median']:.1f} ms | {st.get('n6570dk_ms')} ms |"
        )
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="*", default=[str(model_path("osnet_a025_256_128_tfs_int8.tflite"))], help="model files or globs")
    ap.add_argument("--data", type=Path, default=MARKET_DIR, help="Market-1501-v15.09.15 folder")
    ap.add_argument("--max-query", type=int, default=None)
    ap.add_argument("--max-gallery", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument("--max-fpr", type=float, nargs="*", default=[0.01, 0.05])
    ap.add_argument("--k", type=int, nargs="*", default=[2, 3, 5])
    ap.add_argument("--out", type=Path, default=RESULTS_DIR / "reid")
    args = ap.parse_args(argv)

    paths: list[Path] = []
    for pat in args.models:
        p = Path(pat)
        paths.extend(sorted(p.parent.glob(p.name)) if any(c in pat for c in "*?[") else [p])
    missing = [p for p in paths if not p.exists()]
    if missing or not paths:
        print(f"model(s) not found: {missing or args.models}\nrun: python scripts/download_models.py --only osnet", file=sys.stderr)
        return 2
    if not (args.data / "query").exists():
        print(f"Market-1501 not found at {args.data}; see ai/README.md for the download", file=sys.stderr)
        return 2

    rng = np.random.default_rng(args.seed)
    q_files = _list_split(args.data / "query", args.max_query, rng)
    g_files = _list_split(args.data / "bounding_box_test", args.max_gallery, rng)
    print(f"Market-1501: {len(q_files)} query crops, {len(g_files)} gallery crops")
    for p in paths:
        evaluate_model(p, args, np.random.default_rng(args.seed), q_files, g_files)
    write_summary(args.out)
    print(f"\nwrote {args.out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
