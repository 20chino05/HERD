# Week 9: following with the servos, simulated on labeled video

Date: 2026-11-23. The camera sees half the frame width (60 deg), pans at most to the frame edges,
runs the follow law from pantilt.c with the firmware tracker, applies each box 30 ms after its frame and
steps the servos every 5 ms. 'centered' = the labeled person within +-150/1000 of the view center;
'lost' = target gone for 1.5 s before reaching a pan limit; 'handoff-ready' = reached the edge of the view at the pan limit
(where unit_fsm.c sends "heading your way"); reversals = pan direction changes per minute of following.

Chosen setting: **gain15_speed60_dead0** (default firmware: gain30_speed120_dead0).

## Fixed camera, firmware default, chosen setting

| sequence | setting | people | frames | centered | in view | mean error (/1000) | lost | handoff-ready | reversals / min |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PETS09-S2L1 | gain0_speed120_dead0 | 18 | 1894 | 34 % | 90 % | 262 | 16 | 0 | 0.0 |
| PETS09-S2L1 | gain30_speed120_dead0 | 18 | 2970 | 69 % | 91 % | 167 | 6 | 6 | 7.2 |
| PETS09-S2L1 | gain15_speed60_dead0 | 18 | 3590 | 65 % | 90 % | 197 | 3 | 4 | 6.7 |
| TUD-Stadtmitte | gain0_speed120_dead0 | 7 | 742 | 18 % | 87 % | 344 | 1 | 0 | 0.0 |
| TUD-Stadtmitte | gain30_speed120_dead0 | 7 | 713 | 51 % | 95 % | 170 | 0 | 3 | 10.6 |
| TUD-Stadtmitte | gain15_speed60_dead0 | 7 | 734 | 63 % | 100 % | 129 | 0 | 2 | 10.3 |
| ADL-Rundle-6 | gain0_speed120_dead0 | 18 | 3062 | 11 % | 68 % | 420 | 11 | 0 | 0.0 |
| ADL-Rundle-6 | gain30_speed120_dead0 | 18 | 3590 | 42 % | 91 % | 238 | 1 | 7 | 11.1 |
| ADL-Rundle-6 | gain15_speed60_dead0 | 18 | 4068 | 49 % | 93 % | 231 | 0 | 8 | 8.0 |
| PETS09-S2L1 | gain15_speed60_dead0 + real detector | 18 | 2055 | 54 % | 87 % | 231 | 12 | 1 | 6.0 |

## Frame rate

| sequence | setting | people | frames | centered | in view | mean error (/1000) | lost | handoff-ready | reversals / min |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TUD-Stadtmitte | gain30_speed120_dead0_10fps | 7 | 318 | 58 % | 91 % | 182 | 2 | 2 | 7.2 |
| ADL-Rundle-6 | gain30_speed120_dead0_10fps | 18 | 1093 | 39 % | 84 % | 275 | 4 | 6 | 7.2 |
| PETS09-S2L1 | gain30_speed120_dead0_5fps | 18 | 2970 | 69 % | 91 % | 167 | 6 | 6 | 7.2 |
| TUD-Stadtmitte | gain30_speed120_dead0_5fps | 7 | 148 | 56 % | 100 % | 141 | 1 | 1 | 8.5 |
| ADL-Rundle-6 | gain30_speed120_dead0_5fps | 18 | 389 | 42 % | 82 % | 312 | 9 | 4 | 3.2 |
| TUD-Stadtmitte | gain15_speed60_dead0_10fps | 7 | 380 | 52 % | 100 % | 149 | 0 | 2 | 10.1 |
| ADL-Rundle-6 | gain15_speed60_dead0_10fps | 18 | 1247 | 36 % | 88 % | 282 | 2 | 9 | 7.8 |
| PETS09-S2L1 | gain15_speed60_dead0_5fps | 18 | 3590 | 65 % | 90 % | 197 | 3 | 4 | 6.7 |
| TUD-Stadtmitte | gain15_speed60_dead0_5fps | 7 | 150 | 46 % | 100 % | 187 | 0 | 1 | 8.4 |
| ADL-Rundle-6 | gain15_speed60_dead0_5fps | 18 | 483 | 28 % | 86 % | 298 | 6 | 4 | 3.9 |

