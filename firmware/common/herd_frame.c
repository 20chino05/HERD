/* herd_frame.c - serial framing for Open Herd messages (format in herd_frame.h). */
#include "herd_frame.h"

#include <string.h>

enum { WAIT_SYNC1 = 0, WAIT_SYNC2, WAIT_LEN, IN_DATA, WAIT_CRC_LO, WAIT_CRC_HI };

static uint16_t crc16_step(uint16_t crc, uint8_t byte) {
  crc ^= (uint16_t)byte << 8;
  for (int i = 0; i < 8; i++) {
    crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u) : (uint16_t)(crc << 1);
  }
  return crc;
}

uint16_t herd_crc16(const uint8_t *data, size_t len) {
  uint16_t crc = 0xFFFFu;
  for (size_t i = 0; i < len; i++) crc = crc16_step(crc, data[i]);
  return crc;
}

size_t herd_frame_encode(const uint8_t *msg, size_t msg_len, uint8_t *out, size_t cap) {
  if (msg_len == 0 || msg_len > HERD_MSG_MAX_LEN) return 0;
  size_t total = msg_len + HERD_FRAME_OVERHEAD;
  if (total > cap) return 0;

  out[0] = HERD_FRAME_SYNC1;
  out[1] = HERD_FRAME_SYNC2;
  out[2] = (uint8_t)msg_len;
  memcpy(&out[3], msg, msg_len);
  uint16_t crc = herd_crc16(&out[2], msg_len + 1);
  out[3 + msg_len] = (uint8_t)(crc & 0xFFu);
  out[4 + msg_len] = (uint8_t)(crc >> 8);
  return total;
}

void herd_frame_parser_init(herd_frame_parser_t *p) { memset(p, 0, sizeof(*p)); }

size_t herd_frame_parser_feed(herd_frame_parser_t *p, uint8_t byte, uint8_t *out, size_t cap) {
  switch (p->state) {
    case WAIT_SYNC1:
      if (byte == HERD_FRAME_SYNC1) p->state = WAIT_SYNC2;
      break;
    case WAIT_SYNC2:
      if (byte == HERD_FRAME_SYNC2) {
        p->state = WAIT_LEN;
      } else if (byte != HERD_FRAME_SYNC1) {
        p->state = WAIT_SYNC1;
      }
      break;
    case WAIT_LEN:
      if (byte == 0 || byte > HERD_MSG_MAX_LEN) {
        p->bad_frames++;
        p->state = (byte == HERD_FRAME_SYNC1) ? WAIT_SYNC2 : WAIT_SYNC1;
      } else {
        p->len = byte;
        p->idx = 0;
        p->state = IN_DATA;
      }
      break;
    case IN_DATA:
      p->buf[p->idx++] = byte;
      if (p->idx == p->len) p->state = WAIT_CRC_LO;
      break;
    case WAIT_CRC_LO:
      p->crc_lo = byte;
      p->state = WAIT_CRC_HI;
      break;
    case WAIT_CRC_HI: {
      p->state = WAIT_SYNC1;
      uint16_t got = (uint16_t)(p->crc_lo | (byte << 8));
      uint16_t crc = crc16_step(0xFFFFu, p->len);
      for (uint8_t i = 0; i < p->len; i++) crc = crc16_step(crc, p->buf[i]);
      if (got != crc || p->len > cap) {
        p->bad_frames++;
        return 0;
      }
      memcpy(out, p->buf, p->len);
      return p->len;
    }
    default:
      p->state = WAIT_SYNC1;
      break;
  }
  return 0;
}
