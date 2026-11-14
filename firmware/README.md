# Rig controller

> Chinese version: [README-zh.md](README-zh.md). This file is the source of truth.

The ESP32-S3 in `main/` is the part of the rig a person touches. It reports a button press, shows the last
capture's verdict on a 0.96" OLED, and drives a four-digit seven-segment display. There is no turbidity
sensor and there are no status lamps: the sensor was removed on 2026-11-14 because no register of it
followed the water (`P3-37` records the evidence), and the pins the lamps sat on are the display's commons
now.

It does **no imaging and no inference**. The PC owns both, and the PC is the only authority on a
frame's quality — the firmware displays what it is told.

## Status: the OLED exercised on the panel, the display not yet wired

The OLED layout is a **first draft**, agreed on 2026-11-07. That display was wired to the board and the
five screens were driven on 2026-11-10 (see "What the arrival board settled"), but the full rig is not
assembled: every coordinate in `src/screen.cpp` stays provisional until it is on the bench.

The four-digit display exists in the firmware and nowhere else yet. Its faces run in `main.cpp` and its
pins are declared in `config.h`; the panel is `P3-17`'s to put on the bench.

## Where things live

| File | What it owns | Edit it when |
|---|---|---|
| `src/config.h` | pins, timings, I2C addresses | a wire moves, or a period feels wrong |
| `src/rig_state.h` | what the rig knows: screen, score, reason, session tally, frame count, fault, link | a new value has to be remembered |
| `src/screen.cpp` | the OLED's 128×64 layout, one function per state | the screen should look different |
| `src/protocol.cpp` | the serial grammar | the PC and the board must say something new |
| `src/main.cpp` | the loop, the button gesture, the display's faces, and the timer that multiplexes them | almost never |

Adding a screen state is five edits: an entry in `rig::Screen`, a `drawX` function in `screen.cpp`, a
`case` in `render()`, a `case` in `screenFace()` in `main.cpp` so the panel has a face for it, and a
`case` in `screenName()` in `protocol.cpp` so the PC receives a name it knows. Adding a field to the OLED
is one line in `rig::State` and one in the function that draws it. Nothing else in the firmware knows
about pixels.

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
| Display segment A | GPIO 3 | 240 Ω between the pin and the segment |
| Display segment B | GPIO 13 | the same |
| Display segment C | GPIO 14 | the same |
| Display segment D | GPIO 15 | the same |
| Display segment E | GPIO 16 | the same |
| Display segment F | GPIO 17 | the same |
| Display segment G | GPIO 18 | the same |
| Display digit 1 (left) | GPIO 5 | the common, direct: no resistor |
| Display digit 2 | GPIO 6 | the same |
| Display digit 3 | GPIO 7 | the same |
| Display digit 4 (right) | GPIO 10 | the same |
| OLED SDA | GPIO 8 | I2C, address 0x3C |
| OLED SCL | GPIO 9 | I2C |

**The panel is common anode, which decides what HIGH means.** A digit's common pin driven HIGH selects
that digit, and a segment pin driven LOW lights that segment, so a dark segment is a HIGH pin - the
opposite of the obvious wiring. Check that before wondering why nothing lights.

Each segment has its own 240 Ω resistor between the pin and the segment, and the commons have none. A
common therefore carries the sum of its digit's segment currents, and **only one common may be high at
any moment** - which is what the multiplexer in `main.cpp` guarantees.

Every pin of the panel is a GPIO, so it runs from the board's own 3.3 V through the pins: there is no
supply pin on the display and no 5 V rail in this wiring.

