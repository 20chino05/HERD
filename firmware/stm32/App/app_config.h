/*
 * app_config.h - settings for one camera unit. Change these, not the code.
 *
 * For the second board: set UNIT_ID to 2, NEIGHBOR_LEFT_ID to 1 and
 * NEIGHBOR_RIGHT_ID to HERD_ID_NONE (the two units then face each other's sides).
 */
#ifndef APP_CONFIG_H
#define APP_CONFIG_H

#include "herd_msg.h"

/* ---- Who am I, and who is next to me ---- */
#define UNIT_ID 1u
#define NEIGHBOR_LEFT_ID HERD_ID_NONE /* unit beyond the left edge of my view */
#define NEIGHBOR_RIGHT_ID 2u          /* unit beyond the right edge of my view */

/* 1 = use made-up people so the logic can run without the camera AI. */
#define USE_FAKE_DETECTIONS 1

/* ---- Timing (milliseconds) ---- */
#define STATUS_PERIOD_MS 1000u    /* how often to send STATUS and print a summary */
#define HEARTBEAT_PERIOD_MS 500u  /* LED blink */
#define LINGER_TIME_MS 8000u      /* standing in one spot this long counts as lingering */
#define TARGET_LOST_MS 1500u      /* target unseen this long (not at an edge) = lost */
#define HANDOFF_TIMEOUT_MS 3000u  /* wait this long for the neighbor's TAKEN_OVER */
#define EXPECT_TIMEOUT_MS 4000u   /* after "heading your way", wait this long for the person */
#define ACK_TIMEOUT_MS 250u       /* resend a message if no ACK by then */
#define ACK_MAX_RETRIES 3u        /* resends before giving up */
#define TRACK_DROP_MS 1000u       /* forget a person unseen this long */

/* ---- Image positions are in thousandths of the frame: 0 = left/top, 1000 = right/bottom ---- */
#define FRAME_EDGE_MARGIN 120  /* this close to the side counts as "at the edge" */
#define LINGER_RADIUS 120      /* moving less than this still counts as standing still */
#define TRACK_MATCH_DIST 200   /* max jump between frames to be called the same person */

/* ---- Camera and servos ---- */
#define CAMERA_HFOV_DEG 60     /* horizontal field of view; check the InnoMaker lens */
#define CAMERA_VFOV_DEG 45     /* vertical field of view */
#define PAN_MIN_DEG (-80)      /* turn limits */
#define PAN_MAX_DEG 80
#define TILT_MIN_DEG (-30)
#define TILT_MAX_DEG 30
#define EXPECT_PAN_DEG 60      /* where to point when a neighbor says someone is coming */
#define FOLLOW_GAIN_PCT 30     /* how much of the aiming error to fix each frame */
#define SERVO_MAX_SPEED_DPS 120 /* fastest turn, degrees per second */
#define PAN_REVERSED 0         /* set to 1 if the camera turns the wrong way */
#define TILT_REVERSED 0
/* Pulse widths for -90 and +90 degrees. 1000-2000 us is safe for any hobby servo;
   check the servo datasheet before widening (many SG90s use about 500-2400 us). */
#define SERVO_MIN_US 1000u
#define SERVO_MAX_US 2000u

#endif /* APP_CONFIG_H */
