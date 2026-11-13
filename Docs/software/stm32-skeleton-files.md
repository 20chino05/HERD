# STM32 skeleton: every file, ready to paste

Backup for when you can't use the zip. Make each file in CubeIDE (right-click the `App` folder → **New → File**, type the exact name, **Finish**), paste its contents, and save (Cmd+S). There are 23 files. The order doesn't matter, but every one is needed.

## 1. `app_main.h`

```c
/*
 * app_main.h - the two calls main.c needs.
 *
 * In CubeMX's main.c:
 *   USER CODE BEGIN Includes   ->  #include "app_main.h"
 *   USER CODE BEGIN 2          ->  app_init();
 *   USER CODE BEGIN 3          ->  app_loop();   (inside while (1))
 */
#ifndef APP_MAIN_H
#define APP_MAIN_H

void app_init(void);
void app_loop(void);

#endif /* APP_MAIN_H */
```

## 2. `app_main.c`

```c
/*
 * app_main.c - startup and the main loop for one Open Herd camera unit.
 *
 * Each pass of the loop:
 *   1. read messages from the ESP32 (and resend anything not yet ACKed)
 *   2. if a new camera frame is ready: track people, check for lingering,
 *      and let the state machine react
 *   3. check the state machine's timeouts
 *   4. move the servos a little toward where they should point
 *   5. once a second: send STATUS and print a summary; blink the LED
 */
#include "app_main.h"

#include <string.h>

#include "app_config.h"
#include "behavior.h"
#include "board.h"
#include "detect.h"
#include "link.h"
#include "log.h"
#include "pantilt.h"
#include "tracker.h"
#include "unit_fsm.h"

static uint32_t last_status_ms;
static uint32_t last_blink_ms;
static frame_t frame;

static void send_status(uint32_t now) {
  herd_msg_t m;
  memset(&m, 0, sizeof(m));
  m.type = HERD_MSG_STATUS;
  m.dst = HERD_ID_BROADCAST;
  m.u.status.state = (uint8_t)fsm_state();
  m.u.status.track_count = (uint8_t)tracker_count();
  m.u.status.pan_deg = (int8_t)(pantilt_pan_x10() / 10);
  m.u.status.tilt_deg = (int8_t)(pantilt_tilt_x10() / 10);
  link_send(&m, now);

  const link_stats_t *s = link_stats();
  log_printf("status: %s target=%u people=%u pan=%ld tilt=%ld | link sent=%lu resent=%lu failed=%lu recv=%lu bad=%lu echo=%lu",
             fsm_state_name(fsm_state()), (unsigned)fsm_target(), (unsigned)tracker_count(),
             (long)(pantilt_pan_x10() / 10), (long)(pantilt_tilt_x10() / 10), (unsigned long)s->sent,
             (unsigned long)s->resent, (unsigned long)s->failed, (unsigned long)s->received,
             (unsigned long)s->bad_frames, (unsigned long)s->echoes);
}

static void on_message(const herd_msg_t *m, uint32_t now) {
  if (m->type != HERD_MSG_STATUS) {
    log_printf("got %s from unit %u", herd_msg_type_name(m->type), (unsigned)m->src);
  }
  fsm_on_message(m, now);
}

void app_init(void) {
  board_init();
  uint32_t now = board_millis();

  log_printf("Open Herd unit %u starting (left neighbor %u, right neighbor %u, fake detections %s)",
             (unsigned)UNIT_ID, (unsigned)NEIGHBOR_LEFT_ID, (unsigned)NEIGHBOR_RIGHT_ID,
             USE_FAKE_DETECTIONS ? "ON" : "OFF");

  detect_init();
  tracker_init();
  behavior_init();
  pantilt_init();
  link_init(UNIT_ID, on_message, fsm_on_send_failed);
  fsm_init();

  herd_msg_t boot;
  memset(&boot, 0, sizeof(boot));
  boot.type = HERD_MSG_EVENT;
  boot.dst = HERD_ID_STATION;
  boot.u.event.code = HERD_EVENT_BOOT;
  link_send(&boot, now);

  last_status_ms = now;
  last_blink_ms = now;
}

void app_loop(void) {
  uint32_t now = board_millis();

  link_poll(now);

  detect_set_camera(pantilt_pan_x10(), pantilt_tilt_x10());
  if (detect_poll(now, &frame)) {
    tracker_update(&frame);
    uint16_t lingering = behavior_update(now);
    fsm_on_frame(lingering, now);
  }

  fsm_tick(now);
  pantilt_update(now);

  if ((uint32_t)(now - last_status_ms) >= STATUS_PERIOD_MS) {
    last_status_ms = now;
    send_status(now);
  }
  if ((uint32_t)(now - last_blink_ms) >= HEARTBEAT_PERIOD_MS) {
    last_blink_ms = now;
    board_led_toggle();
  }
}
```

