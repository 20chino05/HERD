# Meeting Notes

Advisor check-in carried over from SAFE-Swarm: Boris Vaisband, in person, Mondays at 6 PM (tentative; the team's Google Doc proposal says 11 AM, confirm).

Add the newest meeting at the top. Copy the template comment below for each meeting.
Earlier meetings, from SAFE-Swarm, are in [legacy/meeting-notes.md](../legacy/meeting-notes.md).

<!--
## YYYY-MM-DD — Team meeting / Advisor check-in

**Attendees:**

**Completed since last meeting:**
-

**Decisions:**
-

**Open questions / blockers:**
-

**Action items:**
| Task | Owner | Due |
|---|---|---|
|  |  |  |
-->

## 2026-11-02 — Advisor check-in (Proposal #2)

**Attendees:**

**Completed since last meeting:**
- Proposal #2 draft: use case flowcharts, critical assumptions with calculations, and a schedule
  rebuilt around the security swarm (crowd monitoring moved to Winter as the backup).

**Questions for the advisor:**
- Are our use cases reasonable? (Main demo: security swarm. Second: crowd monitoring.)
- Are our critical assumptions reasonable? (The next camera recognizing the same person, tracking
  fast enough while turning, handoff messages arriving reliably.)
- Is it reasonable to finish the testing or calculations in 1–2 weeks?
- Is recording video on the laptop okay, as long as tracking and handoff decisions happen on the units?
- Hardware: a second dev board, or wait for the custom board? Camera order status.

**Advisor feedback:**
- (fill in after the meeting)

**Action items:**
| Task | Owner | Due |
|---|---|---|
|  |  |  |

## 2026-10-19 — Advisor check-in

**Attendees:** Prof. Vaisband, Aaron, Devin, Nader, Samuel

**Advisor feedback:**
- Narrow the scope: build several identical camera units (same hardware, same setup) that talk to each other over a network and control themselves as a swarm.
- Read up on how swarm systems work.
- Consider adding more sensors to each unit (which ones isn't decided).
- Work out an algorithm for how the units coordinate on their own, without a person directing them.
- Favor onboard processing over a central computer: each unit should do as much of its own processing and decision-making as possible.

**Decisions:**
- Demo use case: property security and anti-theft. When a camera sees theft or someone loitering suspiciously over the same area or item, it tracks them, turning to keep them in view, and hands them off to the next camera so the target isn't lost.

**Open questions / blockers:**
- How does "onboard over central" fit with saving recordings at a central station? Confirm what should stay on each unit.

**Action items:**
| Task | Owner | Due |
|---|---|---|
|  |  |  |

## 2026-10-12 — First meeting (SAFE-Swarm)

**Attendees:** Prof. Vaisband, Aaron, Devin, Nader, Samuel

The agenda for this meeting is in [legacy/meeting-notes.md](../legacy/meeting-notes.md).

**Advisor feedback:**
- Watch the costs closely so the budget doesn't balloon.
- Have a backup plan (plan B), since the project is complex.
