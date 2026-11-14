// Rig controller for AquaVision (P1-06). Wiring only.
//
// The ESP32 reports a button press, drives the OLED, and lights three lamps and the ten-lamp score bar. It
// does no imaging and no inference: the PC owns both, and the PC is the only authority on a frame's quality.
//
// What lives where, so a change stays small:
//   config.h     pins, timings, addresses — the file to edit when hardware moves
//   rig_state.h  what the rig knows (screen, score, ...)
//   screen.cpp   the 128x64 layout, one function per state
//   protocol.cpp the serial grammar
//   main.cpp     this file: the loop that calls the four above

#include <Arduino.h>
#include <U8g2lib.h>
#include <Wire.h>

#include "config.h"
#include "transport.h"
#include "protocol.h"
#include "rig_state.h"
#include "screen.h"

namespace {

U8G2_SSD1306_128X64_NONAME_F_HW_I2C display(U8G2_R0, U8X8_PIN_NONE);

rig::State state;

uint32_t lastPcMessage = 0;
uint32_t lastHeartbeat = 0;
uint32_t captureStartedAt = 0;
uint32_t lastAnimation = 0;
uint32_t lastButtonEdge = 0;
bool lastButtonLevel = HIGH;

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

//: The score bar. It answers "how good was this shot" from across a room, where the two verdict lamps answer
//: only pass or fail: ten lamps on GPIO 10-18 and 21, and the pins sink them off the 5 V rail, so LOW is lit
//: and HIGH is dark - see `config.h` for that wiring, the pin order and the two step times.
//: READY walks one lamp out and back, CAPTURING fills the bar one lamp at a time, and a verdict shows the
//: score as a level. Every pattern is a function of `now`, so nothing here blocks: a slow loop slows the
//: animation down instead of stalling the serial link.
void serviceBar(uint32_t now) {
  uint16_t mask = 0;  // bit i lights bar lamp i
  switch (state.screen) {
    case rig::Screen::Ready: {
      // One dot, out to the last lamp and back. A still bar says nothing, and this is the state an operator
      // waits in - a rig that has stopped and a rig that is idle must not look the same.
      constexpr uint8_t OUT_AND_BACK = cfg::BAR_LEDS * 2 - 2;
      const uint8_t step = static_cast<uint8_t>((now / cfg::BAR_SWEEP_PERIOD_MS) % OUT_AND_BACK);
      mask = static_cast<uint16_t>(1u << (step < cfg::BAR_LEDS ? step : OUT_AND_BACK - step));
      break;
    }
    case rig::Screen::Capturing: {
      // 1, then 2, up to 10, then 1 again. It reports "working" and does not pretend to know how far along
      // the PC is, because the rig is never told.
      const uint8_t count = static_cast<uint8_t>((now / cfg::BAR_FILL_PERIOD_MS) % cfg::BAR_LEDS + 1);
      mask = static_cast<uint16_t>((1u << count) - 1);
      break;
    }
    case rig::Screen::Pass:
    case rig::Screen::Retake: {
      // The score as a level, one segment per ten percent: the number the panel is showing, readable from
      // where the operator is standing. A score below zero is no verdict at all, and that lights all ten - a
      // dark bar would read as a score of nought, which is a number nobody measured.
      int level = cfg::BAR_LEDS;
      if (state.score >= 0) {
        level = constrain(state.score / 10, 0, cfg::BAR_LEDS);
      }
      mask = static_cast<uint16_t>((1u << level) - 1);
      break;
    }
    case rig::Screen::Offline:
      break;  // dark: the panel is a filled box saying why, and a lit bar would contradict it
  }

  for (uint8_t i = 0; i < cfg::BAR_LEDS; ++i) {
    digitalWrite(cfg::PIN_BAR[i], (mask & (1u << i)) != 0 ? LOW : HIGH);
  }
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
  // The bar is dark until the loop paints the first pattern, so a floating pin cannot light a lamp at boot.
  for (uint8_t i = 0; i < cfg::BAR_LEDS; ++i) {
    pinMode(cfg::PIN_BAR[i], OUTPUT);
    digitalWrite(cfg::PIN_BAR[i], HIGH);
  }

  transport::begin();

  Wire.begin(cfg::PIN_I2C_SDA, cfg::PIN_I2C_SCL);

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
  serviceHeartbeat(now);
  serviceAnimation(now);
  serviceCaptureTimeout(now);
  serviceLeds();
  serviceBar(now);
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
