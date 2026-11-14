# Rig state machine

> Chinese version: [rig-state-machine-zh.md](rig-state-machine-zh.md). This file is the source of truth.
> Owner: @FrozenYty · Revisit when: a screen, a link state or an event is added

The rig controller has five screens and two link states. Every combination of them against every event
has a defined answer, because the combinations nobody wrote down are where a demo fails: a second button
press that shoots twice, a verdict that arrives after the operator has been told the shot failed, a link
that recovers and quietly wipes the result off the screen.

## 1. Screens

| Screen | Meaning |
|---|---|
| `Ready` | Idle, waiting for a press |
| `Capturing` | A capture is in flight; the verdict has not arrived |
| `Pass` | The PC returned PASS, with a score |
| `Retake` | The PC returned RETAKE with a reason, or the rig gave up waiting |
| `Offline` | No keepalive from the PC |

## 2. Link

Two states, and the rig boots in the first one with a ten-second grace.

| Link | Meaning |
|---|---|
| `Alive` | A command arrived within `cfg::OFFLINE_AFTER_MS` |
| `Gone` | Ten seconds of silence |

Boot counts as `Alive`: the timer starts at power-up and a PC on the other end of the cable sends its
first keepalive long before ten seconds are out. Booting `OFFLINE` would have the panel call itself dead
before anything had a chance to speak, which reads as a fault rather than as "waiting". **Losing a live
link is worth reporting; having no history yet is not.** The consequence is honest and visible: a rig on a
bench with no PC software goes `OFFLINE` ten seconds after power-up, because at that moment there really
is nobody to talk to.

## 3. Events

| # | Event | Source |
|---|---|---|
| E1 | Button pressed (falling edge, debounced 25 ms) | operator |
| E2 | `CMD PING` | PC |
| E3 | `CMD READY` | PC |
| E4 | A well-formed `CMD RESULT` (score and verdict present) | PC |
| E5 | A `CMD` line the firmware does not act on (unknown verb, or missing arguments) | PC |
| E6 | Ten seconds of silence | link timer |
| E7 | Heartbeat tick (1 s) | timer |
| E8 | Spinner tick (250 ms) | timer |
| E9 | Bar step (150 ms sweeping, 80 ms filling) | timer |
| E10 | `CMD SCAN` | PC |

Only a line that starts with `CMD` and names an action counts as the PC being alive. A line that is not a
`CMD` line, or a bare `CMD` with nothing after it, is ignored entirely: it does not refresh the link timer
and cannot recover `Offline`.

**`CMD SCAN` is an assembly tool, not part of a run.** It makes the firmware walk addresses 1 to 126 and
print one `EVT I2C <address>` line for each device that answers, then stop. It has no completion marker, so
a reader waits a fixed window rather than a terminator, and **how long it waited belongs in what it
reports** - a short window that found nothing and a complete walk that found nothing are different facts.
Nothing in the state machine changes: it refreshes the link timer like any other `CMD` line and the panel is
untouched, so the screens below are the same with and without a board on the bus.

## 4. Composite states

Ten pairs, five of which must never exist. The right-hand column is the invariant that forbids them.

| Screen \ Link | `Alive` | `Gone` | Why the impossible one is impossible |
|---|---|---|---|
| `Ready` | reachable | **impossible** | `Ready` means the rig has a PC and is waiting for a button |
| `Capturing` | reachable | **impossible** | a capture needs a receiver |
| `Pass` | reachable | **impossible** | a verdict came from the PC, so the PC is there |
| `Retake` | reachable | **impossible** | same, and the `NO REPLY` timeout only runs while `Alive` |
| `Offline` | **impossible** | reachable | recovering from `Gone` raises `Ready` in the same loop |

**The invariant, stated once:**

```
Offline  <=>  Gone          and          everything else  =>  Alive
```

`rig::invariantHolds` encodes it, the loop checks it once per pass and reports `EVT INVARIANT` if it is
ever broken. It has never fired. Two earlier drafts got this wrong in opposite directions - one showed
`OFFLINE` ten seconds after every power-up because it measured the absence of a PC nobody had promised,
the other could leave the panel on `OFFLINE` while the link was alive, because recovery was handled in
the link timer instead of where the PC actually spoke.

