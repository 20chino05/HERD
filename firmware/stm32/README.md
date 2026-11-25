# STM32 unit firmware (NUCLEO-N657X0-Q)

`App/` holds the unit's code: the app logic plus `board_stm32.c`, the only file that touches
the hardware. It is copied into a CubeMX/CubeIDE project together with `../common/`.

Setup, from a blank Mac to a running board: [Docs/software/stm32-skeleton-setup.md](../../Docs/software/stm32-skeleton-setup.md).

Laptop tests for everything except `board_stm32.c`: `make -C firmware/tests` (Mac/Linux, or the
MSYS2 UCRT64 shell on Windows). From PowerShell with MSYS2 installed:

```powershell
$env:Path = "C:\msys64\ucrt64\bin;" + $env:Path
cd firmware\tests
gcc -std=c11 -O1 -g -Wall -Wextra -Werror -Wshadow -Wconversion -Wno-sign-conversion -I../common -I../stm32/App -I. ../common/*.c ../stm32/App/app_main.c ../stm32/App/behavior.c ../stm32/App/detect.c ../stm32/App/link.c ../stm32/App/log.c ../stm32/App/pantilt.c ../stm32/App/tracker.c ../stm32/App/unit_fsm.c board_fake.c test_main.c -o unit_tests.exe
.\unit_tests.exe
```

`tests/trace_main.c` replays recorded detections through the real `tracker.c` + `behavior.c`;
`ai/scripts/check_firmware_parity.py` uses it to prove the Python mirrors in `ai/` give the same
output, so the settings in `App/app_config.h` measured on labeled video apply to this code
(see [Docs/software/2026-11-23-ai-weeks-8-9.md](../../Docs/software/2026-11-23-ai-weeks-8-9.md)).
