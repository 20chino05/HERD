/* herd_msg.c - packs and unpacks Open Herd messages (layout in herd_msg.h). */
#include "herd_msg.h"

#include <string.h>

static void put_u16(uint8_t *p, uint16_t v) {
  p[0] = (uint8_t)(v & 0xFFu);
  p[1] = (uint8_t)(v >> 8);
}

static void put_u32(uint8_t *p, uint32_t v) {
  p[0] = (uint8_t)(v & 0xFFu);
  p[1] = (uint8_t)((v >> 8) & 0xFFu);
  p[2] = (uint8_t)((v >> 16) & 0xFFu);
  p[3] = (uint8_t)(v >> 24);
}

static uint16_t get_u16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }

static uint32_t get_u32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* Payload size for each type, or -1 for an unknown type. */
static int payload_len(uint8_t type) {
  switch (type) {
    case HERD_MSG_STATUS: return 4;
    case HERD_MSG_EVENT: return 3;
    case HERD_MSG_HEADING: return 5;
    case HERD_MSG_TAKEN_OVER: return 2;
    case HERD_MSG_LOST: return 2;
    case HERD_MSG_ACK: return 3;
    default: return -1;
  }
}

size_t herd_msg_encode(const herd_msg_t *m, uint8_t *out, size_t cap) {
  int plen = payload_len(m->type);
  if (plen < 0) return 0;
  size_t total = HERD_MSG_HEADER_LEN + (size_t)plen;
  if (total > cap) return 0;

  out[0] = HERD_MSG_VERSION;
  out[1] = m->type;
  out[2] = m->src;
  out[3] = m->dst;
  put_u16(&out[4], m->seq);
  put_u32(&out[6], m->time_ms);
  out[10] = (uint8_t)plen;

  uint8_t *p = &out[HERD_MSG_HEADER_LEN];
  switch (m->type) {
    case HERD_MSG_STATUS:
      p[0] = m->u.status.state;
      p[1] = m->u.status.track_count;
      p[2] = (uint8_t)m->u.status.pan_deg;
      p[3] = (uint8_t)m->u.status.tilt_deg;
      break;
    case HERD_MSG_EVENT:
      p[0] = m->u.event.code;
      put_u16(&p[1], m->u.event.track_id);
      break;
    case HERD_MSG_HEADING:
      put_u16(&p[0], m->u.heading.track_id);
      p[2] = m->u.heading.exit_side;
      put_u16(&p[3], (uint16_t)m->u.heading.speed_dps);
      break;
    case HERD_MSG_TAKEN_OVER:
    case HERD_MSG_LOST:
      put_u16(&p[0], m->u.track.track_id);
      break;
    case HERD_MSG_ACK:
      put_u16(&p[0], m->u.ack.acked_seq);
      p[2] = m->u.ack.acked_type;
      break;
    default:
      return 0;
  }
  return total;
}

bool herd_msg_decode(const uint8_t *in, size_t len, herd_msg_t *m) {
  if (len < HERD_MSG_HEADER_LEN) return false;
  if (in[0] != HERD_MSG_VERSION) return false;
  int plen = payload_len(in[1]);
  if (plen < 0 || in[10] != (uint8_t)plen) return false;
  if (len != HERD_MSG_HEADER_LEN + (size_t)plen) return false;

  memset(m, 0, sizeof(*m));
  m->type = in[1];
  m->src = in[2];
  m->dst = in[3];
  m->seq = get_u16(&in[4]);
  m->time_ms = get_u32(&in[6]);

  const uint8_t *p = &in[HERD_MSG_HEADER_LEN];
  switch (m->type) {
    case HERD_MSG_STATUS:
      m->u.status.state = p[0];
      m->u.status.track_count = p[1];
      m->u.status.pan_deg = (int8_t)p[2];
      m->u.status.tilt_deg = (int8_t)p[3];
      break;
    case HERD_MSG_EVENT:
      m->u.event.code = p[0];
      m->u.event.track_id = get_u16(&p[1]);
      break;
    case HERD_MSG_HEADING:
      m->u.heading.track_id = get_u16(&p[0]);
      m->u.heading.exit_side = p[2];
      m->u.heading.speed_dps = (int16_t)get_u16(&p[3]);
      break;
    case HERD_MSG_TAKEN_OVER:
    case HERD_MSG_LOST:
      m->u.track.track_id = get_u16(&p[0]);
      break;
    case HERD_MSG_ACK:
      m->u.ack.acked_seq = get_u16(&p[0]);
      m->u.ack.acked_type = p[2];
      break;
    default:
      return false;
  }
  return true;
}

bool herd_msg_needs_ack(uint8_t type) { return type == HERD_MSG_HEADING || type == HERD_MSG_TAKEN_OVER; }

const char *herd_msg_type_name(uint8_t type) {
  switch (type) {
    case HERD_MSG_STATUS: return "STATUS";
    case HERD_MSG_EVENT: return "EVENT";
    case HERD_MSG_HEADING: return "HEADING";
    case HERD_MSG_TAKEN_OVER: return "TAKEN_OVER";
    case HERD_MSG_LOST: return "LOST";
    case HERD_MSG_ACK: return "ACK";
    default: return "UNKNOWN";
  }
}
