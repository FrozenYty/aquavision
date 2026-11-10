// The whole of what the rig is doing, in one struct.
//
// Nothing here draws or parses; those are separate files. Keeping the state plain data means a new
// screen state or a new field costs one line here and one case in the renderer, and anything that
// reads the rig (serial, display, future features) reads the same struct rather than its own copy.

#pragma once

#include <cstring>

namespace rig {

//: The link with the PC, as a first-class part of the state rather than a loose boolean.
//:
//: Two states, and the rig boots in the second one: the PC owns the link and proves it with a keepalive
//: every two seconds, so no heartbeat means no PC. There is deliberately no "never connected yet" state -
//: it would only exist for the couple of seconds between power-up and the PC's first message, and the
//: honest thing to show in that window is OFFLINE.
enum class Link {
  Alive,  // a command arrived within `cfg::OFFLINE_AFTER_MS`
  Gone,   // `cfg::OFFLINE_AFTER_MS` of silence
};

enum class Screen {
  Ready,      // idle, waiting for a press
  Capturing,  // the button was pressed, the frame is on its way to the PC
  Pass,       // the PC returned PASS
  Retake,     // the PC returned RETAKE, with a reason
  Offline,    // the PC has said nothing for `cfg::OFFLINE_AFTER_MS`
};

// Why a frame failed the quality gate. The strings are what the protocol carries; the display maps
// them to words. Adding a new cause means adding one entry here and one line in `screen.cpp`.
// `NoReply` is the one cause the rig decides for itself: no verdict arrived inside
// `cfg::CAPTURE_TIMEOUT_MS`, so there is nothing to report a score for.
enum class Reason { None, LowLight, Blur, ColorCast, Unknown, NoReply };

const char* reasonToken(Reason reason);
Reason reasonFromToken(const char* token);

struct State {
  Screen screen = Screen::Offline;  // no PC has said anything yet, and that is what OFFLINE means
  int score = -1;      // -1 means no verdict yet; the screen leaves the number out
  Reason reason = Reason::None;
  int turbidity = -1;   // -1 means no reading yet; the screen shows "--"
  // No trend field. The screen used to draw a triangle for rising, falling and steady, decided by an
  // absolute threshold of two counts on a reading that spans 700-16000 - two counts is noise at that
  // scale, so the mark flickered. A trend worth showing has to be relative, and until there is a reason
  // for one, the reading itself is the honest display.
  int frames = 0;       // accepted or judged, this session
  Link link = Link::Gone;
  bool heartbeatOn = true;
  uint8_t animPhase = 0;  // which of the three spinner dots is lit, 0-2

  //: Set when something visible changed. The renderer clears it. A redraw per frame would flicker and
  //: waste the I2C bus; a redraw on change is enough.
  bool dirty = true;

  //: Set by the protocol when a verdict arrives, consumed by the loop to pulse the LED. A flag rather
  //: than "did the screen change", because two PASS results in a row are the same screen and the second
  //: one still deserves a pulse.
  bool pulseLeds = false;

  bool pcAlive() const { return link == Link::Alive; }

  void markDirty() { dirty = true; }

  void noteTurbidity(int value) {
    turbidity = value;
    markDirty();
  }
};

//: The three facts that separate a working rig from a lying one. Six of the fifteen screen/link
//: combinations are reachable; these are the lines between them.
inline bool invariantHolds(const State& state) {
  // OFFLINE if and only if the link is gone. Everything else requires a live PC: a capture, a verdict
  // and an idle-but-ready rig all mean somebody is on the other end of the cable.
  if (state.screen == Screen::Offline) {
    return state.link == Link::Gone;
  }
  return state.link == Link::Alive;
}

inline const char* linkName(Link link) { return link == Link::Alive ? "ALIVE" : "GONE"; }

}  // namespace rig
