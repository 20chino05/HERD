# Open Herd – Draft Parts List (v1)

> **Day-0 draft (October 16, 2026).** Built from the team's brainstorm hardware list and voice memo,
> plus a first round of online research. Only the STM32N6 board is reported as bought. (Pay Samuel lol)
> The options below are candidates to look at, not choices. Prices are from store and distributor
> listings seen on October 16, 2026; they change, so check them before ordering.
>
> **Updated October 19, 2026** for the security camera swarm demo. Parts marked **(disclaimer)**
> come from the new use case. The hardware team (Nader and Samuel) decides whether and how to use them.

**Status values:** **Bought** · **On hand** · **To buy** (need is clear, part not chosen) · **To research** · **Maybe**

"(disclaimer)" marks parts that come from the October 19 use case. The hardware team decides on them.

## Phase 1: Dev board prototype (per device)

| Part | What it's for | Status | Options found so far | Price seen | Notes |
|---|---|---|---|---|---|
| STM32N6 dev board (NUCLEO-N657X0-Q) | Runs the AI | Bought (per the voice memo) | — | ~$75 (ST store) | Confirm the exact board and how many were bought. |
| Camera module | Captures video | To buy, with school funding | ST-supported cameras that plug into the board: B-CAMS-IMX (5 MP color), STEVAL-66GYMAI1 (1.5 MP color), STEVAL-55G1MBI1 (0.56 MP black-and-white) | ~$57–84 depending on module and store | Every unit needs one. A color camera likely suits appearance matching better. See "Camera" below. |
| LoRa radio module | Short alerts; the V1 radio in the hardware plan (role depends on the hardware team's call) | Maybe (disclaimer) | RAK3172 or Seeed Wio-E5 (simple text commands over a serial port); SX1262 modules as a backup | ~$7–10 | With ESP-NOW handling messages, LoRa may not be needed. Needs a 915 MHz antenna too. |
| ESP32 board | Sends handoff messages between units over ESP-NOW | On hand (per the hardware plan) | The ESP32s the team already has; more if needed (e.g. Seeed XIAO ESP32C3) | On hand; ~$5 if more are needed | One per unit. Confirm how many the team has. See "Messages between units" below. |
| Pan/tilt mount with two micro servos | Turns the camera to follow a person | To research (disclaimer) | SparkFun ROB-14391 kit; Adafruit Mini Pan-Tilt Kit 1967 (comes with two micro servos) | ~$11.50–19 (online snapshots) | Only the camera board would move, so its ribbon cable flexes. See "Pan/tilt" below. |
| Servo power supply | Powers the servos separately from the board | To research (disclaimer) | A 5 V, 2 A or larger supply sharing a ground with the board | ~$8 | Servos can draw large spikes of current. See "Pan/tilt" below. |
| Video link to the central station | Gets each unit's video to the recording laptop | To research (disclaimer) | V0: a USB cable to a laptop, using ST's built-in USB webcam output. Later: the Nucleo's Ethernet port, or Wi-Fi | Cables; ~$20–40 for a small switch or router if Ethernet | See "Video to the central station" below. |
| Power | Runs the device | To research | USB-C wall power for the first prototype; battery + charger only if off-grid | Charger board seen at ~$20 | See "Power" below. |
| Case | Protects the device | To research | 3D-printed case indoors; sealed box outdoors | TBD | See "Case" below. |

**Shared (not per unit):** the central station that records video and logs events can be a team
laptop ($0).

**Rough Phase 1 cost per unit:** about $160–190 with a color camera, for the board, camera, pan/tilt
kit, servo supply, and ESP32, before power parts, cables, the case, tax, and shipping. Camera prices
are snapshots, and one may not be in US dollars. Keeping LoRa adds about $7–10 plus an antenna. One
board is already bought. The advisor's October 12 note was to watch costs closely.

**How many units?** Not decided. A handoff needs at least two complete units, and a chain needs three.

## Notes on each part

### Dev board
- The NUCLEO-N657X0-Q has a camera connector, but ST's documents suggest the camera does **not**
  come with it (the IMX335 camera comes with the pricier Discovery kit). This would explain the voice
  memo saying both "it does have a camera" and "the camera we will buy."
- It has a built-in programmer/debugger and is powered and programmed over USB-C.
- It has no screen. ST's examples show the camera and AI output on a laptop over USB.
- The STM32N6 chip has no built-in flash memory. Programs go into the board's external flash, set
  with two jumpers. This matters for the custom board too.

### Camera
- The board's camera connector uses MIPI CSI-2. ST's example projects already support the three
  modules listed above on this board, which is the fastest path to a working demo.
- A parallel camera (like the cheap OV2640 or OV5640) is possible with the chip, but ST has no
  example for it on this board, so it would take extra driver work.
- Stock varies a lot: one Digi-Key snapshot showed a 99-week lead time for the B-CAMS-IMX, while
  Mouser showed units in stock. Order early from a store that shows real stock. The STEVAL-66GYMAI1
  (color) could be the backup (hardware team to decide).
- Appearance matching probably relies on clothing color, so a color camera is the better bet than
  the black-and-white one (an inference, not measured).
- ST's re-identification example for this board supports these same cameras.

### LoRa and ESP-NOW
- Handoff messages like "person heading your way" are tiny, about 10–30 bytes. ESP-NOW carries up
  to 250 bytes per message, or 1470 bytes on the newer version 2 (which needs a recent ESP32 core).
  Sending a person's appearance signature (1280 bytes from ST's example) needs ESP-NOW version 2 on
  every ESP32, or splitting it into six 250-byte messages.
