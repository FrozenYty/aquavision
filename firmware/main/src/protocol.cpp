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
  state.pulseLeds = true;
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

void emitTrigger(uint32_t millisNow) { Serial.printf("EVT TRIGGER %lu\n", (unsigned long)millisNow); }

void emitTurbidity(int value) { Serial.printf("EVT TURBIDITY %d\n", value); }

void emitPong() { Serial.println("EVT PONG"); }

}  // namespace protocol
