# Re-identification on Market-1501 (laptop)

Generated 2026-11-15 21:59 by scripts/evaluate_reid.py. Standard protocol: for each query, gallery images of the
same person from the same camera are removed; rank-k = true match within the k nearest; mAP over all queries.
ST's own numbers are on DeepSportradar (basketball players), a different and easier set, so they are context, not a target.

| model | queries / gallery | mAP | rank-1 | rank-5 | ST mAP / rank-1 (DeepSportradar) | threshold at 1% false accepts (same-person accepted) | right one of 2 / 3 / 5 | laptop embed, median | ST N6570-DK |
|---|---|---|---|---|---|---|---|---|---|
| osnet_a025_256_128_tfs_int8 | 200 / 2,000 | 0.061 | 0.078 | 0.149 | 0.703 / 0.920 | 0.134 (8.0%) | 74.9% / 62.1% / 45.5% | 12.2 ms | 7.22 ms |
