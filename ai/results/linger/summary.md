# Week 8: the lingering rule on labeled video

Date: 2026-11-23. Detector yolov8n_256_quant_pc_uf_od_coco-person.tflite, tracker match 200 / drop 1000 ms.
A labeled stay is the rule applied to the labeled tracks with perfect ids. A hit is a pipeline report pointing at
a person who really had been standing for the rule's time (within 1 s); a repeat is a second report of
the same stay after an id switch. False alarms are split into ghost (no labeled person within 150/1000 of the
report), group there (people occupied that spot for at least 90% of the time, just not one labeled id), and too
early (someone there, standing less than that). A miss is a labeled stay with no report within 5 s.

## Default setting: radius 120, time 8 s

| sequence | setting | labeled stays | hits | repeats | ghost | group there | too early | missed | delay median / max |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| PETS09-S2L1 (114 s at 7 fps) | as merged | 9 | 5 | 0 | 2 | 8 | 0 | 6 (5 restarted, 0 never seen) | 2.0 s / 10.7 s |
| TUD-Stadtmitte (7 s at 25 fps) | as merged | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus (3 s at 25 fps) | as merged | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| ADL-Rundle-6 (18 s at 30 fps) | as merged | 1 | 0 | 0 | 0 | 0 | 0 | 1 (1 restarted, 0 never seen) | - |

## Guards at the default setting

| sequence | setting | labeled stays | hits | repeats | ghost | group there | too early | missed | delay median / max |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| PETS09-S2L1 | as merged | 9 | 5 | 0 | 2 | 8 | 0 | 6 (5 restarted, 0 never seen) | 2.0 s / 10.7 s |
| PETS09-S2L1 | drop 2000 ms | 9 | 6 | 0 | 1 | 7 | 2 | 5 (4 restarted, 0 never seen) | 2.4 s / 10.7 s |
| PETS09-S2L1 | drop 3000 ms | 9 | 5 | 0 | 2 | 6 | 4 | 5 (4 restarted, 0 never seen) | 3.0 s / 10.7 s |
| PETS09-S2L1 | require motion | 9 | 2 | 0 | 2 | 6 | 0 | 7 (6 restarted, 0 never seen) | 0.2 s / 0.4 s |
| PETS09-S2L1 | score >= 40 | 9 | 4 | 0 | 1 | 7 | 0 | 7 (6 restarted, 0 never seen) | 5.6 s / 10.7 s |
| PETS09-S2L1 | score >= 50 | 9 | 4 | 0 | 1 | 7 | 0 | 7 (6 restarted, 0 never seen) | 5.6 s / 10.7 s |
| PETS09-S2L1 | motion + score >= 40 | 9 | 1 | 0 | 1 | 5 | 0 | 8 (7 restarted, 0 never seen) | 0.4 s / 0.4 s |
| PETS09-S2L1 | motion + score >= 40 + drop 2000 | 9 | 4 | 0 | 1 | 6 | 1 | 5 (4 restarted, 0 never seen) | -0.1 s / 4.9 s |
| TUD-Stadtmitte | as merged | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Stadtmitte | drop 2000 ms | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Stadtmitte | drop 3000 ms | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Stadtmitte | require motion | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Stadtmitte | score >= 40 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Stadtmitte | score >= 50 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Stadtmitte | motion + score >= 40 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Stadtmitte | motion + score >= 40 + drop 2000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | as merged | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | drop 2000 ms | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | drop 3000 ms | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | require motion | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | score >= 40 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | score >= 50 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | motion + score >= 40 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | motion + score >= 40 + drop 2000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| ADL-Rundle-6 | as merged | 1 | 0 | 0 | 0 | 0 | 0 | 1 (1 restarted, 0 never seen) | - |
| ADL-Rundle-6 | drop 2000 ms | 1 | 0 | 0 | 0 | 0 | 0 | 1 (1 restarted, 0 never seen) | - |
| ADL-Rundle-6 | drop 3000 ms | 1 | 0 | 0 | 0 | 0 | 0 | 1 (1 restarted, 0 never seen) | - |
| ADL-Rundle-6 | require motion | 1 | 0 | 0 | 0 | 0 | 0 | 1 (1 restarted, 0 never seen) | - |
| ADL-Rundle-6 | score >= 40 | 1 | 0 | 0 | 0 | 0 | 0 | 1 (1 restarted, 0 never seen) | - |
| ADL-Rundle-6 | score >= 50 | 1 | 0 | 0 | 0 | 0 | 0 | 1 (1 restarted, 0 never seen) | - |
| ADL-Rundle-6 | motion + score >= 40 | 1 | 0 | 0 | 0 | 0 | 0 | 1 (1 restarted, 0 never seen) | - |
| ADL-Rundle-6 | motion + score >= 40 + drop 2000 | 1 | 0 | 0 | 0 | 0 | 0 | 1 (1 restarted, 0 never seen) | - |

