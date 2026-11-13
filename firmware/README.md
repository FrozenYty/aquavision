# Rig controller

> Chinese version: [README-zh.md](README-zh.md). This file is the source of truth.

The ESP32-S3 in `main/` is the part of the rig a person touches. It reports a button press, reads the
turbidity sensor, shows the last capture's verdict on a 0.96" OLED, and lights one of three LEDs.

It does **no imaging and no inference**. The PC owns both, and the PC is the only authority on a
frame's quality — the firmware displays what it is told.

## Status: first draft, exercised on the panel

The screen layout is a **first draft**, agreed on 2026-11-07. The display was wired to the board and the
five screens were driven on 2026-11-10 (see "What the arrival board settled"), but the full rig is not
assembled: every coordinate in `src/screen.cpp` stays provisional until it is on the bench.

## Where things live

| File | What it owns | Edit it when |
|---|---|---|
| `src/config.h` | pins, timings, I2C addresses | a wire moves, or a period feels wrong |
| `src/rig_state.h` | what the rig knows: screen, score, reason, turbidity, frame count, link | a new value has to be remembered |
| `src/screen.cpp` | the 128×64 layout, one function per state | the screen should look different |
| `src/protocol.cpp` | the serial grammar | the PC and the board must say something new |
| `src/main.cpp` | the loop that calls the four above | almost never |

Adding a screen state is four edits: an entry in `rig::Screen`, a `drawX` function in `screen.cpp`, a
`case` in `render()`, and a `case` in `screenName()` in `protocol.cpp` so the PC receives a name it knows.
Adding a field to the display is one line in `rig::State` and one in the function that draws it. Nothing
else in the firmware knows about pixels.

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
| White LED (PASS) | GPIO 5 | anode to +5 V, cathode through 330 Ω; **the pin sinks, so LOW lights it** |
| Yellow LED (RETAKE) | GPIO 6 | the same |
| Blue LED (state) | GPIO 7 | the same; lit on every screen the other two do not cover |
| OLED SDA | GPIO 8 | I2C, address 0x3C |
| OLED SCL | GPIO 9 | I2C |
| Turbidity SDA | GPIO 8 | same bus, address 0x49 |
| Turbidity SCL | GPIO 9 | same bus |

Each LED needs its own resistor, and **the resistor sits on the cathode side, between the lamp and the
pin**. From 3.3 V a 2 V LED has 1.3 V of headroom, so 330 Ω leaves under 4 mA - too dim to read across a
bench - while the same resistor on the 5 V rail gives about 9 mA. The pin sinks that current and never
sees the rail, because the LED is between the two. HIGH is therefore dark and LOW is lit, which is the
opposite of the obvious wiring; check it before wondering why nothing lights.

## The screen

128 x 64, monochrome, five bands whose baselines are named constants so nothing shifts between states:

```
y 1..7    AQUAVISION                                  ONLINE        disc on the caps' centre row
y 8       -------------------------------------------------------
y 12..31                              94                            18 px score, right-aligned
          QUALITY                                                   7x13 bold label, rows 17-26
y 33..53  +-----------------------------------------------------+
          |                       RETAKE                        |    filled = PASS, outline = RETAKE
          +-----------------------------------------------------+
y 54      -------------------------------------------------------
y 55..62  TURB 12400                                  FRAMES 12
```

**Shape carries the verdict.** A pass fills the banner, a retake outlines it, so the two are
distinguishable from across the room before a single letter is legible. The score row's label is the
word `QUALITY` on a pass and the reason on a retake — that is what let the banner shrink to one word
instead of stacking two lines into twenty pixels, which left one pixel between them and read as a
smudge.

**The label and the number share a centre line.** Measured on the panel: the score font reports ascent
19, so at baseline 31 its digits occupy rows 12-31; the bold 7x13 label reports ascent 9, so at baseline
26 it occupies 17-26. Both centre on 21.5. A 5x7 label at the same baseline sat 1.5 px low.

**The footer keeps one gutter width.** Label, six pixels, value - the same in both columns. The
turbidity value is left-aligned after that gutter because right-aligning it left a two-pixel gap after a
five-digit reading and a wide one after a three-digit reading: two different gaps in one row. The
placeholder is five dashes, matching the width of the reading, so the row does not jump when data
arrives.

**States without a score use the free band.** READY puts `PRESS TO CAPTURE` there and CAPTURING puts
three dots, one lit at a time at a quarter-second. At three pixels a filled and a hollow mark were
indistinguishable; at radius 2 the animation reads. OFFLINE replaces the whole screen with three centred
lines - the earlier single line at 12 px was wider than the panel and lost its last letters.

**There is no trend mark.** The code drew a triangle for rising, falling and steady, decided by an
absolute threshold of two counts on a reading that spans 700-16000. Two counts is noise at that scale, so
the mark flickered; and at five digits it collided with `FRAMES`. A trend worth showing has to be
relative, and until there is a reason for one the reading itself is the honest display.

## Serial protocol

One message per line at 115200 baud, ASCII, `\n` terminated. A line is limited to 95 characters: on
overflow the buffer resets, so anything longer is not handled as one message. The firmware ignores
anything it does not understand, so a garbled byte cannot brick the rig.

