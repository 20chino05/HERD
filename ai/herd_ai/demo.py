"""The local showcase: one page built from ai/results plus live streams of the real pipeline.

``load_results`` reads the committed metrics, ``render_page`` turns them into HTML, ``LiveTracker``
runs detector + tracker frame by frame on a MOT15 video or the webcam and yields JPEGs, and
``reid_showcase`` picks a few Market-1501 queries and their nearest gallery crops so the week 6
result can be seen, not just read. ``scripts/demo_server.py`` serves all of it on localhost.
"""

from __future__ import annotations

import html
import json
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from herd_ai.detector import PersonDetector
from herd_ai.draw import draw_tracks
from herd_ai.paths import DATA_DIR, MODELS_DIR, OUTPUTS_DIR, RESULTS_DIR
from herd_ai.tracker import NearestTracker, detections_from_pixels

MOT_DIR = DATA_DIR / "mot15"
MARKET_DIR = DATA_DIR / "market1501" / "Market-1501-v15.09.15"
SOURCES = {
    "pets": MOT_DIR / "PETS09-S2L1-raw.mp4",
    "tud": MOT_DIR / "TUD-Stadtmitte-raw.mp4",
    "campus": MOT_DIR / "TUD-Campus-raw.mp4",
    "adl": MOT_DIR / "ADL-Rundle-6-raw.mp4",
}
SOURCE_LABELS = {
    "pets": "PETS09-S2L1: fixed camera, 7 fps, up to 8 people",
    "tud": "TUD-Stadtmitte: street level, 25 fps, up to 8 people",
    "campus": "TUD-Campus: side view, 25 fps, up to 6 people",
    "adl": "ADL-Rundle-6: sidewalk, 30 fps, up to 13 people",
    "webcam": "This laptop's webcam",
}
DEFAULT_SETTING = "centroid200_drop1000"
SWEEP_ROWS = [
    ("centroid100_drop1000", "match distance 100"),
    ("centroid200_drop1000", "match distance 200 (firmware default)"),
    ("centroid300_drop1000", "match distance 300"),
    ("centroid200_drop500", "drop after 500 ms"),
    ("centroid200_drop2000", "drop after 2000 ms"),
    ("centroid200_drop1000_pred", "with speed prediction"),
    ("iou30_drop1000", "IoU matching instead of center distance"),
]


# --- results -------------------------------------------------------------------------------------


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_results(results_dir: Path = RESULTS_DIR) -> dict:
    week4 = _read_json(results_dir / "week4_samples" / "detections.json") or {}
    week5 = [m for p in sorted(results_dir.glob("yolov8n_*/metrics.json")) if (m := _read_json(p))]
    week5.sort(key=lambda m: m["input_size"])
    week6 = [m for p in sorted(results_dir.glob("reid/*/metrics.json")) if (m := _read_json(p))]
    runs = [m for p in sorted(results_dir.glob("tracking/*/metrics.json")) if (m := _read_json(p))]
    defaults = [m for m in runs if m["name"].endswith(f"__256__{DEFAULT_SETTING}")]
    by_name = {m["name"]: m for m in runs}
    pets = by_name.get(f"PETS09-S2L1__256__{DEFAULT_SETTING}")
    sequences = sorted({m["name"].split("__")[0] for m in runs})
    sweep = []
    for setting, label in SWEEP_ROWS:
        cells = []
        for s in sequences:
            m = by_name.get(f"{s}__256__{setting}")
            cells.append(None if m is None else {"idsw_per_100": 100 * m["tracking"]["idsw"] / m["frames"], "mota": m["tracking"]["mota"]})
        if any(cells):
            sweep.append({"setting": setting, "label": label, "cells": cells})
    frame = results_dir / "tracking" / "PETS09-S2L1_frame381_tracked.jpg"
    return {
        "week4": week4,
        "week5": week5,
        "week6": week6,
        "week7": {"runs": runs, "defaults": defaults, "pets": pets, "sequences": sequences, "sweep": sweep, "frame": frame.name if frame.exists() else None},
    }


# --- re-identification showcase ------------------------------------------------------------------


