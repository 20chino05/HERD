/*
 * app_main.c - startup and the main loop for one Open Herd camera unit.
 *
 * Each pass of the loop:
 *   1. read messages from the ESP32 (and resend anything not yet ACKed)
 *   2. if a new camera frame is ready: track people, check for lingering,
 *      and let the state machine react
 *   3. check the state machine's timeouts
 *   4. move the servos a little toward where they should point
 *   5. once a second: send STATUS and print a summary; blink the LED
 */
#include "app_main.h"

#include <string.h>

#include "app_config.h"
#include "behavior.h"
#include "board.h"
#include "detect.h"
#include "link.h"
#include "log.h"
#include "pantilt.h"
#include "tracker.h"
#include "unit_fsm.h"

static uint32_t last_status_ms;
static uint32_t last_blink_ms;
static frame_t frame;

static void send_status(uint32_t now) {
  herd_msg_t m;
  memset(&m, 0, sizeof(m));
  m.type = HERD_MSG_STATUS;
  m.dst = HERD_ID_BROADCAST;
  m.u.status.state = (uint8_t)fsm_state();
  m.u.status.track_count = (uint8_t)tracker_count();
  m.u.status.pan_deg = (int8_t)(pantilt_pan_x10() / 10);
  m.u.status.tilt_deg = (int8_t)(pantilt_tilt_x10() / 10);
  link_send(&m, now);

  const link_stats_t *s = link_stats();
  log_printf("status: %s target=%u people=%u pan=%ld tilt=%ld"
             " | link sent=%lu resent=%lu failed=%lu recv=%lu bad=%lu echo=%lu",
             fsm_state_name(fsm_state()), (unsigned)fsm_target(), (unsigned)tracker_count(),
             (long)(pantilt_pan_x10() / 10), (long)(pantilt_tilt_x10() / 10), (unsigned long)s->sent,
             (unsigned long)s->resent, (unsigned long)s->failed, (unsigned long)s->received,
             (unsigned long)s->bad_frames, (unsigned long)s->echoes);
}

static void on_message(const herd_msg_t *m, uint32_t now) {
  if (m->type != HERD_MSG_STATUS) {
    log_printf("got %s from unit %u", herd_msg_type_name(m->type), (unsigned)m->src);
  }
  fsm_on_message(m, now);
}

void app_init(void) {
  board_init();
  uint32_t now = board_millis();

  log_printf("Open Herd unit %u starting (left neighbor %u, right neighbor %u, fake detections %s)",
             (unsigned)UNIT_ID, (unsigned)NEIGHBOR_LEFT_ID, (unsigned)NEIGHBOR_RIGHT_ID,
             USE_FAKE_DETECTIONS ? "ON" : "OFF");

  detect_init();
  tracker_init();
  behavior_init();
  pantilt_init();
  link_init(UNIT_ID, on_message, fsm_on_send_failed);
  fsm_init();

  herd_msg_t boot;
  memset(&boot, 0, sizeof(boot));
  boot.type = HERD_MSG_EVENT;
  boot.dst = HERD_ID_STATION;
  boot.u.event.code = HERD_EVENT_BOOT;
  link_send(&boot, now);

  last_status_ms = now;
  last_blink_ms = now;
}

void app_loop(void) {
  uint32_t now = board_millis();

  link_poll(now);

  detect_set_camera(pantilt_pan_x10(), pantilt_tilt_x10());
  if (detect_poll(now, &frame)) {
    tracker_update(&frame);
    uint16_t lingering = behavior_update(now);
    fsm_on_frame(lingering, now);
  }

  fsm_tick(now);
  pantilt_update(now);

  if ((uint32_t)(now - last_status_ms) >= STATUS_PERIOD_MS) {
    last_status_ms = now;
    send_status(now);
  }
  if ((uint32_t)(now - last_blink_ms) >= HEARTBEAT_PERIOD_MS) {
    last_blink_ms = now;
    board_led_toggle();
  }
}
