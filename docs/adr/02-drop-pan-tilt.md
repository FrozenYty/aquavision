# 02 — No pan-tilt; fixed camera, moving targets

- **Status:** Accepted
- **Date:** 2026-11-03
- **Supersedes:** —

## Context

A single-axis pan-tilt was proposed to sweep the camera across the tank, adding motion to the
demo and collecting multi-angle frames for fine-tuning.

## Decision

Do not build a pan-tilt. The camera stays fixed in front of the tank; targets move instead, either
by hand or along a simple rail.

## Rationale

- **Coverage is already sufficient.** A 70° horizontal field at 50 cm covers about 70 cm, while the
  tank is 40 cm wide. A single frame captures the whole front face.
- **Servo motion blurs the image.** Detection drops when frames are taken while moving; a
  "stop, settle, shoot" sequence is required, which removes most of the perceived benefit.
- **Failure cost is asymmetric.** A working servo buys about five seconds of interest; a stuck
  servo costs thirty seconds of dead air in front of the jury.
- **Multi-angle data is cheaper by hand.** Moving the targets between capture sessions produces
  exactly the angles we want, without vibration or cable drag.

## Consequences

- Demo motion comes from the targets, not the camera — which is also how a fixed underwater
  observation point behaves in reality.
- Multi-view fine-tuning data is collected by re-arranging targets, one session per arrangement.
- Roughly ¥65 and 2.5 days are freed up and redirected to the ablation study.

## Revisit when

Week 15 ends with the main line green and at least two spare days. Even then, spending them on a
second ablation run is likely worth more than a servo.