def reid_showcase(n_queries: int = 8, n_gallery: int = 2000, top_k: int = 5, seed: int = 0, model_name: str = "osnet_a025_256_128_tfs_int8.tflite", cache_dir: Path = OUTPUTS_DIR / "demo") -> list[dict]:
    """A few Market-1501 queries with their nearest gallery crops (same subset and seed as the results)."""
    from herd_ai.reid import PersonEmbedder, cosine_distance_matrix, parse_market_name

    model_path = MODELS_DIR / model_name
    if not (model_path.exists() and (MARKET_DIR / "query").exists()):
        return []
    rng = np.random.default_rng(seed)
    q_files = sorted(p for p in (MARKET_DIR / "query").iterdir() if p.suffix.lower() == ".jpg")
    g_all = sorted(p for p in (MARKET_DIR / "bounding_box_test").iterdir() if p.suffix.lower() == ".jpg")
    g_files = [g_all[i] for i in sorted(rng.choice(len(g_all), size=min(n_gallery, len(g_all)), replace=False))]

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / f"reid_gallery_{Path(model_name).stem}_{n_gallery}_{seed}.npz"
    emb = PersonEmbedder(model_path)
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        g_feats = z["feats"]
    else:
        g_feats = np.stack([emb.embed(cv2.cvtColor(cv2.imread(str(p)), cv2.COLOR_BGR2RGB)) for p in g_files])
        np.savez(cache, feats=g_feats, names=np.array([p.name for p in g_files]))
    g_ids = np.array([parse_market_name(p.name) for p in g_files])

    # queries that have a cross-camera match inside the subset, so the true answer can be shown
    pick_rng = np.random.default_rng(seed + 1)
    valid = [q for q in q_files if any((g_ids[:, 0] == parse_market_name(q.name)[0]) & (g_ids[:, 1] != parse_market_name(q.name)[1]))]
    chosen = [valid[i] for i in sorted(pick_rng.choice(len(valid), size=min(n_queries, len(valid)), replace=False))]

    out = []
    for q in chosen:
        pid, cam = parse_market_name(q.name)
        qv = emb.embed(cv2.cvtColor(cv2.imread(str(q)), cv2.COLOR_BGR2RGB))
        d = cosine_distance_matrix(qv[None], g_feats)[0]
        keep = ~(((g_ids[:, 0] == pid) & (g_ids[:, 1] == cam)) | (g_ids[:, 0] == -1))
        order = [i for i in np.argsort(d) if keep[i]]
        same = [bool(g_ids[i, 0] == pid) for i in order]
        true_rank = same.index(True) + 1 if True in same else None
        out.append(
            {
                "query": q.name,
                "person": pid,
                "camera": cam,
                "true_rank": true_rank,
                "true_distance": float(d[order[true_rank - 1]]) if true_rank else None,
                "matches": [
                    {"file": g_files[i].name, "camera": int(g_ids[i, 1]), "distance": float(d[i]), "same": bool(g_ids[i, 0] == pid)}
                    for i in order[:top_k]
                ],
            }
        )
    return out


# --- live stream ---------------------------------------------------------------------------------