## 5. Transitions

Rows are the five reachable composites. `-` means the state does not change; **rejected** means it does
not change *and* the event is reported.

| Composite \ Event | E1 button | E2 PING | E3 READY | E4 RESULT | E5 unknown | E6 silence | E7 heartbeat | E8 spinner | E9 bar |
|---|---|---|---|---|---|---|---|---|---|
| Ready + Alive | Capturing | Ready | Ready | **rejected** | Ready | Offline | Ready | `-` | Ready |
| Capturing + Alive | **ignored** | Capturing | Ready | Pass / Retake | Capturing | Offline | Capturing | Capturing | Capturing |
| Pass + Alive | Capturing | Pass | Ready | **rejected** | Pass | Offline | Pass | `-` | `-` |
| Retake + Alive | Capturing | Retake | Ready | **rejected** | Retake | Offline | Retake | `-` | `-` |
| Offline + Gone | `-` | Ready | Ready | rejected, then Ready | Ready | `-` | `-` | `-` | `-` |

E7, E8 and E9 never change the screen; they redraw it. They are in the table because a redraw in the
wrong state is itself a visible defect - the spinner must not advance on a result screen, and the bar's
level must not move once a verdict is on it.

## 6. The rules and why

**1. A capture in flight ignores the button.** `serviceButton` returns early unless the link is `Alive`
and the screen is not already `Capturing`. Without it, one press became two frames: the PC would shoot
twice and the operator would see one verdict for two pictures.

**2. A verdict is only accepted while a capture is in flight.** `handleResult` rejects a `RESULT` in any
other state and reports `EVT STRAY RESULT <score>`. Accepted elsewhere it would invent a result for a
shot that never happened, or overwrite a timeout the operator has already read. Reported, because a
silently dropped message leaves the PC believing the rig took it - the same reason TCP answers an
unexpected segment with a reset.

**3. A capture that gets no verdict within five seconds becomes a retake with reason `NO REPLY`.**
`serviceCaptureTimeout`, `cfg::CAPTURE_TIMEOUT_MS`. Without it the spinner turns forever whenever the PC
is healthy enough to keep the link alive but too busy to answer. Five seconds is shorter than the ten
second link timeout on purpose: the operator should learn that this shot failed before the whole link is
declared dead.

**4. A keepalive does not touch the screen.** A `CMD PING` raises `Ready` only on the transition out of
`Gone`, and only when the screen is `Offline`. A `PING` that arrives while a verdict is being read
refreshes the link timer and changes nothing visible.

**5. Losing the PC overrides everything.** `serviceLink`. No screen can make progress without a PC, so
silence forces `Offline` from anywhere. The recovery lives where the PC actually speaks - in `poll` - and
resets exactly the `Offline` screen.

**6. The PC keeps the link alive.** The serial link has no carrier signal: the rig talks UART through a
bridge chip and cannot see whether the cable is plugged in. Liveness is therefore a protocol matter, and
the obligation is the PC's: **send `CMD PING` at least every two seconds; ten seconds of silence is five
missed keepalives and means the PC is gone.** An idle rig still has to be told so, which is why the
heartbeat is not decoration - and why the boot grace of the same ten seconds is enough for the PC's first
message to arrive and confirm that somebody is there.

**7. Every transition is reported.** `EVT SCREEN <name> <score>` on every state change the
firmware makes, including the ones the button, the link timer and boot cause. The capture timeout emits
`EVT TIMEOUT` first, saying why the screen moved, and then `EVT SCREEN RETAKE -1`, saying where it moved to
(§8) - a transition that for one afternoon was the single exception, and was fixed rather than documented.
Before the screen events existed, a wiring fault and a logic fault looked identical from the serial port.

**8. The invariant is checked, not assumed.** One comparison per loop pass; a violation is a serial line
rather than a panel that quietly lies.

## 7. Diagram

