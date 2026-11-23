/*
 * link.h - sends and receives Open Herd messages over the serial wire to the ESP32.
 *
 * - Fills in sender, sequence number and time on outgoing messages.
 * - HEADING and TAKEN_OVER need an ACK: if none comes back within
 *   ACK_TIMEOUT_MS the message is resent, up to ACK_MAX_RETRIES times,
 *   then on_failed is called.
 * - Incoming messages for this unit (or for everyone) go to on_message.
 *   Messages that need an ACK are answered automatically, and repeats
 *   of a message already received are not delivered twice.
 */
#ifndef LINK_H
#define LINK_H

#include <stdbool.h>
#include <stdint.h>

#include "herd_msg.h"

typedef void (*link_message_fn)(const herd_msg_t *msg, uint32_t now_ms);
typedef void (*link_failed_fn)(const herd_msg_t *msg, uint32_t now_ms);

typedef struct {
  uint32_t sent;       /* messages sent (not counting resends) */
  uint32_t resent;
  uint32_t failed;     /* gave up waiting for an ACK */
  uint32_t received;   /* good messages delivered */
  uint32_t bad_frames; /* thrown away: corrupted or wrong format */
  uint32_t echoes;     /* our own messages heard back (e.g. a test wire from D1 to D0) */
} link_stats_t;

void link_init(uint8_t my_id, link_message_fn on_message, link_failed_fn on_failed);

/* Call every loop: reads incoming bytes and resends anything still waiting for an ACK. */
void link_poll(uint32_t now_ms);

/* Sends m (src, seq and time_ms are filled in). Returns false if it couldn't be queued. */
bool link_send(herd_msg_t *m, uint32_t now_ms);

const link_stats_t *link_stats(void);

#endif /* LINK_H */
