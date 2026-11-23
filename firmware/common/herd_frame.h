/*
 * herd_frame.h - wraps messages for a serial (UART) wire, e.g. STM32 <-> ESP32.
 *
 * Frame: 0xA5 0x5A | len | message bytes (len of them) | CRC16 (2 bytes, little-endian)
 * The CRC covers the len byte and the message bytes, so a corrupted or cut-off
 * frame is thrown away instead of being read as a wrong message.
 */
#ifndef HERD_FRAME_H
#define HERD_FRAME_H

#include <stddef.h>
#include <stdint.h>

#include "herd_msg.h"

#define HERD_FRAME_SYNC1 0xA5u
#define HERD_FRAME_SYNC2 0x5Au
#define HERD_FRAME_OVERHEAD 5u
#define HERD_FRAME_MAX_LEN (HERD_MSG_MAX_LEN + HERD_FRAME_OVERHEAD)

/* CRC-16/CCITT-FALSE (polynomial 0x1021, start 0xFFFF). */
uint16_t herd_crc16(const uint8_t *data, size_t len);

/* Wraps msg into a frame. Returns the frame length, or 0 if it doesn't fit. */
size_t herd_frame_encode(const uint8_t *msg, size_t msg_len, uint8_t *out, size_t cap);

typedef struct {
  uint8_t state;
  uint8_t len;
  uint8_t idx;
  uint8_t crc_lo;
  uint8_t buf[HERD_MSG_MAX_LEN];
  uint32_t bad_frames; /* frames thrown away because of a bad CRC or length */
} herd_frame_parser_t;

void herd_frame_parser_init(herd_frame_parser_t *p);

/*
 * Feed received bytes one at a time. When a byte completes a good frame,
 * the message is copied into out and its length is returned; otherwise 0.
 */
size_t herd_frame_parser_feed(herd_frame_parser_t *p, uint8_t byte, uint8_t *out, size_t cap);

#endif /* HERD_FRAME_H */
