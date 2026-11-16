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
| `src/rig_state.h` | what the rig knows: screen, score, reason, frame count, fault, link | a new value has to be remembered |
| `src/screen.cpp` | the OLED's 128×64 layout, one function per state | the screen should look different |
| `src/presentation.cpp` | the third machine: which face both screens draw, and what "waiting for a PC" means | a state, an event or a face changes (`docs/rig-state-machine-en.md` §11) |
| `src/protocol.cpp` | the serial grammar | the PC and the board must say something new |
| `src/main.cpp` | the loop, the button, the display's faces, and the timer that multiplexes them | almost never |

Adding a screen state is five edits: an entry in `rig::Screen`, a `drawX` function in `screen.cpp`, a
`case` in `render()`, a `case` in `screenFace()` in `main.cpp` so the panel has a face for it, and a
`case` in `screenName()` in `protocol.cpp` so the PC receives a name it knows. Adding a field to the OLED
is one line in `rig::State` and one in the function that draws it. Nothing else in the firmware knows
about pixels.

## Build and flash

Two environments, one per wire (`docs/rig-transport-en.md` §11): `rig-serial` is the cable and the bench,
`rig-ble` is the finished rig and writes nothing to the UART.

```
cd firmware/main
pio run -e rig-serial                  # compile the cable build (the default)
pio run -e rig-serial --target upload  # flash it
pio run -e rig-ble                     # compile the Bluetooth build
pio run -e rig-ble --target upload     # flash it
pio device monitor                     # watch the protocol; the serial build only
```

**The serial build survives as a target, not as a paragraph.** A radio that misbehaves must cost thirty
seconds and one cable rather than the demonstration: flash `rig-serial`, plug the cable in, and point the
service at a COM port. That is only true while this target keeps compiling and keeps being used, which is
why it owns bench work.

PlatformIO pulls U8g2 at the pinned version. If `pio` is not installed:

```
python -m pip install platformio
```

## Wiring

| Signal | ESP32-S3 | Note |
|---|---|---|
| Button | GPIO 4 | to GND; `INPUT_PULLUP`, so a press reads LOW |
| Display segment A | GPIO 3 | 330 Ω between the pin and the segment |
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

Each segment has its own 330 Ω resistor between the pin and the segment, and the commons have none. A
common therefore carries the sum of its digit's segment currents, and **only one common may be high at
any moment** - which is what the multiplexer in `main.cpp` guarantees.

Every pin of the panel is a GPIO, so it runs from the board's own 3.3 V through the pins: there is no
supply pin on the display and no 5 V rail in this wiring.

## The OLED screen

128 x 64, monochrome, five bands whose baselines are named constants so nothing shifts between states:

```
y 1..7    AQUAVISION                                      ●              liveness dot only
y 8       -------------------------------------------------------
y 12..31                              94                            18 px score, right-aligned
          QUALITY                                                   7x13 bold label, rows 17-26
y 33..53  +-----------------------------------------------------+
          |                       RETAKE                        |    filled = PASS, outline = RETAKE
          +-----------------------------------------------------+
y 54      -------------------------------------------------------
y 55..62  v1.21                                    FRAMES 12
```

**Shape carries the verdict.** A pass fills the banner, a retake outlines it, so the two are
distinguishable from across the room before a single letter is legible. The score row's label is the
word `QUALITY` on a pass and the reason on a retake — that is what let the banner shrink to one word
instead of stacking two lines into twenty pixels, which left one pixel between them and read as a
smudge.

**The label and the number share a centre line.** Measured on the panel: the score font reports ascent
19, so at baseline 31 its digits occupy rows 12-31; the bold 7x13 label reports ascent 9, so at baseline
26 it occupies 17-26. Both centre on 21.5. A 5x7 label at the same baseline sat 1.5 px low.

**The footer is the firmware version and the frame counter.** `v1.21` on the left, built from the same
constant `EVT HELLO` sends, so the panel and the log cannot disagree about which build is running;
`FRAMES 12` on the right is a real capture count. There is no session tally any more - a count of verdicts
is a statistic, and the PC keeps the record.

**States without a score use the free band.** READY puts `PRESS TO CAPTURE` there and CAPTURING puts a row
of six dots, one lit at a time at a quarter-second, which is one step of the same phase as the panel's
rotating segment (`cfg::DISPLAY_ROTATE_STEPS`). Those six are the panel's rim segments: one per segment
the fourth digit turns through, so the row and the segment cannot disagree. At three pixels a filled and a
hollow mark were indistinguishable; at radius 2 the animation reads.

