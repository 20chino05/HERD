# STM32 unit firmware (NUCLEO-N657X0-Q)

`App/` holds the unit's code: the app logic plus `board_stm32.c`, the only file that touches
the hardware. It is copied into a CubeMX/CubeIDE project together with `../common/`.

Setup, from a blank Mac to a running board: [Docs/software/stm32-skeleton-setup.md](../../Docs/software/stm32-skeleton-setup.md).

Laptop tests for everything except `board_stm32.c`: `make -C firmware/tests`.
