# Open Herd AI (laptop side)

Devin's half of the software: get ST's ready-made person detector running and measured on a laptop
first (Fall weeks 4 and 5), then person re-identification and tracking (weeks 6 and 7), then lingering
detection and camera following on top of it. Everything here runs on a plain Windows/macOS/Linux
laptop with no GPU and no board.

## What is here

| Path | Purpose |
|---|---|
| `herd_ai/` | Small Python package: image preprocessing, YOLOv8 output decoding + NMS, detection metrics, COCO loading, a `PersonDetector` wrapper around the TFLite runtime; `reid.py` / `reid_metrics.py` (OSNet embeddings and the Market-1501 protocol); `tracker.py` (the firmware tracker in Python); `mot.py` (MOTChallenge ground truth and the tracking scorecard). |
| `scripts/download_models.py` | Fetches ST's pretrained person models (int8 TFLite) into `models/`. |
| `scripts/run_detection.py` | **Week 4.** Runs a model on photos (or the webcam) and saves annotated images + `detections.json`. |
| `scripts/evaluate.py` | **Week 5.** Scores a model against COCO val2017 person labels; writes `metrics.json`, a PR curve and `results/summary.md`. |
| `scripts/evaluate_reid.py` | **Week 6.** Scores ST's re-identification models on Market-1501 (6 cameras); writes `results/reid/`. |
| `scripts/track_sequence.py` | **Week 7.** Detector + tracker on a video (or the webcam), scored against MOT15 ground truth; writes `results/tracking/`. |
| `samples/` | Seven COCO photos used as the Week 4 test inputs (see `samples/NOTICE.md` for licenses). |
| `results/` | Committed outputs: Week 4 annotated samples, Week 5 detection metrics, Week 6 re-ID metrics, Week 7 tracking metrics. |
| `tests/` | pytest suite. Unit tests for the math, plus end-to-end checks that run the real models on the real downloads when they are present. |
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

For the Week 6 re-identification check, Market-1501 (153 MB; research use, cite Zheng et al. ICCV 2015):

```powershell
mkdir data\market1501; cd data\market1501
curl -L -o Market-1501-v15.09.15.zip http://apache-mxnet.s3-accelerate.dualstack.amazonaws.com/gluon/dataset/Market-1501-v15.09.15.zip
python -m zipfile -e Market-1501-v15.09.15.zip .
cd ..\..
```

For the Week 7 tracking check, the MOT15 labels (1.5 MB) and the static-camera sequences as video
(about 40 MB; CC BY-NC-SA 3.0, motchallenge.net):

```powershell
mkdir data\mot15; cd data\mot15
curl -L -o MOT15Labels.zip https://motchallenge.net/data/MOT15Labels.zip
python -m zipfile -e MOT15Labels.zip .
foreach ($s in "PETS09-S2L1","TUD-Stadtmitte","TUD-Campus","ADL-Rundle-6") { curl -L -o "$s-raw.mp4" "https://motchallenge.net/sequenceVideos/$s-raw.mp4" }
cd ..\..
```

The frame counts of these videos match the labels (checked: 795 / 179 / 71 / 525). ADL-Rundle-6 is served
at half resolution; the scripts scale the ground truth from `seqinfo.ini` automatically.

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

## Week 6: can the next camera recognize the same person?

```powershell
python scripts/evaluate_reid.py --max-query 300 --max-gallery 3000      # quick (~1 min)
python scripts/evaluate_reid.py --models "models/osnet_*.tflite"        # full: 3,368 queries vs 19,732 gallery crops
```

Each Market-1501 crop goes through ST's OSNet model, and the embeddings are compared by cosine
distance. The script reports the standard rank-1 / rank-5 / mAP (comparable to published re-ID
numbers), how far apart same-person and different-person pairs are across cameras, the distance
threshold that keeps false "same person" decisions under 1 % and 5 %, and how often the right person is
the nearest one when 2, 3 or 5 people walk into the next camera together. See `results/reid/summary.md`.

## Week 7: tracking on video

```powershell
python scripts/track_sequence.py --video data/mot15/PETS09-S2L1-raw.mp4 --gt data/mot15/MOT15Labels/train/PETS09-S2L1
python scripts/track_sequence.py --video ... --gt ... --tracker iou --predict --save-video
python scripts/track_sequence.py --webcam                              # live ids, press q to quit
```

`herd_ai/tracker.py` is the firmware tracker (`firmware/stm32/App/tracker.c`) in Python: boxes in
thousandths of the frame, nearest center within `--match-dist` (TRACK_MATCH_DIST, 200), drop after
`--drop-ms` (TRACK_DROP_MS, 1000), at most `--max-tracks` (TRACK_MAX, 8) people. `--predict` and
`--tracker iou` are the two candidate improvements. With `--gt` the run is scored against the MOT15
labels: recall, precision, id switches and MOTA, split by how many people were in the frame (1-2, 3-4,
5+), next to ms per frame for the same bins. See `results/tracking/summary.md`.

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

The download script also fetches ST's two person re-identification models from model zoo v4.0,
`osnet_a025_256_128_tfs_int8.tflite` (output: 128-d int8 embedding, 7.2 ms and 928 KiB on the N6570-DK)
and `osnet_a100_256_128_tfs_int8.tflite` (512-d, 71.3 ms, 2.6 MB internal + 2 MB external RAM). They
take a 256x128 uint8 RGB person crop (ST trains with nearest-neighbour resizing, which `reid.py` copies)
and are trained on 486 basketball players (DeepSportradar). Week 6 measured how well they separate
ordinary pedestrians; see `results/reid/summary.md`.

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
- Re-ID embeddings are dequantized (int8, scale and zero point from the model) and L2-normalized, so
  "same person" is a cosine-distance threshold. The embedding is 128 bytes for OSNet 0.25, which does
  not fit the 32-byte payload in `firmware/common/herd_msg.h`; see the week 6/7 write-up.
- If the TFLite runtime import fails with "An Application Control policy has blocked this file", that is
  Windows Smart App Control refusing the unsigned `ai_edge_litert\_pywrap_litert_interpreter_wrapper.pyd`.
  It is intermittent on this laptop (the cloud reputation check sometimes times out); simply re-running
  the command has worked every time so far.
