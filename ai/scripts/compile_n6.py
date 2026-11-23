"""Compile a TFLite model for the STM32N6 NPU with ST Edge AI Core and file the reports.

    python scripts/compile_n6.py                                  # analyze + generate the default YOLOv8n 256
    python scripts/compile_n6.py --model models/osnet_a025_256_128_tfs_int8.tflite --action analyze
    python scripts/compile_n6.py --neural-art default@path/to/user_neuralart.json

Generated code goes to outputs/n6/<model>/ (git-ignored); the text reports and logs go to results/n6/<model>/.
Install ST Edge AI Core first (see README, "Week 6 board half"); set STEDGEAI_HOME if it is not in C:/ST/STEdgeAI.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd_ai import stedgeai  # noqa: E402
from herd_ai.models import DEFAULT_MODEL, model_path  # noqa: E402
from herd_ai.paths import OUTPUTS_DIR, RESULTS_DIR  # noqa: E402

INSTALL_HINT = (
    "ST Edge AI Core was not found. Install it from https://www.st.com/en/development-tools/stedgeai-core.html\n"
    "(the online installer needs a myST login and does not work from UCI-WiFi; use another network), or point\n"
    "STEDGEAI_HOME at the install folder, e.g. C:/ST/STEdgeAI/4.1"
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, default=model_path(DEFAULT_MODEL.filename))
    ap.add_argument("--action", choices=["analyze", "generate", "validate", "both"], default="both",
                    help="both = analyze then generate (default)")
    ap.add_argument("--neural-art", default=None, help="profile@config.json for --st-neural-art (default: tool default)")
    ap.add_argument("--stedgeai", type=Path, default=None, help="path to stedgeai.exe (default: auto-detect)")
    ap.add_argument("--out", type=Path, default=None, help="work dir (default outputs/n6/<model>)")
    ap.add_argument("--results", type=Path, default=RESULTS_DIR / "n6")
    ap.add_argument("extra", nargs="*", help="extra stedgeai options, after --")
    args = ap.parse_args(argv)

    exe = args.stedgeai or stedgeai.find_stedgeai()
    if exe is None or not Path(exe).exists():
        print(INSTALL_HINT, file=sys.stderr)
        return 2
    if not args.model.exists():
        print(f"model not found: {args.model} (run scripts/download_models.py)", file=sys.stderr)
        return 2
    print(f"compiler: {exe}\n{stedgeai.version(exe)}\nmodel:    {args.model}")

    work = args.out or OUTPUTS_DIR / "n6" / args.model.stem
    actions = ["analyze", "generate"] if args.action == "both" else [args.action]
    for action in actions:
        print(f"\n== {action} ==")
        res = stedgeai.run(exe, action, args.model, work, results_dir=args.results, neural_art=args.neural_art, extra=args.extra)
        print(f"exit {res.returncode}; log {res.log_path}")
        for r in res.reports:
            print(f"report {r}")
        if res.returncode != 0:
            print(res.stdout[-3000:], file=sys.stderr)
            print(res.stderr[-3000:], file=sys.stderr)
            return res.returncode
        if action == "analyze" and res.reports:
            text = res.reports[0].read_text(encoding="utf-8", errors="replace")
            keep = [ln for ln in text.splitlines() if any(k in ln.lower() for k in ("inference", "ram", "flash", "cycles", "macc", "epoch"))]
            print("\n".join(keep[:20]))
    print(f"\ngenerated files: {work}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
