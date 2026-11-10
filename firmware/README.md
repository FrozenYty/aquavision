# Rig controller

The ESP32-S3 in `main/` is the part of the rig a person touches. It reports a button press, reads the
turbidity sensor, shows the last capture's verdict on a 0.96" OLED, and lights one of two LEDs.

It does **no imaging and no inference**. The PC owns both, and the PC is the only authority on a
frame's quality — the firmware displays what it is told.

## Status: draft

The screen layout is a **first draft**, agreed on 2026-11-07 and never seen on a real panel. Every
coordinate in `src/screen.cpp` is provisional until the rig is on the bench.

## Where things live

| File | What it owns | Edit it when |
|---|---|---|
| `src/config.h` | pins, timings, I2C addresses | a wire moves, or a period feels wrong |
| `src/rig_state.h` | what the rig knows: screen, score, turbidity, trend | a new value has to be remembered |
| `src/screen.cpp` | the 128×64 layout, one function per state | the screen should look different |
| `src/protocol.cpp` | the serial grammar | the PC and the board must say something new |
| `src/main.cpp` | the loop that calls the four above | almost never |

Adding a screen state is three edits: an entry in `rig::Screen`, a `drawX` function in `screen.cpp`, and
a `case` in `render()`. Adding a field to the display is one line in `rig::State` and one in the
function that draws it. Nothing else in the firmware knows about pixels.

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

## What the arrival board settled

The first board was flashed on 2026-11-10 and the first assumption did not survive. `Serial` was
pointed at the S3's native USB port, so the UART bridge showed ROM boot messages and nothing from the
sketch — a board that looked dead while it was running perfectly. `ARDUINO_USB_CDC_ON_BOOT` is now 0,
which puts the sketch on UART0: one cable flashes and monitors, and no BOOT button is needed.

`setup()` also scans the I2C bus once and prints one `EVT I2C <addr>` line per device that answers.
That is how a missing display or an unplugged sensor becomes visible in the serial log instead of only
as a blank screen — during assembly it is the fastest check there is.

Verified on the board: the image flashes and verifies, the firmware prints `EVT HELLO 1.1`, and the
I2C scan reports nothing when nothing is wired.

**The OLED is verified.** Wired directly to the ESP32 - `VCC` to `3V3`, `SDA` to `GPIO8`, `SCL` to
`GPIO9` - the scan reports `EVT I2C 3C`, the splash draws, and `CMD PING` answers `EVT PONG`, so the
PC-to-board command path works as well as the display. The five screens were then driven from the
serial port without a button: `CMD RESULT 94 PASS OK`, `CMD RESULT 30 RETAKE LOWLIGHT`,
`CMD RESULT 55 RETAKE COLORCAST`, `CMD RESULT 20 RETAKE UNKNOWN`, and `OFFLINE` by simply staying
silent for the ten-second timeout.

**Not yet verified:** the two status LEDs, because the 330 ohm resistors had not arrived; the button,
which had not arrived either; and the turbidity sensor, which needs the level shifter first.

## Hardware reference

The three vendor documents behind the rig are kept **outside the repository**, in the submission
folder's `datasheets/` directory — not here: the repository is public, and the turbidity manual forbids
disclosure to third parties without written consent. Facts learned from a document can be recorded; the
document itself cannot be republished.

| Datasheet | Part | What it settled |
|---|---|---|
| `esp32-s3-wroom-1.pdf` | ESP32-S3-WROOM-1 | GPIO are 3.3 V, 40 mA maximum drive per pin |
| `oled-hs96l03w2c03.pdf` | 0.96" 128x64 OLED | I2C address `0x3C`, supply 2.8–3.3 V — the 3V3 rail is correct |
| `turbidity-me2100a-iic.pdf` | ME2100A-IIC, rev A3 | **supply 4.5–5.5 V**, address `0x49`, clean water reads high, turbid water reads low |

**The turbidity sensor is a 5 V part, and that changes the wiring.** Rev A3 removed the 3.3 V
specification earlier revisions carried, and its interface tolerates up to 5.5 V — which the ESP32 does
not. A level shifter on SDA and SCL is **required**, not optional; the assembly plan previously called
it skippable.

## Still not verified

1. **Which register the turbidity value lives in is unknown.** The manual describes how to read a
   register — start, address write, command byte, repeated start, address read, data — but never says
   which register holds the measurement. `readTurbidity()` currently does a bare two-byte read with no
   command byte, relying on the device's pointer already sitting on the measurement. The address and
   the two-byte width are now confirmed; the register is not. Resolve it by measurement once the sensor
   is wired: try a bare read, then reads after writing commands `0x00`–`0x03`, and keep the one whose
   value falls as the water gets turbid. A plausible but wrong number on the screen is worse than none.