- ESP-NOW is too slow for continuous video: Espressif measured about 214 kbps in open space at the
  default rate, roughly one small snapshot per second at best.
- LoRa is also made for short messages. A small 10 KB photo would take about 17 seconds of airtime at
  the fastest common settings. With ESP-NOW handling messages, LoRa may only be useful as a backup.
- If LoRa is kept, there are two ways to set it up: devices talk directly to a receiver the team
  builds ("peer-to-peer"), or they use LoRaWAN, which needs a gateway (one listing: ~$234) and
  network software. Not decided.

### Pan/tilt (new, disclaimer)
- Small hobby pan/tilt kits are sized for a small camera board, so the plan assumes only the camera
  moves and the Nucleo stays put. The camera's 22-pin ribbon cable would then flex with every move.
  Its length and how well it holds up aren't verified.
- A micro servo drew up to about 650 mA when stalled in one test (other sources vary), and the
  servos in the chosen kit aren't confirmed. Sources recommend a separate 5 V supply that shares a
  ground with the board.
- The board can make servo control signals with its timers. ST has a PWM example for this board.

### Video to the central station (new, disclaimer)
- Simplest for V0: ST's example app already shows up as a USB webcam (320x240) on a laptop, which
  can record it. This keeps each unit within about 5 m of the laptop. Each unit would use two USB
  cables, one for power and logs and one for video. Two or three units may not stream into one
  laptop at once; separate ports only help if they're on separate USB controllers. Fallbacks are a
  second laptop or a firmware setting change (untested). This should be tested early.
- Longer distances: the Nucleo has an Ethernet port, and ST has network examples for it, but no
  example of sending video over it. ST's examples get their network address from a router (DHCP),
  and each board needs its own MAC address set. Wi-Fi through the ESP32 would need custom firmware.
- ST's hardware video encoder examples only target the Discovery kit, not the Nucleo.

### Power
- ST powers the board from USB-C in its examples, so wall power is the simplest start.
- ST measured about 0.27 W for the chip's core alone while running a small AI model. One common
  18650 battery cell (about 12 Wh) couldn't run even that for much more than two days. An off-grid
  device would likely need to sleep between checks, use a bigger battery, or add a small solar panel.
