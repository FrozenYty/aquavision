# 10 — The desk lamp is the fill light; ADR 09 is superseded

- **Status:** Accepted
- **Date:** 2026-11-07
- **Supersedes:** ADR 09 (the 12 V LED strip and MOSFET)

## Context

ADR 09 replaced the desk lamps with a 12 V strip, a MOSFET module and a separate supply, on the
grounds that a mains lamp cannot be controlled by the program and that the light level would otherwise
vary between sessions. Two of those grounds did not survive contact with the lamp actually on hand.

The lead's lamp is a **Midea MT-10T4**: 10 W, **4000 K**, Ra90–95, a honeycomb lens across a bar head,
and — the part that decides this — **USB-powered with a lithium battery**, advertised by the
manufacturer as free of visible flicker.

That is a **DC source**. The flicker problem ADR 09 used to justify the strip does not exist for this
lamp. The remaining advantage of the strip was program-controlled dimming, and no requirement asks for
it: the quality score reads brightness, it does not need it to be adjustable, only stable.

## Decision

The fill light is the existing desk lamp. The strip, the MOSFET module, the 12 V adapter and the
adapter lead are **not bought**. ADR 09 is superseded.

Three operational rules turn the lamp into a stable source:

1. **Run it on USB, not on the battery.** A battery-powered lamp dims as the charge falls, and a light
   level that drifts between sessions is exactly what this decision was meant to avoid.
2. **Fix one touch-dimming level and tape over the touch area.** The lamp has discrete steps, not a
   knob; a demo that changes brightness halfway through cannot compare its own frames.
3. **Tape the polariser flat against the head, corners taut.** A warped sheet depolarises, and the
   whole cross-polarisation setup depends on it.

## Alternatives considered

**Buy the strip anyway, for the known colour temperature and the flat mounting surface** — the lamp is
already 4000 K with a high CRI, and its bar head takes a polariser sheet as easily as a board does.
Nothing left to buy it for.

**Keep the strip for program control** — the control was never a requirement; it entered through an
architecture diagram that said the MCU handles the fill light. That diagram is now corrected.

## Consequences

- SRS falls back to V1.8: Table 2-3 lists the lamp, and the MCU row is trigger and turbidity only.
- The parts list drops from ¥417.82 to **¥377.42**, and four orders disappear.
- The acceptance table swaps "PWM dims monotonically" for "ten minutes on USB, first and last frame
  within 5 %", which is the property that actually matters and can be measured with the existing
  capture module.
- The architecture diagram no longer claims the MCU controls the light, so the diagram, the parts list
  and the code agree about what the microcontroller does.
