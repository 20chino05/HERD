# Open Herd unit skeleton on the STM32: setup and test plan

**What you need:** the NUCLEO-N657X0-Q board, one USB cable, your Mac, and the code:
**`herd_unit_App.zip`** (23 files). If you can't use the zip, the same files are in
`stm32-skeleton-files.md`, ready to paste.

**What you get:** the unit's software running on the board with made-up people in place of the
camera. It spots someone lingering, follows them, tries to hand them off to the next unit, and
prints everything it does to your Mac. No camera, ESP32 or servos are needed.

**Time:** about an hour, mostly downloads. Keep every folder name **free of spaces**
(e.g. `~/herd`), because ST's tools can break on them.

---

## 1. Install the three ST apps (once)

1. From the Mac home screen, open **Safari** and go to **st.com**. Make a free **myST** account
   (top right) if you don't have one. Downloads need it.
2. Search **STM32CubeMX** → **Get Software** → the **macOS** version → open the download and run the installer.
3. Search **STM32CubeIDE** → the **macOS** version (2.x) → install it (drag it to Applications if asked).
4. Search **STM32CubeProgrammer** → the **macOS** version → install. CubeIDE uses its board drivers.
5. If macOS says an app "can't be opened": **System Settings → Privacy & Security → Open Anyway**.

## 2. Set up the board

1. Find the two small **BOOT0 / BOOT1** switches. Put **BOOT1 at 2-3** (development mode: the
   program runs from memory and disappears when unplugged, which is right for testing).
   BOOT0 doesn't matter.
2. Plug the USB cable into **CN9** (marked ST-LINK) and into the Mac. LEDs on the board light up.
3. Leave the other USB port (CN8) and the camera unplugged.

## 3. Unzip the code

Download **`herd_unit_App.zip`** from the chat to your Mac and double-click it. You now have a
folder called **`App`** with 23 files. Leave it in Downloads for now.

## 4. Make the project in CubeMX

1. **Launchpad → STM32CubeMX.** Choose **File → New Project**. It may download a list
   first; wait for it.
2. Click the **Board Selector** tab, type `NUCLEO-N657X0-Q`, click the board in the list, then
   **Start Project** (top right).
   - "Initialize all peripherals with their default Mode?" → **No**.
   - Any other pop-up → keep the default.
3. You're on **Pinout & Configuration**, with a picture of the chip in the middle. Set up three
   things from the list on the left. For each one, if you see **Runtime contexts** checkboxes,
   tick **FSBL** (may be labeled "First Stage Boot Loader").

   **USART1: the log to your Mac**
   - Connectivity → **USART1** → Mode **Asynchronous**.
   - On the chip picture, **PE5** should say USART1_TX and **PE6** USART1_RX. If not, click the pin
     and choose that function.
   - **Parameter Settings**: Baud Rate **115200**, Word Length **8 Bits**, Parity **None**, Stop Bits **1**.

   **USART3: the wire to the ESP32 later (Arduino pins D1 / D0)**
   - Connectivity → **USART3** → Mode **Asynchronous**.
   - Pins: **PD8** = USART3_TX, **PD9** = USART3_RX (click to fix if needed).
   - **Parameter Settings**: **115200 / 8 Bits / None / 1**.
   - **NVIC Settings** tab: tick **USART3 global interrupt**.

   **TIM1: the servo signals later (Arduino pins D3 / D7)**
   - Timers → **TIM1** → Clock Source **Internal Clock**.
   - Channel1 **PWM Generation CH1**, Channel2 **PWM Generation CH2**.
   - Pins: **PE9** = TIM1_CH1, **PE11** = TIM1_CH2 (click to fix if needed).
   - Leave the numbers alone; the code sets the timing itself.
4. **Clock Configuration** tab: change nothing.
5. **Project Manager** tab:
   - Project Name **`herd_unit`**, Project Location **`~/herd`** (make the folder if needed).
   - Toolchain / IDE **STM32CubeIDE**.
   - If it lists parts to generate (FSBL / Appli / ExtMemLoader), keep **only FSBL**.
6. Click **GENERATE CODE** (top right). If it asks to download the STM32N6 package, say yes.
   When it says it's done, close that pop-up.

## 5. Put the code in with CubeIDE

1. **Launchpad → STM32CubeIDE.** For the workspace, pick **`~/herd-workspace`** → Launch.
2. **File → Import → General → Existing Projects into Workspace → Next.** Next to "Select root
   directory" click **Browse**, pick **`~/herd/herd_unit/STM32CubeIDE`**, tick the project whose
   name ends in **FSBL**, then **Finish**.
3. Click the project once, then the **hammer** (Build). The Console at the bottom should end with
   **0 errors**. This checks the empty project before you add anything.