| Direction | Message | Meaning |
|---|---|---|
| → PC | `EVT HELLO <version>` | the board is up |
| → PC | `EVT I2C <addr>` | one line per device that answered the boot scan |
| → PC | `EVT SCREEN <name> <score>` | a screen change: READY, CAPTURING, PASS, RETAKE, OFFLINE. A capture timeout sends `EVT TIMEOUT` first and this second |
| → PC | `EVT TRIGGER <millis>` | the button was pressed and a capture started |
| → PC | `EVT TURBIDITY <value>` | a fresh reading, every 5 s |
| → PC | `EVT TIMEOUT <millis>` | no verdict arrived within 5 s; the screen changes to RETAKE, and `EVT SCREEN RETAKE -1` follows |
| → PC | `EVT STRAY RESULT <score>` | a verdict arrived with no capture in flight; it was **not** applied |
| → PC | `EVT INVARIANT <screen> <link>` | a screen/link pair that should be impossible; never expected on the wire |
| → PC | `EVT PONG` | answer to `CMD PING` |
| PC → | `CMD RESULT <score> <PASS\|RETAKE> <REASON>` | what to display, valid only in CAPTURING; the score is clamped to 0-100 |
| PC → | `CMD READY` | back to the idle screen |
| PC → | `CMD PING` | liveness check |
| PC → | `CMD SCAN` | rescan the I2C bus and report every address that answers |

`REASON` is one token: `LOW_LIGHT`, `BLUR`, `COLOR_CAST`, `NONE`, `UNKNOWN` or `NO_REPLY`. `NO_REPLY` is
generated by the rig and never sent to it; `UNKNOWN` is what the server sends when no sub-score names a
cause (`server/app/rig/protocol.py`), and the rig also stores it for any token it does not recognise.

**The PC half now exists** (`server/app/rig/`, P2-17): the server opens the port, sends `CMD PING`
every two seconds, turns `EVT TRIGGER` into a capture and a `CMD RESULT`, and logs every screen change the
rig reports. Its own state machine and the reason a failed capture sends *nothing* - the rig's timeout
then says `NO REPLY`, which is true - are in `docs/rig-state-machine-en.md` §9.

**The PC owns the link, and silence means it is gone.** The rig cannot see whether the USB cable is
plugged in - it talks UART through a bridge chip and has no carrier signal - so liveness is a protocol
matter: **the PC must send `CMD PING` at least every two seconds on an open link**, and the rig declares
`OFFLINE` after ten seconds without a command (five missed keepalives).

The rig boots on `READY` with a ten-second grace, which is far longer than the PC needs to send its first
keepalive. A panel that calls itself dead before anything has had a chance to speak reads as a fault
rather than as waiting. From then on the two are a pair - `OFFLINE` if and only if the link is gone - and
an idle rig stays `READY` only because the PC keeps saying so. A rig on a bench with no PC software goes
`OFFLINE` ten seconds after power-up, which is correct: there is nobody on the other end. `rig::invariantHolds` checks that pairing every loop pass and reports `EVT INVARIANT` if it is ever
broken.

**A verdict is the answer to a capture, so it is only accepted while one is in flight.** A RESULT in any
other state is dropped and reported as `EVT STRAY RESULT`; the PC is told rather than left believing the
rig took it. The rules behind that, and every state/event pair, are in `docs/rig-state-machine-en.md`.

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

**Bus changes need no reboot.** `CMD SCAN` rescans the I2C bus and reports every address that answers,
so a wiring change is tested by sending one line instead of power-cycling and watching the boot window.
It was added during the turbidity bring-up for exactly that reason: the boot scan is the only other look
at the bus, and it happens before anyone has had a chance to move a wire.

**Opening the serial port resets the board.** The bridge chip's DTR and RTS lines feed the auto-reset
circuit, so the sketch restarts whenever a program opens `COM5` — the log begins with the ROM boot banner
and a fresh `EVT SCREEN READY`. That is the board behaving correctly, and it is worth knowing before
debugging: a reader that connects and then waits eleven seconds will watch the rig go `OFFLINE`, because
the boot happens first and the ten-second link timer starts at the same moment. Test the keepalive on a
port held open, not by reconnecting.

Two consequences for tooling. A bench check that opens the port and exits leaves the rig freshly booted,
not in whatever state it was in. And a server restart is a board restart: the link does not "reconnect",
it starts over.

**The OLED is verified.** Wired directly to the ESP32 - `VCC` to `3V3`, `SDA` to `GPIO8`, `SCL` to
`GPIO9` - the scan reports `EVT I2C 3C`, the splash draws, and `CMD PING` answers `EVT PONG`, so the
PC-to-board command path works as well as the display. The five screens were then driven from the
serial port without a button: `CMD RESULT 94 PASS OK`, `CMD RESULT 30 RETAKE LOW_LIGHT`,
`CMD RESULT 55 RETAKE COLOR_CAST`, `CMD RESULT 20 RETAKE UNKNOWN`, and `OFFLINE` by simply staying
silent for the ten-second timeout.

**Not yet verified:** the three status LEDs, because the 330 ohm resistors had not arrived; the button,
which had not arrived either; and the turbidity sensor, which needs the level shifter first.

## Hardware reference

The three vendor documents behind the rig are **not in this repository**: the repository is public, and
the turbidity manual forbids disclosure to third parties without written consent. Facts learned from a
document can be recorded; the document itself cannot be republished. The hardware lead holds copies and
will provide them on request.

| Document | Part | What it settled |
|---|---|---|
| Manufacturer datasheet | ESP32-S3-WROOM-1 | GPIO are 3.3 V, 40 mA maximum drive per pin |
| Module datasheet | 0.96" 128x64 OLED, SSD1306 | I2C address `0x3C`, supply 2.8–3.3 V — the 3V3 rail is correct |
| Sensor manual, rev A3 | ME2100A-IIC turbidity sensor | **supply 4.5–5.5 V**, address `0x49`, clean water reads high, turbid water reads low |

The last column is what this project measured or read and decided to rely on. A document that is not in
the repository cannot be cited by filename: **the name of a PDF on someone's disk is as unportable as a
path**, and a reader who cannot open the file gains nothing from knowing what it is called.

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
