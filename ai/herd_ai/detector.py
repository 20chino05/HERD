"""Run an ST person-detection TFLite model on the laptop with LiteRT (the TFLite runtime)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import numpy as np
from ai_edge_litert.interpreter import Interpreter

from herd_ai.postprocess import boxes_to_pixels, decode_yolov8, nms
from herd_ai.preprocess import prepare_input


@dataclass
class Detections:
    boxes: np.ndarray  # (K, 4) x1, y1, x2, y2 in original-image pixels
    scores: np.ndarray  # (K,)
    latency_ms: float  # interpreter invoke only (the part the NPU would do on the board)
    total_ms: float  # preprocess + invoke + postprocess

    def __len__(self) -> int:
        return int(self.boxes.shape[0])


class PersonDetector:
    """Wraps one of ST's ``yolov8n_*_quant_pc_uf_od_coco-person.tflite`` models.

    Defaults match the board-side post-processing: NMS IoU 0.5, at most 100 boxes. ``score_thresh``
    defaults to 0.25, the operating point chosen from the COCO val2017 sweep (precision 0.88 / recall 0.42
    for the 256 model; 0.5 would keep only 27 % of people). Evaluation uses 0.001 so the whole
    precision/recall curve is visible.
    """

    def __init__(
        self,
        model_path: str | Path,
        score_thresh: float = 0.25,
        iou_thresh: float = 0.5,
        max_det: int = 100,
        mode: str = "fit",
        num_threads: int | None = None,
        warmup: bool = True,
    ):
        self.path = Path(model_path)
        self.name = self.path.stem
        self.score_thresh = score_thresh
        self.iou_thresh = iou_thresh
        self.max_det = max_det
        self.mode = mode

        kwargs = {"num_threads": num_threads} if num_threads else {}
        self._interp = Interpreter(model_path=str(self.path), **kwargs)
        self._interp.allocate_tensors()

        inp = self._interp.get_input_details()[0]
        outs = self._interp.get_output_details()
        if inp["dtype"] != np.uint8 or len(inp["shape"]) != 4 or inp["shape"][3] != 3:
            raise ValueError(f"expected a (1, N, N, 3) uint8 input, got {inp['shape']} {inp['dtype']}")
        if len(outs) != 1 or len(outs[0]["shape"]) != 3 or outs[0]["shape"][1] != 5:
            raise NotImplementedError(
                "only ST YOLOv8n person models with a single (1, 5, F) output are supported; "
                f"this model has outputs {[tuple(o['shape']) for o in outs]}"
            )
        self.input_size = int(inp["shape"][1])
        self._in_index = inp["index"]
        self._out_index = outs[0]["index"]

        if warmup:
            self.detect(np.zeros((self.input_size, self.input_size, 3), dtype=np.uint8))

    def detect(self, img_rgb: np.ndarray) -> Detections:
        t0 = perf_counter()
        tensor, meta = prepare_input(img_rgb, self.input_size, self.mode)
        self._interp.set_tensor(self._in_index, tensor)
        t1 = perf_counter()
        self._interp.invoke()
        t2 = perf_counter()
        raw = self._interp.get_tensor(self._out_index)
        boxes_norm, scores = decode_yolov8(raw, self.score_thresh)
        keep = nms(boxes_norm, scores, self.iou_thresh, self.max_det)
        boxes = boxes_to_pixels(boxes_norm[keep], meta)
        t3 = perf_counter()
        return Detections(boxes, scores[keep], (t2 - t1) * 1000.0, (t3 - t0) * 1000.0)
