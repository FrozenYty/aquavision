# Procurement

> Chinese version: [procurement-zh.md](procurement-zh.md). This file is the source of truth.

Final bill of materials, frozen on 2026-11-05. Ten items, three channels, ¥374.46 before shipping.
This is the list the rig is built from; changing it means changing `PLAN.md` P0-03 and this document
together.

## 1. Final list

| # | Item | Model / part | Qty | Unit ¥ | Channel | Purpose |
|---|---|---|---|---|---|---|
| 1 | USB camera | 柏立 1080P UVC module, 3.6 mm low-distortion lens, with housing | 1 | 200.60 | JD | Image capture |
| 2 | Glass tank | 坤宁王 ultra-clear glass 300×170×200 mm, 5 mm walls, bare tank | 1 | 46.99 | JD | Capture chamber |
| 3 | Linear polariser | FINNER 无胶光面 PL, 200×200 mm, 0.2 mm | 1 | 35.60 | JD | Cross-polarisation, two pieces cut from one sheet |
| 4 | MCU board | DZYJ ESP32-S3 N16R8 DevKitC, headers pre-soldered | 1 | 26.60 | JD | Trigger, PWM, I2C master |
| 5 | Level shifter | 大富瑞 8-channel bidirectional 3.3 V ↔ 5 V, headers pre-soldered | 1 | 7.10 | JD | Bridges the 5 V sensor to 3.3 V GPIO |
| 6 | Jumper wires | DZYJ 40-pin ribbon, male-male / male-female / female-female, 120 pcs | 1 | 8.26 | JD | All wiring |
| 7 | Breadboard | DZYJ MB-102, 1660 tie points, with power rails | 1 | 23.70 | JD | Solderless assembly |
| 8 | Turbidity sensor | LIGHT ME2100A-IIC, I2C, reflective | 1 | 18.82 | LCSC | Reads water clarity |
| 9 | Sensor cable | WHEELTEC GH1.25 4-pin to Dupont female, 200 mm | 1 | 7.84 | JD | Turbidity sensor to the level shifter pins |
| 10 | Button module | Tactile switch on a small PCB, 2.54 mm pins | 1 | 3.00 | JD | Physical capture trigger |

**Total ¥382.43.** Two corrections were made after the first checkout: the GH1.25 cable must end in Dupont female sockets (a tinned end does not hold in a breadboard), and the tactile switch must be a through-hole or module version (the 6×6 mm PCB-mount switches bought first have bent legs that will not seat).

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

- **Camera exposure lock.** The module was bought from a different listing than the one whose seller
  confirmed UVC exposure control. Run `test_exposure.py` the day it arrives; if exposure cannot be
  locked, fall back to fixed lighting with a 15 % brightness tolerance and record the change.
- **Tactile switch package.** The listing names both “贴片” (SMD) and “DIP-4P”. SMD parts cannot be
  plugged into a breadboard. Confirm through-hole legs on arrival.
- **Sensor cable.** The purchased cable is single-ended with tinned wire. A 28 AWG tinned end does not
  hold in a breadboard socket; either replace it with a GH1.25-to-Dupont-female cable or insert the
  tinned end into a screw terminal.

## 4. Assembly order

Assemble and power on in four steps, one at a time, so a fault is localised immediately:

1. ESP32 + tactile switch — serial prints a line on each press.
2. Level shifter — measure 3.3 V on VCCA and 5 V on VCCB.
3. Turbidity sensor — I2C scan finds address `0x49`; clear water reads high, cloudy reads low.
4. Camera + lighting — exposure lock, left/right brightness ratio ≥ 0.7, 5 cm target ≥ 45 px at 640.

## 5. Acceptance numbers

| Check | Pass |
|---|---|
| Exposure | `CAP_PROP_EXPOSURE` writes and reads back a different value |
| Frame stability | 20 consecutive frames, mean brightness spread < 10 % |
| Lighting | Left/right half brightness ratio ≥ 0.7, no hot spot on the tank wall |
| Flicker | Filmed by a phone camera, no rolling bars |
| Target size | A 5 cm object ≥ 45 px wide at 640 input |
| Turbidity | Clear water reads higher than water with a spoon of milk |
| Tank | 24 h filled, no seepage, front wall without scratches or tint |
