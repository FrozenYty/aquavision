# Procurement

> Chinese version: [procurement-zh.md](procurement-zh.md). This file is the source of truth.

> Owner: @FrozenYty · Revisit when: the hardware changes

Final bill of materials, frozen on 2026-11-05: nine items, two channels, ¥377.42. This is the list the
rig is built from; changing it means changing PLAN.md P0-03 and this document together. Brand names
and the Chinese search strings are listed in the Chinese version; this file describes the same parts
in English.

## 1. Final list

| # | Item | Model / part | Qty | Unit ¥ | Channel | Purpose |
|---|---|---|---|---|---|---|
| 1 | USB camera | 1080P UVC module, 3.6 mm low-distortion lens, metal housing | 1 | 200.60 | JD | Image capture |
| 2 | Glass tank | Low-iron ultra-clear glass, 300×170×200 mm, 5 mm walls, bare tank | 1 | 48.90 | JD | Capture chamber |
| 3 | Linear polariser | FINNER PL sheet, gloss finish, no adhesive, 200×200 mm, 0.2 mm | 1 | 35.60 | JD | Cross-polarisation, two pieces cut from one sheet |
| 4 | MCU board | DZYJ ESP32-S3 N16R8 DevKitC, headers pre-soldered | 1 | 26.60 | JD | Trigger, PWM, I2C master |
| 5 | Level shifter | 8-channel bidirectional 3.3 V ↔ 5 V, headers pre-soldered | 1 | 7.10 | JD | Bridges the 5 V sensor to 3.3 V GPIO |
| 6 | Jumper wires | DZYJ 40-pin ribbon, male-male / male-female / female-female, 120 pcs | 1 | 8.26 | JD | All wiring |
| 7 | Breadboard | DZYJ MB-102, 1660 tie points, with power rails | 1 | 23.70 | JD | Solderless assembly; the 405-hole board is too small once the ESP32 and shifter are seated |
| 8 | Turbidity sensor | LIGHT ME2100A-IIC, I2C, reflective | 1 | 18.82 | LCSC | Reads water clarity |
| 9 | Sensor cable | WHEELTEC GH1.25 4-pin to Dupont female, 200 mm | 1 | 7.84 | JD | Turbidity sensor to the level shifter pins |
| 10 | Fill-light strip | 12 V flexible silicone strip, about 10 W/m, 5 cm cut marks, self-adhesive | 2 | 7.10 | JD | Fixed light source, replaces the desk lamp; cut into two 50 cm runs side by side |
| 11 | Switch module | IRF520 MOSFET driver module, 3.3 V compatible input, heatsink | 1 | 5.00 | JD | PWM dimming from the ESP32; 0.83 A at 10 W, ample headroom |
| 12 | Power adapter | 12 V **2 A** DC, 5.5×2.1 mm barrel | 1 | 25.00 | JD | Supplies the strip on its own rail; a 1 A unit would run at its rating, sag and dim |

**Total ¥421.62.** The three lighting parts were added on 11-07; ADR 09 records why: a desk lamp cannot
be controlled by the program, and the brightness term of the quality score needs a source that does not
change between runs. The button is not on the list: a through-hole momentary push button is already on hand. A second, 405-hole breadboard was dropped from the order — the ESP32 with headers, the shifter and the wiring need the 1660-hole board.

## 2. Deliberately not bought

| Item | Why not |
|---|---|
| Capture light | Two desk lamps with tracing paper as a diffuser and a white card reflector. Removes an entire 5 V rail and six wires. |
| Acrylic tank | Ultra-clear glass is cheaper, has no stress birefringence, and keeps cross-polarisation working. |
| Target models | Real seafood bought on the day. Natural colour, natural sinking, naturally wet and specular — which is what the polariser exists for. |
| Scenery | Stones and plants found on site. One dark stone shaped like a sea cucumber is enough to stage a false positive. |
| Water level sensor | The tank level is constant and nothing depends on it. It is not in the SRS. |
| Water temperature probe | It fills one field and drives no decision. The SRS states that missing sensor fields stay empty and are excluded from statistics. |
| Second lamp | Only if the left/right brightness ratio fails; see `PROGRESS.md` 2026-11-05. |

## 3. Things to verify before assembly

- **Camera exposure lock.** The seller confirms the module locks exposure over UVC. `python scripts/test_exposure.py`
  still runs on arrival and its output is kept as evidence; if the driver disagrees with the seller,
  fall back to fixed lighting with a 15 % brightness tolerance and record the change.
- **Button.** A through-hole momentary push button is already on hand. Check its legs are straight: the
  PCB-mount parts with bent legs bought earlier will not seat in a breadboard. A latching switch would
  not work here — the firmware expects a falling edge per press.
- **Sensor cable.** GH1.25 to Dupont female. A single-ended tinned cable has nothing to plug into.

## 4. Assembly order

Assemble and power on in five steps, one at a time, so a fault is localised immediately:

1. ESP32 + tactile switch — serial prints a line on each press. **Debounce first**: one press, one line.
2. Level shifter — measure 3.3 V on VCCA and 5 V on VCCB. **If the sensor accepts 3.3 V, skip this board
   entirely** — one module and eight wires fewer is one less thing to go intermittent.
3. Turbidity sensor — I2C scan finds address `0x49`; clear water reads high, cloudy reads low. Confirm a
   4.7 kΩ pull-up on both SDA and SCL; without them the reads are intermittent, which is the hardest
   fault to diagnose.
4. Fill light — **the MOSFET ground and the ESP32 ground must be common**; drive the gate with PWM and
   confirm brightness rises monotonically from 0 to 100 %. The light board runs from its own 12 V supply
   and **must not be powered from the ESP32's 5 V pin**.
5. Camera — exposure lock, `python scripts/test_exposure.py` exits 0; at a fixed light level, left/right
   brightness ratio ≥ 0.7 and a 5 cm target ≥ 45 px at 640.

## 5. Acceptance numbers

| Check | Pass |
|---|---|
| Exposure | `CAP_PROP_EXPOSURE` writes and reads back a different value |
| Frame stability | 20 consecutive frames, mean brightness spread < 10 % |
| Lighting | Left/right half brightness ratio ≥ 0.7, no hot spot on the tank wall |
| Flicker | Filmed by a phone camera, no rolling bars |
| Light control | PWM from 30 % to 80 % raises mean brightness monotonically, without flicker |
| Common ground | Light board negative, MOSFET ground and ESP32 ground all show continuity |
| Target size | A 5 cm object ≥ 45 px wide at 640 input |
| Turbidity | Clear water reads higher than water with a spoon of milk |
| Tank | 24 h filled, no seepage, front wall without scratches or tint |
