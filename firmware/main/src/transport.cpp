// The serial implementation of `transport` - the one the bench uses, and the `rig-serial` build. The
// Bluetooth implementation lives beside this file as `transport_ble.cpp` and answers the same calls;
// nothing above this layer changes.

#include "transport.h"

#include <Arduino.h>

#include <cstdarg>
#include <cstdio>

#include "config.h"

namespace transport {

namespace {

//: Enough for the longest event this firmware emits - an `EVT INVARIANT` line at 29 bytes - with room to
//: spare, because a truncated line would be a protocol error rather than a display glitch.
constexpr size_t BUFFER_SIZE = 96;

}  // namespace

//: Always `Ok`. Opening the UART cannot fail in a way this rig can see: the bridge chip answers whatever
//: is on the other end, so a missing cable is a link that never speaks, which is the protocol's `Gone`
//: and not a carrier fault.
Result begin() {
  Serial.begin(cfg::SERIAL_BAUD);
  return Result::Ok;
}

int available() { return Serial.available(); }

int readByte() { return Serial.read(); }

//: A cable has no radio to fail, and a carry that cannot drop cannot reach a drop-storm fault.
bool faulted() { return false; }

//: A UART has no subscription to enable: a PC that opens the port sees the very next line, because there
//: is no window between attaching and being able to read one.
bool subscribed() { return false; }

//: Always true: a UART is open from boot, and the bridge chip cannot see whether a cable is plugged in.
//: The serial build therefore never reaches `Pairing` - it has no carrier signal to be paired on - and
//: that is the honest answer rather than a missing state (docs/rig-state-machine-en.md §11).
bool attached() { return true; }

void printf(const char* format, ...) {
  char buffer[BUFFER_SIZE];
  va_list arguments;
  va_start(arguments, format);
  const int written = vsnprintf(buffer, sizeof(buffer), format, arguments);
  va_end(arguments);
  if (written <= 0) {
    return;
  }
  const size_t length = (static_cast<size_t>(written) < sizeof(buffer)) ? static_cast<size_t>(written)
                                                                        : sizeof(buffer) - 1;
  Serial.write(reinterpret_cast<const uint8_t*>(buffer), length);
}

void newline() { Serial.write("\r\n"); }

}  // namespace transport
