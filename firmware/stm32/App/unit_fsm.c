/* unit_fsm.c - the handoff state machine (see unit_fsm.h). */
#include "unit_fsm.h"

#include <string.h>

#include "app_config.h"
#include "link.h"
#include "log.h"
#include "pantilt.h"
#include "tracker.h"

static unit_state_t state;
static uint16_t target;        /* tracker ID we're following */
static uint32_t target_seen_ms;
static uint8_t peer;           /* neighbor involved in the current handoff */
static uint16_t handoff_track; /* track ID used in the HEADING message */
static uint32_t deadline_ms;
static uint32_t expect_since_ms;

const char *fsm_state_name(unit_state_t s) {
  switch (s) {
    case UNIT_WATCHING: return "WATCHING";
    case UNIT_TRACKING: return "TRACKING";
    case UNIT_HANDING_OFF: return "HANDING_OFF";
    case UNIT_EXPECTING: return "EXPECTING";
    default: return "?";
  }
}

static void enter(unit_state_t next) {
  if (next != state) log_printf("state: %s -> %s", fsm_state_name(state), fsm_state_name(next));
  state = next;
  if (next == UNIT_WATCHING) {
    target = 0;
    peer = HERD_ID_NONE;
    pantilt_home();
  }
}

static void send_event(uint8_t code, uint16_t track_id, uint32_t now) {
  herd_msg_t m;
  memset(&m, 0, sizeof(m));
  m.type = HERD_MSG_EVENT;
  m.dst = HERD_ID_STATION;
  m.u.event.code = code;
  m.u.event.track_id = track_id;
  link_send(&m, now);
}

static void send_track_msg(uint8_t type, uint8_t dst, uint16_t track_id, uint32_t now) {
  herd_msg_t m;
  memset(&m, 0, sizeof(m));
  m.type = type;
  m.dst = dst;
  m.u.track.track_id = track_id;
  link_send(&m, now);
}

static void lose_target(uint16_t track_id, const char *why, uint32_t now) {
  log_printf("LOST person %u (%s)", (unsigned)track_id, why);
  send_track_msg(HERD_MSG_LOST, HERD_ID_STATION, track_id, now);
  enter(UNIT_WATCHING);
}

void fsm_init(void) {
  state = UNIT_WATCHING;
  target = 0;
  peer = HERD_ID_NONE;
  handoff_track = 0;
  deadline_ms = 0;
  expect_since_ms = 0;
  target_seen_ms = 0;
}

static void start_handoff(herd_side_t side, const track_t *t, uint32_t now) {
  uint8_t neighbor = (side == HERD_SIDE_LEFT) ? NEIGHBOR_LEFT_ID : NEIGHBOR_RIGHT_ID;
  if (neighbor == HERD_ID_NONE) {
    lose_target(t->id, "left the view and there's no neighbor on that side", now);
    return;
  }

  herd_msg_t m;
  memset(&m, 0, sizeof(m));
  m.type = HERD_MSG_HEADING;
  m.dst = neighbor;
  m.u.heading.track_id = t->id;
  m.u.heading.exit_side = (uint8_t)side;
  m.u.heading.speed_dps = (int16_t)((int32_t)t->vx * CAMERA_HFOV_DEG / 1000);
  log_printf("HANDOFF: person %u leaving %s, telling unit %u \"heading your way\"", (unsigned)t->id,
             side == HERD_SIDE_LEFT ? "left" : "right", (unsigned)neighbor);
  link_send(&m, now);

  peer = neighbor;
  handoff_track = t->id;
  deadline_ms = now + HANDOFF_TIMEOUT_MS;
  enter(UNIT_HANDING_OFF);
}

