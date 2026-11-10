# 01 — Camera connects by USB to the server

- **Status:** Accepted
- **Date:** 2026-11-03
- **Supersedes:** —

## Context

The course requires images to be acquired through a camera module; analysing pre-existing image
files is explicitly forbidden. Two shapes were considered:

1. **On-board capture** — an ESP32-S3-CAM grabs frames, caches them and uploads over WiFi.
2. **Server-side capture** — a USB camera is read directly by the server process.

## Decision

Use a USB camera (1080P, manual exposure, UVC) read by the server through OpenCV.

The ESP32 remains in the system, but only as a controller: trigger button, lamp brightness,
water-temperature and turbidity sensors, OLED status display. It never touches image data.

## Rationale

- Removes firmware for image transport, frame buffering, reconnection and device authentication —
  roughly one week of work with no grading payoff.
- Keeps the acquisition chain genuinely hardware: the camera is physical, the trigger is physical,
  the environment readings are physical.
- The SRS already fixes manual exposure and frame-level timestamps, which a UVC camera supports
  directly.

## Consequences

- The compliant path is trivially demonstrable: unplug the camera and no image can enter.
- A serial protocol must be defined between the ESP32 and the server (see the "Serial protocol"
  section of `firmware/README.md`, and the rules in `docs/rig-state-machine-en.md`).
- The camera must support manual exposure; auto-exposure would invalidate the quality score.

## Revisit when

The teacher requires the camera to be attached to the microcontroller itself. That is a
one-way door: it adds about two weeks and changes the hardware list, the acquisition interface
and the weekly plan.