```mermaid
flowchart TD
    BOOT([boot]) --> READY[Ready]
    OFFLINE[Offline] -->|any command| READY
    READY -->|button| CAPTURING[Capturing]
    CAPTURING -->|RESULT PASS| PASS[Pass]
    CAPTURING -->|RESULT RETAKE| RETAKE[Retake]
    CAPTURING -->|5 s, no verdict| RETAKE
    PASS -->|button| CAPTURING
    RETAKE -->|button| CAPTURING
    READY -->|10 s silence| OFFLINE
    CAPTURING -->|10 s silence| OFFLINE
    PASS -->|10 s silence| OFFLINE
    RETAKE -->|10 s silence| OFFLINE
```

## 8. Serial events per transition

| Transition | Events |
|---|---|
| boot | `EVT HELLO <version>`, ..., `EVT SCREEN READY -1` |
| any command from `Offline` → Ready | `EVT SCREEN READY <score>` |
| `CMD READY` from any other screen → Ready | `EVT SCREEN READY <score>` |
| Ready → Capturing | `EVT SCREEN CAPTURING -1` then `EVT TRIGGER <millis>` |
| Capturing → Pass / Retake | `EVT SCREEN PASS\|RETAKE <score>` |
| Capturing → Retake (`NO REPLY`) | `EVT TIMEOUT <millis>` then `EVT SCREEN RETAKE -1` |
| any → Offline | `EVT SCREEN OFFLINE <score>` |
| rejected RESULT | `EVT STRAY RESULT <score>` |
| invariant broken (never observed) | `EVT INVARIANT <screen> <link>` |

A score of `-1` in `EVT SCREEN` means no verdict has been received yet, so the screen has no number to
draw. The field is not reset by a link transition or by `CMD READY`: on `READY` and `OFFLINE` it can still
carry the last verdict's score, which those screens do not draw.

## 9. The PC side of the link

The server holds the other end of the same cable, and it has a state machine of its own
(`server/app/rig/link.py`). It is smaller than the rig's, and it is written the same way, because the
failures here are the same shape: a port unplugged mid-read, a write attempted on a closed port, a
keepalive thread outliving the transport it was pinging.

| State \ Event | start | port opened | open failed | read failed | write failed | stop | keepalive tick | line in |
|---|---|---|---|---|---|---|---|---|
| `DOWN` | Opening | - | - | - | - | Stopping | - | - |
| `OPENING` | ignored | **Open** | stay, retry | - | - | Stopping | - | - |
| `OPEN` | ignored | - | - | **Opening**, retry | **Opening**, retry | Stopping | send `CMD PING` | dispatch |
| `STOPPING` | ignored | ignored | ignored | - | - | - | ignored | ignored |

**Two invariants, both enforced in the code:**

1. **A transport exists if and only if the state is `OPEN`.** A write on a closed port raises in
   whichever thread made it, and a keepalive thread that raises takes the process down.
2. **Only `OPEN` sends keepalives.** A reconnect loop that also pings is two writers on one port.

The matrix earned its place immediately: the first implementation set the *global* stop event when a
write failed, which ended the reader thread for good - one unlucky write and the link never came back.
The test that found it is `test_a_failed_write_takes_the_link_down_and_it_recovers`.

**The verdict path is not a separate state machine.** On `EVT TRIGGER` the server grabs a frame, scores
it with the same quality gate the rest of the product uses, and answers `CMD RESULT <score> <verdict>
<reason>`. If the capture fails - no camera, device busy, disk full - it answers **nothing**. The rig's
own five-second timeout then reports `RETAKE / NO REPLY` with no score, which is exactly true, and no
new message had to be invented for the rig to learn.

The keepalive obligation of §6 is discharged here: every two seconds, from `OPEN`, for as long as the
port is held.

## 10. The lamps and the LED bar

Three lamps, and **one of them is lit at every moment** - a dark panel must not be able to mean either
"idle" or "dead". Two of them answer the last verdict - **white for `Pass`, red for `Retake`** - and the
blue one answers what the rig is doing.

