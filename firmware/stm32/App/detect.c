/* detect.c - fake detections for now, plus the glue for the real ones (see detect.h). */
#include "detect.h"

#include <string.h>

#include "app_config.h"

#define FRAME_PERIOD_MS 100u /* 10 frames per second */
#define SCENE_LENGTH_MS 45000u
#define PERSON_TILT_X10 (-30) /* the fake person is a little below straight ahead */

static uint32_t last_frame_ms;
static bool have_frame;
static int32_t camera_pan_x10, camera_tilt_x10;
static frame_t submitted;
static bool have_submitted;

void detect_init(void) {
  have_frame = false;
  last_frame_ms = 0;
  camera_pan_x10 = 0;
  camera_tilt_x10 = 0;
  have_submitted = false;
}

void detect_set_camera(int32_t pan_x10, int32_t tilt_x10) {
  camera_pan_x10 = pan_x10;
  camera_tilt_x10 = tilt_x10;
}

static int16_t to_thousandths(float v) {
  if (v < 0.0f) v = 0.0f;
  if (v > 1.0f) v = 1.0f;
  return (int16_t)(v * 1000.0f + 0.5f);
}

uint8_t detect_boxes_to_frame(uint32_t time_ms, const float *cxcywh, const float *conf, uint8_t count, frame_t *out) {
  bool taken[256] = {false};
  memset(out, 0, sizeof(*out));
  out->time_ms = time_ms;
  while (out->count < DETECT_MAX) {
    int best = -1;
    for (int i = 0; i < count; i++) {
      if (!taken[i] && (best < 0 || conf[i] > conf[best])) best = i;
    }
    if (best < 0) break;
    taken[best] = true;
    detection_t *d = &out->det[out->count++];
    d->x = to_thousandths(cxcywh[4 * best + 0]);
    d->y = to_thousandths(cxcywh[4 * best + 1]);
    d->w = to_thousandths(cxcywh[4 * best + 2]);
    d->h = to_thousandths(cxcywh[4 * best + 3]);
    d->score = (uint8_t)(to_thousandths(conf[best]) / 10);
  }
  return out->count;
}

void detect_submit(const frame_t *frame) {
  submitted = *frame;
  have_submitted = true;
}

#if USE_FAKE_DETECTIONS
/*
 * The made-up scene, repeating every 45 s. Angles are where the person is,
 * in tenths of a degree, as seen from this unit (0 = straight ahead).
 * - 0 to 3 s: nobody.
 * - 3 to 6 s: walks in from the left (-20 deg to 0).
 * - 6 to 19 s: stands near the middle, so should be flagged as lingering.
 * - 19 to 33 s: walks off to the right at 10 deg/s; the camera follows, then hands off.
 * - 33 to 45 s: nobody.
 */
static bool fake_person_angle(uint32_t t, int32_t *angle_x10) {
  if (t < 3000u) return false;
  if (t < 6000u) {
    *angle_x10 = -200 + (int32_t)(t - 3000u) * 200 / 3000;
    return true;
  }
  if (t < 19000u) {
    *angle_x10 = (int32_t)((t / 700u) % 3u) * 10 - 10; /* small sway */
    return true;
  }
  if (t < 33000u) {
    *angle_x10 = (int32_t)(t - 19000u) / 10; /* 10 deg per second */
    return true;
  }
  return false;
}

static void fake_frame(uint32_t now_ms, frame_t *out) {
  int32_t angle_x10;
  if (!fake_person_angle(now_ms % SCENE_LENGTH_MS, &angle_x10)) return;

  /* Where that lands in the image, given where the camera points. */
  int32_t x = 500 + (angle_x10 - camera_pan_x10) * 1000 / (CAMERA_HFOV_DEG * 10);
  int32_t y = 500 - (PERSON_TILT_X10 - camera_tilt_x10) * 1000 / (CAMERA_VFOV_DEG * 10);
  if (x < 0 || x > 1000 || y < 0 || y > 1000) return; /* outside the view */

  detection_t *d = &out->det[out->count++];
  d->x = (int16_t)x;
  d->y = (int16_t)y;
  d->w = 120;
  d->h = 400;
  d->score = 80;
}
#endif

bool detect_poll(uint32_t now_ms, frame_t *out) {
#if USE_FAKE_DETECTIONS
  if (have_frame && (uint32_t)(now_ms - last_frame_ms) < FRAME_PERIOD_MS) return false;
  have_frame = true;
  last_frame_ms = now_ms;

  memset(out, 0, sizeof(*out));
  out->time_ms = now_ms;
  fake_frame(now_ms, out);
  return true;
#else
  (void)now_ms;
  if (!have_submitted) return false;
  *out = submitted;
  have_submitted = false;
  return true;
#endif
}