## Full sweep

| sequence | setting | people | frames | centered | in view | mean error (/1000) | lost | handoff-ready | reversals / min |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PETS09-S2L1 | gain15_speed60_dead0 | 18 | 3590 | 65 % | 90 % | 197 | 3 | 4 | 6.7 |
| PETS09-S2L1 | gain15_speed60_dead40 | 18 | 3590 | 65 % | 90 % | 199 | 3 | 4 | 5.6 |
| PETS09-S2L1 | gain15_speed120_dead0 | 18 | 3590 | 65 % | 90 % | 197 | 3 | 4 | 6.7 |
| PETS09-S2L1 | gain15_speed120_dead40 | 18 | 3590 | 65 % | 90 % | 199 | 3 | 4 | 5.6 |
| PETS09-S2L1 | gain15_speed240_dead0 | 18 | 3590 | 65 % | 90 % | 197 | 3 | 4 | 6.7 |
| PETS09-S2L1 | gain15_speed240_dead40 | 18 | 3590 | 65 % | 90 % | 199 | 3 | 4 | 5.6 |
| PETS09-S2L1 | gain30_speed60_dead0 | 18 | 3274 | 64 % | 87 % | 202 | 6 | 6 | 6.7 |
| PETS09-S2L1 | gain30_speed60_dead40 | 18 | 3274 | 64 % | 87 % | 205 | 6 | 6 | 5.8 |
| PETS09-S2L1 | gain30_speed120_dead0 | 18 | 2970 | 69 % | 91 % | 167 | 6 | 6 | 7.2 |
| PETS09-S2L1 | gain30_speed120_dead40 | 18 | 2970 | 70 % | 90 % | 169 | 6 | 6 | 6.0 |
| PETS09-S2L1 | gain30_speed240_dead0 | 18 | 2970 | 69 % | 91 % | 167 | 6 | 6 | 7.2 |
| PETS09-S2L1 | gain30_speed240_dead40 | 18 | 2970 | 70 % | 90 % | 169 | 6 | 6 | 6.0 |
| PETS09-S2L1 | gain50_speed60_dead0 | 18 | 3166 | 65 % | 88 % | 184 | 5 | 7 | 6.6 |
| PETS09-S2L1 | gain50_speed60_dead40 | 18 | 2728 | 64 % | 88 % | 189 | 5 | 6 | 5.3 |
| PETS09-S2L1 | gain50_speed120_dead0 | 18 | 1568 | 53 % | 81 % | 249 | 11 | 4 | 5.4 |
| PETS09-S2L1 | gain50_speed120_dead40 | 18 | 1568 | 60 % | 83 % | 227 | 11 | 4 | 3.6 |
| PETS09-S2L1 | gain50_speed240_dead0 | 18 | 1568 | 53 % | 81 % | 249 | 11 | 4 | 5.4 |
| PETS09-S2L1 | gain50_speed240_dead40 | 18 | 1568 | 60 % | 83 % | 226 | 11 | 4 | 3.6 |
| PETS09-S2L1 | gain80_speed60_dead0 | 18 | 3084 | 65 % | 88 % | 180 | 5 | 7 | 7.2 |
| PETS09-S2L1 | gain80_speed60_dead40 | 18 | 3036 | 67 % | 92 % | 161 | 5 | 5 | 7.1 |
| PETS09-S2L1 | gain80_speed120_dead0 | 18 | 697 | 47 % | 85 % | 249 | 14 | 3 | 3.9 |
| PETS09-S2L1 | gain80_speed120_dead40 | 18 | 697 | 49 % | 83 % | 254 | 14 | 3 | 2.2 |
| PETS09-S2L1 | gain80_speed240_dead0 | 18 | 874 | 39 % | 73 % | 336 | 13 | 3 | 3.6 |
| PETS09-S2L1 | gain80_speed240_dead40 | 18 | 874 | 41 % | 72 % | 341 | 13 | 3 | 2.3 |
| TUD-Stadtmitte | gain15_speed60_dead0 | 7 | 734 | 63 % | 100 % | 129 | 0 | 2 | 10.3 |
| TUD-Stadtmitte | gain15_speed60_dead40 | 7 | 734 | 63 % | 100 % | 134 | 0 | 2 | 6.2 |
| TUD-Stadtmitte | gain15_speed120_dead0 | 7 | 713 | 50 % | 95 % | 180 | 0 | 3 | 10.6 |
| TUD-Stadtmitte | gain15_speed120_dead40 | 7 | 713 | 50 % | 95 % | 183 | 0 | 3 | 4.2 |
| TUD-Stadtmitte | gain15_speed240_dead0 | 7 | 734 | 65 % | 95 % | 150 | 0 | 2 | 14.4 |
| TUD-Stadtmitte | gain15_speed240_dead40 | 7 | 734 | 65 % | 95 % | 155 | 0 | 2 | 6.2 |
| TUD-Stadtmitte | gain30_speed60_dead0 | 7 | 734 | 63 % | 100 % | 119 | 0 | 2 | 12.4 |
| TUD-Stadtmitte | gain30_speed60_dead40 | 7 | 734 | 63 % | 100 % | 127 | 0 | 2 | 6.2 |
| TUD-Stadtmitte | gain30_speed120_dead0 | 7 | 713 | 51 % | 95 % | 170 | 0 | 3 | 10.6 |
| TUD-Stadtmitte | gain30_speed120_dead40 | 7 | 713 | 51 % | 95 % | 175 | 0 | 3 | 4.2 |
| TUD-Stadtmitte | gain30_speed240_dead0 | 7 | 510 | 50 % | 99 % | 187 | 1 | 4 | 6.0 |
| TUD-Stadtmitte | gain30_speed240_dead40 | 7 | 510 | 50 % | 99 % | 187 | 1 | 4 | 3.0 |
| TUD-Stadtmitte | gain50_speed60_dead0 | 7 | 734 | 63 % | 100 % | 115 | 0 | 2 | 14.4 |
| TUD-Stadtmitte | gain50_speed60_dead40 | 7 | 734 | 63 % | 100 % | 125 | 0 | 2 | 8.3 |
| TUD-Stadtmitte | gain50_speed120_dead0 | 7 | 713 | 51 % | 95 % | 167 | 0 | 3 | 12.7 |
| TUD-Stadtmitte | gain50_speed120_dead40 | 7 | 713 | 51 % | 95 % | 174 | 0 | 3 | 8.5 |
| TUD-Stadtmitte | gain50_speed240_dead0 | 7 | 510 | 51 % | 99 % | 185 | 1 | 4 | 6.0 |
| TUD-Stadtmitte | gain50_speed240_dead40 | 7 | 510 | 51 % | 99 % | 188 | 1 | 4 | 3.0 |
| TUD-Stadtmitte | gain80_speed60_dead0 | 7 | 734 | 63 % | 100 % | 113 | 0 | 2 | 14.4 |
| TUD-Stadtmitte | gain80_speed60_dead40 | 7 | 734 | 63 % | 100 % | 122 | 0 | 2 | 8.3 |
| TUD-Stadtmitte | gain80_speed120_dead0 | 7 | 713 | 51 % | 95 % | 167 | 0 | 3 | 14.9 |
| TUD-Stadtmitte | gain80_speed120_dead40 | 7 | 713 | 51 % | 95 % | 175 | 0 | 3 | 6.4 |
| TUD-Stadtmitte | gain80_speed240_dead0 | 7 | 510 | 51 % | 99 % | 183 | 1 | 4 | 11.9 |
| TUD-Stadtmitte | gain80_speed240_dead40 | 7 | 510 | 51 % | 99 % | 187 | 1 | 4 | 8.9 |
| ADL-Rundle-6 | gain15_speed60_dead0 | 18 | 4068 | 49 % | 93 % | 231 | 0 | 8 | 8.0 |
| ADL-Rundle-6 | gain15_speed60_dead40 | 18 | 4068 | 48 % | 94 % | 234 | 0 | 9 | 8.0 |
| ADL-Rundle-6 | gain15_speed120_dead0 | 18 | 4068 | 49 % | 97 % | 203 | 0 | 8 | 7.1 |
| ADL-Rundle-6 | gain15_speed120_dead40 | 18 | 4068 | 47 % | 96 % | 211 | 0 | 8 | 7.1 |
| ADL-Rundle-6 | gain15_speed240_dead0 | 18 | 4068 | 46 % | 92 % | 245 | 0 | 10 | 7.5 |
| ADL-Rundle-6 | gain15_speed240_dead40 | 18 | 4068 | 46 % | 92 % | 245 | 0 | 10 | 7.5 |
| ADL-Rundle-6 | gain30_speed60_dead0 | 18 | 4068 | 50 % | 97 % | 195 | 0 | 10 | 8.4 |
| ADL-Rundle-6 | gain30_speed60_dead40 | 18 | 4068 | 46 % | 90 % | 234 | 0 | 8 | 9.8 |
| ADL-Rundle-6 | gain30_speed120_dead0 | 18 | 3590 | 42 % | 91 % | 238 | 1 | 7 | 11.1 |
| ADL-Rundle-6 | gain30_speed120_dead40 | 18 | 3590 | 46 % | 95 % | 211 | 1 | 8 | 7.5 |
| ADL-Rundle-6 | gain30_speed240_dead0 | 18 | 3271 | 46 % | 89 % | 234 | 5 | 7 | 10.5 |
| ADL-Rundle-6 | gain30_speed240_dead40 | 18 | 3271 | 42 % | 91 % | 242 | 5 | 8 | 7.2 |
| ADL-Rundle-6 | gain50_speed60_dead0 | 18 | 3848 | 49 % | 94 % | 220 | 1 | 9 | 14.5 |
| ADL-Rundle-6 | gain50_speed60_dead40 | 18 | 3849 | 46 % | 89 % | 251 | 1 | 8 | 10.3 |
| ADL-Rundle-6 | gain50_speed120_dead0 | 18 | 3416 | 50 % | 94 % | 201 | 2 | 11 | 14.8 |
| ADL-Rundle-6 | gain50_speed120_dead40 | 18 | 3609 | 45 % | 94 % | 223 | 2 | 10 | 9.5 |
| ADL-Rundle-6 | gain50_speed240_dead0 | 18 | 3187 | 44 % | 90 % | 249 | 4 | 10 | 13.6 |
| ADL-Rundle-6 | gain50_speed240_dead40 | 18 | 2967 | 40 % | 86 % | 267 | 6 | 8 | 9.1 |
| ADL-Rundle-6 | gain80_speed60_dead0 | 18 | 3811 | 47 % | 93 % | 226 | 1 | 8 | 20.8 |
| ADL-Rundle-6 | gain80_speed60_dead40 | 18 | 3811 | 46 % | 94 % | 229 | 1 | 6 | 9.0 |
| ADL-Rundle-6 | gain80_speed120_dead0 | 18 | 3693 | 39 % | 83 % | 299 | 2 | 7 | 29.8 |
| ADL-Rundle-6 | gain80_speed120_dead40 | 18 | 3636 | 43 % | 90 % | 237 | 2 | 9 | 11.9 |
| ADL-Rundle-6 | gain80_speed240_dead0 | 18 | 2939 | 47 % | 93 % | 210 | 6 | 9 | 17.8 |
| ADL-Rundle-6 | gain80_speed240_dead40 | 18 | 2957 | 46 % | 92 % | 210 | 5 | 9 | 10.4 |
