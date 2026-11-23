/* board_fake.h - a pretend board for laptop tests: fake clock, captured messages and servo pulses. */
#ifndef BOARD_FAKE_H
#define BOARD_FAKE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "board.h"
#include "herd_msg.h"

#define FAKE_MAX_SENT 2048

typedef struct {
  uint32_t at_ms;
  herd_msg_t msg;
} fake_sent_t;

void fake_reset(void);
void fake_set_time(uint32_t ms);
void fake_set_echo_log(bool on);

/* Messages the app sent to the ESP32, decoded. */
size_t fake_sent_count(void);
const fake_sent_t *fake_sent(size_t i);

/* Queue a message as if the ESP32 had received it over the radio. */
void fake_inject(const herd_msg_t *m);
void fake_inject_bytes(const uint8_t *data, size_t len);

uint16_t fake_servo_us(uint8_t servo);
uint32_t fake_led_toggles(void);

#endif /* BOARD_FAKE_H */
