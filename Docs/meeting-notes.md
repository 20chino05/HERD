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
- Parts arrived: two dev boards and two cameras. Board work starts this week.

**Questions for the advisor:**
- Are our use cases reasonable? (Main demo: security swarm. Second: crowd monitoring.)
- Are our critical assumptions reasonable? (The next camera recognizing the same person, tracking
  fast enough while turning, handoff messages arriving reliably.)
- Is it reasonable to finish the testing or calculations in 1–2 weeks?
- Is recording video on the laptop okay, as long as tracking and handoff decisions happen on the units?

**Advisor feedback:**
- Make sure the dev board and cameras plug in and work together.
- Make the intelligence in each device clear: the onboard (edge) AI is what makes it a swarm, so
  emphasize it.
- Critical assumptions: the risk of the next camera missing the target is small. Instead:
  - work out the handoff latency we actually need
  - plan for two people entering a camera's view at the same time
  - send data on the target along with the handoff
  - try having the camera predict where a person goes after leaving its view
- Come up with more hardware critical assumptions, including whether the wired parts can handle
  the load.

**Action items:**
| Task | Owner | Due |
|---|---|---|
| Get both dev boards running with the cameras | TBD | Week 6 |
| Work out the handoff latency we need | Aaron | Proposal #2 |
| Plan for two people entering a view at once | Devin | TBD |
| Add the person's appearance data to the handoff message | Aaron | TBD |
| Add 1–2 hardware critical assumptions (power, wired links) | Nader and Samuel | Proposal #2 |
| Make the edge AI clearer in the proposal summary | Aaron | Proposal #2 |

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
