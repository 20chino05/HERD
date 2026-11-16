# Detector + tracker on MOT15 sequences (laptop)

Generated 2026-11-15 22:05 by scripts/track_sequence.py. MOTA = 1 - (misses + false alarms + id switches) / people;
a match is IoU >= 0.5. 'det recall' is the detector alone (no ids), so the gap to 'recall' is the tracker's. ms/frame is this
laptop's CPU (detector + tracker), only useful relative to other rows.

| run | frames | people max | det recall / precision | recall | precision | id switches | MOTA | mostly tracked | ms/frame 1-2 / 3-4 / 5+ people |
|---|---|---|---|---|---|---|---|---|---|
| ADL-Rundle-6__256__centroid100_drop1000 | 525 | 13 | 0.48 / 0.88 | 0.45 | 0.89 | 96 | 0.38 | 4 / 24 | - / 14.4 / 24.4 |
| ADL-Rundle-6__256__centroid200_drop1000 | 525 | 13 | 0.48 / 0.88 | 0.47 | 0.89 | 106 | 0.39 | 4 / 24 | - / 8.1 / 27.7 |
| ADL-Rundle-6__256__centroid200_drop1000_pred | 525 | 13 | 0.48 / 0.88 | 0.42 | 0.89 | 146 | 0.33 | 3 / 24 | - / 13.1 / 22.8 |
| ADL-Rundle-6__256__centroid200_drop2000 | 525 | 13 | 0.48 / 0.88 | 0.46 | 0.90 | 109 | 0.39 | 3 / 24 | - / 12.0 / 23.9 |
| ADL-Rundle-6__256__centroid200_drop500 | 525 | 13 | 0.48 / 0.88 | 0.48 | 0.89 | 113 | 0.39 | 4 / 24 | - / 10.8 / 22.3 |
| ADL-Rundle-6__256__centroid300_drop1000 | 525 | 13 | 0.48 / 0.88 | 0.48 | 0.89 | 117 | 0.40 | 4 / 24 | - / 11.0 / 24.2 |
| ADL-Rundle-6__256__iou30_drop1000 | 525 | 13 | 0.48 / 0.88 | 0.44 | 0.89 | 59 | 0.37 | 4 / 24 | - / 13.7 / 23.3 |
| ADL-Rundle-6__320__centroid200_drop1000 | 525 | 13 | 0.51 / 0.84 | 0.50 | 0.88 | 126 | 0.41 | 4 / 24 | - / 17.9 / 37.8 |
| PETS09-S2L1__256__centroid100_drop1000 | 795 | 8 | 0.84 / 0.88 | 0.84 | 0.88 | 86 | 0.70 | 14 / 19 | 31.6 / 32.8 / 30.1 |
| PETS09-S2L1__256__centroid200_drop1000 | 795 | 8 | 0.84 / 0.88 | 0.84 | 0.88 | 99 | 0.70 | 15 / 19 | 24.6 / 32.4 / 31.2 |
| PETS09-S2L1__256__centroid200_drop1000_pred | 795 | 8 | 0.84 / 0.88 | 0.83 | 0.88 | 104 | 0.70 | 14 / 19 | 35.6 / 35.2 / 28.2 |
| PETS09-S2L1__256__centroid200_drop2000 | 795 | 8 | 0.84 / 0.88 | 0.84 | 0.88 | 110 | 0.70 | 14 / 19 | 39.1 / 36.3 / 28.6 |
| PETS09-S2L1__256__centroid200_drop500 | 795 | 8 | 0.84 / 0.88 | 0.84 | 0.88 | 117 | 0.70 | 15 / 19 | 40.2 / 35.9 / 25.7 |
| PETS09-S2L1__256__centroid300_drop1000 | 795 | 8 | 0.84 / 0.88 | 0.84 | 0.88 | 123 | 0.69 | 15 / 19 | 38.2 / 32.5 / 34.1 |
| PETS09-S2L1__256__iou30_drop1000 | 795 | 8 | 0.84 / 0.88 | 0.81 | 0.89 | 139 | 0.67 | 11 / 19 | 25.5 / 28.0 / 29.9 |
| PETS09-S2L1__320__centroid200_drop1000 | 795 | 8 | 0.89 / 0.84 | 0.88 | 0.85 | 106 | 0.69 | 16 / 19 | 38.6 / 38.6 / 39.6 |
| TUD-Campus__256__centroid100_drop1000 | 71 | 6 | 0.75 / 0.87 | 0.74 | 0.87 | 4 | 0.62 | 5 / 8 | - / 15.4 / 8.7 |
| TUD-Campus__256__centroid200_drop1000 | 71 | 6 | 0.75 / 0.87 | 0.75 | 0.87 | 5 | 0.63 | 5 / 8 | - / 8.0 / 10.1 |
| TUD-Campus__256__centroid200_drop1000_pred | 71 | 6 | 0.75 / 0.87 | 0.75 | 0.87 | 5 | 0.63 | 5 / 8 | - / 8.3 / 8.8 |
| TUD-Campus__256__centroid200_drop2000 | 71 | 6 | 0.75 / 0.87 | 0.75 | 0.87 | 5 | 0.63 | 5 / 8 | - / 9.7 / 11.5 |
| TUD-Campus__256__centroid200_drop500 | 71 | 6 | 0.75 / 0.87 | 0.75 | 0.87 | 5 | 0.63 | 5 / 8 | - / 12.4 / 11.9 |
| TUD-Campus__256__centroid300_drop1000 | 71 | 6 | 0.75 / 0.87 | 0.75 | 0.87 | 4 | 0.63 | 5 / 8 | - / 13.0 / 9.7 |
| TUD-Campus__256__iou30_drop1000 | 71 | 6 | 0.75 / 0.87 | 0.70 | 0.89 | 6 | 0.59 | 3 / 8 | - / 10.4 / 8.4 |
| TUD-Stadtmitte__256__centroid100_drop1000 | 179 | 8 | 0.81 / 0.98 | 0.80 | 0.98 | 12 | 0.77 | 8 / 10 | - / - / 8.0 |
| TUD-Stadtmitte__256__centroid200_drop1000 | 179 | 8 | 0.81 / 0.98 | 0.81 | 0.98 | 10 | 0.78 | 8 / 10 | - / - / 8.5 |
| TUD-Stadtmitte__256__centroid200_drop1000_pred | 179 | 8 | 0.81 / 0.98 | 0.81 | 0.98 | 11 | 0.78 | 8 / 10 | - / - / 8.7 |
| TUD-Stadtmitte__256__centroid200_drop2000 | 179 | 8 | 0.81 / 0.98 | 0.81 | 0.98 | 14 | 0.77 | 8 / 10 | - / - / 8.8 |
| TUD-Stadtmitte__256__centroid200_drop500 | 179 | 8 | 0.81 / 0.98 | 0.81 | 0.98 | 11 | 0.78 | 8 / 10 | - / - / 9.3 |
| TUD-Stadtmitte__256__centroid300_drop1000 | 179 | 8 | 0.81 / 0.98 | 0.81 | 0.98 | 11 | 0.78 | 8 / 10 | - / - / 7.8 |
| TUD-Stadtmitte__256__iou30_drop1000 | 179 | 8 | 0.81 / 0.98 | 0.79 | 0.98 | 14 | 0.76 | 8 / 10 | - / - / 7.5 |
