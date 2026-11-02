"""Download ST's ready-made person-detection models into ai/models/.

    python scripts/download_models.py              # everything in the catalog
    python scripts/download_models.py --only yolov8n_256 yolov8n_320
    python scripts/download_models.py --force      # re-download even if present
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd_ai.models import MODEL_CATALOG  # noqa: E402
from herd_ai.paths import MODELS_DIR  # noqa: E402

TFLITE_MAGIC = b"TFL3"


def download(url: str, dest: Path) -> int:
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as resp, open(tmp, "wb") as f:
        while chunk := resp.read(1 << 16):
            f.write(chunk)
    with open(tmp, "rb") as f:
        head = f.read(8)
    if head[4:8] != TFLITE_MAGIC:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"{url} did not return a TFLite file (got {head!r}); is it a Git LFS pointer?")
    tmp.replace(dest)
    return dest.stat().st_size


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", default=None, help="substrings; download only models whose file name contains one")
    ap.add_argument("--force", action="store_true", help="re-download files that already exist")
    ap.add_argument("--dest", type=Path, default=MODELS_DIR)
    args = ap.parse_args(argv)

    args.dest.mkdir(parents=True, exist_ok=True)
    wanted = [m for m in MODEL_CATALOG if not args.only or any(s in m.filename for s in args.only)]
    if not wanted:
        print(f"no catalog entry matches {args.only}", file=sys.stderr)
        return 2

    for m in wanted:
        dest = args.dest / m.filename
        if dest.exists() and not args.force:
            print(f"already present: {dest.name} ({dest.stat().st_size / 1e6:.2f} MB)")
            continue
        print(f"downloading {m.filename} ...", end=" ", flush=True)
        size = download(m.url, dest)
        print(f"{size / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
