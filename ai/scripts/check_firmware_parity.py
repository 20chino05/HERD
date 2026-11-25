"""Replay every MOT15 ground-truth stream through the firmware's C (tracker.c + behavior.c) and the
Python mirrors, and record whether they agree frame for frame.

    python scripts/check_firmware_parity.py            # all four sequences -> results/firmware_parity.md

Needs a C compiler (MSYS2's gcc at C:/msys64/ucrt64/bin, or gcc on PATH).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd_ai import parity  # noqa: E402
from herd_ai.mot import load_mot_gt, load_seqinfo  # noqa: E402
from herd_ai.paths import DATA_DIR, OUTPUTS_DIR, RESULTS_DIR  # noqa: E402

MOT = DATA_DIR / "mot15" / "MOT15Labels" / "train"
SEQS = ["PETS09-S2L1", "TUD-Stadtmitte", "TUD-Campus", "ADL-Rundle-6"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seqs", nargs="*", default=SEQS)
    ap.add_argument("--out", type=Path, default=RESULTS_DIR / "firmware_parity.md")
    args = ap.parse_args(argv)

    gcc = parity.find_gcc()
    if gcc is None:
        print("no C compiler found (install MSYS2 or put gcc on PATH)", file=sys.stderr)
        return 2
    exe = parity.build_trace_tool(OUTPUTS_DIR / "parity", gcc)
    gcc_version = subprocess.run([str(gcc), "--version"], capture_output=True, text=True).stdout.splitlines()[0]

    rows = []
    for seq in args.seqs:
        info = load_seqinfo(MOT / seq / "seqinfo.ini")
        gt = load_mot_gt(MOT / seq / "gt" / "gt.txt")
        stream = parity.gt_to_trace(gt, info["width"], info["height"], info["frame_rate"])
        res = parity.compare(exe, stream)
        n_boxes = sum(len(d) for _, d in stream)
        rows.append((seq, info["frame_rate"], res["frames"], n_boxes, res["linger_reports"], len(res["mismatches"]), res["identical"]))
        print(f"{seq}: {res['frames']} frames, {n_boxes} boxes, {res['linger_reports']} lingering reports, "
              f"{len(res['mismatches'])} mismatches -> {'identical' if res['identical'] else 'DIFFERENT'}")
        for i, c, p in res["mismatches"][:3]:
            print(f"  frame {i}:\n    C : {c}\n    Py: {p}")

    lines = [
        "# Firmware parity: C vs Python mirrors",
        "",
        f"Date: {date.today().isoformat()}. Compiler: {gcc_version}.",
        "",
        "The MOT15 ground-truth boxes (ids dropped, at most 8 per frame, thousandths of the frame) were replayed",
        "through `firmware/stm32/App/tracker.c` + `behavior.c` (built into `firmware/tests/trace_main.c`) and through",
        "`ai/herd_ai/tracker.py` + `behavior.py`. Each frame's line lists the lingering report and every active track's",
        "id, position and speed in slot order; the lines must be identical.",
        "",
        "| sequence | fps | frames | boxes | lingering reports | mismatching frames | result |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for seq, fps, n, nb, nl, nm, ok in rows:
        lines.append(f"| {seq} | {fps:g} | {n} | {nb} | {nl} | {nm} | {'identical' if ok else 'DIFFERENT'} |")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0 if all(r[-1] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
