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
//: A capture that produced no verdict inside `cfg::CAPTURE_TIMEOUT_MS`.
void emitTimeout(uint32_t millisNow);
//: A verdict that arrived when no capture was in flight. Reported rather than swallowed: a silently
//: dropped message leaves the PC believing the rig accepted it, which is why TCP answers an unexpected
//: segment with a reset instead of ignoring it.
void emitStrayResult(int score);
//: A screen/link combination that should be impossible. Never expected on the wire; if it appears, the
//: state machine has a hole and the panel is showing something it should not.
void emitInvariant(rig::Screen screen, rig::Link link);
void emitTurbidity(int value);

//: Reads two bytes from one register of the turbidity sensor and returns them big-endian, or -1 when the
//: sensor does not answer. This is the only place the manual's read sequence is written down: it wants a
//: *repeated* START between the command byte and the data, which is easy to get subtly wrong in a second copy.
int readRegister(uint8_t command);
//: Reports a register read as `EVT TREG <cmd> <value>`. The vendor manual publishes no table of command
//: bytes, so the one this firmware uses was found by sweeping the address space - and this is how that stays
//: repeatable instead of becoming folklore.
void emitRegisterRead(uint8_t command);
//: Reports a raw multi-byte read as `EVT TDUMP <cmd> ack=<n> n=<n> <b0> <b1> ...`.
//: The reading was byte-identical in air and against a full tank, which says the two bytes this firmware was
//: collecting are not the measurement - most likely they are a frame header. This command exists to show the
//: whole frame instead of the first two bytes of it.
void emitRegisterDump(uint8_t command, uint8_t count);
void emitPong();

}  // namespace protocol
