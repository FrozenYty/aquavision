// The serial implementation of `transport` - the one the bench uses. A Bluetooth implementation joins it
// beside this file and implements the same four calls; nothing above this layer changes.

#include "transport.h"

#include <Arduino.h>

#include <cstdarg>
#include <cstdio>

#include "config.h"

namespace transport {

namespace {

//: Enough for the longest event this firmware emits (a six-byte register dump is about 45 characters) with
//: room to spare, because a truncated line would be a protocol error rather than a display glitch.
constexpr size_t BUFFER_SIZE = 96;

}  // namespace

void begin() { Serial.begin(cfg::SERIAL_BAUD); }

int available() { return Serial.available(); }

int readByte() { return Serial.read(); }

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