def _placeholder(text: str, size=(640, 360)) -> np.ndarray:
    img = np.full((size[1], size[0], 3), 24, dtype=np.uint8)
    cv2.putText(img, text, (24, size[1] // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (240, 160, 0), 2, cv2.LINE_AA)
    return img


class LiveTracker:
    """Detector + firmware tracker on a video file or the webcam, one JPEG per frame."""

    def __init__(self, model_path: Path, score_thresh: float = 0.25, match_dist: int = 200, drop_ms: int = 1000, max_tracks: int = 8):
        self.det = PersonDetector(model_path, score_thresh)
        self.match_dist, self.drop_ms, self.max_tracks = match_dist, drop_ms, max_tracks
        self._lock = threading.Lock()  # the interpreter is not thread-safe: one stream at a time
        self.status: dict = {"source": None, "frame": 0, "tracked": 0, "ms": 0.0}

    def _tracker(self) -> NearestTracker:
        return NearestTracker(match_dist=self.match_dist, drop_ms=self.drop_ms, max_tracks=self.max_tracks)

    def frames(self, source: str, keep_going, pace: bool = True, jpeg_quality: int = 80):
        webcam = source == "webcam"
        if not webcam and source not in SOURCES:
            raise KeyError(source)
        with self._lock:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if webcam else cv2.VideoCapture(str(SOURCES[source]))
            if not cap.isOpened():
                msg = "No webcam found on this laptop" if webcam else f"Video not found: {SOURCES[source].name}"
                ok, buf = cv2.imencode(".jpg", _placeholder(msg))
                yield buf.tobytes(), {"frame": 0, "tracked": 0, "ms": 0.0, "error": msg}
                return
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            if webcam or fps > 30:
                fps = 30.0
            tracker = self._tracker()
            label = SOURCE_LABELS.get(source, source)
            frame_idx = 0
            t_start = time.perf_counter()
            try:
                while keep_going():
                    tick = time.perf_counter()
                    ok, bgr = cap.read()
                    if not ok:
                        if webcam:
                            break
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # loop the clip
                        tracker = self._tracker()
                        frame_idx = 0
                        continue
                    frame_idx += 1
                    time_ms = int((tick - t_start) * 1000) if webcam else int(round((frame_idx - 1) * 1000.0 / fps))
                    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                    res = self.det.detect(rgb)
                    h, w = rgb.shape[:2]
                    tracks = tracker.update(detections_from_pixels(res.boxes, res.scores, w, h), time_ms)
                    seen = [t for t in tracks if t.last_seen_ms == time_ms]
                    shown = draw_tracks(rgb, seen)
                    ms = (time.perf_counter() - tick) * 1000.0
                    hud = f"{label.split(':')[0]}   frame {frame_idx}   {len(seen)} tracked   {ms:.0f} ms on this CPU"
                    bar = shown.copy()
                    cv2.rectangle(bar, (0, 0), (w, 32), (0, 0, 0), -1)
                    shown = cv2.addWeighted(bar, 0.55, shown, 0.45, 0)
                    cv2.putText(shown, hud, (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 1, cv2.LINE_AA)
                    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(shown, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                    info = {"source": source, "frame": frame_idx, "tracked": len(seen), "ids": [t.id for t in seen], "ms": ms}
                    self.status = info
                    yield buf.tobytes(), info
                    if pace:
                        time.sleep(max(0.0, 1.0 / fps - (time.perf_counter() - tick)))
            finally:
                cap.release()
                self.status = {"source": None, "frame": 0, "tracked": 0, "ms": 0.0}


# --- page ----------------------------------------------------------------------------------------


def _e(x) -> str:
    return html.escape(str(x))


def _pct(x, digits=0) -> str:
    return "-" if x is None else f"{100 * x:.{digits}f} %"


def _f(x, spec=".2f") -> str:
    return "-" if x is None else format(x, spec)


CSS = """
:root{--page:#F3F5F8;--panel:#FFFFFF;--ink:#15202B;--ink-2:#4A5A6A;--ink-3:#7C8A99;--line:#D5DBE3;
--amber:#D98A00;--amber-mark:#F0A000;--green:#1F8F57;--red:#B4382E;--radius:6px}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--page);color:var(--ink);font-family:Bahnschrift,"Segoe UI",system-ui,sans-serif;font-size:17px;line-height:1.5;font-variant-numeric:tabular-nums}
a{color:var(--amber);text-decoration:none}a:hover,a:focus-visible{text-decoration:underline}
:focus-visible{outline:3px solid var(--amber-mark);outline-offset:2px}
.top{position:sticky;top:0;z-index:5;background:var(--page);border-bottom:1px solid var(--line);padding:12px 24px;display:flex;flex-wrap:wrap;gap:8px 28px;align-items:baseline}
.top h1{font-size:22px;margin:0;font-weight:600;letter-spacing:.01em}
.top .sub{color:var(--ink-2);font-size:15px}
.top nav{margin-left:auto;display:flex;flex-wrap:wrap;gap:18px;font-size:15px}
.top nav a{color:var(--ink-2)}
main{max-width:1120px;margin:0 auto;padding:16px 24px 80px}
section{padding:40px 0 8px;border-top:1px solid var(--line)}
section:first-of-type{border-top:0;padding-top:24px}
h2{font-size:30px;font-weight:600;margin:0 0 6px;letter-spacing:-.01em;line-height:1.15}
h2 small{display:block;font-size:17px;font-weight:400;color:var(--ink-2);margin-top:4px}
h3{font-size:19px;font-weight:600;margin:28px 0 8px}
p{max-width:72ch;margin:10px 0}
.lead{font-size:19px;max-width:66ch;color:var(--ink)}
.stage{background:#0E141B;border-radius:var(--radius);padding:10px;display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:12px}
.stage img{width:100%;aspect-ratio:4/3;object-fit:contain;background:#000;border-radius:4px;display:block}
.controls{display:flex;flex-direction:column;gap:8px;padding:6px 4px}
.controls button{font:inherit;font-size:15px;text-align:left;padding:9px 12px;border-radius:4px;border:1px solid #2C3844;background:#182028;color:#E6EBF0;cursor:pointer}
.controls button:hover{border-color:var(--amber-mark)}
.controls button[aria-pressed=true]{background:var(--amber-mark);color:#15202B;border-color:var(--amber-mark);font-weight:600}
.controls .stop{margin-top:auto;background:transparent;color:#B8C2CC}
.controls .status{color:#B8C2CC;font-size:14px;min-height:3em;padding:4px 2px}
.flow{display:flex;flex-wrap:wrap;gap:0;margin:18px 0 6px;align-items:stretch}
.flow .step{flex:1 1 150px;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:10px 12px;font-size:15px;position:relative;margin-right:22px;min-width:150px}
.flow .step::after{content:"";position:absolute;right:-16px;top:50%;width:10px;height:10px;border-top:2px solid var(--ink-3);border-right:2px solid var(--ink-3);transform:translateY(-50%) rotate(45deg)}
.flow .step:last-child{margin-right:0}.flow .step:last-child::after{display:none}
.flow .step b{display:block;font-weight:600}
.flow .step.done{border-left:4px solid var(--green)}
.flow .step.todo{border-left:4px solid var(--line);color:var(--ink-2)}
table{border-collapse:collapse;width:100%;font-size:15px;margin:10px 0 4px;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius)}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-weight:600;color:var(--ink-2)}
td.n,th.n{text-align:right;white-space:nowrap}
tr:last-child td{border-bottom:0}
tr.hl td{background:#FFF6E3}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;margin:14px 0}
figure{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:8px}
figure img{width:100%;display:block;border-radius:3px}
figcaption{font-size:14px;color:var(--ink-2);padding:6px 2px 0}
.figs{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin:14px 0}
.kv{display:flex;flex-wrap:wrap;gap:12px 36px;margin:12px 0 4px}
.kv div{font-size:15px;color:var(--ink-2)}
.kv div b{display:block;font-size:30px;font-weight:600;color:var(--ink);line-height:1.1}
.reid{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:14px;margin:14px 0}
.q{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:10px;display:flex;gap:10px;align-items:flex-start}
.q .crop{width:64px;flex:0 0 64px;text-align:center;font-size:12px;color:var(--ink-2)}
.q .crop img{width:64px;height:128px;object-fit:cover;display:block;border:3px solid var(--line);border-radius:3px;image-rendering:auto}
.q .crop.query img{border-color:var(--ink)}
.q .crop.same img{border-color:var(--green)}
.q .crop.diff img{border-color:var(--red)}
.q .crop span{display:block;margin-top:3px}
.q .arrow{align-self:center;color:var(--ink-3);font-size:22px;padding:0 2px}
.q .note{font-size:13px;color:var(--ink-2);align-self:center;margin-left:auto;max-width:150px}
.callout{background:var(--panel);border-left:4px solid var(--amber-mark);border-radius:var(--radius);padding:12px 16px;margin:16px 0;max-width:72ch}
.callout ul{margin:6px 0 0;padding-left:20px}
code{font-family:Consolas,"Cascadia Mono",monospace;font-size:.92em;background:#E9EDF2;padding:1px 5px;border-radius:3px}
.muted{color:var(--ink-3);font-size:14px}
@media (max-width:820px){.stage{grid-template-columns:1fr}.controls{flex-direction:row;flex-wrap:wrap}.controls .stop{margin-top:0}.reid{grid-template-columns:1fr}}
"""

JS = """
const img=document.getElementById('live');const status=document.getElementById('status');
const buttons=[...document.querySelectorAll('.controls button[data-src]')];
let current=null,timer=null;
function play(src){current=src;buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.src===src)));
 img.src='/stream/'+src+'?t='+Date.now();status.textContent='Starting '+src+'...';
 if(!timer)timer=setInterval(poll,1000);}
function stop(){current=null;buttons.forEach(b=>b.setAttribute('aria-pressed','false'));img.removeAttribute('src');
 fetch('/stop');status.textContent='Stopped.';if(timer){clearInterval(timer);timer=null;}}
async function poll(){try{const r=await fetch('/status');const s=await r.json();
 if(s.error){status.textContent=s.error;return;}
 if(s.source)status.textContent=`frame ${s.frame}, ${s.tracked} tracked (ids ${s.ids.join(', ')||'none'}), ${s.ms.toFixed(0)} ms per frame on this CPU`;
 }catch(e){}}
buttons.forEach(b=>b.addEventListener('click',()=>play(b.dataset.src)));
document.getElementById('stop').addEventListener('click',stop);
const first=buttons.find(b=>b.dataset.src==='pets')||buttons[0];
if(first){current=first.dataset.src;first.setAttribute('aria-pressed','true');timer=setInterval(poll,1000);}
"""


def render_page(results: dict, reid_demo: list[dict], model_name: str = "yolov8n 256") -> str:
    w4, w5, w6, w7 = results["week4"], results["week5"], results["week6"], results["week7"]
    parts: list[str] = []

    # --- live ---
    buttons = "".join(
        f'<button type="button" data-src="{k}" aria-pressed="false">{_e(SOURCE_LABELS[k].split(":")[0])}<br><span class="muted">{_e(SOURCE_LABELS[k].split(":", 1)[1].strip() if ":" in SOURCE_LABELS[k] else "")}</span></button>'
        for k in ("pets", "tud", "campus", "adl")
        if SOURCES[k].exists()
    )
    buttons += '<button type="button" data-src="webcam" aria-pressed="false">Webcam<br><span class="muted">this laptop, live</span></button>'
    parts.append(
        f"""
<section id="live">
  <h2>Live<small>The real pipeline, frame by frame, on this laptop's CPU: ST's {_e(model_name)} int8 detector (the exact file the STM32N6 runs), then the firmware's tracker giving each person an id.</small></h2>
  <div class="stage">
    <img id="live" alt="Live detection and tracking output" src="/stream/pets?t=0">
    <div class="controls">
      {buttons}
      <div class="status" id="status">Starting...</div>
      <button type="button" class="stop" id="stop">Stop</button>
    </div>
  </div>
  <p class="muted">Amber boxes and ids come from the tracker; the id survives as long as the same person is matched frame to frame. Video clips loop. The webcam needs no setup; if none is attached the frame says so.</p>
  <div class="flow">
    <div class="step done"><b>Camera frame</b>videos from MOT15, or the webcam</div>
    <div class="step done"><b>Detector</b>ST YOLOv8n 256 int8, week 4 and 5</div>
    <div class="step done"><b>Tracker</b>firmware algorithm, week 7</div>
    <div class="step todo"><b>Lingering</b>week 8, next</div>
    <div class="step todo"><b>Handoff</b>position and timing, appearance as tie-breaker (week 6)</div>
  </div>
</section>"""
    )

    # --- week 4 ---
    if w4:
        cards = ""
        for im in w4.get("images", []):
            scores = " ".join(f"{d['score']:.2f}" for d in im["detections"])
            scores_txt = f", scores {scores}" if scores else ""
            title = im["image"].replace("_", " ").replace(".jpg", "")
            cards += (
                f'<figure><img src="/results/week4_samples/{_e(im["image"])}" alt="{_e(im["image"])} with detections" loading="lazy">'
                f'<figcaption>{_e(title)}: {len(im["detections"])} found{scores_txt}, {im["latency_ms"]:.0f} ms</figcaption></figure>'
            )
        n_det = sum(len(im["detections"]) for im in w4.get("images", []))
        parts.append(
            f"""
<section id="week4">
  <h2>Week 4<small>ST's ready-made person detector running on a laptop with sample photos.</small></h2>
  <p class="lead">Seven COCO photos through {_e(w4.get("model", ""))} at threshold {w4.get("score_thresh", 0.25)}: {n_det} people found, boxes drawn by our code from the model's raw output.</p>
  <div class="grid">{cards}</div>
</section>"""
        )

    # --- week 5 ---
    if w5:
        rows = ""
        for m in w5:
            t25 = m.get("at_threshold", {}).get("0.25", {})
            hl = ' class="hl"' if m["input_size"] == 256 else ""
            rows += (
                f'<tr{hl}><td>YOLOv8n {m["input_size"]}</td><td class="n">{m["ap50"]:.3f}</td><td class="n">{_f(m.get("pycocotools_ap50"), ".3f")}</td>'
                f'<td class="n">{m["st_ap50_percent"] / 100:.3f}</td><td class="n">{_f(t25.get("precision"))} / {_f(t25.get("recall"))}</td>'
                f'<td class="n">{m["latency_ms"]["median"]:.1f} ms</td><td class="n">{m["st_n6_ms"]:.1f} ms</td></tr>'
            )
        curves = "".join(
            f'<figure><img src="/results/{_e(Path(m["model_path"]).stem)}/pr_curve.png" alt="precision-recall curve, {m["input_size"]}" loading="lazy"><figcaption>Precision against recall, {m["input_size"]} input</figcaption></figure>'
            for m in w5
        )
        m256 = next((m for m in w5 if m["input_size"] == 256), w5[0])
        parts.append(
            f"""
<section id="week5">
  <h2>Week 5<small>Accuracy on a free dataset at the image sizes the board will use.</small></h2>
  <p class="lead">All {m256["n_images"]:,} COCO val2017 images, {m256["n_gt_boxes"]:,} labeled people, scored with ST's own settings and cross-checked with the official COCO API. Our number lands within 3 points of ST's for every size, so the laptop measurement can be trusted.</p>
  <table>
    <thead><tr><th>model</th><th class="n">AP@0.5, ours</th><th class="n">COCO API</th><th class="n">ST published</th><th class="n">precision / recall at 0.25</th><th class="n">laptop CPU, median</th><th class="n">ST on N6570-DK</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p>256 is the default (fits the N6's internal RAM, about 24 ms a frame); 320 is the fallback if far-away people matter. The threshold 0.25 comes from the precision/recall sweep, because the int8 scores come out in coarse steps.</p>
  <div class="figs">{curves}</div>
</section>"""
        )

    # --- week 6 ---
    if w6 or reid_demo:
        m = w6[0] if w6 else None
        kv = ""
        if m:
            rec = m["pair_separation"]["recommended"].get("fpr_0.01", {})
            nk = m["nearest_of_k"]
            kv = f"""
  <div class="kv">
    <div><b>{_pct(m["cmc"]["rank1"])}</b>rank-1 on Market-1501<br>ST reports {_pct(m["st_published"].get("rank1", 0) / 100)} on its own test set</div>
    <div><b>{_pct(nk.get("2"))}</b>right person out of 2 arrivals<br>chance is 50 %</div>
    <div><b>{_pct(nk.get("5"))}</b>right person out of 5<br>chance is 20 %</div>
    <div><b>{_pct(rec.get("tpr"))}</b>true matches accepted<br>at 1 % false accepts (distance {_f(rec.get("threshold"), ".3f")})</div>
    <div><b>{m["latency_ms"]["median"]:.0f} ms</b>per crop on this CPU<br>ST: {m["st_published"].get("n6570dk_ms")} ms on the N6570-DK</div>
  </div>
  <p class="muted">Subset run: {m["dataset"]["n_query"]} queries against {m["dataset"]["n_gallery"]:,} gallery crops, {m["embedding_dim"]}-d embedding, cosine distance.</p>"""
        strips = ""
        for q in reid_demo:
            crops = "".join(
                f'<div class="crop {"same" if mt["same"] else "diff"}"><img src="/market/bounding_box_test/{_e(mt["file"])}" alt="gallery crop" loading="lazy"><span>cam {mt["camera"]}, {mt["distance"]:.2f}</span></div>'
                for mt in q["matches"]
            )
            note = f'true match at rank {q["true_rank"]}, distance {q["true_distance"]:.2f}' if q["true_rank"] else "no true match in subset"
            strips += (
                f'<div class="q"><div class="crop query"><img src="/market/query/{_e(q["query"])}" alt="query crop"><span>person {q["person"]}, cam {q["camera"]}</span></div>'
                f'<div class="arrow">&#8250;</div>{crops}<div class="note">{_e(note)}</div></div>'
            )
        hist = f'<figure><img src="/results/reid/{_e(Path(m["model_path"]).stem)}/distances.png" alt="distance histograms" loading="lazy"><figcaption>Same person seen by another camera (left) against different people (right): the two overlap heavily.</figcaption></figure>' if m else ""
        parts.append(
            f"""
<section id="week6">
  <h2>Week 6<small>Can the next camera recognize the same person? ST's re-identification model on a 6-camera pedestrian dataset.</small></h2>
  <p class="lead">Each person crop becomes a 128-number signature; the next camera compares signatures. ST trained this model on basketball players, so we measured it on Market-1501, 1,501 ordinary pedestrians seen by six cameras.</p>
  {kv}
  <h3>What the model actually picks</h3>
  <p>Left: a person seen by one camera. Then the five crops from the other cameras the model finds most similar. Green means the same person, red means someone else. This is why rank-1 is low: similar clothing from a different angle beats the real match.</p>
  <div class="reid">{strips}</div>
  <div class="figs">{hist}</div>
  <div class="callout">What this changes: the handoff between cameras stays position-and-timing first (which side, when, how fast). The signature is a tie-breaker when more than one person walks in. Fine-tuning on pedestrian data is a Winter option. The 128-byte signature also does not fit the message format's 32-byte payload yet.</div>
</section>"""
        )

    # --- week 7 ---
    if w7["defaults"]:
        rows = ""
        for m in w7["defaults"]:
            t, d = m["tracking"], m["detection_only"]
            rows += (
                f'<tr><td>{_e(m["name"].split("__")[0])}</td><td class="n">{m["fps_source"]:.0f}</td><td class="n">{m["frames"]}</td><td class="n">{m["people_per_frame_max"]}</td>'
                f'<td class="n">{d["recall"]:.2f} / {d["precision"]:.2f}</td><td class="n">{t["recall"]:.2f} / {t["precision"]:.2f}</td>'
                f'<td class="n">{t["idsw"]} ({100 * t["idsw"] / m["frames"]:.1f})</td><td class="n">{t["mota"]:.2f}</td><td class="n">{t["mostly_tracked"]} / {t["n_gt_tracks"]}</td></tr>'
            )
        crowd = ""
        if w7["pets"]:
            for b, s in sorted(w7["pets"]["tracking_by_crowd"].items()):
                crowd += f'<tr><td>{_e(b)} people</td><td class="n">{s["n_frames"]}</td><td class="n">{s["recall"]:.2f}</td><td class="n">{s["precision"]:.2f}</td><td class="n">{s["idsw"]} ({100 * s["idsw"] / s["n_frames"]:.1f})</td><td class="n">{s["mota"]:.2f}</td></tr>'
        sweep_head = "".join(f'<th class="n">{_e(s)}</th>' for s in w7["sequences"])
        sweep = ""
        for r in w7["sweep"]:
            hl = ' class="hl"' if r["setting"] == DEFAULT_SETTING else ""
            cells = ""
            for c in r["cells"]:
                val = "-" if c is None else f"{c['idsw_per_100']:.1f}"
                cells += f'<td class="n">{val}</td>'
            sweep += f'<tr{hl}><td>{_e(r["label"])}</td>{cells}</tr>'
        frame = f'<figure><img src="/results/tracking/{_e(w7["frame"])}" alt="annotated PETS frame" loading="lazy"><figcaption>PETS09-S2L1, frame 381: seven people with ids from the firmware tracker.</figcaption></figure>' if w7["frame"] else ""
        parts.append(
            f"""
<section id="week7">
  <h2>Week 7<small>Tracking: the firmware's tracker scored on public pedestrian video, by how many people are in the frame.</small></h2>
  <p class="lead">The tracker in <code>firmware/stm32/App/tracker.c</code> was rebuilt line for line in Python and run behind the detector on four fixed-camera sequences with ground-truth labels. Id switches are counted every time a labeled person gets a different id than before.</p>
  <table>
    <thead><tr><th>sequence</th><th class="n">fps</th><th class="n">frames</th><th class="n">people at once</th><th class="n">detector alone recall / precision</th><th class="n">with ids recall / precision</th><th class="n">id switches (per 100 frames)</th><th class="n">MOTA</th><th class="n">mostly tracked</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p>At 25 fps the tracker loses nothing against the detector. Where accuracy is low (the sidewalk clip) the detector misses small, far people, the same limit measured in week 5.</p>
  <div class="figs">{frame}</div>
  <h3>One, three, five people in the frame (PETS09-S2L1)</h3>
  <table>
    <thead><tr><th>people in frame</th><th class="n">frames</th><th class="n">recall</th><th class="n">precision</th><th class="n">id switches (per 100 frames)</th><th class="n">MOTA</th></tr></thead>
    <tbody>{crowd}</tbody>
  </table>
  <p>Detection cost does not depend on the number of people, so frames per second on the board will not either. What crowding costs is id switches, and a low frame rate makes it worse: the same tracker switched 2.2 times more often per frame at 7 fps than at 25 fps.</p>
  <h3>Which settings to put in app_config.h</h3>
  <p>Id switches per 100 frames for each setting, 256 detector. Lower is better.</p>
  <table>
    <thead><tr><th>setting</th>{sweep_head}</tr></thead>
    <tbody>{sweep}</tbody>
  </table>
  <div class="callout">Recommendation for the board:
    <ul>
      <li>TRACK_MATCH_DIST: try 100 to 150 on a static camera (fewer wrong matches, no lost recall); keep 200 while panning.</li>
      <li>TRACK_DROP_MS: keep 1000; both 500 and 2000 were worse everywhere.</li>
      <li>Do not add speed prediction or IoU matching; both were measured and neither helps.</li>
      <li>Measure the achieved frame rate first thing on the board; it matters more than any tracker setting.</li>
    </ul>
  </div>
</section>"""
        )

    parts.append(
        """
<section id="next">
  <h2>Next<small>Week 8 and the board.</small></h2>
  <p>Lingering: the firmware already defines it (within 120/1000 of one spot for 8 seconds). Next is to run that rule on the tracked video above and on a team-member clip to pick the radius and time, and to see how often an id switch would reset the timer on a real loiterer.</p>
  <p>Board: confirm the InnoMaker camera's pinout, install ST Edge AI Core 4.0.0, and put the detector on one Nucleo through ST's deployment flow. Everything on this page then runs on the unit instead of the laptop.</p>
  <p class="muted">Write-ups: Docs/software/2026-11-02-ai-weeks-4-5.md and Docs/software/2026-11-15-ai-weeks-6-7.md. Pull requests 6 and 8 on the team repo.</p>
</section>"""
    )

    nav = " ".join(f'<a href="#{k}">{v}</a>' for k, v in (("live", "Live"), ("week4", "Week 4"), ("week5", "Week 5"), ("week6", "Week 6"), ("week7", "Week 7"), ("next", "Next")))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Open Herd AI demo</title><style>{CSS}</style></head>
<body>
<header class="top"><h1>Open Herd</h1><span class="sub">The AI side, Fall weeks 4 to 7, running on this laptop</span><nav>{nav}</nav></header>
<main>{"".join(parts)}</main>
<script>{JS}</script>
</body></html>"""