## 3. `app_config.h`

```c
/*
 * app_config.h - settings for one camera unit. Change these, not the code.
 *
 * For the second board: set UNIT_ID to 2, NEIGHBOR_LEFT_ID to 1 and
 * NEIGHBOR_RIGHT_ID to HERD_ID_NONE (the two units then face each other's sides).
 */
#ifndef APP_CONFIG_H
#define APP_CONFIG_H

#include "herd_msg.h"

/* ---- Who am I, and who is next to me ---- */
#define UNIT_ID 1u
#define NEIGHBOR_LEFT_ID HERD_ID_NONE /* unit beyond the left edge of my view */
#define NEIGHBOR_RIGHT_ID 2u          /* unit beyond the right edge of my view */

/* 1 = use made-up people so the logic can run without the camera AI. */
#define USE_FAKE_DETECTIONS 1

/* ---- Timing (milliseconds) ---- */
#define STATUS_PERIOD_MS 1000u    /* how often to send STATUS and print a summary */
#define HEARTBEAT_PERIOD_MS 500u  /* LED blink */
#define LINGER_TIME_MS 8000u      /* standing in one spot this long counts as lingering */
#define TARGET_LOST_MS 1500u      /* target unseen this long (not at an edge) = lost */
#define HANDOFF_TIMEOUT_MS 3000u  /* wait this long for the neighbor's TAKEN_OVER */
#define EXPECT_TIMEOUT_MS 4000u   /* after "heading your way", wait this long for the person */
#define ACK_TIMEOUT_MS 250u       /* resend a message if no ACK by then */
#define ACK_MAX_RETRIES 3u        /* resends before giving up */
#define TRACK_DROP_MS 1000u       /* forget a person unseen this long */

/* ---- Image positions are in thousandths of the frame: 0 = left/top, 1000 = right/bottom ---- */
#define FRAME_EDGE_MARGIN 120  /* this close to the side counts as "at the edge" */
#define LINGER_RADIUS 120      /* moving less than this still counts as standing still */
#define TRACK_MATCH_DIST 200   /* max jump between frames to be called the same person */

/* ---- Camera and servos ---- */
#define CAMERA_HFOV_DEG 60     /* horizontal field of view; check the InnoMaker lens */
#define CAMERA_VFOV_DEG 45     /* vertical field of view */
#define PAN_MIN_DEG (-80)      /* turn limits */
#define PAN_MAX_DEG 80
#define TILT_MIN_DEG (-30)
#define TILT_MAX_DEG 30
#define EXPECT_PAN_DEG 60      /* where to point when a neighbor says someone is coming */
#define FOLLOW_GAIN_PCT 30     /* how much of the aiming error to fix each frame */
#define SERVO_MAX_SPEED_DPS 120 /* fastest turn, degrees per second */
#define PAN_REVERSED 0         /* set to 1 if the camera turns the wrong way */
#define TILT_REVERSED 0
/* Pulse widths for -90 and +90 degrees. 1000-2000 us is safe for any hobby servo;
   check the servo datasheet before widening (many SG90s use about 500-2400 us). */
#define SERVO_MIN_US 1000u
#define SERVO_MAX_US 2000u

#endif /* APP_CONFIG_H */
```

## 4. `board.h`

```c
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
```

## 5. `board_stm32.c`

