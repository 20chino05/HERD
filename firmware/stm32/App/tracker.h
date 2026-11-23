/*
 * tracker.h - keeps the same ID on the same person from frame to frame.
 *
 * Owner: Devin. Simple version: each box is matched to the nearest person
 * from the last frames. Good enough for one camera; swap in something
 * smarter later without changing the interface.
 */
#ifndef TRACKER_H
#define TRACKER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "detect.h"

#define TRACK_MAX 8

typedef struct {
  bool active;
  uint16_t id;
  int16_t x, y;           /* last position, thousandths of the frame */
  int16_t vx;             /* sideways speed, thousandths of the frame per second */
  uint32_t first_seen_ms;
  uint32_t last_seen_ms;
} track_t;

void tracker_init(void);
void tracker_update(const frame_t *frame);

/* All slots; check .active. Always TRACK_MAX long. */
const track_t *tracker_tracks(void);
size_t tracker_count(void); /* active people */
const track_t *tracker_find(uint16_t id);

#endif /* TRACKER_H */
