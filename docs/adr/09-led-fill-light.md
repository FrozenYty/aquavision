# 09 — The fill light is a low-voltage LED board driven by the MCU

- **Status:** Superseded by ADR 10
- **Date:** 2026-11-07
- **Supersedes:** the "two desk lamps" decision recorded in `procurement.md` §2
- **Superseded by:** ADR 10, after the lamp on hand proved to be a DC source with no visible flicker

## Context

The architecture diagram said the ESP32 handles *trigger, fill light and sensors*, and the parts list
said the MCU board's job is *trigger, PWM, I2C master*. The procurement document then chose two desk
lamps and recorded the reason as "saves a whole 5 V rail and six wires".

Both cannot be true. A desk lamp plugs into the wall; the MCU had no relay, no MOSFET and no triac in
the parts list. **The dimming claim was empty** — a document saying the software controls something the
hardware cannot reach.

That mattered beyond tidiness, for two reasons.

1. **The quality score reads brightness.** A score that must pass 60 is only meaningful if the light
   level is comparable between captures. A desk lamp moved between runs produces a different picture,
   and the operator reads that as a bug in the scoring code.
2. **The rig has to survive a defence.** A lamp aimed by hand at 45°, with tracing paper taped over it,
   is a geometry that changes every time it is set up.

## Decision

Replace the desk lamps with a **12 V white LED board, an IRF520 MOSFET module, and its own 12 V
adapter**, with the ESP32 driving the module's gate by PWM.

Three parts, about ¥55, no custom board, no mains switching.

- **Low voltage only.** A 12 V board removes the question of switching a mains lamp. There is water on
  the same table; a 12 V rail and a MOSFET are appropriate, a 220 V dimmer is not.
- **MOSFET, not a relay.** A relay gives on and off; the requirement is brightness, and a relay cycling
  next to a camera is a flicker source.
- **Its own supply.** The light board must not draw from the ESP32's 5 V pin; a 5–10 W board would brown
  out the board mid-capture.
- **Common ground** between the 12 V supply, the MOSFET module and the ESP32 — stated in the assembly
  order because a floating ground produces a gate signal that only sometimes switches.

## Alternatives considered

**Keep the lamps and delete the dimming claim** — the cheapest option and defensible, since no
functional requirement asks for adjustable light. Rejected because the light level then varies between
sessions, which weakens every quality score and the left/right brightness ratio the rig must meet.

**Software-only exposure compensation** — leaves the sensor's exposure range to absorb whatever the lamp
does, and the capture module already treats exposure as something to lock, not to chase.

**A mains dimmer with an opto-isolated triac** — solves dimming and introduces mains wiring next to a
water tank. Not worth it for a demonstration rig.

## Consequences

- SRS rises to V1.7: Table 2-3 replaces the lamp with three parts and the MCU row gains PWM dimming.
- The parts list grows by ¥55 to ¥432.42; two acceptance checks are added, one for monotonic brightness
  and one for ground continuity.
- The firmware now owns one more output. The dimming must be set before capture and left alone during a
  session, because the quality gate compares frames to each other.
- Photographing the rig for the report is easier: the light no longer moves.