```c
/*
 * board_stm32.c - board.h for the NUCLEO-N657X0-Q, using ST's HAL.
 *
 * Uses what CubeMX generates in main.c (see Docs/software/stm32-skeleton-setup.md):
 *   huart1  USART1, PE5/PE6, the ST-LINK USB virtual COM port   -> debug log
 *   huart3  USART3, PD8 (TX, Arduino D1) / PD9 (RX, Arduino D0) -> ESP32
 *           (its "global interrupt" must be enabled in CubeMX)
 *   htim1   TIM1 CH1 on PE9 (Arduino D3) -> pan servo
 *           TIM1 CH2 on PE11 (Arduino D7) -> tilt servo
 * The green user LED (PG0) is set up here, so CubeMX doesn't need to.
 *
 * If CubeMX named anything differently, only the #defines below need changing.
 */
#include "main.h" /* CubeMX's header: brings in the STM32 HAL */

#include "board.h"
#include "log.h"

extern UART_HandleTypeDef huart1;
extern UART_HandleTypeDef huart3;
extern TIM_HandleTypeDef htim1;

#define LOG_UART (&huart1)
#define LINK_UART (&huart3)
#define SERVO_TIM (&htim1)
#define SERVO_PAN_CHANNEL TIM_CHANNEL_1
#define SERVO_TILT_CHANNEL TIM_CHANNEL_2
#define LED_PORT GPIOG
#define LED_PIN GPIO_PIN_0

#define SERVO_PERIOD_US 20000u /* 50 Hz, standard for hobby servos */
#define RX_BUF_SIZE 256u

static volatile uint8_t rx_buf[RX_BUF_SIZE];
static volatile uint16_t rx_head; /* written by the UART interrupt */
static volatile uint16_t rx_tail; /* read by the main loop */
static uint8_t rx_byte;
static bool servo_ready;

/*
 * Sets TIM1 to count in microseconds with a 20 ms period, so a compare value
 * of 1500 is a 1.5 ms servo pulse. The timer's input clock depends on the
 * clock settings, so it's measured here against the 1 ms system tick instead
 * of being typed in by hand.
 */
static void servo_timer_setup(void) {
  __HAL_TIM_SET_PRESCALER(SERVO_TIM, 999u); /* count at clock / 1000 while measuring */
  __HAL_TIM_SET_AUTORELOAD(SERVO_TIM, 0xFFFFu);
  SERVO_TIM->Instance->EGR = TIM_EGR_UG; /* apply the new settings now */
  __HAL_TIM_SET_COMPARE(SERVO_TIM, SERVO_PAN_CHANNEL, 0u);
  __HAL_TIM_SET_COMPARE(SERVO_TIM, SERVO_TILT_CHANNEL, 0u);
  if (HAL_TIM_PWM_Start(SERVO_TIM, SERVO_PAN_CHANNEL) != HAL_OK ||
      HAL_TIM_PWM_Start(SERVO_TIM, SERVO_TILT_CHANNEL) != HAL_OK) {
    log_printf("board: couldn't start TIM1 PWM, servos disabled (check TIM1 in CubeMX)");
    return;
  }

  uint32_t t = HAL_GetTick();
  while (HAL_GetTick() == t) {
  } /* line up with a tick edge */
  uint32_t start = HAL_GetTick();
  uint16_t c0 = (uint16_t)__HAL_TIM_GET_COUNTER(SERVO_TIM);
  while ((uint32_t)(HAL_GetTick() - start) < 50u) {
  }
  uint16_t c1 = (uint16_t)__HAL_TIM_GET_COUNTER(SERVO_TIM);
  uint32_t counts = (uint16_t)(c1 - c0);
  uint32_t timer_hz = counts * 20000u; /* counts in 50 ms, times 1000 (prescaler) and 20 */

  if (timer_hz < 1000000u) {
    log_printf("board: TIM1 isn't counting, servos disabled (check TIM1 in CubeMX)");
    return;
  }

  uint32_t prescaler = (timer_hz + 500000u) / 1000000u - 1u; /* round to whole MHz */
  __HAL_TIM_SET_PRESCALER(SERVO_TIM, prescaler);
  __HAL_TIM_SET_AUTORELOAD(SERVO_TIM, SERVO_PERIOD_US - 1u);
  SERVO_TIM->Instance->EGR = TIM_EGR_UG;
  servo_ready = true;
  log_printf("board: servo timer clock measured at about %lu MHz, servos on D3 (pan) and D7 (tilt)",
             (unsigned long)((timer_hz + 500000u) / 1000000u));
}

void board_init(void) {
  __HAL_RCC_GPIOG_CLK_ENABLE();
  GPIO_InitTypeDef led = {0};
  led.Pin = LED_PIN;
  led.Mode = GPIO_MODE_OUTPUT_PP;
  led.Pull = GPIO_NOPULL;
  led.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(LED_PORT, &led);

  rx_head = rx_tail = 0;
  if (HAL_UART_Receive_IT(LINK_UART, &rx_byte, 1) != HAL_OK) {
    log_printf("board: couldn't start listening on USART3 (check it in CubeMX)");
  }

  servo_timer_setup();
}

uint32_t board_millis(void) { return HAL_GetTick(); }

void board_led_toggle(void) { HAL_GPIO_TogglePin(LED_PORT, LED_PIN); }

void board_log_write(const char *text, size_t len) {
  HAL_UART_Transmit(LOG_UART, (const uint8_t *)text, (uint16_t)len, 100u);
}

void board_link_write(const uint8_t *data, size_t len) {
  HAL_UART_Transmit(LINK_UART, data, (uint16_t)len, 50u);
}

bool board_link_read(uint8_t *byte) {
  if (rx_tail == rx_head) return false;
  *byte = rx_buf[rx_tail];
  rx_tail = (uint16_t)((rx_tail + 1u) % RX_BUF_SIZE);
  return true;
}

void board_servo_write_us(uint8_t servo, uint16_t pulse_us) {
  if (!servo_ready) return;
  uint32_t channel = (servo == BOARD_SERVO_PAN) ? SERVO_PAN_CHANNEL : SERVO_TILT_CHANNEL;
  __HAL_TIM_SET_COMPARE(SERVO_TIM, channel, pulse_us);
}

/* Called by the HAL from the USART3 interrupt each time a byte arrives. */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
  if (huart != LINK_UART) return;
  uint16_t next = (uint16_t)((rx_head + 1u) % RX_BUF_SIZE);
  if (next != rx_tail) { /* if the buffer is full, the byte is dropped */
    rx_buf[rx_head] = rx_byte;
    rx_head = next;
  }
  HAL_UART_Receive_IT(LINK_UART, &rx_byte, 1);
}

/* A glitch on the wire (noise, a cable unplugged) stops reception; start it again. */
void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart) {
  if (huart == LINK_UART) HAL_UART_Receive_IT(LINK_UART, &rx_byte, 1);
}
```

