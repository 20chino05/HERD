/*
 * board.h - the only functions the app uses to touch hardware.
 *
 * board_stm32.c implements them for the NUCLEO-N657X0-Q. The laptop tests
 * (firmware/tests) implement them with fakes, so the app logic can be tested
 * without a board.
 */
#ifndef BOARD_H
#define BOARD_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define BOARD_SERVO_PAN 0u
#define BOARD_SERVO_TILT 1u

void board_init(void);
uint32_t board_millis(void);                             /* milliseconds since start */
void board_led_toggle(void);                             /* heartbeat LED */
void board_log_write(const char *text, size_t len);      /* debug text to the laptop */
void board_link_write(const uint8_t *data, size_t len);  /* bytes to the ESP32 */
bool board_link_read(uint8_t *byte);                     /* next byte from the ESP32, if any */
void board_servo_write_us(uint8_t servo, uint16_t pulse_us);

#endif /* BOARD_H */
