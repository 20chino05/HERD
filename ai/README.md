# Open Herd AI (laptop side)

Devin's half of the software: get ST's ready-made person detector running and measured on a laptop
first (Fall weeks 4 and 5), then tracking, lingering detection and camera following on top of it.
Everything here runs on a plain Windows/macOS/Linux laptop with no GPU and no board.

## What is here

| Path | Purpose |
|---|---|
| `herd_ai/` | Small Python package: image preprocessing, YOLOv8 output decoding + NMS, detection metrics (AP@0.5, precision/recall), COCO loading, a `PersonDetector` wrapper around the TFLite runtime. |
| `scripts/download_models.py` | Fetches ST's pretrained person models (int8 TFLite) into `models/`. |
| `scripts/run_detection.py` | **Week 4.** Runs a model on photos (or the webcam) and saves annotated images + `detections.json`. |
| `scripts/evaluate.py` | **Week 5.** Scores a model against COCO val2017 person labels; writes `metrics.json`, a PR curve and `results/summary.md`. |
| `samples/` | Seven COCO photos used as the Week 4 test inputs (see `samples/NOTICE.md` for licenses). |
| `results/` | Committed outputs: Week 4 annotated samples and Week 5 metrics. |
| `tests/` | pytest suite. Unit tests for the math, plus end-to-end checks that run the real model on real COCO images when they are present. |
| `models/`, `data/`, `outputs/` | Downloaded or generated; git-ignored. |

## Setup (about 5 minutes plus downloads)

Requires Python 3.10 to 3.12 (the TFLite runtime has no 3.13+ wheels yet) and [uv](https://docs.astral.sh/uv/)
or plain pip.

```powershell
cd ai
uv venv --python 3.12 .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
uv pip install -e ".[dev]"        # or: pip install -e ".[dev]"
python scripts/download_models.py # ~22 MB, from ST's GitHub
python -m pytest                  # unit tests only, until the data below exists
```

For the Week 5 accuracy check you also need COCO val2017 (about 1 GB total):

```powershell
mkdir data\coco; cd data\coco
curl -L -o annotations_trainval2017.zip http://images.cocodataset.org/annotations/annotations_trainval2017.zip
curl -L -o val2017.zip http://images.cocodataset.org/zips/val2017.zip
tar -xf annotations_trainval2017.zip annotations/instances_val2017.json
tar -xf val2017.zip
cd ..\..
```

## Week 4: run the detector

```powershell
python scripts/run_detection.py                       # yolov8n 256 on samples/, writes outputs/run_.../
python scripts/run_detection.py --score-thresh 0.25   # lower threshold, more boxes
python scripts/run_detection.py --webcam              # live, press q to quit
python scripts/run_detection.py --model models/yolov8n_320_quant_pc_uf_od_coco-person.tflite --images C:\photos
```

Each run prints people found and per-image latency, saves annotated JPEGs, and writes `detections.json`
with every box, score and timing. The committed Week 4 run is in `results/week4_samples/`.

## Week 5: measure accuracy and speed

```powershell
python scripts/evaluate.py --n-with-person 300 --n-without 100        # quick, fixed subset (~1 min)
python scripts/evaluate.py --models "models/yolov8n_*_coco-person.tflite" --pycocotools   # full, all sizes
```

The evaluator uses ST's own settings so our number is directly comparable to the AP they publish for each
model: a detection is correct at IoU >= 0.5, NMS 0.5, score threshold 0.001, at most 100 boxes per image.
`--pycocotools` recomputes AP@0.5 with the official COCO API as an independent check of our evaluator.
Besides AP it reports precision / recall / F1 at thresholds from 0.1 to 0.9 (to pick the operating
threshold for the demo) and invoke latency statistics. See `results/summary.md` for the current numbers.

## Models

All from ST's model zoo, trained on COCO person, int8 per-channel quantized, uint8 RGB input, one
`(1, 5, F)` float output = `cx, cy, w, h` normalized to the input plus the person score, no NMS inside.

| file | input | ST AP@0.5 | ST time on STM32N6570-DK | internal RAM |
|---|---|---|---|---|
| `yolov8n_192_quant_pc_uf_od_coco-person.tflite` | 192 | 53.6 % | 16.3 ms | 270 KiB |
| `yolov8n_256_quant_pc_uf_od_coco-person.tflite` | 256 | 58.4 % | 23.8 ms | 624 KiB |
| `yolov8n_320_quant_pc_uf_od_coco-person.tflite` | 320 | 61.9 % | 29.9 ms | 758 KiB |
| `yolov8n_416_quant_pc_uf_od_coco-person.tflite` | 416 | 64.8 % | 54.7 ms | 2068 KiB |

The three `st_yoloxn_*` files are also downloaded (they are what ST's N6 people-tracking demo ships on
the Discovery Kit) but their three-head output is not decoded here yet; `PersonDetector` raises a clear
error if you point it at one.

For Week 6 the download script also fetches ST's two person re-identification models from model zoo v4.0,
`osnet_a025_256_128_tfs_int8.tflite` (output: 128-d int8 embedding, 3.5 ms on the N6) and
`osnet_a100_256_128_tfs_int8.tflite` (512-d, 13.4 ms). They take a 256x128 person crop and are trained on
basketball players (DeepSportradar), so how well they separate ordinary people is the thing to measure.

## Design notes

- Resize mode defaults to `fit` (stretch to NxN). That is what ST's evaluation does and what the N6's
  camera pipeline does in hardware, so accuracy numbers match the deployment. `--mode letterbox` exists
  for comparison.
- Latency printed here is the TFLite interpreter on the laptop CPU (XNNPACK). It only shows relative
  cost between model sizes. Board timing comes from ST's table above until we measure on hardware.
- Scores from the int8 models come out in coarse steps (0.24, 0.36, 0.50, 0.64, 0.76, 0.85, 0.92), so
  the operating threshold is chosen from the F1 sweep in `metrics.json`, not assumed to be 0.5. The
  default is 0.25 (keeps scores >= 0.36): on COCO val2017 that is precision 0.88 / recall 0.42 for the
  256 model, versus 0.97 / 0.27 at 0.5. Thresholds 0.25 and 0.3 behave identically, as do 0.5 and 0.6.
  COCO recall looks low because it counts every tiny background person; people at demo distances are
  the high-score cases.