| Screen | white, PASS | red, RETAKE | blue, state |
|---|---|---|---|
| `Ready` | off | off | steady |
| `Capturing` | off | off | slow blink, 500 ms |
| `Pass` | lit | off | off |
| `Retake` | off | lit | off |
| `Offline` | off | off | fast blink, 150 ms |

**The pins sink, they do not drive.** Each lamp's anode is on the 5 V rail and the pin pulls its cathode
down, so a multimeter on a lamp pin reads LOW while that lamp is lit - the opposite of what the panel shows.
That is what makes them bright enough to read: from 3.3 V a 2 V LED through 330 Ohm leaves under 4 mA,
while from 5 V the same resistor gives about 9 mA, and the pin never sees more than the LED's own drop.

**Two blink rates, not one.** "Busy" and "broken" are different questions, and a single pattern would make
the operator read the panel twice to tell them apart.

**The verdict lamps are steady, and they hand over to the blue one.** White stays lit while `Pass` is on
the screen and red while `Retake` is, so a lamp is a second view of the fact the panel is already showing
rather than a separate fact to time. The blue lamp goes **dark** in those two screens: two lamps saying one
thing is noise.

**Why these three colours.** Red on `Retake` because that is the signal nobody may miss, and red is what a
reader already stops for. White on `Pass` because it is the brightest thing available at 9 mA and carries no
bad news. Blue on the state because an always-on lamp has to recede: white there would dominate the two that
matter, and it blooms into a featureless blob on a phone camera. Green was the obvious choice for `Pass` and
was given up twice over - the parts on hand were too dim to read from a metre, and **red against green is the
one pair a red-green colour-blind operator cannot separate**, while red, white and blue differ in brightness
as well as hue.

**What the lamps must never do is leave the panel dark.** Between them they cover every screen - green or
yellow for a verdict, blue for idle, in flight and disconnected - so no lamp at all can only mean no power.

**The bar is ten lamps on GPIO 10-18 and 21, and it is the panel's second view of the score.** Its wiring is
the lamps' wiring repeated ten times: each anode on the 5 V rail through its own 330 Ohm, each cathode on
its own pin, so **LOW lights a bar lamp and HIGH puts it out**. The pins are not contiguous because 19 and
20 are the USB pair, which is why the last lamp leaves on the other header. It is what replaced the turbidity
sensor, which was removed on 11-14 because no register of it tracked the water (P3-37).

| Screen | bar |
|---|---|
| `Ready` | one dot, walking out to the last lamp and back, 150 ms per step |
| `Capturing` | a bar filling 1, 2, ... 10 and starting over, 80 ms per lamp |
| `Pass` | the score as a level, one lamp per ten percent |
| `Retake` | the same, from that verdict's score |
| `Offline` | all dark |

**Levels 1 to 7 are yellow and 8 to 10 white - the top band, 80 and above.** White is the brightest thing
available at 9 mA. Red was dropped because the red lamps on the bench are a different height, and a row of
mismatched lamps reads as damage rather than as design; blue is absent because it belongs to the state lamp,
so a blue segment would be read as "idle". **Pass and fail are not in this row either**: they stay with the
two verdict lamps, which answer a question the bar does not.

**A score below zero lights all ten rather than none.** No verdict at all is not a score of nought, and a
dark bar would be reporting a number nobody measured.

**The bar is the one part of the panel allowed to go dark, and the rule above survives it.** `Offline` is
the single screen where the blue lamp is already saying that nobody is talking to the rig, so ten dark lamps
beside a fast-blinking lamp read as a panel that is alive with nothing to show, not as a panel without
power. That is also why the never-all-dark invariant belongs to the three lamps: a bar that dimmed its own
level would lose the one thing it is there for.

**Ten steps is a display, not a measurement.** The score is on the screen as digits; the bar is what a
person reads from across the room, where digits are not legible, and one lamp per ten percent is the
resolution that distance supports. Nothing reads the bar back, and no level of it is an acceptance number.

The blue lamp is lit from the first millisecond of `setup()`, before the splash, because proving that the
board has power is its first job: nothing lit at all points at the supply, not at the firmware.
