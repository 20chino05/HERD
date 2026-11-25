/* tracker.c - nearest-match tracker (see tracker.h). */
#include "tracker.h"

#include <string.h>

#include "app_config.h"

static track_t tracks[TRACK_MAX];
static uint16_t next_id;

void tracker_init(void) {
  memset(tracks, 0, sizeof(tracks));
  next_id = 1;
}

static int32_t dist2(int32_t ax, int32_t ay, int32_t bx, int32_t by) {
  int32_t dx = ax - bx, dy = ay - by;
  return dx * dx + dy * dy;
}

void tracker_update(const frame_t *frame) {
  bool matched[TRACK_MAX] = {false};
  const int32_t max_d2 = (int32_t)TRACK_MATCH_DIST * TRACK_MATCH_DIST;

  for (uint8_t i = 0; i < frame->count; i++) {
    const detection_t *d = &frame->det[i];

    /* Nearest person not already claimed by another box this frame. */
    int best = -1;
    int32_t best_d2 = max_d2 + 1;
    for (int k = 0; k < TRACK_MAX; k++) {
      if (!tracks[k].active || matched[k]) continue;
      int32_t d2 = dist2(d->x, d->y, tracks[k].x, tracks[k].y);
      if (d2 < best_d2) {
        best_d2 = d2;
        best = k;
      }
    }

    if (best >= 0) {
      track_t *t = &tracks[best];
      uint32_t dt = frame->time_ms - t->last_seen_ms;
      if (dt > 0) t->vx = (int16_t)(((int32_t)d->x - t->x) * 1000 / (int32_t)dt);
      t->x = d->x;
      t->y = d->y;
      t->score = d->score;
      t->last_seen_ms = frame->time_ms;
      matched[best] = true;
      continue;
    }

    /* Someone new: take a free slot (if none, ignore them this frame). */
    for (int k = 0; k < TRACK_MAX; k++) {
      if (tracks[k].active) continue;
      track_t *t = &tracks[k];
      t->active = true;
      t->id = next_id++;
      if (next_id == 0) next_id = 1; /* 0 means "nobody" elsewhere */
      t->x = d->x;
      t->y = d->y;
      t->vx = 0;
      t->score = d->score;
      t->first_seen_ms = frame->time_ms;
      t->last_seen_ms = frame->time_ms;
      matched[k] = true;
      break;
    }
  }

  /* Forget people we haven't seen for a while. */
  for (int k = 0; k < TRACK_MAX; k++) {
    if (tracks[k].active && (uint32_t)(frame->time_ms - tracks[k].last_seen_ms) > TRACK_DROP_MS) {
      tracks[k].active = false;
    }
  }
}

const track_t *tracker_tracks(void) { return tracks; }

size_t tracker_count(void) {
  size_t n = 0;
  for (int k = 0; k < TRACK_MAX; k++) n += tracks[k].active ? 1u : 0u;
  return n;
}

const track_t *tracker_find(uint16_t id) {
  if (id == 0) return NULL;
  for (int k = 0; k < TRACK_MAX; k++) {
    if (tracks[k].active && tracks[k].id == id) return &tracks[k];
  }
  return NULL;
}