## 6. `log.h`

```c
/* log.h - printf-style debug log, one line per call, prefixed with the time. */
#ifndef LOG_H
#define LOG_H

void log_printf(const char *fmt, ...) __attribute__((format(printf, 1, 2)));

#endif /* LOG_H */
```

## 7. `log.c`

```c
/* log.c - formats a line and hands it to the board's debug serial port. */
#include "log.h"

#include <stdarg.h>
#include <stdio.h>

#include "board.h"

void log_printf(const char *fmt, ...) {
  char line[192];
  int n = snprintf(line, sizeof(line), "[%7lu] ", (unsigned long)board_millis());
  if (n < 0) return;

  va_list args;
  va_start(args, fmt);
  int m = vsnprintf(&line[n], sizeof(line) - (size_t)n, fmt, args);
  va_end(args);
  if (m < 0) return;

  size_t len = (size_t)n + (size_t)m;
  if (len > sizeof(line) - 3) len = sizeof(line) - 3; /* message was cut short */
  line[len++] = '\r';
  line[len++] = '\n';
  board_log_write(line, len);
}
```

## 8. `herd_msg.h`

```c
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
```

## 9. `herd_msg.c`

```c
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
```

## 10. `herd_frame.h`

```c
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
```

## 11. `herd_frame.c`

```c
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
```

## 12. `detect.h`

```c
/*
 * detect.h - people boxes for each camera frame.
 *
 * Owner: Devin. Right now this makes up one person who walks in, lingers,
 * then walks off to the right (USE_FAKE_DETECTIONS in app_config.h).
 * Later it wraps ST's person-detection pipeline; the rest of the app only
 * sees frame_t, so nothing else has to change.
 */
#ifndef DETECT_H
#define DETECT_H

#include <stdbool.h>
#include <stdint.h>

#define DETECT_MAX 8

typedef struct {
  int16_t x, y;  /* box center, thousandths of the frame */
  int16_t w, h;  /* box size, thousandths of the frame */
  uint8_t score; /* confidence, percent */
} detection_t;

typedef struct {
  uint32_t time_ms;
  uint8_t count;
  detection_t det[DETECT_MAX];
} frame_t;

void detect_init(void);

/* Where the camera is pointing (tenths of a degree); the fake person uses it. */
void detect_set_camera(int32_t pan_x10, int32_t tilt_x10);

/* Fills *out and returns true when a new frame is ready. */
bool detect_poll(uint32_t now_ms, frame_t *out);

#endif /* DETECT_H */
```

## 13. `detect.c`