**At power-up, with no central attached, the OLED shows the house status face with the headline `WAITING`,
and nothing moves.** That is the `Pairing` face of the presentation layer
(`docs/rig-state-machine-en.md` §11): the rig has no PC yet and nothing is wrong. `WAITING` is drawn by the
same `drawStatusFace` as `RADIO FAULT` - same inverted box, same `AQUAVISION` header, same baselines, same
body line, and the same Helvetica bold 12 title - because the twelve-cell progress row it replaced implied an
amount of progress that does not exist, and a misleading indicator is worse than none. **The title is
`WAITING`, not `WAITING FOR PC`, because of the character count and not the font**: thirteen characters do
not fit bold 12, and shrinking the type to fit them is what made this face look empty. A seven-character
title at the house size plus the body line `NO LINK TO PC` reads as "waiting - nothing connected yet". The
panel draws `APP` with its fourth digit turning through the six rim segments at the same 250 ms step as
`CAPTURING`, from the same `presentation::rotationStep`, so the two faces cannot disagree. **There is no
position table anywhere**: the ring this replaces was a twelve-entry table, and one wrong pair lit the
fourth digit's bottom twice while the first digit's never appeared; the step is now `1u << step`, and a
shift has no entry to get wrong.

**`OFFLINE`, `Err0` and the `NoLink` state are retired.** In BLE a link simply ends and the rig is available
again; a client that stays connected but stops talking has the same remedy as one that never connected -
wait. Two faces for one remedy made the operator think a step further for nothing, and `Err0` called
"waiting" a fault. So an attached-but-silent client lands in `Live` and sees the rig's own screen. **`Err0`'s
number is not reused**: the remaining codes keep `Err1`-`Err4`, and the gap costs nothing. The OLED header
no longer names the link either: a silent peer is not a fault, so the right-hand side is the liveness dot
alone. On `rig-serial` the `Pairing` face never appears: a UART has no carrier signal and always answers
attached, so the serial build starts and stays `Live`.

**The face is static and is sent once.** There is no per-step redraw and no partial tile update - that path
was the only writer in this build that addressed less than a full buffer, and it corrupted the glass - so
the only thing that could repaint the waiting face is a stray dirty flag, which the heartbeat no longer
sets outside `Live`. The panel mask is published by the loop and the OLED module never touches it, and the
rotation is **not** in an interrupt: I2C blocks, and an ISR that waits on the bus would stall the screen it
protects.

## The four-digit display

**The pacing is a rule rather than a set of numbers: what is working runs at a steady pace, what has failed
blinks at a warning pace, and nothing on a desk instrument exceeds about 1 Hz.** Every speed below follows
from it: a `RETAKE` and every one of the fault codes blink at one hertz, so a code is told from a score by
what it says rather than by its rhythm.

**Four digits, one lit at a time, switched by a hardware timer rather than by the loop.** The panel is
refreshed one digit every 250 µs, which is about 1 kHz for the whole face - above what the eye sees, which
is what makes four multiplexed digits read as four steady ones. The reason it is a timer: an OLED transfer
blocks the loop for 20-25 ms, and a panel driven from the loop spent that time showing one digit at full
duty, which read as a flicker on the animated faces. The loop now works out the four segment masks and
publishes them under a critical section; the timer handler reads one mask per tick and writes GPIO
registers, and neither can tear the other's work.

**A face runs only on its own age.** The end of the boot sequence and any screen change both start that age
at zero, so nothing inherits a phase from what was on the panel a moment before; a fault's age is its own
phase, so the blink starts with the fault. Both screens read one boot clock: the OLED holds its splash card
until the panel's two-second self-test ends, and the two arrive at `READY` together. That clamp exists
because of a real defect: without it the idle cycle picked up wherever the self-test stopped, and the first
dash after a power-up sat on digit 2 instead of digit 1.

| Face | What it shows | Timing |
|---|---|---|
| boot | one segment at a time through all 28 positions, then `8888`, then dark | 25 ms per position (700 ms), 300 ms of eights, 1000 ms dark: two seconds, once |
| `Pairing` | `APP`, with the fourth digit turning through its six rim segments | 250 ms per step, six-step lap |
| `READY` | one dash, segment G alone, walking digit 1, 2, 3, 4 and starting over at 1 | 500 ms per position, 2 s a cycle |
| `CAPTURING` | `CAP`, with one segment walking the rim of the fourth digit | 250 ms per step |
| `PASS` | a left-to-right sweep, then the score in digits 1-3 and `P`: ` 95P` | 250 ms sweep on arrival, then steady |
| `RETAKE` | the score and `F`, the whole panel blinking: ` 40F` | 1 Hz |
| fault `Err1` | capture timeout, blinking | 1 Hz for 2 s |
| fault `Err2` | stray result, blinking | 1 Hz for 2 s |
| fault `Err3` | broken invariant, blinking | 1 Hz for 2 s |
| fault `Err4` | radio dead, blinking | 1 Hz, and no window: until a power cycle or a reflash |

