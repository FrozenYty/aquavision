// Rendering. The display is a parameter, not a global, so a second screen or a host-side preview can
// call the same code.

#pragma once

#include <U8g2lib.h>

#include "presentation.h"
#include "rig_state.h"

namespace screen {

//: Power-on card. Held until the panel's boot sequence has finished, so both screens agree on when the
//: rig is ready; the caller draws it once and the loop keeps it on the glass.
void renderSplash(U8G2& display);

//: Whatever the presentation layer says these two screens show. `state` carries the rig's own screen
//: and is drawn only while the presentation face is `RigScreen` (docs/rig-state-machine-en.md §11);
//: the other faces replace it, which is how a verdict cannot paint over `WAITING`. Does not
//: clear `state.dirty`; the caller does that after sending.
void render(U8G2& display, const rig::State& state, presentation::State presentation);

}  // namespace screen