4. **Add the files:** drag the unzipped **`App`** folder from Finder onto the FSBL project in
   CubeIDE's Project Explorer (left panel). When asked, choose **Copy files and folders** → OK.
   An `App` folder with 23 files appears under the project.
5. **Tell the compiler about the folder:** right-click the project → **Properties** →
   **C/C++ Build → Settings** → **Tool Settings** tab → **MCU/MPU GCC Compiler → Include paths**.
   Click the green **+**, type **`../App`**, OK, then **Apply and Close**.
6. **Hook it into main.c:** in the Project Explorer open **Application → User → main.c**
   (or press **Cmd+Shift+R** and type `main.c`). Add these three lines. Each goes **between** the
   comment pair shown, because CubeMX keeps only what's between a BEGIN/END pair:

   Near the top:
   ```c
   /* USER CODE BEGIN Includes */
   #include "app_main.h"
   /* USER CODE END Includes */
   ```

   Further down, after the `MX_..._Init()` calls:
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
   (Add only the `app_loop();` line; the `}` is already there.)

   Save with **Cmd+S**.
7. **Hammer** again. You want **0 errors**.

## 6. Run it

1. **Terminal** (Launchpad → Other → Terminal). Find the board's port:
   ```sh
   ls /dev/cu.usbmodem*
   ```
   Then open it (use the name it printed):
   ```sh
   screen /dev/cu.usbmodemXXXX 115200
   ```
   Leave this window open. To quit later: **Ctrl-A**, then **K**, then **Y**.
2. In CubeIDE: right-click the project → **Debug As → STM32 C/C++ Application** → **OK**.
   If it offers to update the ST-LINK firmware, say yes and try again.
3. It loads the program and pauses at the start. Press **Resume** (green play button, or **F8**).
4. The Terminal starts printing, and the green LED blinks. Now run the test plan below.

You should see something like this:
```
[     51] board: servo timer clock measured at about 400 MHz, servos on D3 (pan) and D7 (tilt)
[     51] Open Herd unit 1 starting (left neighbor 0, right neighbor 2, fake detections ON)
[   1051] status: WATCHING target=0 people=0 pan=0 tilt=0 | link sent=2 resent=0 failed=0 recv=0 bad=0 echo=0
[  13200] LINGERING: person 1, start tracking
[  13200] state: WATCHING -> TRACKING
[  29300] HANDOFF: person 1 leaving right, telling unit 2 "heading your way"
[  29550] link: no ACK yet for HEADING to unit 2, resending (1/3)
[  30300] link: no ACK from unit 2 for HEADING, giving up
[  30300] LOST person 1 (neighbor never answered)
[  30300] state: HANDING_OFF -> WATCHING
```
"Giving up" is correct: there's no second unit to answer yet. The clock number can be different
from 400; any number works.

---

## 7. Test plan

Times are seconds after pressing Resume (the number in brackets ÷ 1000). Copy this table into
your notes and fill in the last column.

