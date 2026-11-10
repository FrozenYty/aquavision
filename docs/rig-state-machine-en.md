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

Two states, and the rig boots in the second one.

| Link | Meaning |
|---|---|
| `Alive` | A command arrived within `cfg::OFFLINE_AFTER_MS` |
| `Gone` | Ten seconds of silence |

There is deliberately no "never connected yet" state. It would exist only for the couple of seconds
between power-up and the PC's first message, and the honest thing to show in that window is `OFFLINE`:
at that moment there is indeed no PC. The handshake is therefore one line - the first keepalive raises
`READY` - rather than a special case.

## 3. Events

| # | Event | Source |
|---|---|---|
| E1 | Button pressed (falling edge, debounced 25 ms) | operator |
| E2 | `CMD PING` | PC |
| E3 | `CMD READY` | PC |
| E4 | `CMD RESULT` | PC |
| E5 | Unknown or malformed command | PC |
| E6 | Ten seconds of silence | link timer |
| E7 | Turbidity reading (every 5 s) | sensor |
| E8 | Heartbeat tick (1 s) | timer |
| E9 | Spinner tick (250 ms) | timer |

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

| Composite \ Event | E1 button | E2 PING | E3 READY | E4 RESULT | E5 unknown | E6 silence | E7 turbidity | E8 heartbeat | E9 spinner |
|---|---|---|---|---|---|---|---|---|---|
| Ready + Alive | Capturing | Ready | Ready | **rejected** | Ready | Offline | Ready | Ready | `-` |
| Capturing + Alive | **ignored** | Capturing | Ready | Pass / Retake | Capturing | Offline | Capturing | Capturing | Capturing |
| Pass + Alive | Capturing | Pass | Ready | **rejected** | Pass | Offline | Pass | Pass | `-` |
| Retake + Alive | Capturing | Retake | Ready | **rejected** | Retake | Offline | Retake | Retake | `-` |
| Offline + Gone | `-` | Ready | Ready | rejected, then Ready | Ready | `-` | `-` | `-` | `-` |

E7, E8 and E9 never change the screen; they redraw it. They are in the table because a redraw in the
wrong state is itself a visible defect - the spinner must not advance on a result screen.

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

**4. A keepalive does not touch the screen.** `poll` raises `Ready` only on the transition out of `Gone`,
and only when the screen is `Offline`. A `PING` that arrives while a verdict is being read refreshes the
link timer and changes nothing visible.

**5. Losing the PC overrides everything.** `serviceLink`. No screen can make progress without a PC, so
silence forces `Offline` from anywhere. The recovery lives where the PC actually speaks - in `poll` - and
resets exactly the `Offline` screen.

**6. The PC keeps the link alive.** The serial link has no carrier signal: the rig talks UART through a
bridge chip and cannot see whether the cable is plugged in. Liveness is therefore a protocol matter, and
the obligation is the PC's: **send `CMD PING` at least every two seconds; ten seconds of silence is five
missed keepalives and means the PC is gone.** An idle rig still has to be told so, which is why the
heartbeat is not decoration.

**7. Every transition is reported.** `EVT SCREEN <name> <score>` on every change, including the ones the
button, the link timer and boot cause. Before this, a wiring fault and a logic fault looked identical from
the serial port.

**8. The invariant is checked, not assumed.** One comparison per loop pass; a violation is a serial line
rather than a panel that quietly lies.

## 7. Diagram

```
  boot
   |
   v
+---------+   keepalive    +-------+   button    +-----------+   RESULT   +--------+
| Offline |--------------->| Ready |------------>| Capturing |----------->| Pass   |
+---------+                +-------+             +-----------+            +--------+
   ^                          ^  |                     |                      |
   |                          |  | 10 s silence        | 5 s, no verdict      | button
   |                          |  +---------------------+                      |
   |                          |                        v                      |
   |                     (any command)          +-----------+                 |
   +--------------------------+----------------|  Retake   |<----------------+
                                               +-----------+

  Offline also follows 10 s of silence from any other screen.
```

## 8. Serial events per transition

| Transition | Events |
|---|---|
| boot | `EVT HELLO <version>`, ..., `EVT SCREEN OFFLINE -1` |
| Offline → Ready (first keepalive or recovery) | `EVT SCREEN READY -1` |
| Ready → Capturing | `EVT SCREEN CAPTURING -1` then `EVT TRIGGER <millis>` |
| Capturing → Pass / Retake | `EVT SCREEN PASS\|RETAKE <score>` |
| Capturing → Retake (`NO REPLY`) | `EVT TIMEOUT <millis>` then `EVT SCREEN RETAKE -1` |
| any → Offline | `EVT SCREEN OFFLINE -1` |
| rejected RESULT | `EVT STRAY RESULT <score>` |
| invariant broken (never observed) | `EVT INVARIANT <screen> <link>` |

A score of `-1` in `EVT SCREEN` means the screen deliberately shows no number: there is no verdict, and
a stale or invented one would be worse than a blank.