void fsm_on_frame(uint16_t lingering_id, uint32_t now) {
  switch (state) {
    case UNIT_WATCHING:
      if (lingering_id != 0) {
        log_printf("LINGERING: person %u, start tracking", (unsigned)lingering_id);
        send_event(HERD_EVENT_LINGERING, lingering_id, now);
        target = lingering_id;
        target_seen_ms = now;
        enter(UNIT_TRACKING);
      }
      break;

    case UNIT_TRACKING: {
      const track_t *t = tracker_find(target);
      if (t == NULL) break; /* fsm_tick decides when it's been gone too long */
      target_seen_ms = now;
      pantilt_follow(t->x, t->y);
      if (t->x >= 1000 - FRAME_EDGE_MARGIN && pantilt_at_limit(HERD_SIDE_RIGHT)) {
        start_handoff(HERD_SIDE_RIGHT, t, now);
      } else if (t->x <= FRAME_EDGE_MARGIN && pantilt_at_limit(HERD_SIDE_LEFT)) {
        start_handoff(HERD_SIDE_LEFT, t, now);
      }
      break;
    }

    case UNIT_EXPECTING: {
      /* The first person who shows up after the warning is taken to be them. */
      const track_t *tracks = tracker_tracks();
      for (int k = 0; k < TRACK_MAX; k++) {
        if (!tracks[k].active || (int32_t)(tracks[k].first_seen_ms - expect_since_ms) < 0) continue;
        log_printf("PICKED UP: unit %u's person %u is my person %u", (unsigned)peer, (unsigned)handoff_track,
                   (unsigned)tracks[k].id);
        send_track_msg(HERD_MSG_TAKEN_OVER, peer, handoff_track, now);
        target = tracks[k].id;
        target_seen_ms = now;
        enter(UNIT_TRACKING);
        break;
      }
      break;
    }

    case UNIT_HANDING_OFF:
    default:
      break;
  }
}

void fsm_on_message(const herd_msg_t *m, uint32_t now) {
  switch (m->type) {
    case HERD_MSG_HEADING: {
      if (m->src != NEIGHBOR_LEFT_ID && m->src != NEIGHBOR_RIGHT_ID) {
        log_printf("ignoring HEADING from unit %u (not my neighbor)", (unsigned)m->src);
        break;
      }
      if (state != UNIT_WATCHING) {
        log_printf("busy (%s), can't take unit %u's person", fsm_state_name(state), (unsigned)m->src);
        break;
      }
      herd_side_t side = (m->src == NEIGHBOR_LEFT_ID) ? HERD_SIDE_LEFT : HERD_SIDE_RIGHT;
      log_printf("unit %u says person %u is heading my way, turning %s", (unsigned)m->src,
                 (unsigned)m->u.heading.track_id, side == HERD_SIDE_LEFT ? "left" : "right");
      peer = m->src;
      handoff_track = m->u.heading.track_id;
      expect_since_ms = now;
      deadline_ms = now + EXPECT_TIMEOUT_MS;
      pantilt_look_toward(side);
      enter(UNIT_EXPECTING);
      break;
    }

    case HERD_MSG_TAKEN_OVER:
      if (state == UNIT_HANDING_OFF && m->src == peer && m->u.track.track_id == handoff_track) {
        log_printf("unit %u took over person %u", (unsigned)m->src, (unsigned)handoff_track);
        send_event(HERD_EVENT_HANDOFF_DONE, handoff_track, now);
        enter(UNIT_WATCHING);
      }
      break;

    default:
      break; /* STATUS, EVENT, LOST from others: nothing to do yet */
  }
}

void fsm_on_send_failed(const herd_msg_t *m, uint32_t now) {
  if (m->type == HERD_MSG_HEADING && state == UNIT_HANDING_OFF && m->dst == peer) {
    send_event(HERD_EVENT_HANDOFF_FAILED, handoff_track, now);
    lose_target(handoff_track, "neighbor never answered", now);
  }
}

void fsm_tick(uint32_t now) {
  switch (state) {
    case UNIT_TRACKING:
      if ((uint32_t)(now - target_seen_ms) > TARGET_LOST_MS) lose_target(target, "out of sight", now);
      break;
    case UNIT_HANDING_OFF:
      if ((int32_t)(now - deadline_ms) >= 0) lose_target(handoff_track, "neighbor didn't pick them up", now);
      break;
    case UNIT_EXPECTING:
      if ((int32_t)(now - deadline_ms) >= 0) lose_target(handoff_track, "never showed up here", now);
      break;
    case UNIT_WATCHING:
    default:
      break;
  }
}

unit_state_t fsm_state(void) { return state; }
uint16_t fsm_target(void) { return target; }
