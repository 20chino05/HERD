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
