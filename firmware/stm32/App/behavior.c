/* behavior.c - lingering check (see behavior.h). */
#include "behavior.h"

#include <stdbool.h>
#include <string.h>

#include "app_config.h"

typedef struct {
  bool used;
  bool anchored; /* has a standing spot been recorded yet */
  bool reported;
  uint16_t id;
  int16_t anchor_x, anchor_y; /* where they started standing */
  uint32_t since_ms;          /* when they started standing there */
} linger_t;

static linger_t slots[TRACK_MAX];

void behavior_init(void) { memset(slots, 0, sizeof(slots)); }

static linger_t *slot_for(uint16_t id) {
  for (int i = 0; i < TRACK_MAX; i++) {
    if (slots[i].used && slots[i].id == id) return &slots[i];
  }
  for (int i = 0; i < TRACK_MAX; i++) {
    if (!slots[i].used) {
      memset(&slots[i], 0, sizeof(slots[i]));
      slots[i].used = true;
      slots[i].id = id;
      return &slots[i];
    }
  }
  return NULL;
}

uint16_t behavior_update(uint32_t now_ms) {
  const track_t *tracks = tracker_tracks();
  const int32_t r2 = (int32_t)LINGER_RADIUS * LINGER_RADIUS;
  uint16_t lingering = 0;

  /* Drop slots for people the tracker has forgotten. */
  for (int i = 0; i < TRACK_MAX; i++) {
    if (slots[i].used && tracker_find(slots[i].id) == NULL) slots[i].used = false;
  }

  for (int k = 0; k < TRACK_MAX; k++) {
    const track_t *t = &tracks[k];
    if (!t->active) continue;

    linger_t *s = slot_for(t->id);
    if (s == NULL) continue;

    int32_t dx = t->x - s->anchor_x, dy = t->y - s->anchor_y;
    if (!s->anchored || dx * dx + dy * dy > r2) {
      /* Just appeared, or moved away: start timing from here. */
      s->anchored = true;
      s->anchor_x = t->x;
      s->anchor_y = t->y;
      s->since_ms = now_ms;
      s->reported = false;
      continue;
    }

    if (!s->reported && (uint32_t)(now_ms - s->since_ms) >= LINGER_TIME_MS && lingering == 0) {
      s->reported = true;
      lingering = t->id;
    }
  }
  return lingering;
}