```c
/* detect.c - fake detections for now (see detect.h). */
#include "detect.h"

#include <string.h>

#include "app_config.h"

#define FRAME_PERIOD_MS 100u /* 10 frames per second */
#define SCENE_LENGTH_MS 45000u
#define PERSON_TILT_X10 (-30) /* the fake person is a little below straight ahead */

static uint32_t last_frame_ms;
static bool have_frame;
static int32_t camera_pan_x10, camera_tilt_x10;

void detect_init(void) {
  have_frame = false;
  last_frame_ms = 0;
  camera_pan_x10 = 0;
  camera_tilt_x10 = 0;
}

void detect_set_camera(int32_t pan_x10, int32_t tilt_x10) {
  camera_pan_x10 = pan_x10;
  camera_tilt_x10 = tilt_x10;
}

#if USE_FAKE_DETECTIONS
/*
 * The made-up scene, repeating every 45 s. Angles are where the person is,
 * in tenths of a degree, as seen from this unit (0 = straight ahead).
 *   0-3 s    nobody
 *   3-6 s    walks in from the left (-20 deg to 0)
 *   6-19 s   stands near the middle  -> should be flagged as lingering
 *   19-33 s  walks off to the right at 10 deg/s -> camera follows, then hands off
 *   33-45 s  nobody
 */
static bool fake_person_angle(uint32_t t, int32_t *angle_x10) {
  if (t < 3000u) return false;
  if (t < 6000u) {
    *angle_x10 = -200 + (int32_t)(t - 3000u) * 200 / 3000;
    return true;
  }
  if (t < 19000u) {
    *angle_x10 = (int32_t)((t / 700u) % 3u) * 10 - 10; /* small sway */
    return true;
  }
  if (t < 33000u) {
    *angle_x10 = (int32_t)(t - 19000u) / 10; /* 10 deg per second */
    return true;
  }
  return false;
}

static void fake_frame(uint32_t now_ms, frame_t *out) {
  int32_t angle_x10;
  if (!fake_person_angle(now_ms % SCENE_LENGTH_MS, &angle_x10)) return;

  /* Where that lands in the image, given where the camera points. */
  int32_t x = 500 + (angle_x10 - camera_pan_x10) * 1000 / (CAMERA_HFOV_DEG * 10);
  int32_t y = 500 - (PERSON_TILT_X10 - camera_tilt_x10) * 1000 / (CAMERA_VFOV_DEG * 10);
  if (x < 0 || x > 1000 || y < 0 || y > 1000) return; /* outside the view */

  detection_t *d = &out->det[out->count++];
  d->x = (int16_t)x;
  d->y = (int16_t)y;
  d->w = 120;
  d->h = 400;
  d->score = 80;
}
#endif

bool detect_poll(uint32_t now_ms, frame_t *out) {
  if (have_frame && (uint32_t)(now_ms - last_frame_ms) < FRAME_PERIOD_MS) return false;
  have_frame = true;
  last_frame_ms = now_ms;

  memset(out, 0, sizeof(*out));
  out->time_ms = now_ms;
#if USE_FAKE_DETECTIONS
  fake_frame(now_ms, out);
#else
  /* TODO (Devin): copy the boxes from ST's person-detection pipeline into out->det. */
#endif
  return true;
}
```

## 14. `tracker.h`

```c
/*
 * tracker.h - keeps the same ID on the same person from frame to frame.
 *
 * Owner: Devin. Simple version: each box is matched to the nearest person
 * from the last frames. Good enough for one camera; swap in something
 * smarter later without changing the interface.
 */
#ifndef TRACKER_H
#define TRACKER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "detect.h"

#define TRACK_MAX 8

typedef struct {
  bool active;
  uint16_t id;
  int16_t x, y;           /* last position, thousandths of the frame */
  int16_t vx;             /* sideways speed, thousandths of the frame per second */
  uint32_t first_seen_ms;
  uint32_t last_seen_ms;
} track_t;

void tracker_init(void);
void tracker_update(const frame_t *frame);

/* All slots; check .active. Always TRACK_MAX long. */
const track_t *tracker_tracks(void);
size_t tracker_count(void); /* active people */
const track_t *tracker_find(uint16_t id);

#endif /* TRACKER_H */
```

## 15. `tracker.c`

