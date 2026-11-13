/*
 * unit_fsm.h - the Use case 1 flowchart as a state machine.
 *
 *   WATCHING    nobody targeted, camera at home. Someone lingers -> TRACKING.
 *   TRACKING    follow the target. Target reaches the edge with the camera
 *               turned as far as it goes -> tell that neighbor "heading your
 *               way" -> HANDING_OFF. Target vanishes elsewhere -> LOST.
 *   HANDING_OFF wait for the neighbor's TAKEN_OVER -> WATCHING.
 *               No answer in time -> LOST -> WATCHING.
 *   EXPECTING   a neighbor said "heading your way": turn toward that side
 *               and wait. A new person appears -> TAKEN_OVER -> TRACKING.
 *               Nobody in time -> LOST -> WATCHING.
 */
#ifndef UNIT_FSM_H
#define UNIT_FSM_H

#include <stdint.h>

#include "herd_msg.h"

typedef enum { UNIT_WATCHING = 0, UNIT_TRACKING, UNIT_HANDING_OFF, UNIT_EXPECTING } unit_state_t;

void fsm_init(void);
void fsm_on_frame(uint16_t lingering_id, uint32_t now_ms);   /* after tracker + behavior each frame */
void fsm_on_message(const herd_msg_t *m, uint32_t now_ms);  /* from link */
void fsm_on_send_failed(const herd_msg_t *m, uint32_t now_ms); /* from link: no ACK */
void fsm_tick(uint32_t now_ms);                             /* every loop: timeouts */

unit_state_t fsm_state(void);
uint16_t fsm_target(void); /* tracker ID of the person being followed, 0 if none */
const char *fsm_state_name(unit_state_t s);

#endif /* UNIT_FSM_H */
