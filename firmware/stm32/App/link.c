/* link.c - message link to the ESP32 with ACKs and resends (see link.h). */
#include "link.h"

#include <string.h>

#include "app_config.h"
#include "board.h"
#include "herd_frame.h"
#include "log.h"

#define PENDING_MAX 4 /* messages waiting for an ACK at once */
#define SEEN_MAX 8    /* recent (sender, seq) pairs remembered to spot repeats */

typedef struct {
  bool used;
  uint8_t tries; /* times sent so far */
  uint32_t last_sent_ms;
  herd_msg_t msg;
} pending_t;

typedef struct {
  bool used;
  uint8_t src;
  uint16_t seq;
} seen_t;

static uint8_t my_id;
static uint16_t next_seq;
static link_message_fn on_message;
static link_failed_fn on_failed;
static herd_frame_parser_t parser;
static pending_t pending[PENDING_MAX];
static seen_t seen[SEEN_MAX];
static uint8_t seen_next;
static link_stats_t stats;

void link_init(uint8_t id, link_message_fn msg_fn, link_failed_fn fail_fn) {
  my_id = id;
  next_seq = 1;
  on_message = msg_fn;
  on_failed = fail_fn;
  herd_frame_parser_init(&parser);
  memset(pending, 0, sizeof(pending));
  memset(seen, 0, sizeof(seen));
  seen_next = 0;
  memset(&stats, 0, sizeof(stats));
}

static void transmit(const herd_msg_t *m) {
  uint8_t raw[HERD_MSG_MAX_LEN];
  uint8_t frame[HERD_FRAME_MAX_LEN];
  size_t n = herd_msg_encode(m, raw, sizeof(raw));
  if (n == 0) return;
  size_t f = herd_frame_encode(raw, n, frame, sizeof(frame));
  if (f > 0) board_link_write(frame, f);
}

bool link_send(herd_msg_t *m, uint32_t now_ms) {
  m->src = my_id;
  m->seq = next_seq++;
  if (next_seq == 0) next_seq = 1;
  m->time_ms = now_ms;

  bool reliable = herd_msg_needs_ack(m->type) && m->dst != HERD_ID_BROADCAST;
  if (reliable) {
    pending_t *slot = NULL;
    for (int i = 0; i < PENDING_MAX; i++) {
      if (!pending[i].used) {
        slot = &pending[i];
        break;
      }
    }
    if (slot == NULL) {
      log_printf("link: too many messages waiting for an ACK, dropped %s", herd_msg_type_name(m->type));
      stats.failed++;
      return false;
    }
    slot->used = true;
    slot->tries = 1;
    slot->last_sent_ms = now_ms;
    slot->msg = *m;
  }
  transmit(m);
  stats.sent++;
  return true;
}

static void send_ack(const herd_msg_t *m, uint32_t now_ms) {
  herd_msg_t ack;
  memset(&ack, 0, sizeof(ack));
  ack.type = HERD_MSG_ACK;
  ack.dst = m->src;
  ack.u.ack.acked_seq = m->seq;
  ack.u.ack.acked_type = m->type;
  link_send(&ack, now_ms);
}

static bool already_seen(uint8_t src, uint16_t seq) {
  for (int i = 0; i < SEEN_MAX; i++) {
    if (seen[i].used && seen[i].src == src && seen[i].seq == seq) return true;
  }
  seen[seen_next].used = true;
  seen[seen_next].src = src;
  seen[seen_next].seq = seq;
  seen_next = (uint8_t)((seen_next + 1u) % SEEN_MAX);
  return false;
}

static void handle_message(const herd_msg_t *m, uint32_t now_ms) {
  if (m->src == my_id) { /* our own message heard back */
    stats.echoes++;
    return;
  }
  if (m->dst != my_id && m->dst != HERD_ID_BROADCAST) return; /* for someone else */

  if (m->type == HERD_MSG_ACK) {
    for (int i = 0; i < PENDING_MAX; i++) {
      pending_t *p = &pending[i];
      if (p->used && p->msg.dst == m->src && p->msg.seq == m->u.ack.acked_seq &&
          p->msg.type == m->u.ack.acked_type) {
        p->used = false;
      }
    }
    return;
  }

  if (herd_msg_needs_ack(m->type) && m->dst == my_id) {
    send_ack(m, now_ms); /* always answer, even a repeat: our first ACK may have been lost */
    if (already_seen(m->src, m->seq)) return;
  }

  stats.received++;
  if (on_message) on_message(m, now_ms);
}

void link_poll(uint32_t now_ms) {
  uint8_t byte;
  uint8_t raw[HERD_MSG_MAX_LEN];
  while (board_link_read(&byte)) {
    size_t n = herd_frame_parser_feed(&parser, byte, raw, sizeof(raw));
    if (n == 0) continue;
    herd_msg_t m;
    if (herd_msg_decode(raw, n, &m)) {
      handle_message(&m, now_ms);
    } else {
      stats.bad_frames++;
    }
  }
  stats.bad_frames += parser.bad_frames;
  parser.bad_frames = 0;

  for (int i = 0; i < PENDING_MAX; i++) {
    pending_t *p = &pending[i];
    if (!p->used || (uint32_t)(now_ms - p->last_sent_ms) < ACK_TIMEOUT_MS) continue;
    if (p->tries > ACK_MAX_RETRIES) {
      p->used = false;
      stats.failed++;
      log_printf("link: no ACK from unit %u for %s, giving up", (unsigned)p->msg.dst,
                 herd_msg_type_name(p->msg.type));
      if (on_failed) on_failed(&p->msg, now_ms);
      continue;
    }
    p->tries++;
    p->last_sent_ms = now_ms;
    stats.resent++;
    log_printf("link: no ACK yet for %s to unit %u, resending (%u/%u)", herd_msg_type_name(p->msg.type),
               (unsigned)p->msg.dst, (unsigned)(p->tries - 1u), (unsigned)ACK_MAX_RETRIES);
    transmit(&p->msg);
  }
}

const link_stats_t *link_stats(void) { return &stats; }
