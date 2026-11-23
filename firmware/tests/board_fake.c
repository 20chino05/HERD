/* board_fake.c - board.h for the laptop tests (see board_fake.h). */
#include "board_fake.h"

#include <stdio.h>
#include <string.h>

#include "herd_frame.h"

#define RX_QUEUE 4096

static uint32_t now_ms;
static bool echo_log;
static fake_sent_t sent[FAKE_MAX_SENT];
static size_t sent_count;
static herd_frame_parser_t tx_parser;
static uint8_t rx_queue[RX_QUEUE];
static size_t rx_head, rx_tail;
static uint16_t servo_us[2];
static uint32_t led_toggles;

void fake_reset(void) {
  now_ms = 0;
  sent_count = 0;
  herd_frame_parser_init(&tx_parser);
  rx_head = rx_tail = 0;
  servo_us[0] = servo_us[1] = 0;
  led_toggles = 0;
}

void fake_set_time(uint32_t ms) { now_ms = ms; }
void fake_set_echo_log(bool on) { echo_log = on; }
size_t fake_sent_count(void) { return sent_count; }
const fake_sent_t *fake_sent(size_t i) { return i < sent_count ? &sent[i] : NULL; }
uint16_t fake_servo_us(uint8_t servo) { return servo_us[servo & 1u]; }
uint32_t fake_led_toggles(void) { return led_toggles; }

void fake_inject_bytes(const uint8_t *data, size_t len) {
  for (size_t i = 0; i < len && rx_head < RX_QUEUE; i++) rx_queue[rx_head++] = data[i];
}

void fake_inject(const herd_msg_t *m) {
  uint8_t raw[HERD_MSG_MAX_LEN], frame[HERD_FRAME_MAX_LEN];
  size_t n = herd_msg_encode(m, raw, sizeof(raw));
  size_t f = herd_frame_encode(raw, n, frame, sizeof(frame));
  fake_inject_bytes(frame, f);
}

/* ---- board.h ---- */

void board_init(void) {}
uint32_t board_millis(void) { return now_ms; }
void board_led_toggle(void) { led_toggles++; }

void board_log_write(const char *text, size_t len) {
  if (echo_log) fwrite(text, 1, len, stdout);
}

void board_link_write(const uint8_t *data, size_t len) {
  uint8_t raw[HERD_MSG_MAX_LEN];
  for (size_t i = 0; i < len; i++) {
    size_t n = herd_frame_parser_feed(&tx_parser, data[i], raw, sizeof(raw));
    if (n == 0 || sent_count >= FAKE_MAX_SENT) continue;
    if (herd_msg_decode(raw, n, &sent[sent_count].msg)) {
      sent[sent_count].at_ms = now_ms;
      sent_count++;
    }
  }
}

bool board_link_read(uint8_t *byte) {
  if (rx_tail >= rx_head) return false;
  *byte = rx_queue[rx_tail++];
  return true;
}

void board_servo_write_us(uint8_t servo, uint16_t pulse_us) { servo_us[servo & 1u] = pulse_us; }
