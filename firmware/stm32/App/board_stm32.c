/*
 * board_stm32.c - board.h for the NUCLEO-N657X0-Q, using ST's HAL.
 *
 * Uses what CubeMX generates in main.c (see Docs/software/stm32-skeleton-setup.md):
 * - huart1: USART1 on PE5/PE6, the ST-LINK USB virtual COM port. Used for the debug log.
 * - huart3: USART3, PD8 = TX (Arduino D1), PD9 = RX (Arduino D0). Used for the ESP32.
 *   Its "global interrupt" must be enabled in CubeMX.
 * - htim1: TIM1 CH1 on PE9 (Arduino D3) for the pan servo,
 *   and TIM1 CH2 on PE11 (Arduino D7) for the tilt servo.
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