| # | Test | How | Pass if | Result |
|---|---|---|---|---|
| T1 | Builds | Hammer after Part 5 | `0 errors` (warnings from ST's own files are fine) | |
| T2 | Starts up | Watch the first lines | Startup lines appear within 1 s, and the servo-timer line says "measured at about … MHz" (not "isn't counting") | |
| T3 | Heartbeat | Watch the green LED for 1 minute | Blinks steadily, on and off about once a second | |
| T4 | Status | Watch the `status:` lines | One per second; `sent=` goes up every second; `bad=0` | |
| T5 | Spots lingering | Watch for `LINGERING` | Appears between 12 and 16 s, then `WATCHING -> TRACKING` | |
| T6 | Follows | Watch `pan=` in the status lines | Starts rising at about 20 s, reaches 80 at about 28 s; `tilt=` stays at about -2 | |
| T7 | Hands off | Watch for `HANDOFF` | Appears between 27 and 31 s, followed by 3 resends 0.25 s apart, then `giving up`, `LOST`, and `-> WATCHING` | |
| T8 | Goes home | Status line after T7 | `pan=0`, `state WATCHING` within about 1 s | |
| T9 | Repeats | Keep watching | The same story again every 45 s (second `LINGERING` around 58 s) | |
| T10 | Runs for a while | Leave it 10 minutes | Timestamps keep going up (no restarts), `failed=` equals the number of handoffs (about 13), `bad=0` | |

**Optional tests** (need one extra item each):

| # | Test | Needs | How | Pass if | Result |
|---|---|---|---|---|---|
| T11 | ESP32 port sends and receives | One jumper wire | With the program running, connect **D1 to D0**. Remove it after. | `echo=` starts going up every second, `bad=` stays 0, nothing else changes | |
| T12 | Servo signals | ET lab oscilloscope (no servos attached) | Probe **D3** and **D7** against **GND** | 50 Hz (20 ms apart), 1.5 ms pulses at rest; during T6 the D3 pulse grows to about 1.94 ms, D7 stays near 1.49 ms; back to 1.5 ms after T8 | |

When a test fails, write down what you saw and copy the last ~20 log lines. That's enough to
find the problem.

---

## 8. What this completes in our plan

| Plan item | Status with this skeleton |
|---|---|
| Week 4: draft the messages units send each other | **Done.** Six message types (status, event, heading your way, taken over, lost, ACK) with a fixed byte layout and an error check |
| Week 6: send a test message from the board itself | **Board side done.** A status message goes out on D1 every second (T4, T11). Connecting the ESP32 is next |
| Week 7: base station that logs events | **Unit side done.** The unit sends boot, lingering, handoff and lost events addressed to the station. The laptop program is next |
| Week 8: servos turn on command | **Code done**, checkable with T12 before the mount exists |
| Week 9: "heading your way" at the edge of the turn range | **Done** (T7), on made-up people |
| Winter Weeks 4–6: camera-to-camera handoff | **Logic in place early:** taken over, lost, timeouts, and resend-until-confirmed are all written and tested on the laptop |
| Flowchart boxes | Boxes 3, 5, 6, 7 and 10 run on the unit. Boxes 1, 2 and 4 run on made-up people until Devin's detection plugs in at `detect.c` |
| Critical assumption 3 (messages arrive reliably) | Confirm-and-resend is built in. The 1,000-message test still needs the ESP32s |

---

## 9. Troubleshooting

- **`undefined reference to huart3`** (or `huart1`, `htim1`): that part isn't turned on for FSBL in
  CubeMX. Fix it in Part 4, **GENERATE CODE** again, then build.
- **`app_main.h: No such file`**: the include path (Part 5 step 5) is missing, or the files ended
  up in a folder inside `App`.
- **`multiple definition of HAL_UART_RxCpltCallback`**: something else in the project also has it.
  Keep the one in `App/board_stm32.c`.
- **LED blinks but Terminal shows nothing**: check `115200` and the right `/dev/cu.usbmodem…`, and
  that USART1 is on PE5/PE6.
- **No LED and no text**: check BOOT1 is at 2-3, unplug and replug, then Debug again. Development
  mode forgets the program when unplugged.
- **"TIM1 isn't counting"**: TIM1 or its two channels aren't set up (Part 4, TIM1). Everything else
  still runs, so the other tests still apply.
- **CubeIDE can't find the ST-LINK**: try another cable. Some cables only charge and don't carry data.

## 10. Later (not needed now)

- **Second board:** in `App/app_config.h` set `UNIT_ID 2`, `NEIGHBOR_LEFT_ID 1`,
  `NEIGHBOR_RIGHT_ID HERD_ID_NONE`.
- **ESP32:** Nucleo **D1** → ESP32 **RX**, Nucleo **D0** → ESP32 **TX**, **GND** → **GND** (both are 3.3 V).
- **Servos:** signal wires to **D3** (pan) and **D7** (tilt). Power them from their **own 5 V supply**,
  never from the board, and connect that supply's GND to the board's GND.
- **Camera:** check its pinout against the board first. Then Devin replaces the made-up people in
  `detect.c` and sets `USE_FAKE_DETECTIONS 0`.
- **Changing CubeMX settings later:** edit and **GENERATE CODE** again. The `App` folder and your
  three lines in main.c are kept.

## The files, briefly

| File | What it's for |
|---|---|
| `app_main` | Startup and the main loop |
| `app_config.h` | Settings: unit ID, neighbors, timings, camera view, servo limits |
| `detect` | People in each frame. Made up for now (Devin's) |
| `tracker` | Keeps the same ID on the same person (Devin's) |
| `behavior` | Flags someone who stays in one spot for 8 s (Devin's) |
| `unit_fsm` | The flowchart: watching, tracking, handing off, expecting |
| `pantilt` | Aims the camera at a limited speed and knows the turn limits |
| `link` | Messages to the ESP32, with confirm-and-resend |
| `log` | Text to your Mac |
| `board.h`, `board_stm32.c` | The only code that touches the hardware |
| `herd_msg`, `herd_frame` | The message format and its serial wrapping, shared with the ESP32 and laptop |

Pins used on the NUCLEO-N657X0-Q come from ST's board files and example projects:
- USART1 on PE5/PE6 is the ST-LINK USB port
- USART3 on PD8/PD9 is Arduino D1/D0
- TIM1 channels 1 and 2 on PE9/PE11 are Arduino D3/D7
- the green LED is PG0
