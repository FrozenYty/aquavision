// The whole of what the rig is doing, in one struct.
//
// Nothing here draws or parses; those are separate files. Keeping the state plain data means a new
// screen state or a new field costs one line here and one case in the renderer, and anything that
// reads the rig (serial, display, future features) reads the same struct rather than its own copy.

#pragma once

#include <cstdint>
#include <cstring>

namespace rig {

//: The link with the PC, as a first-class part of the state rather than a loose boolean.
//:
//: Two states, and the rig boots in the first one: `setup()` starts the link Alive and the screen
//: Ready, with a ten-second grace before silence is treated as a lost PC.
enum class Link {
  Alive,  // a command arrived within `cfg::OFFLINE_AFTER_MS`
  Gone,   // `cfg::OFFLINE_AFTER_MS` of silence
};

enum class Screen {
  Ready,      // idle, waiting for a press
  Capturing,  // the button was pressed, the frame is on its way to the PC
  Pass,       // the PC returned PASS
  Retake,     // the PC returned RETAKE, with a reason
};

// Why a frame failed the quality gate. The strings are what the protocol carries; the display maps
// them to words. Adding a new cause means adding one entry here and one line in `screen.cpp`.
// `NoReply` is the one cause the rig decides for itself: no verdict arrived inside
// `cfg::CAPTURE_TIMEOUT_MS`, so there is nothing to report a score for.
enum class Reason { None, LowLight, Blur, ColorCast, Unknown, NoReply };

//: A fault is not a screen: the rig stays in the state it was in, and the panel shows the fault over the
//: top for `cfg::FAULT_FACE_MS`. These are the events that used to produce a log line and nothing a
//: person at the bench could see, which made a broken rig and an idle one look the same.
//:
//: `Radio` is the one entry a serial rig can never raise, and the one with no window: a lost link and a
//: dead radio are both true at the same moment, and only one of them telling the operator to wait is the
//: whole reason `Err4` exists (docs/rig-transport-en.md §10). It outranks every other fault and every
//: screen until the rig is power-cycled or reflashed.
enum class Fault { None, Timeout, Stray, Invariant, Radio };

const char* reasonToken(Reason reason);
Reason reasonFromToken(const char* token);

struct State {
  Screen screen = Screen::Ready;  // `setup()` starts Alive; a fresh rig is waiting, not broken
  //: -1 means "no measurement": the panel draws blanks for the digits and the OLED draws no number, so
  //: neither screen invents a zero. Only two places write it - a capture in flight, and the retake that
  //: `serviceCaptureTimeout` creates - while `protocol.cpp` clamps whatever the PC sends into 0-100.
  int score = -1;
  Reason reason = Reason::None;
  int frames = 0;       // accepted or judged, this session
  Fault fault = Fault::None;
  uint32_t faultAt = 0;  // millis of the most recent fault; the face holds `cfg::FAULT_FACE_MS`
  //: When PASS or RETAKE was shown, and **0 when no verdict face is armed**. The panel returns to READY
  //: after `cfg::VERDICT_FACE_MS` without a new capture, so a conclusion does not stay up forever with no
  //: date on it. **Only `armVerdictFace` stamps it and only `serviceButton` clears it** - a third writer is
  //: how one event ends up with two clocks. Starting a capture clears it: the previous verdict's timer must
  //: not be able to pull the new capture back, which is the flash the bench saw.
  uint32_t verdictAt = 0;
  Link link = Link::Alive;
  bool heartbeatOn = true;
  //: The shared animation phase, 0 to `cfg::DISPLAY_ROTATE_STEPS` - 1: which step of the CAPTURING
  //: rotation is current. The panel lights that rim segment and the OLED fills that dot above its banner,
  //: so both screens read this one number. Derived by `serviceDisplay`, never advanced by a counter of its
  //: own - two periods for one event drift, however carefully they are tuned. `Pairing` does not read this:
  //: its panel face computes the same expression from its own face age, and its OLED face does not animate.
  uint8_t animPhase = 0;

  //: Set when something visible changed. The renderer clears it. A redraw per frame would flicker and
  //: waste the I2C bus; a redraw on change is enough.
  bool dirty = true;

  void markDirty() { dirty = true; }
};

//: Arm the verdict face at **this pass's clock reading**. `now` is the loop's own reading - the one the
//: expiry compares against - so the age starts at exactly zero and advances with real time. A second
//: `millis()` call here is one clock reading too many: when the millisecond boundary falls between the
//: loop's reading and the verdict's, the stamp is one ahead, `now - verdictAt` wraps to ~4.29e9, and the
//: face expires on the pass it appeared. That is `CAP` flashing back to `READY`, and it was systematic
//: enough to look like a timer of its own.
inline void armVerdictFace(State& state, uint32_t now) { state.verdictAt = now; }

//: True once the verdict face's window has run out. The age is a **signed** difference on purpose: a stamp
//: even one millisecond ahead of `now` makes an unsigned subtraction wrap to the largest 32-bit value, so the
//: face would expire immediately. `armVerdictFace` stamps from the same reading, so in production the age is
//: never negative; the cast keeps a boundary tick from inverting the comparison if one ever slips through.
inline bool verdictFaceExpired(uint32_t now, uint32_t verdictAt, uint32_t window) {
  return verdictAt != 0 && static_cast<int32_t>(now - verdictAt) >= static_cast<int32_t>(window);
}

//: The line between a working rig and a lying one, now that the link no longer has a screen: **a capture
//: in flight carries no verdict face's timer, and a verdict face carries one**. The first half is the older
//: flash - an armed timer during `CAPTURING` is the previous verdict's, and it could pull the new capture
//: back to `READY`. The second half keeps every verdict face expirable.
inline bool invariantHolds(const State& state) {
  if (state.screen == Screen::Capturing) {
    return state.verdictAt == 0;
  }
  if (state.screen == Screen::Pass || state.screen == Screen::Retake) {
    return state.verdictAt != 0;
  }
  return true;
}

inline const char* linkName(Link link) { return link == Link::Alive ? "ALIVE" : "GONE"; }

}  // namespace rig
