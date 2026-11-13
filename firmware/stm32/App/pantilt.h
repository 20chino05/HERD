/*
 * pantilt.h - points the camera with the two servos.
 *
 * Angles are tenths of a degree (x10) so small moves stay smooth.
 * Positive pan = turn right, positive tilt = look up (flip with
 * PAN_REVERSED / TILT_REVERSED in app_config.h if the mount is the other way).
 */
#ifndef PANTILT_H
#define PANTILT_H

#include <stdbool.h>
#include <stdint.h>

#include "herd_msg.h"

void pantilt_init(void);                    /* go to the home position */
void pantilt_home(void);                    /* look straight ahead */
void pantilt_follow(int16_t x, int16_t y);  /* nudge toward a box center (thousandths of the frame) */
void pantilt_look_toward(herd_side_t side); /* turn toward a neighbor's side */
bool pantilt_at_limit(herd_side_t side);    /* turned as far as allowed toward that side? */
void pantilt_update(uint32_t now_ms);       /* call every loop: moves the servos, speed-limited */

int32_t pantilt_pan_x10(void);
int32_t pantilt_tilt_x10(void);

/* Servo pulse for an angle, clamped to SERVO_MIN_US..SERVO_MAX_US. */
uint16_t pantilt_angle_to_us(int32_t angle_x10);

#endif /* PANTILT_H */
