# Person detection on COCO val2017 (laptop run)

Generated 2026-11-02 10:47. AP@0.5 uses ST's settings (NMS 0.5, score 0.001, max 100 dets).
Laptop times are LiteRT on CPU and only indicate relative cost; the board column is ST's published NPU time.

| model | input | images | GT boxes | AP50 ours | AP50 pycocotools | AP50 ST published | P / R / F1 @0.5 | best F1 (thr) | laptop invoke ms mean / p95 | ST N6 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| yolov8n_192_quant_pc_uf_od_coco-person | 192 | 5000 | 10777 | 0.507 | 0.500 | 0.536 | 0.93 / 0.30 / 0.45 | 0.55 (0.1) | 4.8 / 8.6 | 16.3 |
| yolov8n_256_quant_pc_uf_od_coco-person | 256 | 5000 | 10777 | 0.577 | 0.570 | 0.584 | 0.97 / 0.27 / 0.42 | 0.60 (0.1) | 7.7 / 12.4 | 23.8 |
| yolov8n_320_quant_pc_uf_od_coco-person | 320 | 5000 | 10777 | 0.623 | 0.616 | 0.619 | 0.92 / 0.41 / 0.56 | 0.63 (0.2) | 11.8 / 18.1 | 29.9 |
| yolov8n_416_quant_pc_uf_od_coco-person | 416 | 5000 | 10777 | 0.667 | 0.660 | 0.648 | 0.93 / 0.41 / 0.57 | 0.66 (0.2) | 26.8 / 48.1 | 54.7 |
