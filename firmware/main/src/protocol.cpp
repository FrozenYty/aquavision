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

void handleResult(rig::State& state, char** cursor) {
  const char* scoreText = strtok_r(nullptr, " ", cursor);
  const char* verdict = strtok_r(nullptr, " ", cursor);
  const char* reason = strtok_r(nullptr, " ", cursor);
  if (scoreText == nullptr || verdict == nullptr) {
    return;
  }

  state.score = constrain(atoi(scoreText), 0, 100);
  state.reason = rig::reasonFromToken(reason);
  state.frames += 1;
  state.screen = (strcmp(verdict, "PASS") == 0) ? rig::Screen::Pass : rig::Screen::Retake;
  state.pulseLeds = true;
  state.markDirty();
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
  } else if (strcmp(command, "RESULT") == 0) {
    handleResult(state, &cursor);
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

void emitHello() { Serial.printf("EVT HELLO %s\n", cfg::FIRMWARE_VERSION); }

void emitTrigger(uint32_t millisNow) { Serial.printf("EVT TRIGGER %lu\n", (unsigned long)millisNow); }

void emitTurbidity(int value) { Serial.printf("EVT TURBIDITY %d\n", value); }

void emitPong() { Serial.println("EVT PONG"); }

}  // namespace protocol