**`Pairing` draws `APP` with a rotating fourth digit, not a code and not the `READY` marquee.** With no
central attached there is no fault to report: the rig is ready and only the link detail differs. The word
names the PC-side application the operator is about to open - the action this state waits for - and the
fourth digit turns through the six rim segments at the same 250 ms step and through the same
`presentation::rotationStep` as `CAPTURING`. Both halves are things this panel already draws, and that is
deliberate: the same rotation the operator has already seen on a capture means "working", and the word says
what to do. **There is no position table** - the ring this replaces was a twelve-entry table, and one
wrong pair lit the fourth digit's bottom twice while the first digit's never appeared, so a position
vanished and another lingered. The step is `1u << step` now, and a bit shift has no entry to get wrong; the
check asserts the definition (six positions, six distinct segments, no repeats) rather than a copy of the
table. **The shape is the distinction, not the direction**: the first version walked the `READY` marquee
backwards and the bench rejected it, because two dashes moving opposite ways look the same at a glance.
A central that attaches and then goes silent is not a third face: the rig stays on its own screen, which is
the presentation layer's decision (`docs/rig-state-machine-en.md` §11), and it is why a rig powered up on a
bench no longer blinks a fault at nobody.

**`READY` is a one-way marquee.** Digits 1, 2, 3, 4 and straight back to 1, half a second at each position:
two seconds a cycle, no dark frame, and never more than one dash lit. **The wrap is deliberate** - the dash
starts over at the first digit instead of turning round, so the face is a conveyor with a visible break, and
`config.h` says not to "fix" it into a bounce. An earlier version held all four dashes for a second instead;
the marquee replaced it.

**`Err1`-`Err4` are fault windows and they look the same.** Each code blinks at one hertz - the code is the
identifier and the rhythm carries nothing, so there is no second rate. What differs is only how long a face
stays: `Err4` has no window because a dead radio is not fixed by waiting, and `Err1` to `Err3` clear after
two seconds. That is when it leaves, not how it looks. The three windows are there because those events used
to produce a log line and nothing a person at the bench could see, which made a broken rig and an idle one
look the same. **`Err4` is the `rig-ble` build's code for a radio that did not start, or whose link died
five times in a minute while it was carrying the protocol** - a client that connects and leaves politely is
not a drop, which is what lets a bench session of deliberate connect/disconnect cycles run without taking
the rig off the air. The OLED has no code face, so on `Err4` it draws `RADIO FAULT` and `REFLASH RIG-SERIAL`
itself, and its body line reads `NO LINK TO PC` instead of `CHECK USB CABLE` in that build. **The retired
`Err0` keeps its number free**: the remaining codes are not renumbered.

**A retake reads `F`, not `E`.** `E` begins every fault code, so ` 40E` and an `Err` face were one glance
apart; `F` is the left column with the top and middle bars, and no code contains it.

**A verdict is a conclusion, not a label.** `PASS` and `RETAKE` go back to `READY` after 12 s with no new
press. The score is not lost - the PC keeps the record - and a panel still reading ` 95P` long after the
press looks hung rather than waiting. A capture started inside that window cancels the timer outright: the
previous verdict's timer must never pull the new capture back to `READY`. **The verdict is stamped with the
loop's own clock reading** - the same one the expiry compares against - because a second `millis()` taken
just after it can land a millisecond ahead and wrap the unsigned age, which expires the face on the pass it
appears (`CAP` flashing back to `READY`, the 1.22 defect).

**There is no rehearsal; the button has one meaning.** A press captures, on the pressing edge, and the release
is not an event at all, so a fault face appears only when its event happens: a bench where nothing is failing
never shows `Err1` to `Err3`. A press is refused only while a face owns the screens (`Pairing`,
`RadioFault`); in `Live` it captures even when the protocol layer has gone `Gone`, because a quiet peer is
not "nobody". That is why those events are reported on the wire as well as drawn - `EVT TIMEOUT`,
`EVT STRAY RESULT`, `EVT INVARIANT` are the other place a fault is visible.

**A fault outranks the screen, and an unknown score is never a zero.** A fault window covers the panel while
the screen underneath moves, so a verdict that arrives inside one loses its arrival sweep - the 250 ms has
expired by the time the fault clears, and the animation is eaten rather than deferred. And a score of `-1`,
which is what a capture with no reply leaves behind, draws **blanks and the verdict letter**: a `NO REPLY`
retake reads `   F`, not `  0F`, because a zero beside a timeout invents the number the timeout says is
missing. The OLED draws no number for the same score.