## Radius x time sweep (as merged)

| sequence | setting | labeled stays | hits | repeats | ghost | group there | too early | missed | delay median / max |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| PETS09-S2L1 | radius 80, 4 s | 23 | 16 | 4 | 2 | 13 | 0 | 9 (6 restarted, 0 never seen) | 0.0 s / 6.4 s |
| PETS09-S2L1 | radius 80, 6 s | 12 | 7 | 2 | 1 | 8 | 0 | 6 (6 restarted, 0 never seen) | 0.0 s / 6.4 s |
| PETS09-S2L1 | radius 80, 8 s | 5 | 2 | 0 | 1 | 1 | 0 | 4 (4 restarted, 0 never seen) | 2.7 s / 6.4 s |
| PETS09-S2L1 | radius 80, 10 s | 3 | 1 | 1 | 1 | 0 | 0 | 3 (3 restarted, 0 never seen) | 6.4 s / 6.4 s |
| PETS09-S2L1 | radius 120, 4 s | 37 | 23 | 6 | 4 | 20 | 1 | 15 (8 restarted, 0 never seen) | 0.0 s / 6.6 s |
| PETS09-S2L1 | radius 120, 6 s | 16 | 11 | 3 | 0 | 9 | 0 | 7 (6 restarted, 0 never seen) | 0.4 s / 6.6 s |
| PETS09-S2L1 | radius 120, 8 s | 9 | 5 | 0 | 2 | 8 | 0 | 6 (5 restarted, 0 never seen) | 2.0 s / 10.7 s |
| PETS09-S2L1 | radius 120, 10 s | 6 | 2 | 0 | 1 | 3 | 0 | 5 (5 restarted, 0 never seen) | 4.9 s / 9.3 s |
| PETS09-S2L1 | radius 160, 4 s | 48 | 28 | 5 | 4 | 23 | 0 | 19 (13 restarted, 0 never seen) | 0.3 s / 7.1 s |
| PETS09-S2L1 | radius 160, 6 s | 25 | 17 | 3 | 1 | 13 | 0 | 10 (8 restarted, 0 never seen) | 0.3 s / 7.1 s |
| PETS09-S2L1 | radius 160, 8 s | 18 | 9 | 1 | 3 | 8 | 1 | 12 (12 restarted, 0 never seen) | -0.3 s / 8.7 s |
| PETS09-S2L1 | radius 160, 10 s | 10 | 4 | 0 | 2 | 7 | 1 | 8 (8 restarted, 0 never seen) | 2.0 s / 7.1 s |
| PETS09-S2L1 | radius 200, 4 s | 56 | 29 | 9 | 5 | 18 | 5 | 29 (16 restarted, 0 never seen) | -0.3 s / 12.1 s |
| PETS09-S2L1 | radius 200, 6 s | 34 | 18 | 8 | 1 | 11 | 3 | 16 (9 restarted, 0 never seen) | 0.1 s / 4.7 s |
| PETS09-S2L1 | radius 200, 8 s | 20 | 9 | 3 | 1 | 8 | 3 | 13 (11 restarted, 0 never seen) | 0.2 s / 12.3 s |
| PETS09-S2L1 | radius 200, 10 s | 15 | 2 | 0 | 1 | 8 | 5 | 14 (13 restarted, 0 never seen) | 7.1 s / 12.1 s |
| TUD-Stadtmitte | radius 80, 4 s | 2 | 1 | 0 | 0 | 0 | 0 | 1 (1 restarted, 0 never seen) | 0.1 s / 0.1 s |
| TUD-Stadtmitte | radius 80, 6 s | 1 | 1 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | 0.1 s / 0.1 s |
| TUD-Stadtmitte | radius 80, 8 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Stadtmitte | radius 80, 10 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Stadtmitte | radius 120, 4 s | 2 | 1 | 0 | 0 | 0 | 0 | 1 (1 restarted, 0 never seen) | 0.1 s / 0.1 s |
| TUD-Stadtmitte | radius 120, 6 s | 1 | 1 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | 0.1 s / 0.1 s |
| TUD-Stadtmitte | radius 120, 8 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Stadtmitte | radius 120, 10 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Stadtmitte | radius 160, 4 s | 3 | 1 | 0 | 0 | 0 | 0 | 2 (2 restarted, 0 never seen) | 0.1 s / 0.1 s |
| TUD-Stadtmitte | radius 160, 6 s | 1 | 1 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | 0.1 s / 0.1 s |
| TUD-Stadtmitte | radius 160, 8 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Stadtmitte | radius 160, 10 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Stadtmitte | radius 200, 4 s | 3 | 1 | 0 | 0 | 0 | 0 | 2 (2 restarted, 0 never seen) | 0.1 s / 0.1 s |
| TUD-Stadtmitte | radius 200, 6 s | 2 | 1 | 0 | 0 | 0 | 0 | 1 (1 restarted, 0 never seen) | 0.1 s / 0.1 s |
| TUD-Stadtmitte | radius 200, 8 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Stadtmitte | radius 200, 10 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 80, 4 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 80, 6 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 80, 8 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 80, 10 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 120, 4 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 120, 6 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 120, 8 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 120, 10 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 160, 4 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 160, 6 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 160, 8 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 160, 10 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 200, 4 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 200, 6 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 200, 8 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| TUD-Campus | radius 200, 10 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 80, 4 s | 3 | 0 | 0 | 1 | 2 | 0 | 3 (3 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 80, 6 s | 2 | 0 | 0 | 0 | 0 | 0 | 2 (2 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 80, 8 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 80, 10 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 120, 4 s | 4 | 1 | 0 | 1 | 3 | 0 | 4 (4 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 120, 6 s | 2 | 0 | 0 | 0 | 1 | 0 | 2 (2 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 120, 8 s | 1 | 0 | 0 | 0 | 0 | 0 | 1 (1 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 120, 10 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 160, 4 s | 7 | 0 | 0 | 1 | 5 | 0 | 7 (7 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 160, 6 s | 3 | 0 | 0 | 0 | 2 | 0 | 3 (3 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 160, 8 s | 2 | 0 | 0 | 0 | 0 | 0 | 2 (2 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 160, 10 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 200, 4 s | 9 | 1 | 0 | 1 | 6 | 0 | 8 (8 restarted, 0 never seen) | -0.8 s / -0.8 s |
| ADL-Rundle-6 | radius 200, 6 s | 4 | 0 | 0 | 0 | 3 | 1 | 4 (4 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 200, 8 s | 2 | 0 | 0 | 0 | 1 | 0 | 2 (2 restarted, 0 never seen) | - |
| ADL-Rundle-6 | radius 200, 10 s | 1 | 0 | 0 | 0 | 0 | 0 | 1 (1 restarted, 0 never seen) | - |