```c
/* tracker.c - nearest-match tracker (see tracker.h). */
#include "tracker.h"

#include <string.h>

#include "app_config.h"

static track_t tracks[TRACK_MAX];
static uint16_t next_id;

void tracker_init(void) {
  memset(tracks, 0, sizeof(tracks));
  next_id = 1;
}

static int32_t dist2(int32_t ax, int32_t ay, int32_t bx, int32_t by) {
  int32_t dx = ax - bx, dy = ay - by;
  return dx * dx + dy * dy;
}

void tracker_update(const frame_t *frame) {
  bool matched[TRACK_MAX] = {false};
  const int32_t max_d2 = (int32_t)TRACK_MATCH_DIST * TRACK_MATCH_DIST;

  for (uint8_t i = 0; i < frame->count; i++) {
    const detection_t *d = &frame->det[i];

    /* Nearest person not already claimed by another box this frame. */
    int best = -1;
    int32_t best_d2 = max_d2 + 1;
    for (int k = 0; k < TRACK_MAX; k++) {
      if (!tracks[k].active || matched[k]) continue;
      int32_t d2 = dist2(d->x, d->y, tracks[k].x, tracks[k].y);
      if (d2 < best_d2) {
        best_d2 = d2;
        best = k;
      }
    }

    if (best >= 0) {
      track_t *t = &tracks[best];
      uint32_t dt = frame->time_ms - t->last_seen_ms;
      if (dt > 0) t->vx = (int16_t)(((int32_t)d->x - t->x) * 1000 / (int32_t)dt);
      t->x = d->x;
      t->y = d->y;
      t->last_seen_ms = frame->time_ms;
      matched[best] = true;
      continue;
    }

    /* Someone new: take a free slot (if none, ignore them this frame). */
    for (int k = 0; k < TRACK_MAX; k++) {
      if (tracks[k].active) continue;
      track_t *t = &tracks[k];
      t->active = true;
      t->id = next_id++;
      if (next_id == 0) next_id = 1; /* 0 means "nobody" elsewhere */
      t->x = d->x;
      t->y = d->y;
      t->vx = 0;
      t->first_seen_ms = frame->time_ms;
      t->last_seen_ms = frame->time_ms;
      matched[k] = true;
      break;
    }
  }

  /* Forget people we haven't seen for a while. */
  for (int k = 0; k < TRACK_MAX; k++) {
    if (tracks[k].active && (uint32_t)(frame->time_ms - tracks[k].last_seen_ms) > TRACK_DROP_MS) {
      tracks[k].active = false;
    }
  }
}

const track_t *tracker_tracks(void) { return tracks; }

size_t tracker_count(void) {
  size_t n = 0;
  for (int k = 0; k < TRACK_MAX; k++) n += tracks[k].active ? 1u : 0u;
  return n;
}

const track_t *tracker_find(uint16_t id) {
  if (id == 0) return NULL;
  for (int k = 0; k < TRACK_MAX; k++) {
    if (tracks[k].active && tracks[k].id == id) return &tracks[k];
  }
  return NULL;
}
```

## 16. `behavior.h`

```c
/*
 * behavior.h - decides when someone is lingering.
 *
 * Owner: Devin. "Lingering" = staying within LINGER_RADIUS of one spot for
 * LINGER_TIME_MS (app_config.h). Each stay is reported once.
 */
#ifndef BEHAVIOR_H
#define BEHAVIOR_H

#include <stdint.h>

#include "tracker.h"

void behavior_init(void);

/* Call once per frame after tracker_update. Returns the ID of someone who
   just started lingering, or 0 if nobody did. */
uint16_t behavior_update(uint32_t now_ms);

#endif /* BEHAVIOR_H */
```

## 17. `behavior.c`

