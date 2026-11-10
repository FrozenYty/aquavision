# Rig state machine

> Chinese version: [rig-state-machine-zh.md](rig-state-machine-zh.md). This file is the source of truth.
> Owner: @FrozenYty · Revisit when: a state or an event is added

The rig controller has five screens and ten things that can happen to it. Every pair has a defined
answer, because the pairs that nobody wrote down are where a demo fails: a second button press that
shoots twice, a verdict that arrives after the operator has already been told the shot failed, a link
that recovers and quietly wipes the result off the screen.

## 1. States

| State | Meaning |
|---|---|
| `Ready` | Idle, waiting for a press |
| `Capturing` | A capture is in flight; the verdict has not arrived |
| `Pass` | The PC returned PASS, with a score |
| `Retake` | The PC returned RETAKE with a reason, or the rig gave up waiting |
| `Offline` | The PC has said nothing for ten seconds. Because the PC must keep the link alive, this means a real disconnection, not an idle rig |

## 2. Events

| # | Event | Source |
|---|---|---|
| E1 | Button pressed (falling edge, debounced 25 ms) | operator |
| E2 | `CMD PING` | PC |
| E3 | `CMD READY` | PC |
| E4 | `CMD RESULT` | PC |
| E5 | Unknown or malformed command | PC |
| E6 | PC silent for ten seconds | link timer |
| E7 | PC speaks again after silence | link timer |
| E8 | Turbidity reading (every 5 s) | sensor |
| E9 | Heartbeat tick (1 s) | timer |
| E10 | Spinner tick (250 ms) | timer |

## 3. The transition table

A cell gives the state after the event, or `-` when the state does not change. A rejected event is
marked: it leaves the state alone **and** reports itself on the serial port.

| State \ Event | E1 button | E2 PING | E3 READY | E4 RESULT | E5 unknown | E6 silence | E7 recovery | E8 turbidity | E9 heartbeat | E10 spinner |
|---|---|---|---|---|---|---|---|---|---|---|
| **Ready** | Capturing | Ready | Ready | **rejected** | Ready | **Offline** | Ready | Ready | Ready | `-` |
| **Capturing** | **ignored** | Capturing | Ready | Pass / Retake | Capturing | **Offline** | `-` | Capturing | Capturing | Capturing |
| **Pass** | Capturing | Pass | Ready | **rejected** | Pass | **Offline** | `-` | Pass | Pass | `-` |
| **Retake** | Capturing | Retake | Ready | **rejected** | Retake | **Offline** | `-` | Retake | Retake | `-` |
| **Offline** | Offline | **Ready** | **Ready** | rejected, then **Ready** | **Ready** | Offline | **Ready** | Offline | Offline | `-` |

`E8`, `E9` and `E10` never change the state; they redraw it. They are in the table because a redraw in
the wrong state is a visible defect — the spinner must not advance on a result screen.

## 4. The rules and why

**1. A capture in flight ignores the button.** `serviceButton` returns early when the screen is already
`Capturing`. Without it, one press became two frames: the PC would shoot twice and the operator would
see one verdict for two pictures.

**2. A verdict is only accepted while a capture is in flight.** `handleResult` rejects a `RESULT` in any
other state and reports `EVT STRAY RESULT <score>`. Accepted elsewhere it would invent a result for a
shot that never happened, or overwrite a timeout the operator has already read. Reported, because a
silently dropped message leaves the PC believing the rig took it — the same reason TCP answers an
unexpected segment with a reset.

**3. A capture that gets no verdict within five seconds becomes a retake with reason `NO REPLY`.**
`serviceCaptureTimeout`, `cfg::CAPTURE_TIMEOUT_MS`. Without it the spinner turns forever whenever the PC
is healthy enough to keep the link alive but too busy to answer — the one state where a still, silent
screen is worst. Five seconds is shorter than the ten-second link timeout on purpose: the operator should
learn that this shot failed before the whole link is declared dead.

**4. A result stays on screen.** `serviceHeartbeat`, `serviceLink`, and rule 1 together: a keepalive
`PING` refreshes the link timer but does not touch the screen, and the second press of rule 1 starts the
next capture deliberately rather than the link doing it by accident.

**5. Losing the PC overrides everything; recovering from it only resets `Offline`.** `serviceLink`. No
state can make progress without the PC, so silence forces `Offline` from anywhere. The reverse is not
true: a verdict or a capture belongs to the rig, and replacing it because the link came back was how a
result could vanish from the panel one loop after it appeared.

**6. Silence means the PC is gone, because the PC keeps the link alive.** The serial link has no carrier
signal - the rig talks UART through a bridge and cannot see the cable - so liveness is a protocol
matter: the PC sends `CMD PING` at least every two seconds, and ten seconds of silence is five missed
keepalives. Without that obligation the rig would declare a healthy idle system offline, which is the
normal state of a rig waiting for a button.

**7. Every transition is reported.** `EVT SCREEN <name> <score>` on every state change, including the
ones the button and the link timer cause. Before this, a wiring question and a logic question looked
identical from the serial port.

## 5. Diagram

```
                  button                 RESULT
      +----------------------------+--------------------+
      |                            v                    |
   +-------+   button    +-----------+   RESULT   +--------+
   | Ready |------------>| Capturing |----------->| Pass   |
   +-------+             +-----------+            +--------+
      ^   ^                    |                       |
      |   |                    | 5 s, no verdict       | button
      |   |  any command       v                       |
      |   |              +-----------+                 |
      |   +--------------|  Retake   |<----------------+
      |                  +-----------+   RESULT (NO REPLY keeps it here)
      |                        |
      | 10 s of silence        |
      +--------+---------------+
               v
          +---------+
          | Offline |   any command -> Ready
          +---------+
```

## 6. Serial events per transition

| Transition | Events |
|---|---|
| Ready → Capturing | `EVT SCREEN CAPTURING` then `EVT TRIGGER <millis>` |
| Capturing → Pass / Retake | `EVT SCREEN PASS\|RETAKE <score>` |
| Capturing → Retake (`NO REPLY`) | `EVT TIMEOUT <millis>` then `EVT SCREEN RETAKE -1` |
| \* → Offline | `EVT SCREEN OFFLINE -1` |
| Offline → Ready | `EVT SCREEN READY -1` |
| rejected RESULT | `EVT STRAY RESULT <score>` |

A score of `-1` in `EVT SCREEN` means the screen deliberately shows no number: there is no verdict, and
a stale or invented one would be worse than a blank.
