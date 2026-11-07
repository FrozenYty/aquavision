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
  int trend = -1;       // -1 unknown, 0 flat, 1 rising, 2 falling
  int frames = 0;       // accepted or judged, this session
  bool pcAlive = false;
  bool heartbeatOn = true;

  //: Set when something visible changed. The renderer clears it. A redraw per frame would flicker and
  //: waste the I2C bus; a redraw on change is enough.
  bool dirty = true;

  //: Set by the protocol when a verdict arrives, consumed by the loop to pulse the LED. A flag rather
  //: than "did the screen change", because two PASS results in a row are the same screen and the second
  //: one still deserves a pulse.
  bool pulseLeds = false;

  void markDirty() { dirty = true; }

  void noteTurbidity(int value) {
    if (turbidity >= 0 && value >= 0) {
      const int delta = value - turbidity;
      trend = delta > 2 ? 1 : (delta < -2 ? 2 : 0);
    } else {
      trend = -1;
    }
    turbidity = value;
    markDirty();
  }
};

}  // namespace rig