```c
/* behavior.c - lingering check (see behavior.h). */
#include "behavior.h"

#include <stdbool.h>
#include <string.h>

#include "app_config.h"

typedef struct {
  bool used;
  bool anchored; /* has a standing spot been recorded yet */
  bool reported;
  uint16_t id;
  int16_t anchor_x, anchor_y; /* where they started standing */
  uint32_t since_ms;          /* when they started standing there */
} linger_t;

static linger_t slots[TRACK_MAX];

void behavior_init(void) { memset(slots, 0, sizeof(slots)); }

static linger_t *slot_for(uint16_t id) {
  for (int i = 0; i < TRACK_MAX; i++) {
    if (slots[i].used && slots[i].id == id) return &slots[i];
  }
  for (int i = 0; i < TRACK_MAX; i++) {
    if (!slots[i].used) {
      memset(&slots[i], 0, sizeof(slots[i]));
      slots[i].used = true;
      slots[i].id = id;
      return &slots[i];
    }
  }
  return NULL;
}

uint16_t behavior_update(uint32_t now_ms) {
  const track_t *tracks = tracker_tracks();
  const int32_t r2 = (int32_t)LINGER_RADIUS * LINGER_RADIUS;
  uint16_t lingering = 0;

  /* Drop slots for people the tracker has forgotten. */
  for (int i = 0; i < TRACK_MAX; i++) {
    if (slots[i].used && tracker_find(slots[i].id) == NULL) slots[i].used = false;
  }

  for (int k = 0; k < TRACK_MAX; k++) {
    const track_t *t = &tracks[k];
    if (!t->active) continue;

    linger_t *s = slot_for(t->id);
    if (s == NULL) continue;

    int32_t dx = t->x - s->anchor_x, dy = t->y - s->anchor_y;
    if (!s->anchored || dx * dx + dy * dy > r2) {
      /* Just appeared, or moved away: start timing from here. */
      s->anchored = true;
      s->anchor_x = t->x;
      s->anchor_y = t->y;
      s->since_ms = now_ms;
      s->reported = false;
      continue;
    }

    if (!s->reported && (uint32_t)(now_ms - s->since_ms) >= LINGER_TIME_MS && lingering == 0) {
      s->reported = true;
      lingering = t->id;
    }
  }
  return lingering;
}
```

## 18. `pantilt.h`

```c
/*
 * pantilt.h - points the camera with the two servos.
 *
 * Angles are tenths of a degree (x10) so small moves stay smooth.
 * Positive pan = turn right, positive tilt = look up (flip with
 * PAN_REVERSED / TILT_REVERSED in app_config.h if the mount is the other way).
 */
#ifndef PANTILT_H
#define PANTILT_H

#include <stdbool.h>
#include <stdint.h>

#include "herd_msg.h"

void pantilt_init(void);                    /* go to the home position */
void pantilt_home(void);                    /* look straight ahead */
void pantilt_follow(int16_t x, int16_t y);  /* nudge toward a box center (thousandths of the frame) */
void pantilt_look_toward(herd_side_t side); /* turn toward a neighbor's side */
bool pantilt_at_limit(herd_side_t side);    /* turned as far as allowed toward that side? */
void pantilt_update(uint32_t now_ms);       /* call every loop: moves the servos, speed-limited */

int32_t pantilt_pan_x10(void);
int32_t pantilt_tilt_x10(void);

/* Servo pulse for an angle, clamped to SERVO_MIN_US..SERVO_MAX_US. */
uint16_t pantilt_angle_to_us(int32_t angle_x10);

#endif /* PANTILT_H */
```

## 19. `pantilt.c`

