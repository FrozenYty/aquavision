#include <Wire.h>

#include "protocol.h"

#include <Arduino.h>
#include <cstdlib>
#include <cstring>

#include "config.h"

namespace {

//: One line at a time. A line longer than this is dropped whole rather than truncated into nonsense.
constexpr size_t LINE_CAPACITY = 96;

char line[LINE_CAPACITY];
size_t length = 0;

//: Set by `handleLine` when a command was applied; cleared by `poll`.
bool sawCommand = false;

bool handleResult(rig::State& state, char** cursor) {
  const char* scoreText = strtok_r(nullptr, " ", cursor);
  const char* verdict = strtok_r(nullptr, " ", cursor);
  const char* reason = strtok_r(nullptr, " ", cursor);
  if (scoreText == nullptr || verdict == nullptr) {
    return false;
  }

  const int score = constrain(atoi(scoreText), 0, 100);

  // A verdict answers a capture, so it means something only while one is in flight. Accepted in any
  // other state it would invent a result for a shot that never happened, or overwrite a timeout the
  // operator has already read. Dropped silently it would leave the PC believing the rig took it, so it
  // is dropped loudly - the same reason TCP answers an unexpected segment with a reset.
  if (state.screen != rig::Screen::Capturing) {
    protocol::emitStrayResult(score);
    return false;
  }

  state.score = score;
  state.reason = rig::reasonFromToken(reason);
  state.frames += 1;
  state.screen = (strcmp(verdict, "PASS") == 0) ? rig::Screen::Pass : rig::Screen::Retake;
  state.markDirty();
  return true;
}

void handleLine(rig::State& state, char* text) {
  char* cursor = nullptr;
  char* verb = strtok_r(text, " ", &cursor);
  if (verb == nullptr || strcmp(verb, "CMD") != 0) {
    return;
  }
  char* command = strtok_r(nullptr, " ", &cursor);
  if (command == nullptr) {
    return;
  }

  sawCommand = true;

  if (strcmp(command, "PING") == 0) {
    protocol::emitPong();
  } else if (strcmp(command, "READY") == 0) {
    state.screen = rig::Screen::Ready;
    state.markDirty();
    protocol::emitScreen(state);
  } else if (strcmp(command, "SCAN") == 0) {
    // Rescan on demand. The boot scan is the only other look at the bus, and it happens before anyone has
    // had a chance to move a wire: without this, every wiring change costs a power cycle to test.
    protocol::emitI2CScan();
  } else if (strcmp(command, "TREAD") == 0) {
    // `CMD TREAD 00` - read one register and report it. Bench-only, and the reason it exists is that the
    // sensor's manual gives the shape of a read but not the command byte to put in it.
    char* argument = strtok_r(nullptr, " ", &cursor);
    if (argument != nullptr) {
      protocol::emitRegisterRead(static_cast<uint8_t>(strtol(argument, nullptr, 16)));
    }
  } else if (strcmp(command, "TDUMP") == 0) {
    char* argument = strtok_r(nullptr, " ", &cursor);
    if (argument != nullptr) {
      char* length = strtok_r(nullptr, " ", &cursor);
      const uint8_t count = (length == nullptr) ? 8 : static_cast<uint8_t>(atoi(length));
      protocol::emitRegisterDump(static_cast<uint8_t>(strtol(argument, nullptr, 16)), count);
    }
  } else if (strcmp(command, "TWRITE") == 0) {
    char* address = strtok_r(nullptr, " ", &cursor);
    char* value = strtok_r(nullptr, " ", &cursor);
    if (address != nullptr && value != nullptr) {
      protocol::emitRegisterWrite(static_cast<uint8_t>(strtol(address, nullptr, 16)),
                                  static_cast<uint8_t>(strtol(value, nullptr, 16)));
    }
  } else if (strcmp(command, "RESULT") == 0) {
    if (handleResult(state, &cursor)) {
      protocol::emitScreen(state);
    }
  }
}

}  // namespace

