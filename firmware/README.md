# Rig controller

The ESP32-S3 in `main/` is the part of the rig a person touches. It reports a button press, reads the
turbidity sensor, shows the last capture's verdict on a 0.96" OLED, and lights one of two LEDs.

It does **no imaging and no inference**. The PC owns both, and the PC is the only authority on a
frame's quality — the firmware displays what it is told.

## Build and flash

```
cd firmware/main
pio run                 # compile
pio run --target upload # flash
pio device monitor      # watch the protocol
```

PlatformIO pulls U8g2 at the pinned version. If `pio` is not installed:

```
python -m pip install platformio
```

## Wiring

| Signal | ESP32-S3 | Note |
|---|---|---|
| Button | GPIO 4 | to GND; `INPUT_PULLUP`, so a press reads LOW |
| Green LED | GPIO 5 | series resistor, 330 Ω |
| Yellow LED | GPIO 6 | series resistor, 330 Ω |
| OLED SDA | GPIO 8 | I2C, address 0x3C |
| OLED SCL | GPIO 9 | I2C |
| Turbidity SDA | GPIO 8 | same bus, address 0x49 |
| Turbidity SCL | GPIO 9 | same bus |

Both LEDs need a resistor. Three 1 kΩ resistors in parallel make 333 Ω, which is close enough and
saves buying anything if the parts box already has a bag of 1 kΩ.

## The screen

128 × 64, monochrome. Five bands, with every baseline a named constant so nothing shifts between
states:

```
y 0                                      AQUAVISION  ·  online, disc blinks while idle
y 9   ─────────────────────────────────────────────────────────────────────────────
y26   QUALITY                                    86      label 5x7, value 24 px, same row
y35   ████████████████████████████████████████████████████████████████████████████
y49   █                              PASS >=60                                  █
y51   ─────────────────────────────────────────────────────────────────────────────
y62   TURB 12 ^                                          FRAMES 34                       5x7
```

The footer says `TURB`, not `TURBIDITY`: at 6 px per glyph the full word runs to x=88 while
`FRAMES 34` starts at x=70, and the two collide. Dropping the frame counter would let the full word
back in — a trade worth making only if the counter turns out to matter less than the label.

The label and the number **share a centre line** (`Y_LABEL_BASELINE` 26, `Y_VALUE_BASELINE` 32) —
a 5x7 label sitting above a 24 px number reads as two unrelated rows, which is how the first draft of
this code looked.

A retake replaces the footer's turbidity reading with the reason — `LOW LIGHT`, `BLUR`, `COLOR CAST` —
because a score without a cause tells the operator nothing to do.

Everything on the screen is ASCII. That is deliberate: a Chinese font costs one to two megabytes of
flash for the fourteen words this screen needs, and the labels stay unambiguous either way.

## Serial protocol

One message per line, ASCII, `\n` terminated. The firmware ignores anything it does not understand, so
a garbled byte cannot brick the rig.

| Direction | Message | Meaning |
|---|---|---|
| → PC | `EVT HELLO 1.0` | the board is up |
| → PC | `EVT TRIGGER <millis>` | the button was pressed |
| → PC | `EVT TURBIDITY <0-100>` | a fresh reading, every 5 s |
| → PC | `EVT PONG` | answer to `CMD PING` |
| PC → | `CMD RESULT <score> <PASS\|RETAKE> <REASON>` | what to display |
| PC → | `CMD READY` | back to the idle screen |
| PC → | `CMD PING` | liveness check |

`REASON` is one token: `LOW_LIGHT`, `BLUR`, `COLOR_CAST` or `NONE`.

## Two things not yet verified

1. **This has never been compiled.** No PlatformIO toolchain existed on the machine it was written on.
   The first task on the rig is `pio run`, and the first thing to expect is a compile error, not a
   working board.
2. **The turbidity read is a guess.** `readTurbidity()` assumes two bytes, big-endian, from address
   0x49. The ME2100A-IIC datasheet has not been checked against it. Confirm the register layout before
   trusting the number on screen — a plausible but wrong reading is worse than none.
