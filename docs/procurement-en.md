# Procurement

> Chinese version: [procurement-zh.md](procurement-zh.md). This file is the source of truth.

> Owner: @FrozenYty · Revisit when: the hardware changes

Final bill of materials: nine items were ordered on 2026-11-05 (¥377.42), and the 330 ohm resistors and the trigger button joined the list on 2026-11-10, making eleven items and ¥388.32. This is the list the
rig is built from; changing it means changing PLAN.md P0-03 and this document together. Brand names
and the Chinese search strings are listed in the Chinese version; this file describes the same parts
in English.

## 1. Final list

| # | Item | Model / part | Qty | Unit ¥ | Channel | Purpose |
|---|---|---|---|---|---|---|
| 1 | USB camera | 1080P UVC module, 3.6 mm low-distortion lens, metal housing | 1 | 200.60 | JD | Image capture |
| 2 | Glass tank | Low-iron ultra-clear glass, 300×170×200 mm, 5 mm walls, bare tank | 1 | 48.90 | JD | Capture chamber |
| 3 | Linear polariser | FINNER PL sheet, gloss finish, no adhesive, 200×200 mm, 0.2 mm | 1 | 35.60 | JD | Cross-polarisation, two pieces cut from one sheet |
| 4 | MCU board | DZYJ ESP32-S3 N16R8 DevKitC, headers pre-soldered | 1 | 26.60 | JD | Trigger, I2C master |
| 5 | Level shifter | 8-channel bidirectional 3.3 V ↔ 5 V, headers pre-soldered | 1 | 7.10 | JD | Bridges the 5 V sensor to 3.3 V GPIO |
| 6 | Jumper wires | DZYJ 40-pin ribbon, male-male / male-female / female-female, 120 pcs | 1 | 8.26 | JD | All wiring |
| 7 | Breadboard | DZYJ MB-102, 1660 tie points, with power rails | 1 | 23.70 | JD | Solderless assembly; the 405-hole board is too small once the ESP32 and shifter are seated |
| 8 | Turbidity sensor | LIGHT ME2100A-IIC, I2C, reflective | 1 | 18.82 | LCSC | Reads water clarity |
| 9 | Sensor cable | WHEELTEC GH1.25 4-pin to Dupont female, 200 mm | 1 | 7.84 | JD | Turbidity sensor to the level shifter pins |
| 10 | Resistors | LR1F330R metal film 330 Ω ±1% 600 mW, through-hole, 10 pieces | 1 | 5.10 | LCSC | LED current limiting; the rig needs two, the rest are spares |
| 11 | Trigger button | XKB8080-W 8×8 through-hole **momentary** switch, blue cap, 13.65 mm tall, 5 pieces | 1 | 5.80 | LCSC | Panel mount; the larger cap and height fix the kit's hard-to-hit small switch |