- A ready-made charger board that takes USB or solar input (for example, Adafruit's bq24074 board)
  avoids designing battery charging from scratch.
- The whole device (board + camera + radio) hasn't been measured yet. A USB-C power meter would do it.

### Case
- Indoors, a simple 3D-printed case is probably enough.
- Outdoors: look for an IP65 (dust-tight, handles water jets) or IP67 (survives brief dunking)
  rating, a clear UV-resistant window for the camera, a vent to stop fogging, and room for heat to escape.

## Phase 2: Custom board

The team's own board, replacing the dev board. Its goals are to be cheaper, mass-producible,
easier to tune, and probably smaller. Nothing is designed yet.

It would combine:

- The STM32N6 chip, plus external flash memory (the chip has none built in)
- A camera connector (CSI-2 or parallel, matching Phase 1)
- A radio for messages between units (an ESP32 module or LoRa; the hardware team decides)
- Power circuitry (USB and/or battery). ST's application note AN6000 covers the chip's power supply options.
- **New (disclaimer):** a servo header and a 5 V servo supply if pan/tilt is kept, and Ethernet or
  Wi-Fi if units need to sit far from the central station. These make the hardware plan's ~$100-per-unit V1 target harder.

The SAFE-Swarm plan used JLCPCB to make and assemble its custom board. The same or a similar
service could work here.

## Not needed anymore

The SAFE-Swarm drone parts (frame, motors, ESC, flight controller, ELRS radio) aren't part of
Open Herd. The team's notes only mention buying the STM32N6 board. Whether a device needs GPS is
an open question in the proposal.
The old parts lists are in [legacy/](../legacy/README.md).

## Budget

Not set. The voice memo says the camera would be bought with school funding. At the October 12
meeting, the advisor said to watch costs closely so they don't balloon.

## Sources

- Board, camera support, and setup: [STM32N6-GettingStarted-ObjectDetection](https://github.com/STMicroelectronics/STM32N6-GettingStarted-ObjectDetection), [ST's N6 deployment guide](https://github.com/STMicroelectronics/stm32ai-modelzoo-services/blob/main/object_detection/docs/README_DEPLOYMENT_STM32N6.md), [STM32CubeN6](https://github.com/STMicroelectronics/STM32CubeN6)
- Power measured by ST: [x-cube-n6-ai-power-measurement](https://github.com/STMicroelectronics/x-cube-n6-ai-power-measurement/blob/main/Utilities/pwr_scripts/README.md)
- LoRa modules: [RAK3172 datasheet](https://raw.githubusercontent.com/RAKWireless/rakwireless-docs/master/docs/Product-Categories/WisDuo/RAK3172-Module/Datasheet/README.md), [Seeed Wio-E5](https://raw.githubusercontent.com/Seeed-Studio/wiki-documents/docusaurus-version/sites/en/docs/Network/LoRa_Wio_Series/Wio-E5/LoRa-E5_STM32WLE5JC_Module.md)
- Wi-Fi: [Seeed XIAO ESP32C3 (RobotShop)](https://www.robotshop.com/products/seeedstudio-xiao-esp32c3-tiny-mcu-w-wi-fi-ble)
- Charger: [Adafruit bq24074 charger](https://www.adafruit.com/product/4755)
- Camera price example: [B-CAMS-IMX at Digi-Key](https://www.digikey.com/en/products/detail/stmicroelectronics/B-CAMS-IMX/24737934)
- Re-identification example for this board: [STM32N6-GettingStarted-ReID](https://github.com/STMicroelectronics/STM32N6-GettingStarted-ReID)
- ESP-NOW message sizes and speed: [ESP-IDF ESP-NOW docs](https://github.com/espressif/esp-idf/blob/master/docs/en/api-reference/network/esp_now.rst), [Espressif ESP-NOW FAQ](https://raw.githubusercontent.com/espressif/esp-faq/master/docs/en/application-solution/esp-now.rst)
- Pan/tilt kits: [SparkFun ROB-14391](https://www.sparkfun.com/pan-tilt-bracket-kit-single-attachment.html), [Adafruit 1967](https://www.adafruit.com/product/1967); servo current: [ProtoSupplies SG92R](https://protosupplies.com/product/servo-motor-micro-sg92r/)
- Other prices: ST eStore, Future Electronics, Mouser, Rokland, and Jameco listings, checked October 16, 2026; pan/tilt and supply prices are search snapshots seen October 19, 2026
