// The presentation layer: the third machine, and the only one that decides what the two screens draw.
//
// Two machines already run here and they stay apart (docs/rig-transport-en.md §2): the BLE layer owns
// the connection and the subscription, and the protocol layer owns the keepalive and `Alive`/`Gone`.
// This file is **not** a merge of them. It is a third machine that reads both, because one question an
// operator asks has no answer in either alone: "is a PC expected right now, or has nobody arrived yet?"
// The BLE layer can say whether a central is attached; the protocol layer can say whether one has
// spoken for ten seconds; neither can tell "nobody has arrived" from "somebody left", because `Gone`
// already means the second thing to the protocol. Merging them would force one state to answer both,
// which is exactly the merge the transport document forbids.
//
// The four states, six events and every cell between them are §11 of `docs/rig-state-machine-en.md`.
// The table itself lives once, in `presentation.cpp`, where the machine reads it; this header declares
// the states and the events and does not repeat the cells, because two copies of one contract drift.
//
// **The presentation layer outranks the screen.** A screen change made while this is not `Live` is
// **dropped, not deferred**: the face below is drawn over the rig's screen, the change never replays,
// and when `Live` returns the screens draw the rig's *current* screen. That is the same choice §10
// already makes for a verdict that lands inside a fault window - eaten, not deferred - and it is the
// honest one here too: a verdict that arrived while the rig had no PC did not come from the PC that is
// here now. The one rule made literal in code is the first screen of a capture: a press while this is
// not `Live` is refused, because there is nowhere to send the trigger.

#pragma once

#include <cstdint>

namespace presentation {

//: The four states of §11. `Pairing` is the only one with no central attached, and it is the state that
//: removes the false `Err0` at power-up: no carrier and no conversation is "waiting", not "broken".
enum class State : uint8_t {
  Pairing,     // no central attached
  NoLink,      // attached, but the protocol layer is `Gone` - including before `B2` completes it
  Live,        // attached, and the protocol layer is `Alive`
  RadioFault,  // the radio would not start, or the drop storm reached `Fault`
};

//: The six events of §11, one per column. B1-B3 come from the BLE layer, B4 from the same layer's
//: fault, and P1/P2 from the protocol layer. Nothing here is a new protocol event: the wire is
//: untouched, and these are readings of the two machines that already exist.
enum class Event : uint8_t {
  Attached,      // B1: a central attaches
  Subscribed,    // B2: the notification subscription completes
  Detached,      // B3: the central disconnects
  RadioFaulted,  // B4: the radio will not start, or the drop storm reached `Fault`
  Command,       // P1: a command arrives
  Silence,       // P2: ten seconds without a command
};

//: The four kinds of cell, the vocabulary §4 of the transport document defines and §11 shares: a
//: target state; `Handled`, consumed without a move; `Ignored`, cannot move this layer and is not
//: reported; or `Rejected`, no move **and** reported, because the sender has to learn it was refused.
//: The report belongs to the layer that refused the event - a second central is disconnected by the
//: BLE layer (its rule 1) - and the cell exists so that even a delivered B1 cannot repaint `Live`.
enum class Outcome : uint8_t { Ignored, Handled, Rejected, Move };

struct Cell {
  Outcome outcome;
  State target;
};

//: What each screen draws. `RigScreen` is the only face that hands the glass back to the rig's own
//: screen; the other three replace it, which is what makes "a verdict cannot paint over `WAITING`"
//: structural rather than a condition someone has to remember. `Pairing`'s panel face is the word `PAr`
//: with its fourth digit rotating through the six rim segments: the word says what the state is, and the
//: rotation says the rig is still working, both of them shapes this panel already draws elsewhere
//: (`CAPTURING` draws `CAP` with the same rotation).
enum class OledFace : uint8_t { WaitingForPc, Offline, RigScreen, RadioFault };
enum class PanelFace : uint8_t { Pairing, Err0, RigScreen, Err4 };

struct Face {
  OledFace oled;
  PanelFace panel;
};

//: The rotating fourth digit's step after `faceAgeMs`: 0 to `cfg::DISPLAY_ROTATE_STEPS` - 1, one every
//: `cfg::DISPLAY_ROTATE_MS`, the digit's A-F rim clockwise. `CAPTURING` and `Pairing` both read this, so
//: the two faces cannot end up on different steps or different clocks. **There is no position table**: the
//: segment is `1u << step`, six single bits, and a bit shift has no entry that can be wrong - which is
//: exactly what the twelve-entry ring this replaces got wrong, duplicating one digit's bottom and
//: dropping another's.
uint8_t rotationStep(uint32_t faceAgeMs);

//: The state the machine is in. One rig, one loop, one writer: every call below comes from the Arduino
//: loop, never from a radio callback.
State state();

//: The starting state, from the wire that actually opened. Not an event and not in the matrix: a stack
//: that starts has exactly one thing to be, and the alternative - a `boot` column with two non-empty
//: cells - would hide that this is the only unconditional assignment in the layer. A UART answers
//: `attached` true always (it cannot see a cable), so `rig-serial` starts `Live` or `NoLink` and never
//: reaches `Pairing`.
void begin(bool attached, bool protocolAlive);

//: One event, one cell. Returns the cell so a caller can see what happened without reading the state.
Cell apply(Event event);

//: The face table of §11 for a state, for the renderers to switch on.
const Face& faceFor(State state);

}  // namespace presentation
