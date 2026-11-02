"""Where things live inside the ai/ folder. Everything is relative to this package's parent."""

from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = AI_ROOT / "models"
DATA_DIR = AI_ROOT / "data"
COCO_DIR = DATA_DIR / "coco"
ANNOTATIONS_FILE = COCO_DIR / "annotations" / "instances_val2017.json"
IMAGES_DIR = COCO_DIR / "val2017"
SAMPLES_DIR = AI_ROOT / "samples"
OUTPUTS_DIR = AI_ROOT / "outputs"
RESULTS_DIR = AI_ROOT / "results"
