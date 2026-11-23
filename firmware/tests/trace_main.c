/*
 * trace_main.c - replays recorded detections through the real tracker and lingering code.
 *
 * The laptop side (ai/) runs the same detections through its Python mirrors of tracker.c and
 * behavior.c and compares the output line for line, so the numbers measured on video on a laptop
 * are the numbers the board will produce. Build with the app sources, no board needed:
 *
 *   gcc -std=c11 -I../common -I../stm32/App trace_main.c ../stm32/App/tracker.c ../stm32/App/behavior.c -o trace_tool
 *
 * Input, one frame per line on stdin:   <time_ms> <count> x y w h score [x y w h score ...]
 *   (positions in thousandths of the frame, score in percent, at most DETECT_MAX boxes)
 * Output, one line per frame:           <time_ms> L=<id that just started lingering, or 0> <id>:<x>:<y>:<vx> ...
 *   (active tracks in slot order)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "behavior.h"
#include "tracker.h"

int main(void) {
  char line[8192];
  tracker_init();
  behavior_init();
  while (fgets(line, sizeof(line), stdin) != NULL) {
    frame_t f;
    char *p = line, *end;
    unsigned long t = strtoul(p, &end, 10);
    if (end == p) continue; /* blank line */
    p = end;
    long n = strtol(p, &end, 10);
    p = end;
    memset(&f, 0, sizeof(f));
    f.time_ms = (uint32_t)t;
    for (long i = 0; i < n && f.count < DETECT_MAX; i++) {
      long v[5];
      for (int k = 0; k < 5; k++) {
        v[k] = strtol(p, &end, 10);
        p = end;
      }
      detection_t *d = &f.det[f.count++];
      d->x = (int16_t)v[0];
      d->y = (int16_t)v[1];
      d->w = (int16_t)v[2];
      d->h = (int16_t)v[3];
      d->score = (uint8_t)v[4];
    }
    tracker_update(&f);
    uint16_t lingering = behavior_update(f.time_ms);
    printf("%lu L=%u", t, (unsigned)lingering);
    const track_t *tr = tracker_tracks();
    for (int k = 0; k < TRACK_MAX; k++) {
      if (tr[k].active) printf(" %u:%d:%d:%d", (unsigned)tr[k].id, (int)tr[k].x, (int)tr[k].y, (int)tr[k].vx);
    }
    printf("\n");
  }
  return 0;
}
