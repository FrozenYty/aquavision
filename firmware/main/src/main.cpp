// Rig controller for AquaVision (P1-06). Wiring only.
//
// The ESP32 reports a button press, reads turbidity, drives the OLED and pulses two LEDs. It does no
// imaging and no inference: the PC owns both, and the PC is the only authority on a frame's quality.
//
// What lives where, so a change stays small:
//   config.h     pins, timings, addresses — the file to edit when hardware moves
//   rig_state.h  what the rig knows (screen, score, turbidity, ...)
//   screen.cpp   the 128x64 layout, one function per state
//   protocol.cpp the serial grammar
//   main.cpp     this file: the loop that calls the four above

#include <Arduino.h>
#include <U8g2lib.h>
#include <Wire.h>

#include "config.h"
#include "protocol.h"
#include "rig_state.h"
#include "screen.h"

namespace {

U8G2_SSD1306_128X64_NONAME_F_HW_I2C display(U8G2_R0, U8X8_PIN_NONE);

rig::State state;

uint32_t lastPcMessage = 0;
uint32_t lastTurbidity = 0;
uint32_t lastHeartbeat = 0;
uint32_t ledPassUntil = 0;
uint32_t ledRetakeUntil = 0;
uint32_t lastButtonEdge = 0;
bool lastButtonLevel = HIGH;

//: The measurement itself. Returns -1 when the sensor does not answer, which the screen shows as
//: "--" rather than as a zero — a plausible wrong number is worse than a visible gap.
int readTurbidity() {
  Wire.requestFrom(cfg::TURBIDITY_ADDR, static_cast<uint8_t>(2));
  if (Wire.available() < 2) {
    return -1;
  }
  const int high = Wire.read();
  const int low = Wire.read();
  return (high << 8) | low;
}

void serviceButton(uint32_t now) {
  const bool level = digitalRead(cfg::PIN_BUTTON);
  if (level == lastButtonLevel || now - lastButtonEdge < cfg::BUTTON_DEBOUNCE_MS) {
    return;
  }
  lastButtonEdge = now;
  lastButtonLevel = level;
  if (level != LOW) {
    return;  // the release edge, not a press
  }

  if (!state.pcAlive) {
    // Nothing is listening, so there is nothing to capture. Say so on the screen instead of leaving
    // it on CAPTURING forever.
    state.screen = rig::Screen::Offline;
    state.markDirty();
    return;
  }
  state.screen = rig::Screen::Capturing;
  state.markDirty();
  protocol::emitTrigger(now);
}

void serviceTurbidity(uint32_t now) {
  if (now - lastTurbidity < cfg::TURBIDITY_PERIOD_MS) {
    return;
  }
  lastTurbidity = now;
  const int value = readTurbidity();
  if (value < 0) {
    return;
  }
  state.noteTurbidity(value);
  protocol::emitTurbidity(value);
}

void serviceHeartbeat(uint32_t now) {
  if (now - lastHeartbeat < cfg::HEARTBEAT_PERIOD_MS) {
    return;
  }
  lastHeartbeat = now;
  state.heartbeatOn = !state.heartbeatOn;
  // Only the idle screen blinks; during a result the score is what matters and a redraw every second
  // would compete with it.
  if (state.screen == rig::Screen::Ready) {
    state.markDirty();
  }
}

void serviceLeds(uint32_t now) {
  digitalWrite(cfg::PIN_LED_PASS, now < ledPassUntil ? HIGH : LOW);
  digitalWrite(cfg::PIN_LED_RETAKE, now < ledRetakeUntil ? HIGH : LOW);
}

void serviceLink(uint32_t now) {
  const bool alive = (now - lastPcMessage) < cfg::OFFLINE_AFTER_MS;
  if (alive == state.pcAlive) {
    return;
  }
  state.pcAlive = alive;
  state.screen = alive ? rig::Screen::Ready : rig::Screen::Offline;
  state.markDirty();
}

//: A result arrived from the PC: light the right LED for a moment.
void noteResult() {
  if (state.screen == rig::Screen::Pass) {
    ledPassUntil = millis() + cfg::LED_PULSE_MS;
  } else {
    ledRetakeUntil = millis() + cfg::LED_PULSE_MS;
  }
}

}  // namespace

void setup() {
  pinMode(cfg::PIN_BUTTON, INPUT_PULLUP);
  pinMode(cfg::PIN_LED_PASS, OUTPUT);
  pinMode(cfg::PIN_LED_RETAKE, OUTPUT);
  digitalWrite(cfg::PIN_LED_PASS, LOW);
  digitalWrite(cfg::PIN_LED_RETAKE, LOW);

  Serial.begin(cfg::SERIAL_BAUD);

  Wire.begin(cfg::PIN_I2C_SDA, cfg::PIN_I2C_SCL);
  display.begin();

  screen::renderSplash(display);
  delay(cfg::SPLASH_MS);

  protocol::emitHello();
  lastPcMessage = millis();
  state.screen = rig::Screen::Ready;
  state.markDirty();
}

void loop() {
  const uint32_t now = millis();

  protocol::poll(state);
  if (state.pulseLeds) {
    noteResult();
    state.pulseLeds = false;
  }
  serviceButton(now);
  serviceTurbidity(now);
  serviceHeartbeat(now);
  serviceLeds(now);
  serviceLink(now);

  if (state.dirty) {
    screen::render(display, state);
    state.dirty = false;
  }
}
