# Laptop tests for the Open Herd unit code. Needs only gcc (or clang) and make.
#   make -C firmware/tests            build and run
#   make -C firmware/tests VERBOSE=1  also print the unit's log
CC ?= cc
CFLAGS ?= -std=c11 -O1 -g -Wall -Wextra -Werror -Wshadow -Wconversion -Wno-sign-conversion
CFLAGS += -I../common -I../stm32/App -I.

APP_SRC := $(filter-out ../stm32/App/board_stm32.c,$(wildcard ../stm32/App/*.c))
SRC := $(wildcard ../common/*.c) $(APP_SRC) board_fake.c test_main.c

unit_tests: $(SRC) $(wildcard ../common/*.h ../stm32/App/*.h *.h)
	$(CC) $(CFLAGS) $(SRC) -o $@

run: unit_tests
	./unit_tests $(if $(VERBOSE),-v)

.DEFAULT_GOAL := run

clean:
	rm -f unit_tests

.PHONY: run clean