## The OLED screen

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
y 55..62  P3 R1                                    FRAMES 12
```

**Shape carries the verdict.** A pass fills the banner, a retake outlines it, so the two are
distinguishable from across the room before a single letter is legible. The score row's label is the
word `QUALITY` on a pass and the reason on a retake — that is what let the banner shrink to one word
instead of stacking two lines into twenty pixels, which left one pixel between them and read as a
smudge.

**The label and the number share a centre line.** Measured on the panel: the score font reports ascent
19, so at baseline 31 its digits occupy rows 12-31; the bold 7x13 label reports ascent 9, so at baseline
26 it occupies 17-26. Both centre on 21.5. A 5x7 label at the same baseline sat 1.5 px low.

**The footer is the session tally and the frame counter.** `P3 R1` on the left, `FRAMES 12` on the right,
and both are drawn on the first screen as well as later ones: a blank cell reads as a cell that failed,
not as a tally at zero. The tally counts since boot with nothing persisted, so a reboot is a new session
by definition.

**States without a score use the free band.** READY puts `PRESS TO CAPTURE` there and CAPTURING puts
three dots, one lit at a time at a quarter-second. At three pixels a filled and a hollow mark were
indistinguishable; at radius 2 the animation reads. OFFLINE replaces the whole screen with three centred
lines - the earlier single line at 12 px was wider than the panel and lost its last letters.

## The four-digit display

**The pacing is a rule rather than a set of numbers: what is working runs at a steady pace, what has failed
blinks at a warning pace, and nothing on a desk instrument exceeds about 1 Hz.** Every speed below follows
from it, and the comparison that matters is `E0` at half a hertz against a `RETAKE` face at one: a warning
should be quicker than a fault report, and the two must not read alike.

**Four digits, one lit at a time, switched by a hardware timer rather than by the loop.** The panel is
refreshed one digit every 250 µs, which is about 1 kHz for the whole face - above what the eye sees, which
is what makes four multiplexed digits read as four steady ones. The reason it is a timer: an OLED transfer
blocks the loop for 20-25 ms, and a panel driven from the loop spent that time showing one digit at full
duty, which read as a flicker on the animated faces. The loop now works out the four segment masks and
publishes them under a critical section; the timer handler reads one mask per tick and writes GPIO
registers, and neither can tear the other's work.

| Face | What it shows | Timing |
|---|---|---|
| boot | `8888` - all 28 segments lit - then all dark | 400 ms lit, 150 ms dark, once |
| `READY` | one dash, segment G alone, at digit 1, 2, 3, 4, then all four dashes held | 500 ms per position, 1 s hold |
| `CAPTURING` | `CAP`, with one segment walking the rim of the fourth digit | 250 ms per step |
| `PASS` | a left-to-right sweep, then the score in digits 1-3 and `P`: ` 95P` | 300 ms sweep on arrival, then steady |
| `RETAKE` | the score and `E`, the whole panel blinking | 1 Hz |
| `OFFLINE` | the code `E0`: `E` on digit 1, `0` on digit 2, blinking | 0.5 Hz, and it never times out |
| fault `E1` | capture timeout | 2 s |
| fault `E2` | stray result | 2 s |
| fault `E3` | broken invariant | 2 s |

**`READY` fills its four positions and holds them; `OFFLINE` is a code.** The idle face adds one dash per
half second and then sits with all four for a second before starting again - filling and holding reads as
breathing, while filling and vanishing reads as a break. That hold is also why the offline face stopped
being four dashes: the two would have looked alike. It is `E0` now, one second lit and one second dark.

**`E0` is a screen's code; `E1`-`E3` are fault events.** Losing the link is a fault, so numbering it is
honest rather than a workaround, and the panel says `E0` for as long as the link is gone. The other three -
a capture timeout, a stray result and a broken invariant - used to produce a log line and nothing a person
at the bench could see, which made a broken rig and an idle one look the same. Each holds all four digits
for one keepalive as `E1`, `E2` or `E3`: highest priority, the most recent wins, and the screen underneath
does not change.

**A verdict is a conclusion, not a label.** `PASS` and `RETAKE` go back to `READY` after 12 s with no new
press. The score is not lost - the OLED's tally keeps the session and the PC keeps the record - and a
panel still reading ` 95P` long after the press looks hung rather than waiting. `OFFLINE` is deliberately
excluded: a lost link is a fault, not a completion, and it stays until the link returns.

**The rehearsal exists because the fault faces are otherwise unreachable.** Holding the button for 6 s
from `READY` walks all eight faces - self-test, `READY`, `CAPTURING`, `PASS`, `RETAKE`, `E1`, `E2`, `E3` -
one every 2 s, and a press ends it. A release before the hold completes is still a capture, and the press
that ends the rehearsal is spent doing so.

**Only nine characters can be drawn: the digits and A, C, E, F, H, L, P, U.** Anything else either
collides with a digit - `O` reads as `0`, `S` as `5`, `I` as `1`, `G` sits between `6` and `9` - or
cannot be formed at all, like M, W, K, V, X, Y and Z. A word therefore becomes a code, which is why a
fault is `E1` and not `TIME`. The table in `main.cpp` implements the digits, `A`, `C`, `E`, `P` and the
dash, because a glyph nothing displays is a glyph nothing can check.

**Every interval is a multiple of the PC keepalive, 2 s.** One keepalive is a fault face and one
rehearsal step; two is the capture timeout (**4 s**); three the rehearsal hold; five the offline
threshold; six the verdict face. They are written as products of `cfg::PC_KEEPALIVE_MS` on purpose: a
keepalive that changes must move all of them with it, and that is the one number that cannot be edited
alone. A verdict therefore outlives the link-loss threshold deliberately - the link is reported before a
verdict clears on its own.

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
| → PC | `EVT TIMEOUT <millis>` | no verdict arrived within 4 s; the screen changes to RETAKE, and `EVT SCREEN RETAKE -1` follows |
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
other state is dropped, reported as `EVT STRAY RESULT` and shown as the fault face `E2`; the PC is told
rather than left believing the rig took it. The rules behind that, and every state/event pair, are in
`docs/rig-state-machine-en.md`.

## What the arrival board settled

The first board was flashed on 2026-11-10 and the first assumption did not survive. `Serial` was
pointed at the S3's native USB port, so the UART bridge showed ROM boot messages and nothing from the
sketch — a board that looked dead while it was running perfectly. `ARDUINO_USB_CDC_ON_BOOT` is now 0,
which puts the sketch on UART0: one cable flashes and monitors, and no BOOT button is needed.

`setup()` also scans the I2C bus once and prints one `EVT I2C <addr>` line per device that answers.
That is how a missing display becomes visible in the serial log instead of only as a blank screen —
during assembly it is the fastest check there is.

Verified on the board: the image flashes and verifies, the firmware prints `EVT HELLO 1.1`, and the
I2C scan reports nothing when nothing is wired.

**Bus changes need no reboot.** `CMD SCAN` rescans the I2C bus and reports every address that answers,
so a wiring change is tested by sending one line instead of power-cycling and watching the boot window.
The boot scan is the only other look at the bus, and it happens before anyone has had a chance to move a
wire.

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

**Not yet verified: the four-digit display**, which has not been wired. Everything the panel does on the
bench is `P3-17`'s acceptance, not a measurement.

## Hardware reference

The two vendor documents behind the rig are **not in this repository**: the repository is public, and a
file on someone's disk cannot be cited from a clone. Facts learned from a document can be recorded; the
document itself cannot be republished. The hardware lead holds copies and will provide them on request.
The turbidity manual that forbade disclosure to third parties left with the sensor on 2026-11-14.

| Document | Part | What it settled |
|---|---|---|
| Manufacturer datasheet | ESP32-S3-WROOM-1 | GPIO are 3.3 V, 40 mA maximum drive per pin |
| Module datasheet | 0.96" 128x64 OLED, SSD1306 | I2C address `0x3C`, supply 2.8–3.3 V — the 3V3 rail is correct |

The last column is what this project measured or read and decided to rely on. A document that is not in
the repository cannot be cited by filename: **the name of a PDF on someone's disk is as unportable as a
path**, and a reader who cannot open the file gains nothing from knowing what it is called.

## Still not verified

1. **The panel has not been on the bench.** The four digits, their seven 240 Ω segment resistors and the
   four commons are declared in `config.h` and driven by `main.cpp`, and nothing has been wired yet:
   `P3-17` is the assembly task. Until that session, which physical segment a pin lands on is the
   firmware's declaration rather than a measurement.
