"""Read COCO instance annotations and keep only the person class."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

PERSON_CATEGORY_ID = 1


@dataclass
class ImageGT:
    image_id: int
    file_name: str
    width: int
    height: int
    boxes: np.ndarray  # (N, 4) xyxy person boxes, iscrowd == 0
    crowd: np.ndarray  # (M, 4) xyxy person regions marked iscrowd == 1 (ignored, not counted)
    coco_url: str = field(default="")

    @property
    def has_person(self) -> bool:
        return self.boxes.shape[0] > 0 or self.crowd.shape[0] > 0


def load_person_gt(path: str | Path) -> dict[int, ImageGT]:
    """Load an ``instances_*.json`` file into {image_id: ImageGT} with every image present."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    boxes: dict[int, list] = defaultdict(list)
    crowd: dict[int, list] = defaultdict(list)
    for ann in data["annotations"]:
        if ann["category_id"] != PERSON_CATEGORY_ID:
            continue
        x, y, w, h = ann["bbox"]
        target = crowd if ann.get("iscrowd", 0) else boxes
        target[ann["image_id"]].append([x, y, x + w, y + h])

    out: dict[int, ImageGT] = {}
    for im in data["images"]:
        iid = im["id"]
        out[iid] = ImageGT(
            image_id=iid,
            file_name=im["file_name"],
            width=im["width"],
            height=im["height"],
            boxes=np.array(boxes.get(iid, []), dtype=np.float64).reshape(-1, 4),
            crowd=np.array(crowd.get(iid, []), dtype=np.float64).reshape(-1, 4),
            coco_url=im.get("coco_url", ""),
        )
    return out


def select_images(
    gts: dict[int, ImageGT],
    n_with_person: int | None = None,
    n_without: int | None = None,
    seed: int = 0,
) -> list[int]:
    """Pick a reproducible subset: images with people first, then images without. None means all."""
    with_person = sorted(i for i, g in gts.items() if g.has_person)
    without = sorted(i for i, g in gts.items() if not g.has_person)
    rng = random.Random(seed)
    rng.shuffle(with_person)
    rng.shuffle(without)
    if n_with_person is not None:
        with_person = with_person[:n_with_person]
    if n_without is not None:
        without = without[:n_without]
    return with_person + without
