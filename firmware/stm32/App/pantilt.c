/* pantilt.c - camera aiming (see pantilt.h). */
#include "pantilt.h"

#include "app_config.h"
#include "board.h"

#define PAN_MIN_X10 (PAN_MIN_DEG * 10)
#define PAN_MAX_X10 (PAN_MAX_DEG * 10)
#define TILT_MIN_X10 (TILT_MIN_DEG * 10)
#define TILT_MAX_X10 (TILT_MAX_DEG * 10)
#define LIMIT_SLACK_X10 10 /* within 1 degree of the limit counts as "at the limit" */

static int32_t pan_x10, tilt_x10;               /* where the servos are now */
static int32_t pan_target_x10, tilt_target_x10; /* where they're heading */
static uint32_t last_update_ms;
static bool started;

static int32_t clamp(int32_t v, int32_t lo, int32_t hi) { return v < lo ? lo : (v > hi ? hi : v); }

uint16_t pantilt_angle_to_us(int32_t angle_x10) {
  const int32_t mid = (int32_t)(SERVO_MIN_US + SERVO_MAX_US) / 2;
  const int32_t span = (int32_t)(SERVO_MAX_US - SERVO_MIN_US);
  int32_t us = mid + angle_x10 * span / 1800; /* 1800 = 180 degrees in tenths */
  return (uint16_t)clamp(us, (int32_t)SERVO_MIN_US, (int32_t)SERVO_MAX_US);
}

static void write_servos(void) {
  board_servo_write_us(BOARD_SERVO_PAN, pantilt_angle_to_us(PAN_REVERSED ? -pan_x10 : pan_x10));
  board_servo_write_us(BOARD_SERVO_TILT, pantilt_angle_to_us(TILT_REVERSED ? -tilt_x10 : tilt_x10));
}

void pantilt_init(void) {
  pan_x10 = tilt_x10 = 0;
  pan_target_x10 = tilt_target_x10 = 0;
  started = false;
  write_servos();
}

void pantilt_home(void) { pan_target_x10 = tilt_target_x10 = 0; }

void pantilt_follow(int16_t x, int16_t y) {
  /* How far off-center the box is; small errors are box jitter, not movement. */
  int32_t ex = (int32_t)x - 500;
  int32_t ey = 500 - (int32_t)y; /* up is positive */
  if (ex > -FOLLOW_DEADBAND && ex < FOLLOW_DEADBAND) ex = 0;
  if (ey > -FOLLOW_DEADBAND && ey < FOLLOW_DEADBAND) ey = 0;
  /* ... as an angle. */
  int32_t err_pan = ex * CAMERA_HFOV_DEG * 10 / 1000;
  int32_t err_tilt = ey * CAMERA_VFOV_DEG * 10 / 1000;
  pan_target_x10 = clamp(pan_x10 + err_pan * FOLLOW_GAIN_PCT / 100, PAN_MIN_X10, PAN_MAX_X10);
  tilt_target_x10 = clamp(tilt_x10 + err_tilt * FOLLOW_GAIN_PCT / 100, TILT_MIN_X10, TILT_MAX_X10);
}

void pantilt_look_toward(herd_side_t side) {
  pan_target_x10 = (side == HERD_SIDE_RIGHT) ? EXPECT_PAN_DEG * 10 : -EXPECT_PAN_DEG * 10;
  tilt_target_x10 = 0;
}

bool pantilt_at_limit(herd_side_t side) {
  if (side == HERD_SIDE_RIGHT) return pan_x10 >= PAN_MAX_X10 - LIMIT_SLACK_X10;
  return pan_x10 <= PAN_MIN_X10 + LIMIT_SLACK_X10;
}

static int32_t step_toward(int32_t now, int32_t target, int32_t max_step) {
  if (target > now) return (target - now > max_step) ? now + max_step : target;
  return (now - target > max_step) ? now - max_step : target;
}

void pantilt_update(uint32_t now_ms) {
  if (!started) {
    started = true;
    last_update_ms = now_ms;
    return;
  }
  uint32_t dt = now_ms - last_update_ms;
  int32_t max_step = (int32_t)(SERVO_MAX_SPEED_DPS * 10 * dt / 1000u);
  if (max_step == 0) return; /* not enough time passed to move; keep the remainder */
  last_update_ms = now_ms;

  int32_t new_pan = step_toward(pan_x10, pan_target_x10, max_step);
  int32_t new_tilt = step_toward(tilt_x10, tilt_target_x10, max_step);
  if (new_pan != pan_x10 || new_tilt != tilt_x10) {
    pan_x10 = new_pan;
    tilt_x10 = new_tilt;
    write_servos();
  }
}

int32_t pantilt_pan_x10(void) { return pan_x10; }
int32_t pantilt_tilt_x10(void) { return tilt_x10; }
