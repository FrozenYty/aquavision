// Rig controller for AquaVision (P1-06). Wiring only.
//
// The ESP32 reports a button press, reads turbidity, drives the OLED and lights three lamps. It does no
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
uint32_t lastButtonEdge = 0;
bool lastButtonLevel = HIGH;

//: The measurement itself. Returns -1 when the sensor does not answer, which the screen shows as
//: "--" rather than as a zero — a plausible wrong number is worse than a visible gap.
//: The bus sequence lives in `protocol::readRegister` so that the bench sweep and this call cannot drift
//: apart - a second copy of a repeated-START read is a bug waiting for a quiet afternoon.
int readTurbidity() { return protocol::readRegister(cfg::TURBIDITY_CMD); }

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

  // A capture needs a PC to receive it, and the invariant already ties `Gone` to the OFFLINE screen, so
  // there is nothing to set here - only the refusal.
  if (state.link != rig::Link::Alive) {
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
  // Both events, in this order: TIMEOUT says why the screen moved, SCREEN says where it moved to. Emitting
  // only the first made this the one transition a PC could not observe as a screen change, and the
  // protocol rule is that every screen change is reported.
  protocol::emitTimeout(now);
  protocol::emitScreen(state);
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

//: The verdict lamps follow the screen: white while PASS is shown, red while RETAKE is. **Steady, not a
//: 300 ms pulse** - the lamp is a second view of the fact the panel is showing, and a pulse had to be
//: timed, so a verdict arriving while the loop was busy could have been missed entirely.
//: The pins sink the lamps (5 V rail), so LOW is lit and HIGH is dark. See `config.h` for why the
//: brightness was worth the inversion.
void serviceLeds() {
  digitalWrite(cfg::PIN_LED_PASS, state.screen == rig::Screen::Pass ? LOW : HIGH);
  digitalWrite(cfg::PIN_LED_RETAKE, state.screen == rig::Screen::Retake ? LOW : HIGH);
}

//: The blue lamp answers what the verdict lamps do not: idle, in flight, and disconnected. Between them the
//: three lamps cover every screen, so a completely dark panel can only mean no power - which is the whole
//: reason the third lamp exists.
void serviceStateLed(uint32_t now) {
  bool lit;
  switch (state.screen) {
    case rig::Screen::Capturing:
      lit = ((now / cfg::STATE_BLINK_MS) % 2) == 0;
      break;
    case rig::Screen::Offline:
      lit = ((now / cfg::FAULT_BLINK_MS) % 2) == 0;
      break;
    case rig::Screen::Pass:
    case rig::Screen::Retake:
      lit = false;  // the verdict lamp is lit instead, and two lamps saying one thing is noise
      break;
    default:
      lit = true;  // Ready
      break;
  }
  digitalWrite(cfg::PIN_LED_STATE, lit ? LOW : HIGH);
}

void serviceLink(uint32_t now) {
  const bool alive = (now - lastPcMessage) < cfg::OFFLINE_AFTER_MS;
  if (!alive && state.link == rig::Link::Alive) {
    state.link = rig::Link::Gone;
    state.screen = rig::Screen::Offline;  // invariant: Offline if and only if Gone
    state.markDirty();
    protocol::emitScreen(state);
  }
  // Recovery is handled where it happens - by `poll` setting `Alive` - and the screen reset lives in the
  // command handlers, so a keepalive cannot overwrite a verdict that is still being read.
}

}  // namespace

void setup() {
  pinMode(cfg::PIN_BUTTON, INPUT_PULLUP);
  pinMode(cfg::PIN_LED_PASS, OUTPUT);
  pinMode(cfg::PIN_LED_RETAKE, OUTPUT);
  pinMode(cfg::PIN_LED_STATE, OUTPUT);
  // HIGH is dark here: the pins sink the lamps rather than feeding them.
  digitalWrite(cfg::PIN_LED_PASS, HIGH);
  digitalWrite(cfg::PIN_LED_RETAKE, HIGH);
  // Lit from the first millisecond: this lamp's job is to prove the board has power, so it must not wait
  // for the loop or for the splash to finish before saying so.
  digitalWrite(cfg::PIN_LED_STATE, LOW);

  Serial.begin(cfg::SERIAL_BAUD);

  Wire.begin(cfg::PIN_I2C_SDA, cfg::PIN_I2C_SCL);
  Wire.setClock(cfg::I2C_CLOCK_HZ);

  // Bring-up aid: say what answered on the bus, so a display or a sensor that is not wired shows up
  // in the serial log instead of only as a blank screen. The PC ignores line types it does not know.
  protocol::emitI2CScan();

  display.begin();

  screen::renderSplash(display);
  delay(cfg::SPLASH_MS);

  protocol::emitHello();
  // The rig starts READY with a ten-second grace: a PC on the other end of the cable sends its first
  // keepalive long before it expires. Booting OFFLINE would show the panel calling itself dead before
  // anything has had a chance to speak, and the operator would be looking at a screen that reads like a
  // fault. Losing a live link is worth reporting; having no history yet is not.
  lastPcMessage = millis();
  state.link = rig::Link::Alive;
  state.screen = rig::Screen::Ready;
  state.markDirty();
  protocol::emitScreen(state);  // the PC should learn the starting state, not infer it
}

void loop() {
  const uint32_t now = millis();

  // A command from the PC *is* the PC being alive. The return value used to be discarded, so the link
  // timer only ever started at boot and the rig declared OFFLINE ten seconds later however much it was
  // talking to the PC.
  if (protocol::poll(state)) {
    lastPcMessage = now;
    const bool wasGone = (state.link == rig::Link::Gone);
    state.link = rig::Link::Alive;
    // A command is the PC's return, so the link failure screen gives way. It is the *only* screen this
    // resets: a verdict or a capture belongs to the rig and a keepalive must not clear it.
    if (wasGone && state.screen == rig::Screen::Offline) {
      state.screen = rig::Screen::Ready;
      state.markDirty();
      protocol::emitScreen(state);
    }
  }
  serviceButton(now);
  serviceTurbidity(now);
  serviceHeartbeat(now);
  serviceAnimation(now);
  serviceCaptureTimeout(now);
  serviceLeds();
  serviceStateLed(now);
  serviceLink(now);

  // The five reachable screen/link combinations are enforced here rather than assumed. This costs a
  // comparison per loop and turns a state bug into a serial line instead of a panel that quietly lies.
  static bool invariantReported = false;
  if (!rig::invariantHolds(state) && !invariantReported) {
    invariantReported = true;
    protocol::emitInvariant(state.screen, state.link);
  }

  if (state.dirty) {
    screen::render(display, state);
    state.dirty = false;
  }
}