**The alphabet is the digits, `A`, `C`, `E`, `F`, `P` and a lowercase `r`.** `r` is admitted for `Err`, the
one word the fault codes are built from, and it is the only lowercase letter drawn; `-` is segment G alone,
the idle dash. Anything outside the set either collides with a digit - `O` reads as `0`, `S` as `5`, `I` as
`1`, `G` sits between `6` and `9` - or cannot be formed at all, like M, W, K, V, X, Y and Z. A word
therefore becomes a code, which is why a fault is `Err1` and not `TIME`. The table in `main.cpp` implements
only what a face displays, because an unused glyph is how the next person concludes a character is safe.

**Every state interval is a multiple of the PC keepalive, 2 s.** One keepalive is a fault window; two is the
capture timeout (**4 s**); five the offline threshold; six the verdict face. They are written as products of
`cfg::PC_KEEPALIVE_MS` on purpose: a keepalive that changes must move all of them with it, and that is the
one number that cannot be edited alone. A verdict therefore outlives the link-loss threshold deliberately -
the link is reported before a verdict clears on its own.

**Every face interval is a multiple of `cfg::DISPLAY_UNIT_MS`, 25 ms**, and written as a product for the
same reason: each of them divides by twenty-five and gives a whole number. The 250 µs digit period is a
different domain - a hardware figure in microseconds, not a face interval - and neither is the 25 ms button
debounce: the number matches by coincidence, not by construction.

## Serial protocol

One message per line at 115200 baud, ASCII, `\n` terminated. A line is limited to 95 characters: on
overflow the buffer resets, so anything longer is not handled as one message. The firmware ignores
anything it does not understand, so a garbled byte cannot brick the rig.

| Direction | Message | Meaning |
|---|---|---|
| → PC | `EVT HELLO <version>` | the board is up |
| → PC | `EVT I2C <addr>` | one line per device that answered the boot scan |
| → PC | `EVT SCREEN <name> <score>` | a screen change: READY, CAPTURING, PASS, RETAKE. A capture timeout sends `EVT TIMEOUT` first and this second |
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

**The PC owns the link, and silence means it is quiet.** The rig cannot see whether the USB cable is
plugged in - it talks UART through a bridge chip and has no carrier signal - so liveness is a protocol
matter: **the PC must send `CMD PING` at least every two seconds on an open link**, and the rig sets its
own `Gone` flag after ten seconds without a command (five missed keepalives).

The rig boots on `READY` with a ten-second grace, which is far longer than the PC needs to send its first
keepalive. `Gone` no longer changes a screen: a quiet peer is still a peer, the rig stays on whatever screen
it was on, and the button keeps working. `rig::invariantHolds` watches the verdict-face timer instead - a
capture in flight carries none, a verdict face carries one - and reports `EVT INVARIANT` if that is ever
broken.

**`rig-ble` is the exception, and it is the presentation layer's job** (`docs/rig-state-machine-en.md`
§11). With no central attached the panel draws `APP` with its fourth digit rotating and the OLED says
`WAITING`, because a radio really can tell that nobody has arrived. A central that attaches and then goes
silent stays on the rig's own screen: a quiet peer is not a fault, so there is no link face left to draw.
The presentation layer decides which face is shown; it does not change what the protocol layer reports.

**A verdict is the answer to a capture, so it is only accepted while one is in flight.** A RESULT in any
other state is dropped, reported as `EVT STRAY RESULT` and shown as the fault window `Err2`; the PC is told
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
debugging: a reader that connects and then waits eleven seconds will watch the rig set its `Gone` flag,
because the boot happens first and the ten-second link timer starts at the same moment. Test the keepalive
on a port held open, not by reconnecting.

Two consequences for tooling. A bench check that opens the port and exits leaves the rig freshly booted,
not in whatever state it was in. And a server restart is a board restart: the link does not "reconnect",
it starts over.

**The OLED is verified.** Wired directly to the ESP32 - `VCC` to `3V3`, `SDA` to `GPIO8`, `SCL` to
`GPIO9` - the scan reports `EVT I2C 3C`, the splash draws, and `CMD PING` answers `EVT PONG`, so the
PC-to-board command path works as well as the display. The screens were then driven from the serial port
without a button: `CMD RESULT 94 PASS OK`, `CMD RESULT 30 RETAKE LOW_LIGHT`,
`CMD RESULT 55 RETAKE COLOR_CAST`, `CMD RESULT 20 RETAKE UNKNOWN`, and the idle screen by simply staying
silent past the ten-second link threshold - which now changes the flag and nothing on the glass.

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

1. **The panel has not been checked on the bench.** The four digits, their seven 330 Ω segment resistors and
   the four commons are declared in `config.h` and driven by `main.cpp`, and the resistors are fitted:
   `P3-17` is the bench session that checks the rest. Until that session, which physical segment a pin lands
   on is the firmware's declaration rather than a measurement.