```c
/* pantilt.c - camera aiming (see pantilt.h). */
#include "pantilt.h"

#include "app_config.h"
#include "board.h"

#define PAN_MIN_X10 (PAN_MIN_DEG * 10)
#define PAN_MAX_X10 (PAN_MAX_DEG * 10)
#define TILT_MIN_X10 (TILT_MIN_DEG * 10)
#define TILT_MAX_X10 (TILT_MAX_DEG * 10)
#define LIMIT_SLACK_X10 10 /* within 1 degree of the limit counts as "at the limit" */

static int32_t pan_x10, tilt_x10;               /* where the servos are now */
static int32_t pan_target_x10, tilt_target_x10; /* where they're heading */
static uint32_t last_update_ms;
static bool started;

static int32_t clamp(int32_t v, int32_t lo, int32_t hi) { return v < lo ? lo : (v > hi ? hi : v); }

uint16_t pantilt_angle_to_us(int32_t angle_x10) {
  const int32_t mid = (int32_t)(SERVO_MIN_US + SERVO_MAX_US) / 2;
  const int32_t span = (int32_t)(SERVO_MAX_US - SERVO_MIN_US);
  int32_t us = mid + angle_x10 * span / 1800; /* 1800 = 180 degrees in tenths */
  return (uint16_t)clamp(us, (int32_t)SERVO_MIN_US, (int32_t)SERVO_MAX_US);
}

static void write_servos(void) {
  board_servo_write_us(BOARD_SERVO_PAN, pantilt_angle_to_us(PAN_REVERSED ? -pan_x10 : pan_x10));
  board_servo_write_us(BOARD_SERVO_TILT, pantilt_angle_to_us(TILT_REVERSED ? -tilt_x10 : tilt_x10));
}

void pantilt_init(void) {
  pan_x10 = tilt_x10 = 0;
  pan_target_x10 = tilt_target_x10 = 0;
  started = false;
  write_servos();
}

void pantilt_home(void) { pan_target_x10 = tilt_target_x10 = 0; }

void pantilt_follow(int16_t x, int16_t y) {
  /* How far off-center the box is, as an angle. */
  int32_t err_pan = ((int32_t)x - 500) * CAMERA_HFOV_DEG * 10 / 1000;
  int32_t err_tilt = (500 - (int32_t)y) * CAMERA_VFOV_DEG * 10 / 1000; /* up is positive */
  pan_target_x10 = clamp(pan_x10 + err_pan * FOLLOW_GAIN_PCT / 100, PAN_MIN_X10, PAN_MAX_X10);
  tilt_target_x10 = clamp(tilt_x10 + err_tilt * FOLLOW_GAIN_PCT / 100, TILT_MIN_X10, TILT_MAX_X10);
}

void pantilt_look_toward(herd_side_t side) {
  pan_target_x10 = (side == HERD_SIDE_RIGHT) ? EXPECT_PAN_DEG * 10 : -EXPECT_PAN_DEG * 10;
  tilt_target_x10 = 0;
}

bool pantilt_at_limit(herd_side_t side) {
  if (side == HERD_SIDE_RIGHT) return pan_x10 >= PAN_MAX_X10 - LIMIT_SLACK_X10;
  return pan_x10 <= PAN_MIN_X10 + LIMIT_SLACK_X10;
}

static int32_t step_toward(int32_t now, int32_t target, int32_t max_step) {
  if (target > now) return (target - now > max_step) ? now + max_step : target;
  return (now - target > max_step) ? now - max_step : target;
}

void pantilt_update(uint32_t now_ms) {
  if (!started) {
    started = true;
    last_update_ms = now_ms;
    return;
  }
  uint32_t dt = now_ms - last_update_ms;
  int32_t max_step = (int32_t)(SERVO_MAX_SPEED_DPS * 10 * dt / 1000u);
  if (max_step == 0) return; /* not enough time passed to move; keep the remainder */
  last_update_ms = now_ms;

  int32_t new_pan = step_toward(pan_x10, pan_target_x10, max_step);
  int32_t new_tilt = step_toward(tilt_x10, tilt_target_x10, max_step);
  if (new_pan != pan_x10 || new_tilt != tilt_x10) {
    pan_x10 = new_pan;
    tilt_x10 = new_tilt;
    write_servos();
  }
}

int32_t pantilt_pan_x10(void) { return pan_x10; }
int32_t pantilt_tilt_x10(void) { return tilt_x10; }
```

## 20. `link.h`

```c
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
```

## 21. `link.c`

```c
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
```

## 22. `unit_fsm.h`

```c
/*
 * unit_fsm.h - the Use case 1 flowchart as a state machine.
 *
 *   WATCHING    nobody targeted, camera at home. Someone lingers -> TRACKING.
 *   TRACKING    follow the target. Target reaches the edge with the camera
 *               turned as far as it goes -> tell that neighbor "heading your
 *               way" -> HANDING_OFF. Target vanishes elsewhere -> LOST.
 *   HANDING_OFF wait for the neighbor's TAKEN_OVER -> WATCHING.
 *               No answer in time -> LOST -> WATCHING.
 *   EXPECTING   a neighbor said "heading your way": turn toward that side
 *               and wait. A new person appears -> TAKEN_OVER -> TRACKING.
 *               Nobody in time -> LOST -> WATCHING.
 */
#ifndef UNIT_FSM_H
#define UNIT_FSM_H

#include <stdint.h>

#include "herd_msg.h"

typedef enum { UNIT_WATCHING = 0, UNIT_TRACKING, UNIT_HANDING_OFF, UNIT_EXPECTING } unit_state_t;

void fsm_init(void);
void fsm_on_frame(uint16_t lingering_id, uint32_t now_ms);   /* after tracker + behavior each frame */
void fsm_on_message(const herd_msg_t *m, uint32_t now_ms);  /* from link */
void fsm_on_send_failed(const herd_msg_t *m, uint32_t now_ms); /* from link: no ACK */
void fsm_tick(uint32_t now_ms);                             /* every loop: timeouts */

unit_state_t fsm_state(void);
uint16_t fsm_target(void); /* tracker ID of the person being followed, 0 if none */
const char *fsm_state_name(unit_state_t s);

#endif /* UNIT_FSM_H */
```

## 23. `unit_fsm.c`

```c
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
```
