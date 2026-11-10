// The serial protocol, in one place.
//
// Line oriented ASCII. The firmware **ignores** anything it does not understand rather than erroring:
// a garbled byte must never take the rig out of service, least of all ten minutes before a demo.
//
// Directions and messages are documented in firmware/README.md; this file only implements them.

#pragma once

#include <cstdint>

#include "rig_state.h"

namespace protocol {

//: Reads whatever is available and applies complete lines to `state`. Never blocks.
//: Returns true if a command arrived, which is what keeps the link watchdog alive.
bool poll(rig::State& state);

//: Outgoing events. Each writes one line to `Serial`.
void emitHello();
// Reports every address that answers on the I2C bus, one EVT line each.
void emitI2CScan();

//: Reports the screen the rig just switched to. Without it, a state change is invisible from the PC -
//: the only witness is the panel, which makes a wiring question and a logic question look identical.
void emitScreen(const rig::State& state);
void emitTrigger(uint32_t millisNow);
void emitTurbidity(int value);
void emitPong();

}  // namespace protocol
