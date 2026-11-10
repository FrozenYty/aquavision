// The whole of what the rig is doing, in one struct.
//
// Nothing here draws or parses; those are separate files. Keeping the state plain data means a new
// screen state or a new field costs one line here and one case in the renderer, and anything that
// reads the rig (serial, display, future features) reads the same struct rather than its own copy.

#pragma once

#include <cstring>

namespace rig {

enum class Screen {
  Ready,      // idle, waiting for a press
  Capturing,  // the button was pressed, the frame is on its way to the PC
  Pass,       // the PC returned PASS
  Retake,     // the PC returned RETAKE, with a reason
  Offline,    // the PC has said nothing for `cfg::OFFLINE_AFTER_MS`
};

// Why a frame failed the quality gate. The strings are what the protocol carries; the display maps
// them to words. Adding a new cause means adding one entry here and one line in `screen.cpp`.
enum class Reason { None, LowLight, Blur, ColorCast, Unknown };

const char* reasonToken(Reason reason);
Reason reasonFromToken(const char* token);

struct State {
  Screen screen = Screen::Ready;
  int score = 0;
  Reason reason = Reason::None;
  int turbidity = -1;   // -1 means no reading yet; the screen shows "--"
  // No trend field. The screen used to draw a triangle for rising, falling and steady, decided by an
  // absolute threshold of two counts on a reading that spans 700-16000 - two counts is noise at that
  // scale, so the mark flickered. A trend worth showing has to be relative, and until there is a reason
  // for one, the reading itself is the honest display.
  int frames = 0;       // accepted or judged, this session
  bool pcAlive = false;
  bool heartbeatOn = true;
  uint8_t animPhase = 0;  // which of the three spinner dots is lit, 0-2

  //: Set when something visible changed. The renderer clears it. A redraw per frame would flicker and
  //: waste the I2C bus; a redraw on change is enough.
  bool dirty = true;

  //: Set by the protocol when a verdict arrives, consumed by the loop to pulse the LED. A flag rather
  //: than "did the screen change", because two PASS results in a row are the same screen and the second
  //: one still deserves a pulse.
  bool pulseLeds = false;

  void markDirty() { dirty = true; }

  void noteTurbidity(int value) {
    turbidity = value;
    markDirty();
  }
};

}  // namespace rig
