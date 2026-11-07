// Rendering. The display is a parameter, not a global, so a second screen or a host-side preview can
// call the same code.

#pragma once

#include <U8g2lib.h>

#include "rig_state.h"

namespace screen {

//: Power-on card. Shown once, for `cfg::SPLASH_MS`.
void renderSplash(U8G2& display);

//: Whatever `state.screen` says. Does not clear `state.dirty`; the caller does that after sending.
void render(U8G2& display, const rig::State& state);

}  // namespace screen
