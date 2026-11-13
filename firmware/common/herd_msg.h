/*
 * herd_msg.h - Open Herd message format.
 *
 * Shared by the STM32 unit, the ESP32 radio bridge and the laptop station,
 * so all three agree on what the bytes mean.
 *
 * Wire layout (all multi-byte fields little-endian):
 *   [0]     version      HERD_MSG_VERSION
 *   [1]     type         herd_msg_type_t
 *   [2]     src          sender unit ID
 *   [3]     dst          receiver unit ID, HERD_ID_STATION or HERD_ID_BROADCAST
 *   [4..5]  seq          sender's message counter
 *   [6..9]  time_ms      sender's clock when sent
 *   [10]    payload_len  bytes that follow
 *   [11..]  payload      depends on type (see herd_msg.c)
 */
#ifndef HERD_MSG_H
#define HERD_MSG_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define HERD_MSG_VERSION 1u
#define HERD_MSG_HEADER_LEN 11u
#define HERD_MSG_MAX_PAYLOAD 32u
#define HERD_MSG_MAX_LEN (HERD_MSG_HEADER_LEN + HERD_MSG_MAX_PAYLOAD)

#define HERD_ID_NONE 0x00u      /* "no neighbor on this side" */
#define HERD_ID_STATION 0xFEu   /* the laptop base station */
#define HERD_ID_BROADCAST 0xFFu /* everyone */

typedef enum {
  HERD_MSG_STATUS = 1,     /* heartbeat, once a second */
  HERD_MSG_EVENT = 2,      /* something for the station's log */
  HERD_MSG_HEADING = 3,    /* "heading your way" (needs an ACK) */
  HERD_MSG_TAKEN_OVER = 4, /* "I have them now" (needs an ACK) */
  HERD_MSG_LOST = 5,       /* the person was lost */
  HERD_MSG_ACK = 6         /* "got your message" */
} herd_msg_type_t;

typedef enum { HERD_SIDE_LEFT = 0, HERD_SIDE_RIGHT = 1 } herd_side_t;

typedef enum {
  HERD_EVENT_BOOT = 1,
  HERD_EVENT_LINGERING = 2,
  HERD_EVENT_HANDOFF_DONE = 3,
  HERD_EVENT_HANDOFF_FAILED = 4
} herd_event_code_t;

typedef struct {
  uint8_t state;       /* unit_state_t of the sender */
  uint8_t track_count; /* people currently in view */
  int8_t pan_deg;
  int8_t tilt_deg;
} herd_status_t;

typedef struct {
  uint8_t code; /* herd_event_code_t */
  uint16_t track_id;
} herd_event_t;

typedef struct {
  uint16_t track_id; /* sender's ID for the person */
  uint8_t exit_side; /* herd_side_t: the side of the sender's view they left by */
  int16_t speed_dps; /* how fast they were moving across the view, degrees per second */
} herd_heading_t;

typedef struct {
  uint16_t track_id; /* used by TAKEN_OVER and LOST: the ID from the HEADING message */
} herd_track_ref_t;

typedef struct {
  uint16_t acked_seq;
  uint8_t acked_type;
} herd_ack_t;

typedef struct {
  uint8_t type;
  uint8_t src;
  uint8_t dst;
  uint16_t seq;
  uint32_t time_ms;
  union {
    herd_status_t status;
    herd_event_t event;
    herd_heading_t heading;
    herd_track_ref_t track;
    herd_ack_t ack;
  } u;
} herd_msg_t;

/* Packs a message into bytes. Returns the number of bytes, or 0 if it doesn't fit or the type is unknown. */
size_t herd_msg_encode(const herd_msg_t *m, uint8_t *out, size_t cap);

/* Unpacks bytes into a message. Returns false if the bytes aren't a valid message. */
bool herd_msg_decode(const uint8_t *in, size_t len, herd_msg_t *m);

/* True for the types the receiver must answer with an ACK. */
bool herd_msg_needs_ack(uint8_t type);

/* Short name for logs, e.g. "HEADING". */
const char *herd_msg_type_name(uint8_t type);

#endif /* HERD_MSG_H */
