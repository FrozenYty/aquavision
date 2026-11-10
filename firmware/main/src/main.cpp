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
uint32_t captureStartedAt = 0;
uint32_t lastAnimation = 0;
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
    protocol::emitScreen(state);
    return;
  }
  if (state.screen == rig::Screen::Capturing) {
    // Already waiting for a verdict. A second press must not become a second frame: the PC would shoot
    // twice for one shot and the operator would see one result for two pictures.
    return;
  }

  state.screen = rig::Screen::Capturing;
  state.score = -1;           // no verdict for this shot yet, so the screen shows no number
  state.reason = rig::Reason::None;
  state.animPhase = 0;
  captureStartedAt = now;
  state.markDirty();
  // Every state change is reported, so the PC never has to infer a screen from the event that caused
  // it. TRIGGER says "capture this frame"; SCREEN says "the panel is now on CAPTURING".
  protocol::emitScreen(state);
  protocol::emitTrigger(now);
}

// A capture whose verdict never arrives. Without this the spinner turns forever while the PC is
// healthy enough to keep the link alive - the one state where a still, silent screen is worst.
void serviceCaptureTimeout(uint32_t now) {
  if (state.screen != rig::Screen::Capturing) {
    return;
  }
  if (now - captureStartedAt < cfg::CAPTURE_TIMEOUT_MS) {
    return;
  }
  state.screen = rig::Screen::Retake;
  state.reason = rig::Reason::NoReply;
  state.score = -1;
  state.animPhase = 0;
  state.markDirty();
  protocol::emitTimeout(now);
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
  // The dot is the only thing that moves between events, so it redraws wherever it is visible. On
  // OFFLINE the whole screen is a filled box and the header is not drawn at all.
  if (state.screen != rig::Screen::Offline) {
    state.markDirty();
  }
}

// Advance the CAPTURING spinner. Only that state animates: every other screen changes when something
// happens, and a redraw every quarter second would be noise.
void serviceAnimation(uint32_t now) {
  if (state.screen != rig::Screen::Capturing) {
    return;
  }
  if (now - lastAnimation < cfg::SPIN_PERIOD_MS) {
    return;
  }
  lastAnimation = now;
  state.animPhase = (state.animPhase + 1) % 3;
  state.markDirty();
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
  if (!alive) {
    // Losing the PC overrides everything: no state can make progress without it.
    state.screen = rig::Screen::Offline;
    state.markDirty();
    protocol::emitScreen(state);
    return;
  }
  // The PC is back. Only a screen that was showing the link failure resets - a verdict or a capture in
  // progress belongs to the rig and must not be replaced by the mere fact that the link recovered.
  if (state.screen == rig::Screen::Offline) {
    state.screen = rig::Screen::Ready;
    state.markDirty();
    protocol::emitScreen(state);
  }
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

  // Bring-up aid: say what answered on the bus, so a display or a sensor that is not wired shows up
  // in the serial log instead of only as a blank screen. The PC ignores line types it does not know.
  protocol::emitI2CScan();

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

  // A command from the PC *is* the PC being alive. The return value used to be discarded, so the link
  // timer only ever started at boot and the rig declared OFFLINE ten seconds later however much it was
  // talking to the PC.
  if (protocol::poll(state)) {
    lastPcMessage = now;
  }
  if (state.pulseLeds) {
    noteResult();
    state.pulseLeds = false;
  }
  serviceButton(now);
  serviceTurbidity(now);
  serviceHeartbeat(now);
  serviceAnimation(now);
  serviceCaptureTimeout(now);
  serviceLeds(now);
  serviceLink(now);

  if (state.dirty) {
    screen::render(display, state);
    state.dirty = false;
  }
}
