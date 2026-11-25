/*
 * detect.h - people boxes for each camera frame.
 *
 * Owner: Devin. Right now this makes up one person who walks in, lingers,
 * then walks off to the right (USE_FAKE_DETECTIONS in app_config.h).
 * With USE_FAKE_DETECTIONS 0 the frames come from ST's person-detection
 * pipeline: its thread converts the post-processed boxes with
 * detect_boxes_to_frame() and hands the frame in with detect_submit(). The
 * rest of the app only sees frame_t, so nothing else has to change.
 */
#ifndef DETECT_H
#define DETECT_H

#include <stdbool.h>
#include <stdint.h>

#define DETECT_MAX 8

typedef struct {
  int16_t x, y;  /* box center, thousandths of the frame */
  int16_t w, h;  /* box size, thousandths of the frame */
  uint8_t score; /* confidence, percent */
} detection_t;

typedef struct {
  uint32_t time_ms;
  uint8_t count;
  detection_t det[DETECT_MAX];
} frame_t;

void detect_init(void);

/* Where the camera is pointing (tenths of a degree); the fake person uses it. */
void detect_set_camera(int32_t pan_x10, int32_t tilt_x10);

/* Fills *out and returns true when a new frame is ready. */
bool detect_poll(uint32_t now_ms, frame_t *out);

/*
 * ST's post-processing gives boxes as center x, center y, width, height in
 * fractions of the image (0..1) plus a confidence (0..1). This packs the
 * DETECT_MAX most confident ones into *out, clamped to the frame. Returns the
 * number kept. `cxcywh` holds 4 floats per box.
 */
uint8_t detect_boxes_to_frame(uint32_t time_ms, const float *cxcywh, const float *conf, uint8_t count, frame_t *out);

/* Hand in a real frame; detect_poll() returns it once (USE_FAKE_DETECTIONS 0). */
void detect_submit(const frame_t *frame);

#endif /* DETECT_H */
