# Firmware parity: C vs Python mirrors

Date: 2026-11-23. Compiler: gcc.exe (Rev8, Built by MSYS2 project) 15.2.0.

The MOT15 ground-truth boxes (ids dropped, at most 8 per frame, thousandths of the frame) were replayed
through `firmware/stm32/App/tracker.c` + `behavior.c` (built into `firmware/tests/trace_main.c`) and through
`ai/herd_ai/tracker.py` + `behavior.py`. Each frame's line lists the lingering report and every active track's
id, position and speed in slot order; the lines must be identical.

| sequence | fps | frames | boxes | lingering reports | mismatching frames | result |
|---|---:|---:|---:|---:|---:|---|
| PETS09-S2L1 | 7 | 795 | 4476 | 8 | 0 | identical |
| TUD-Stadtmitte | 25 | 179 | 1156 | 0 | 0 | identical |
| TUD-Campus | 25 | 71 | 359 | 0 | 0 | identical |
| ADL-Rundle-6 | 30 | 525 | 3982 | 1 | 0 | identical |
