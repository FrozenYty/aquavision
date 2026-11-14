// The rig's one line of I/O, behind an interface.
//
// `protocol` emits a line-oriented ASCII protocol and must not care which wire carries it. Today the wire is
// the UART the USB cable lands on; the finished rig has to run with no cable at all, so a Bluetooth service
// will implement the same four calls. Everything else - the parser, the state machine, the screens, the
// keepalive rule - is already transport-agnostic and does not change.
//
// The interface is deliberately `printf`-shaped rather than "write a string": rewriting fourteen call sites
// to build strings by hand would be a larger change than the seam it hides, and it would risk the byte-level
// output that the PC end and every test currently expect.

#pragma once

#include <cstdint>

namespace transport {

//: Opens the wire. Serial at the baud in `config.h` for now.
void begin();

//: Bytes waiting to be read. Zero when the wire is quiet.
int available();

//: One byte, or -1 when there is none.
int readByte();

//: Formats like `printf` and puts the bytes on the wire. Fragments are fine: `EVT PONG` goes out as two calls,
//: and the wire is a byte stream either way. Lines are short by design - the longest thing this firmware emits
//: is an `EVT INVARIANT` line, 29 bytes, and the longest routine one is `EVT SCREEN` at 24.
void printf(const char* format, ...);

//: Ends the current line. Bytes, not a newline convention: `Serial.println` writes `\r\n` and the PC end
//: strips both, so this writes `\r\n` too rather than quietly changing what is on the wire.
void newline();

}  // namespace transport