namespace protocol {

bool poll(rig::State& state) {
  sawCommand = false;

  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\n' || c == '\r') {
      if (length > 0) {
        line[length] = '\0';
        handleLine(state, line);
        length = 0;
      }
      continue;
    }
    if (length < LINE_CAPACITY - 1) {
      line[length++] = c;
    } else {
      length = 0;
    }
  }

  return sawCommand;
}

const char* screenName(rig::Screen screen) {
  switch (screen) {
    case rig::Screen::Ready:
      return "READY";
    case rig::Screen::Capturing:
      return "CAPTURING";
    case rig::Screen::Pass:
      return "PASS";
    case rig::Screen::Retake:
      return "RETAKE";
    case rig::Screen::Offline:
      return "OFFLINE";
  }
  return "UNKNOWN";
}

void emitI2CScan() {
  for (uint8_t address = 1; address < 127; ++address) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) {
      Serial.printf("EVT I2C %02X\n", address);
    }
  }
}

void emitScreen(const rig::State& state) {
  Serial.printf("EVT SCREEN %s %d\n", screenName(state.screen), state.score);
}

void emitHello() { Serial.printf("EVT HELLO %s\n", cfg::FIRMWARE_VERSION); }

void emitTimeout(uint32_t millisNow) {
  Serial.printf("EVT TIMEOUT %lu\n", (unsigned long)millisNow);
}

void emitStrayResult(int score) { Serial.printf("EVT STRAY RESULT %d\n", score); }

void emitInvariant(rig::Screen screen, rig::Link link) {
  Serial.printf("EVT INVARIANT %s %s\n", screenName(screen), rig::linkName(link));
}

void emitTrigger(uint32_t millisNow) { Serial.printf("EVT TRIGGER %lu\n", (unsigned long)millisNow); }

void emitTurbidity(int value) { Serial.printf("EVT TURBIDITY %d\n", value); }

int readRegister(uint8_t command) {
  Wire.beginTransmission(cfg::TURBIDITY_ADDR);
  Wire.write(command);
  // The manual is explicit about this: "note there is one STOP and two STARTs" - the command write is closed
  // with a **STOP** and the read begins with a fresh START. `false` here (a repeated START, no STOP) is the
  // more common idiom and it is what this firmware did first; the sensor answered that with a status byte
  // (`0xFF`) instead of a measurement.
  if (Wire.endTransmission(true) != 0) {
    return -1;
  }
  // The STOP closes the command write, so the sensor is free to go and fetch what it was asked for; without
  // this pause the read that follows can catch it before the register is ready.
  delay(20);
  Wire.requestFrom(cfg::TURBIDITY_ADDR, static_cast<uint8_t>(2));
  if (Wire.available() < 2) {
    return -1;
  }
  const int high = Wire.read();
  const int low = Wire.read();
  return (high << 8) | low;
}

void emitRegisterRead(uint8_t command) {
  Serial.printf("EVT TREG %02X %d\n", command, readRegister(command));
}

void emitRegisterWrite(uint8_t command, uint8_t value) {
  Wire.beginTransmission(cfg::TURBIDITY_ADDR);
  Wire.write(command);
  Wire.write(value);
  const uint8_t ack = Wire.endTransmission(true);
  Serial.printf("EVT TWRITE %02X %02X ack=%u\n", command, value, ack);
}

void emitRegisterDump(uint8_t command, uint8_t count) {
  Wire.beginTransmission(cfg::TURBIDITY_ADDR);
  Wire.write(command);
  const uint8_t ack = Wire.endTransmission(true);
  const uint8_t got = static_cast<uint8_t>(Wire.requestFrom(cfg::TURBIDITY_ADDR, count));
  Serial.printf("EVT TDUMP %02X ack=%u n=%u", command, ack, got);
  for (uint8_t i = 0; i < got && Wire.available() > 0; i += 1) {
    Serial.printf(" %02X", static_cast<uint8_t>(Wire.read()));
  }
  Serial.println();
}

void emitPong() { Serial.println("EVT PONG"); }

}  // namespace protocol
