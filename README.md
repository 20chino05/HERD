# Open Herd

Identical camera units with onboard AI that work together as a swarm

UCI EECS 159 Senior Design | Fall 2026 – Winter 2027

> **Draft (updated November 2, 2026).** After the October 19 advisor check-in, the team narrowed
> Open Herd to a security camera swarm. The plan is still a plan; the first measured results are the
> laptop-side AI checks linked under Documents.

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

Done on the software side (Fall weeks 4 and 5): ST's ready-made person detector runs on a laptop,
and its accuracy and speed are measured on COCO at the image sizes the board will use. See the
[AI write-up](Docs/software/2026-11-02-ai-weeks-4-5.md) and [`ai/README.md`](ai/README.md).

## Repository layout

| Folder | Owner | What lives here |
|---|---|---|
| `ai/` | Devin | Laptop-side AI: person detection, accuracy and speed measurements, later tracking, lingering logic and person matching. Python. |
| `station/` | Aaron | Laptop base station: recording and the event log. |
| `firmware/` | Devin + Aaron | Code that runs on the units: STM32N6 camera + AI app, ESP32 ESP-NOW messaging. |
| `hardware/` | Nader + Samuel | Schematics, layout, BOM, pan/tilt mount. |
| `Docs/` | everyone | Proposal, parts list, meeting notes, and write-ups of decisions and test results (`Docs/software/` for the software side). |
| `legacy/` | — | The archived SAFE-Swarm drone project. |

## Hardware the software targets

- V0: NUCLEO-N657X0-Q (STM32N6 with the Neural-ART NPU) + ST B-CAMS-IMX camera module (Sony IMX335,
  MIPI CSI-2, 22-pin FFC) + an ESP32 for ESP-NOW messages between units + pan/tilt servos.
- V1: a custom board with the same STM32N6 and camera connector; the radio is still to be decided.

Details and purchase status are in the [parts list](Docs/parts-list.md).

## Team

Roles are carried over from SAFE-Swarm and may change.

- Nader Guirguis — Hardware
- Samuel Malak — Hardware
- Devin Mccaw — Software (AI: detection, tracking, person matching)
- Aaron Torres — Software (messages between units, servos, base station)

Faculty Advisor: Boris Vaisband

## Documents

- [Draft proposal](Docs/proposal.md): the idea, the demo, scope, phases, and open questions
- [Draft parts list](Docs/parts-list.md): what's bought, what's needed, and options to research
- [Meeting notes](Docs/meeting-notes.md): including the October 12 and 19 advisor feedback
- [AI, Fall weeks 4–5](Docs/software/2026-11-02-ai-weeks-4-5.md): decisions, findings and measured results from running ST's person detector on a laptop
- [AI setup and usage](ai/README.md): how to install and run the detector and the accuracy check
- [Legacy: SAFE-Swarm](legacy/README.md): the original drone project, archived October 16, 2026
