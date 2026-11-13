/* log.h - printf-style debug log, one line per call, prefixed with the time. */
#ifndef LOG_H
#define LOG_H

void log_printf(const char *fmt, ...) __attribute__((format(printf, 1, 2)));

#endif /* LOG_H */
