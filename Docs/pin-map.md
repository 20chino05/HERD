# Open Herd unit: pin map (NUCLEO-N657X0-Q)

Every pin the unit firmware uses now, and the ones it is planned to use. Both units use the same
pins. "D" numbers are the Arduino-style header labels printed on the board. CN15 positions come from
ST's own example projects and forum answers for this board. Confirm anything marked **TBD** before
wiring it.

All STM32 signal pins are **3.3 V logic**. Never connect 5 V to a signal pin.

## In use now (set up in CubeMX, running in the firmware)

| What | STM32 pin | Header | Peripheral | Settings | Wire to |
|---|---|---|---|---|---|
| Link to ESP32, TX | PD8 | D1 (CN15 pin 37) | USART3_TX | 115200, 8N1 | ESP32 **RX** |
| Link to ESP32, RX | PD9 | D0 (CN15 pin 35) | USART3_RX | 115200, 8N1, interrupt on | ESP32 **TX** |
| Pan servo signal | PE9 | D3 (CN15 pin 31) | TIM1_CH1 | 50 Hz PWM, 1.0–2.0 ms pulse | pan servo signal wire |
| Tilt servo signal | PE11 | D7 (CN15 pin 23) | TIM1_CH2 | 50 Hz PWM, 1.0–2.0 ms pulse | tilt servo signal wire |
| Debug log | PE5 / PE6 | none (inside ST-LINK) | USART1 | 115200, 8N1 | nothing: goes over the CN9 USB cable to the laptop |
| Heartbeat LED | PG0 | onboard green LED | GPIO output | toggles every 0.5 s | nothing |
| Power, programming, debug | CN9 (USB-C) | ST-LINK port | ST-LINK | | laptop, USB-C to USB-C data cable |
| Ground | GND | any GND pin | | | ESP32 GND, servo supply GND |

Boot switch for development: **BOOT1 at 2-3** (BOOT0 doesn't matter).

## Planned

| What | Where | Status | Notes |
|---|---|---|---|
| Camera (InnoMaker CAM-IMX335-5MP) | the board's 22-pin MIPI CSI-2 ribbon connector | **TBD: check pinout first** | Third-party module, not ST's B-CAMS-IMX. Compare its pinout with the board's camera connector before plugging in. The camera's control lines (I2C, enable, reset) run through this same connector and are set by ST's camera driver. |
| Camera video to the laptop | CN8 (USB-C, next to the Ethernet jack) | planned | ST's demos send video here as a USB webcam. Not used by the skeleton yet. |
| Servo power | external 5 V supply, 2 A or more | **TBD (hardware team)** | Red and brown/black servo wires go to this supply, **not** to the board. Tie its GND to the board's GND. Most hobby servos accept a 3.3 V signal; check the datasheet. |
| ESP32 UART pins | ESP32 side | **TBD: depends on the ESP32 board model** | For a classic ESP32 DevKit, UART2 on GPIO16 (RX) / GPIO17 (TX) is a common choice. Wire ESP32 RX ← Nucleo D1 and ESP32 TX → Nucleo D0, plus GND. |
| LoRa radio (Winter) | probably a second UART | **TBD** | Pick free pins in CubeMX when the module is chosen (e.g. RAK3172 talks over a UART). |
| Extra sensors (advisor's suggestion) | TBD | idea only | Nothing chosen yet. |

## Don't use these for anything else

- **PE5 / PE6**: the ST-LINK virtual COM port (the debug log).
- **CN8 USB** and **the camera connector**: reserved for video and the camera.
- **The debug (SWD) pins and the external flash (XSPI) pins**: CubeMX marks these. Reusing them breaks programming or booting from flash.
- **D1 / D0** are only for the ESP32 link. To test that port without an ESP32, put a jumper from D1 to D0; the log's `echo=` count goes up.

## Sources

- ST's NUCLEO-N657X0-Q examples in STM32CubeN6: UART_Printf (USART1 on PE5/PE6 is the ST-LINK port), TIM_PWMOutput (TIM1 CH1/CH2 on PE9/PE11, CN15 pins 31/23), and the board's LED definitions (green LED on PG0).
- Zephyr's board files for this Nucleo: Arduino D0 = PD9, D1 = PD8, D3 = PE9, D7 = PE11, Arduino serial = USART3.
- ST Community: USART3 TX/RX on PD8/PD9 at CN15 pins 37/35.
