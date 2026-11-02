# Open Herd

Identical camera units with onboard AI that work together as a swarm

UCI EECS 159 Senior Design | Fall 2026 – Winter 2027

> **Draft (updated October 19, 2026).** After the October 19 advisor check-in, the team narrowed
> Open Herd to a security camera swarm. Everything here is still a plan, not a result.

## Overview

Open Herd is about modular hardware and AI: one camera unit, built on the STM32N6 chip, that runs
its AI on the unit itself and can be reprogrammed for different jobs. Several identical units (same
hardware, same setup) talk to each other and coordinate on their own, as a swarm. The plan is still
to make it open source.

Our demo is property security and anti-theft:

1. Each camera watches its area and looks for people, using AI on its own chip.
2. When someone lingers suspiciously over the same area or item, that camera starts tracking them
   and turns to keep them in view. Spotting theft directly is a harder, later goal.
3. As the person walks out of view, the camera tells the neighbor on that side, which turns toward
   that direction and picks the person up.
4. The result is one continuous track across the property, so the target is less likely to be lost between cameras.

The units make the decisions themselves, not a central computer. A central station (a team laptop)
only records the video and logs events. We also plan no face recognition and no audio, and the
recordings stay on the owner's own station rather than a third-party cloud.

The same hardware could later be reprogrammed for other jobs, such as crowd monitoring or traffic counting.

## Current Status

Planning. According to the team's notes, one STM32N6 development board has been bought. The team narrowed the scope on
October 19, and the [proposal](Docs/proposal.md#estimated-deliverables-at-major-milestones)
lays out what we think fits in the time we have.

## Team

Roles are carried over from SAFE-Swarm and may change.

- Nader Guirguis — Hardware
- Samuel Malak — Hardware
- Devin Mccaw — Software
- Aaron Torres — Software

Faculty Advisor: Boris Vaisband

## Documents

- [Draft proposal](Docs/proposal.md): the idea, the demo, scope, phases, and open questions
- [Draft parts list](Docs/parts-list.md): what's bought, what's needed, and options to research
- [Meeting notes](Docs/meeting-notes.md): including the October 12 and 19 advisor feedback
- [Legacy: SAFE-Swarm](legacy/README.md): the original drone project, archived October 16, 2026
