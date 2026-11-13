# STM32 unit skeleton: setup from a blank Mac to a running board

Goal: the Open Herd skeleton running on a NUCLEO-N657X0-Q. When it works you'll see the
green LED blinking and a log on your Mac showing a fake person being spotted, tracked and handed
off. No camera, ESP32 or servos are needed for this.

Time: about 1 hour, most of it downloads.

What the code does is in [the summary at the end](#what-the-code-does). The code is in
`firmware/common/` and `firmware/stm32/App/`.

---

## Part 1. Install the tools (once)

All three are free downloads from st.com. You'll need a free myST account to download.

1. **STM32CubeMX**: search "STM32CubeMX", download the macOS version, run the installer.
2. **STM32CubeIDE** (version 2.x): search "STM32CubeIDE", download the macOS version, install.
3. **STM32CubeProgrammer**: search "STM32CubeProgrammer", download the macOS version, install.
   CubeIDE uses its drivers to talk to the board.

If macOS blocks an installer, go to **System Settings → Privacy & Security** and click **Open Anyway**.

Keep every folder you use for this **free of spaces** (for example `~/herd`). ST's tools can
break on paths with spaces.

## Part 2. Get the code

On GitHub, open the `20chino05/SAFE-Swarm` repo, switch to the branch
`claude/safe-swarm-senior-design-i9elpx` (or `main` once it's merged), click
**Code → Download ZIP**, and unzip it. You'll need two folders from it later:

- `firmware/common/` (4 files)
- `firmware/stm32/App/` (all the files)

## Part 3. Set up the board

1. Find the two small **BOOT** switches on the board. Set **BOOT1 to position 2-3**.
   That's **development mode**: the code runs from memory and is gone when you unplug, which
   is what you want while testing. BOOT0 doesn't matter.
   (This is the setting ST's own examples for this board use.)
2. Plug a **USB-C to USB-C** cable into **CN9** (labeled ST-LINK) and straight into your Mac.
   Don't use a USB-A adapter, because ST says it may not give the board enough power.
   Leave the other USB-C port (CN8) empty.
3. Leave the camera unplugged for now.

## Part 4. Make the project in CubeMX

1. Open CubeMX → **File → New Project** → the **Board Selector** tab.
2. Type `NUCLEO-N657X0-Q`, select it, click **Start Project**.
   - "Initialize all peripherals with their default Mode?" → **No**.
   - Any other pop-up: keep the default.
3. You're now on **Pinout & Configuration**. Set up three things on the left.

   For each one, if you see **Runtime contexts** checkboxes, tick **FSBL** (it may say "First
   Stage Boot Loader"). FSBL is the part of the program that runs in development mode.

   **a. USART1: the log to your Mac**
   - Connectivity → **USART1** → Mode: **Asynchronous**.
   - In the chip picture, check that **PE5** shows USART1_TX and **PE6** shows USART1_RX. If not,
     click PE5 → choose USART1_TX, and click PE6 → choose USART1_RX.
   - Parameter Settings: Baud Rate **115200**, Word Length **8 Bits**, Parity **None**, Stop Bits **1**.

   **b. USART3: the wire to the ESP32 (Arduino pins D1/D0)**
   - Connectivity → **USART3** → Mode: **Asynchronous**.
   - Pins: **PD8** = USART3_TX and **PD9** = USART3_RX. Fix them by clicking if CubeMX picked others.
   - Parameter Settings: **115200**, **8 Bits**, **None**, **1**.
   - **NVIC Settings** tab: tick **USART3 global interrupt**. Without it, the board never hears the ESP32.

   **c. TIM1: the servos (Arduino pins D3 and D7)**
   - Timers → **TIM1** → Clock Source: **Internal Clock**.
   - Channel1: **PWM Generation CH1**, Channel2: **PWM Generation CH2**.
   - Pins: **PE9** = TIM1_CH1 and **PE11** = TIM1_CH2. Fix them by clicking if needed.
   - Leave the prescaler and period alone. The code measures the timer clock and sets them itself.

4. **Clock Configuration** tab: don't change anything.
5. **Project Manager** tab:
   - Project Name: `herd_unit`. Project Location: a folder without spaces (e.g. `~/herd`).
   - Toolchain / IDE: **STM32CubeIDE**.
   - If it offers which parts to generate (FSBL / Appli / ExtMemLoader), keep **only FSBL**.
   - Code Generator (left side): leave "Generate peripheral initialization as a pair of .c/.h
     files" **unticked**.
6. Click **GENERATE CODE**. If it asks to download the STM32N6 software pack, say yes. When it
   finishes, close the pop-up. You can keep CubeMX open.

## Part 5. Open it in CubeIDE and add the code

1. Open CubeIDE and pick a workspace folder (no spaces, e.g. `~/herd-workspace`).
2. **File → Import → General → Existing Projects into Workspace → Next**.
   Root directory: browse to `~/herd/herd_unit/STM32CubeIDE`. Tick the project ending in **FSBL**,
   then **Finish**.
3. Build it once as-is to make sure the empty project is fine: select the project, click the
   **hammer**. The Console should end with `Build Finished. 0 errors`.
4. **Copy the code in.** In Finder, open `~/herd/herd_unit/STM32CubeIDE/FSBL/` (the folder with
   `.project` in it; press Cmd+Shift+. to see hidden files). Make a new folder there named
   **`App`**. Copy into it:
   - every file from `firmware/common/`
   - every file from `firmware/stm32/App/`

   That's 23 files, all in one folder, no subfolders.
5. Back in CubeIDE, right-click the project → **Refresh**. An `App` folder appears in the project.
6. **Add the include path.** Right-click the project → **Properties** → **C/C++ Build → Settings**
   → **Tool Settings** → **MCU/MPU GCC Compiler → Include paths**. Click the green **+**, type
   `../App`, OK, then **Apply and Close**.
7. **Edit main.c.** In the project tree, open **Application → User → main.c** (or search for it
   with Cmd+Shift+R). Add three lines, each **between** the comment pair shown. CubeMX only keeps
   your code if it's between a BEGIN/END pair:

   ```c
   /* USER CODE BEGIN Includes */
   #include "app_main.h"
   /* USER CODE END Includes */
   ```

   ```c
     /* USER CODE BEGIN 2 */
     app_init();
     /* USER CODE END 2 */
   ```

   Inside `while (1)`:

   ```c
       /* USER CODE BEGIN 3 */
       app_loop();
     }
     /* USER CODE END 3 */
   ```

   (For the last one, only add the `app_loop();` line. The `}` is already there.)
8. Save, then build with the **hammer**. You want `0 errors`. If not, see Troubleshooting.

## Part 6. Run it

1. Right-click the project → **Debug As → STM32 C/C++ Application**. Accept the defaults (OK).
   If it offers to update the ST-LINK firmware, say yes, then try again.
2. CubeIDE loads the code onto the board and pauses at the start of `main`. Press **Resume**
   (the green play button, or F8).
3. The **green LED** starts blinking (on and off about once a second).
4. **See the log.** Open Terminal on your Mac:

   ```sh
   ls /dev/cu.usbmodem*
   screen /dev/cu.usbmodemXXXX 115200
   ```

   Use the name the first command printed. To quit `screen`, press **Ctrl-A**, then **K**, then **Y**.

   You should see something like this (times in milliseconds; the scene repeats every 45 s):

   ```
   [     51] board: servo timer clock measured at about 400 MHz, servos on D3 (pan) and D7 (tilt)
   [     51] Open Herd unit 1 starting (left neighbor 0, right neighbor 2, fake detections ON)
   [   1051] status: WATCHING target=0 people=0 pan=0 tilt=0 | link sent=2 ...
   [  13200] LINGERING: person 1, start tracking
   [  13200] state: WATCHING -> TRACKING
   [  29300] HANDOFF: person 1 leaving right, telling unit 2 "heading your way"
   [  29550] link: no ACK yet for HEADING to unit 2, resending (1/3)
   [  30300] link: no ACK from unit 2 for HEADING, giving up
   [  30300] LOST person 1 (neighbor never answered)
   [  30300] state: HANDING_OFF -> WATCHING
   ```

   "Giving up" is expected: there's no second unit yet to answer. That's the skeleton working.

The clock number depends on your clock settings, so it may not say 400. That's fine.

## Part 7. Using it later

- **Second board:** in `App/app_config.h` set `UNIT_ID 2`, `NEIGHBOR_LEFT_ID 1`,
  `NEIGHBOR_RIGHT_ID HERD_ID_NONE`. Everything else is the same.
- **Changing CubeMX settings:** edit the `.ioc`, click Generate again. Your `App` folder and the
  three lines in main.c are kept.
- **Updating the code:** copy the new files over the old ones in `App`, then Refresh and build.
- **ESP32 wire (later, with the ESP32 code):**
  - Nucleo **D1** (PD8, TX) → ESP32 **RX**
  - Nucleo **D0** (PD9, RX) → ESP32 **TX**
  - **GND** → **GND**

  Both run at 3.3 V, so no converter is needed.
- **Servos (later, once Nader has the mount):** signal wires to **D3** (pan) and **D7** (tilt). Power
  the servos from their **own 5 V supply**, never from the board, and connect that supply's GND to
  the board's GND. The code uses a safe 1.0–2.0 ms pulse range. Widen `SERVO_MIN_US` and
  `SERVO_MAX_US` in `app_config.h` only after checking the servo datasheet.
- **Real detections:** Devin replaces the fake part of `detect.c` and sets
  `USE_FAKE_DETECTIONS 0`. Nothing else changes.

## Troubleshooting

- **`undefined reference to huart3` (or `huart1`, `htim1`)**: that peripheral isn't turned on
  for FSBL in CubeMX. Turn it on (Part 4), Generate, then build again.
- **`app_main.h: No such file`**: the include path is missing or wrong (Part 5 step 6), or the
  files went into a subfolder of `App`.
- **`multiple definition of HAL_UART_RxCpltCallback`**: something else in the project also
  defines it. Keep the one in `App/board_stm32.c`.
- **LED blinks but no log**: check the `screen` command used 115200 and the right
  `/dev/cu.usbmodem...`, and that USART1 is on PE5/PE6.
- **No LED, no log**: check BOOT1 is at 2-3, then unplug and replug the cable and start
  Debug again. Remember development mode forgets the program when unplugged.
- **Log says "TIM1 isn't counting"**: TIM1 or its channels aren't set up (Part 4c). The rest still runs.

## Optional: run the laptop tests

The logic (everything except `board_stm32.c`) has tests that run on a Mac with no board:

```sh
xcode-select --install   # once, if you don't have a compiler
make -C firmware/tests
make -C firmware/tests VERBOSE=1   # also prints the unit's log
```

## What the code does

| File | What it's for |
|---|---|
| `app_main.c/.h` | Startup and the main loop. Each pass: read messages, process a new frame, check timeouts, move the servos, and once a second send a status message and blink the LED. |
| `app_config.h` | Settings: unit ID, neighbors, timings, camera field of view, servo limits. |
| `detect.c/.h` | People boxes per frame. Fake for now: one person walks in, lingers, walks off to the right. Devin's. |
| `tracker.c/.h` | Keeps the same ID on the same person from frame to frame. Devin's. |
| `behavior.c/.h` | Flags someone who stays in one spot for 8 s. Devin's. |
| `unit_fsm.c/.h` | The flowchart: watching, tracking, handing off, expecting someone from a neighbor. |
| `pantilt.c/.h` | Turns the camera to keep the person centered, at a limited speed, and knows when it's at its turn limit. |
| `link.c/.h` | Sends and receives messages to the ESP32, resends anything that isn't confirmed (ACKed), and ignores repeats. |
| `log.c/.h` | Debug printing to your Mac. |
| `board.h`, `board_stm32.c` | The only code that touches the hardware: LED, serial ports, servo timer. |
| `herd_msg.c/.h` (common) | The message format shared by the STM32, the ESP32 and the laptop station. |
| `herd_frame.c/.h` (common) | Wraps messages for the serial wire, with an error check so corrupted messages are thrown away. |

Pins used on the NUCLEO-N657X0-Q come from ST's board files and example projects: USART1 on
PE5/PE6 is the ST-LINK virtual COM port, USART3 on PD8/PD9 is Arduino D1/D0, TIM1 CH1/CH2 on
PE9/PE11 is Arduino D3/D7, and the green LED is PG0.