**Total ¥388.32.** The status display (0.96" OLED) and the green and yellow LEDs come from the STM32 kit on hand and are not bought. The fill light is the Midea MT-10T4 lamp already on hand: 10 W, 4000 K, Ra90,
USB-powered (DC) and advertised as flicker-free. A strip was planned on 11-07 and withdrawn the same
day after the lamp was checked — ADR 10.

## 2. Deliberately not bought

| Item | Why not |
|---|---|
| Capture light | The team's existing Midea MT-10T4 desk lamp: 10 W, 4000 K, USB-powered, no visible flicker. Buying a light is only revisited if the acceptance numbers are not met (ADR 10). |
| Acrylic tank | Ultra-clear glass is cheaper, has no stress birefringence, and keeps cross-polarisation working. |
| Target models | Real seafood bought on the day. Natural colour, natural sinking, naturally wet and specular — which is what the polariser exists for. |
| Scenery | Stones and plants found on site. One dark stone shaped like a sea cucumber is enough to stage a false positive. |
| Water level sensor | The tank level is constant and nothing depends on it. It is not in the SRS. |
| Water temperature probe | It fills one field and drives no decision. The SRS states that missing sensor fields stay empty and are excluded from statistics. |
| Second lamp | Only if the left/right brightness ratio fails; see `PROGRESS.md` 2026-11-05. |

## 3. Things to verify before assembly

- **Camera exposure lock — verified on arrival, 11-10.** `python scripts/test_exposure.py --index 1` exits
  0: 1080p, exposure controllable, lock holds a 0.5 % frame-to-frame spread, 5 fps. Three things the unit
  taught us that no datasheet said:
  - **It is index 1**, not 0 — index 0 is the laptop's built-in camera.
  - **Never use 720p on this unit**: that mode stalls at 1 fps. 1080p gives 5 fps (the USB 2.0 ceiling
    for uncompressed video) and 640×480 gives 30 fps. MJPEG is ignored.
  - **Exposure must be set explicitly** — the device opens at whatever auto-exposure last chose, which
    was dark enough that every frame failed the quality gate. Use
    `python -m app.vision.capture --camera 1 --exposure -6` from `server/`.
  - **White balance must stay automatic.** Manual balance on this driver is a lie: it echoes the
    temperature back without acting on it, and the colour cast score drops from 83 to 0.
- **Button.** The XKB8080-W must be the **momentary** version. A latching one stays closed after the
  press and needs a second press to release, while the firmware triggers on the closing edge once —
  the result is one frame per two presses. Check the listing says momentary before ordering. Six pins
  are internally paired: **find the pair that closes with a multimeter**, do not guess from the
  layout; a wrong pair shows up as "the button does nothing".
- **Panel hole.** Drill for the cap only, about 5 mm; the 8×8 mm body sits behind the panel. An 8 mm
  hole leaves the switch loose. Check its legs are straight: the
  PCB-mount parts with bent legs bought earlier will not seat in a breadboard. A latching switch would
  not work here — the firmware expects a falling edge per press.
- **Sensor cable.** GH1.25 to Dupont female. A single-ended tinned cable has nothing to plug into.

## 4. Assembly order

Assemble and power on in six steps, one at a time, so a fault is localised immediately:

1. ESP32 + tactile switch — serial prints a line on each press. **Debounce first**: one press, one line.
2. Level shifter — measure 3.3 V on VCCA and 5 V on VCCB. **This board cannot be skipped:** rev A3 of the
   ME2100A-IIC datasheet dropped the 3.3 V specification, so the part runs at 4.5-5.5 V and its I2C
   lines are pulled up to 5 V, which the ESP32 does not tolerate. Low side to the ESP32's 3V3 and
   GPIO8/9; high side to 5 V and the sensor's SDA/SCL.
3. Turbidity sensor — I2C scan finds address `0x49`; clear water reads high, cloudy reads low. Confirm a
   4.7 kΩ pull-up on both SDA and SCL; without them the reads are intermittent, which is the hardest
   fault to diagnose.
4. Fill light — run the lamp **on USB, not on its battery**: falling charge drifts the brightness.
   Set one touch-dimming level and **tape over the touch area**. Tape the polariser flat to the lamp
   head, corners taut, no warp.
5. Display and LEDs — an I2C scan shows both `0x3C` (OLED) and `0x49` (turbidity); the screen boots to
   `AQUAVISION` then settles on `READY`; a button press pulses the green or yellow LED for 300 ms.
6. Camera — exposure lock, `python scripts/test_exposure.py` exits 0; then `python scripts/test_rig.py`
   exits 0, which measures the left/right brightness ratio, the 5 cm target width and the brightness
   drift of a ten-minute run under a fixed light level. **Both are required**: the first asks whether
   the camera can be used, the second whether the picture is good enough to detect on.

## 5. Power and wiring

One 12 V adapter feeds an MB-102 breadboard supply, and **that supply powers only the 5 V side of the
rig**. The controller keeps its own: the USB cable to the PC carries both power and the serial link, and
the board's own regulator makes the 3.3 V that the OLED and the shifter's low side run on. Two supplies,
one ground.

| Rail | Source | Loads |
|---|---|---|
| 5 V | 12 V adapter into the MB-102, its rail jumper set to 5 V | turbidity sensor VCC, shifter VCCB, the two 4.7 kOhm pull-ups |
| 3.3 V | the controller board's `3V3` pin | OLED VCC, shifter VCCA, the ESP32's own logic |
| ground | common | every part, including the adapter's negative lead |

```mermaid
flowchart LR
  DC["12 V adapter"] --> MB["MB-102, rail jumper on 5 V"]
  MB -->|"5 V"| S["Turbidity ME2100A-IIC, 0x49"]
  MB -->|"5 V"| HV["BSS138 VCCB"]
  HV ---|"B0 / B1"| S
  PC["PC USB"] -->|"power and data"| ESP["ESP32-S3, USB-UART"]
  ESP -->|"3V3"| LV["BSS138 VCCA"]
  ESP -->|"3V3"| OLED["OLED, 0x3C"]
  LV ---|"A0 / A1"| ESP
  ESP --> B["button, GPIO4"]
  ESP --> L1["green LED, GPIO5"]
  ESP --> L2["yellow LED, GPIO6"]
  GND["common ground"] --- MB
  GND --- ESP
  GND --- S
```

| From | To | Why it matters |
|---|---|---|
| MB-102 5 V | sensor VCC | the part is specified 4.5-5.5 V, and rev A3 dropped the 3.3 V that earlier revisions carried |
| MB-102 5 V | shifter VCCB | the far side of the bus is 5 V |
| board `3V3` | shifter VCCA | the near side must match the ESP32's logic level |
| GPIO8 | shifter A0, then B0 to sensor SDA | wiring the sensor straight to GPIO8 puts 5 V on a 3.3 V pin |
| GPIO9 | shifter A1, then B1 to sensor SCL | the same, on the clock |
| sensor SDA and SCL | 4.7 kOhm to **5 V** | the pull-ups belong on the high side |
| GPIO4 | button, other leg to GND | the part must be momentary: a latching one gives one frame per two presses |
| GPIO5, GPIO6 | 330 Ohm into an LED, cathode to GND | one resistor per LED, not one shared |

**Check three things before the first power-on.** Measure the MB-102's 5 V rail with nothing else
connected: on several boards that rail passes the input through instead of regulating it, so 12 V arrives
where 5 V is printed and the sensor does not survive it. Check whether the shifter board already carries
10 kOhm pull-ups on each side, because adding 4.7 kOhm beside them leaves about 3.2 kOhm - usable at
100 kHz, but not something to stack twice. And the register that holds the turbidity reading is still
unknown, so the first reading is an experiment: try a bare read, then reads after writing commands `0x00`
to `0x03`, and keep the one whose value falls as the water gets turbid.

## 6. Acceptance numbers

| Check | Pass |
|---|---|
| Exposure | `CAP_PROP_EXPOSURE` writes and reads back a different value |
| Frame stability | 20 consecutive frames, mean brightness spread < 10 % |
| Lighting | Left/right half brightness ratio ≥ 0.7, no hot spot on the tank wall |
| Flicker | Filmed by a phone camera, no rolling bars |
| Light stability | Ten minutes of capture on USB: mean brightness of the first and last frame differ by < 5 % |
| Polariser flatness | No visible warp; the lens-side sheet locked at the darkest orientation |
| Target size | A 5 cm object ≥ 45 px wide at 640 input |
| Turbidity | Clear water reads higher than water with a spoon of milk |
| Tank | 24 h filled, no seepage, front wall without scratches or tint |
