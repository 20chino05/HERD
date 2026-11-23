/*
 * behavior.h - decides when someone is lingering.
 *
 * Owner: Devin. "Lingering" = staying within LINGER_RADIUS of one spot for
 * LINGER_TIME_MS (app_config.h). Each stay is reported once.
 */
#ifndef BEHAVIOR_H
#define BEHAVIOR_H

#include <stdint.h>

#include "tracker.h"

void behavior_init(void);

/* Call once per frame after tracker_update. Returns the ID of someone who
   just started lingering, or 0 if nobody did. */
uint16_t behavior_update(uint32_t now_ms);

#endif /* BEHAVIOR_H */
