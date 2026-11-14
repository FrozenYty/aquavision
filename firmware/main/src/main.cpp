// Rig controller for AquaVision (P1-06). Wiring only.
//
// The ESP32 reports a button press, drives the OLED, and multiplexes the four-digit seven-segment display.
// It does no imaging and no inference: the PC owns both, and the PC is the only authority on a frame's quality.
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
#include <soc/gpio_struct.h>

#include <cstdio>

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
//: The button's gesture state. The release is what tells a capture from a rehearsal, so a press has to be
//: remembered rather than acted on: `buttonHeld` until it is let go, `holdBecameRehearsal` once the hold
//: has become one, and `pressedFromReady` because a rehearsal may only start from READY.
bool buttonHeld = false;
bool holdBecameRehearsal = false;
bool pressedFromReady = false;
uint32_t buttonPressedAt = 0;
//: The bench rehearsal: display-only, started from READY, one face every `cfg::REHEARSAL_STEP_MS`.
struct Rehearsal {
  bool active = false;
  uint32_t startedAt = 0;
};
Rehearsal rehearsal;
//: When the display's own clock starts. The loop takes over from the splash card here, so the boot
//: self-test runs in front of an operator who is already looking at the panel rather than behind it.
uint32_t displayStartedAt = 0;
//: The screen the display painted last, and when it changed. The PASS sweep is a one-shot on arrival, so
//: the face has to know how long the verdict has been up.
rig::Screen lastDisplayedScreen = rig::Screen::Ready;
uint32_t lastDisplayChange = 0;

//: The button does two things with one gesture, and the release is what tells them apart: let go before
//: `cfg::REHEARSAL_HOLD_MS` and it is a capture, still held when the hold completes and it is the
//: rehearsal. A short press therefore stays a capture however slowly it is released, and a rehearsal exists
//: only from READY, so it can neither interrupt nor imitate a capture in flight.
void serviceButton(uint32_t now) {
  const bool level = digitalRead(cfg::PIN_BUTTON);
  if (level == lastButtonLevel || now - lastButtonEdge < cfg::BUTTON_DEBOUNCE_MS) {
    // No edge, or one still bouncing. The long press is noticed while the button is held, because three
    // seconds is a moment rather than a second event.
    if (buttonHeld && !holdBecameRehearsal && now - buttonPressedAt >= cfg::REHEARSAL_HOLD_MS) {
      if (pressedFromReady && state.screen == rig::Screen::Ready) {
        rehearsal.active = true;
        rehearsal.startedAt = now;
        holdBecameRehearsal = true;
      }
    }
    return;
  }

  lastButtonEdge = now;
  lastButtonLevel = level;

  if (level == LOW) {
    // A press during the rehearsal ends it, and is spent doing so: its release must not fire a capture.
    if (rehearsal.active) {
      rehearsal.active = false;
      return;
    }
    buttonHeld = true;
    buttonPressedAt = now;
    holdBecameRehearsal = false;
    pressedFromReady = (state.screen == rig::Screen::Ready);
    return;
  }

  // The release edge.
  if (!buttonHeld) {
    return;  // the release of the press that ended the rehearsal
  }
  buttonHeld = false;
  if (holdBecameRehearsal) {
    return;  // the hold already became the rehearsal, so letting go captures nothing
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
  state.fault = rig::Fault::Timeout;
  state.faultAt = now;
  state.verdictAt = now;
  state.markDirty();
  // Both events, in this order: TIMEOUT says why the screen moved, SCREEN says where it moved to. Emitting
  // only the first made this the one transition a PC could not observe as a screen change, and the
  // protocol rule is that every screen change is reported.
  protocol::emitTimeout(now);
  protocol::emitScreen(state);
}

//: A verdict is a conclusion, not a permanent label. After `cfg::VERDICT_FACE_MS` with no new capture the
//: panel goes back to the idle face; the score is not lost, because the OLED's session tally is where the
//: history lives, and a panel still reading ` 95P` long after the press looks hung rather than waiting.
//: OFFLINE is deliberately not covered: losing the link is a fault, not a completion, and it stays visible
//: until the link comes back. A fault face keeps its own two seconds as well.
void serviceVerdictTimeout(uint32_t now) {
  if (state.screen != rig::Screen::Pass && state.screen != rig::Screen::Retake) {
    return;
  }
  if (now - state.verdictAt < cfg::VERDICT_FACE_MS) {
    return;
  }
  state.screen = rig::Screen::Ready;
  state.markDirty();
  // The PC is told, like every other screen change: a panel that moved on its own must not be invisible.
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

//: The alphabet this panel draws, and the rule that keeps it readable: **only the digits and the letters
//: A, C, E, F, H, L, P and U.** Every other character either collides with a digit - `O` is `0`, `S` is
//: `5`, `I` is `1`, `G` resembles `6` and `9` - or cannot be formed at all, like M, W, K, V, X, Y and Z.
//: Do not add a glyph outside that set; transliterate the word into a code instead, the way the fault
//: faces do. The table holds only what a face actually shows, because a character nothing displays is a
//: table entry nothing can check.
uint8_t segmentsFor(char c) {
  switch (c) {
    case '0': return 0x3F;
    case '1': return 0x06;
    case '2': return 0x5B;
    case '3': return 0x4F;
    case '4': return 0x66;
    case '5': return 0x6D;
    case '6': return 0x7D;
    case '7': return 0x07;
    case '8': return 0x7F;
    case '9': return 0x6F;
    case 'C': return 0x39;
    case 'A': return 0x77;
    case 'P': return 0x73;
    case 'E': return 0x79;
    case 'H': return 0x76;  // both columns and the middle bar
    case 'L': return 0x38;  // the left column and the bottom bar
    case '-': return 0x40;
  }
  return 0x00;  // blank: all seven segments off
}

//: A score right-aligned in digits 1-3 with the verdict letter in the fourth: 95 reads ` 95P`. Clamped,
//: not trusted: the protocol clamps too, but this is the last place a -1 or a 137 could reach the glass.
void scoreMask(int score, char verdict, uint8_t mask[4]) {
  if (score < 0) {
    score = 0;
  }
  if (score > 100) {
    score = 100;
  }
  char number[4];
  const int digits = snprintf(number, sizeof(number), "%d", score);
  for (int i = 0; i < digits; ++i) {
    mask[3 - digits + i] = segmentsFor(number[i]);
  }
  mask[3] = segmentsFor(verdict);
}

//: The fault codes: **E0 the link is gone** (the OFFLINE screen), `E1` a capture timeout, `E2` a stray
//: result, `E3` a broken invariant - looked up rather than pronounced. Numbered because the alphabet above
//: has no unambiguous `t`, `O` or `I`, and because the next fault then costs nothing: `E4` needs no glyph
//: work. The loop below draws E1-E3; E0 belongs to the screen, not to a fault event.
void faultMask(uint32_t now, rig::Fault fault, uint8_t mask[4]) {
  const char* code = "E2";
  if (fault == rig::Fault::Timeout) {
    code = "E1";
  } else if (fault == rig::Fault::Invariant) {
    // E3 alternates with the word at the warning pace: the code for whoever reads the log, the word for
    // whoever is standing in the room. HELP is the only four-letter word this alphabet can spell, and a
    // broken invariant is the one fault the person at the rig cannot clear by themselves.
    code = ((now / cfg::DISPLAY_BLINK_MS) % 2 == 0) ? "E3" : "HELP";
  }
  for (uint8_t i = 0; i < 4 && code[i] != '\0'; ++i) {
    mask[i] = segmentsFor(code[i]);
  }
}

//: One face of one screen: the idle dash, `CAP`, a verdict or the link code. `screenAge` is how long
//: that screen has been up, which is what the PASS arrival sweep needs. Parameterised rather than read
//: from `state` because the rehearsal shows these same faces without any screen having changed.
void screenFace(uint32_t now, uint32_t screenAge, rig::Screen screen, int score, uint8_t mask[4]) {
  switch (screen) {
    case rig::Screen::Ready: {
      // One dash filling the four positions, half a second each, then all four held for a second and round
      // again. Slow on purpose: a waiting rig should sit quietly rather than perform, and the hold is what
      // makes it breathe - filling and vanishing reads as a break. It cannot be mistaken for OFFLINE
      // either, because that face is the code E0.
      const uint32_t cycle = 4 * cfg::DISPLAY_READY_STEP_MS + cfg::DISPLAY_READY_HOLD_MS;
      const uint32_t elapsed = now % cycle;
      if (elapsed < 4 * cfg::DISPLAY_READY_STEP_MS) {
        mask[elapsed / cfg::DISPLAY_READY_STEP_MS] = segmentsFor('-');
      } else {
        mask[0] = mask[1] = mask[2] = mask[3] = segmentsFor('-');
      }
      break;
    }
    case rig::Screen::Capturing:
      // CAP, and one segment walking the rim of the fourth digit: A-B-C-D-E-F is clockwise, and G stays
      // out because the middle bar would read as a dropped frame in the rotation. A still fourth digit
      // would look like a character that failed to draw rather than like work in progress.
      mask[0] = segmentsFor('C');
      mask[1] = segmentsFor('A');
      mask[2] = segmentsFor('P');
      mask[3] = static_cast<uint8_t>(1u << ((now / cfg::DISPLAY_ROTATE_MS) % 6));
      break;
    case rig::Screen::Pass:
    case rig::Screen::Retake: {
      const bool pass = screen == rig::Screen::Pass;
      // On arrival a PASS wipes left to right once, each digit filling with all seven segments as the wipe
      // reaches it, and then settles on the score. One shot per verdict: it marks the moment the answer
      // came back, while a loop would turn the moment into decoration.
      if (pass && screenAge < cfg::DISPLAY_SWEEP_MS) {
        const uint8_t reached = static_cast<uint8_t>(screenAge * 4 / cfg::DISPLAY_SWEEP_MS) + 1;
        for (uint8_t d = 0; d < reached; ++d) {
          mask[d] = segmentsFor('8');
        }
        break;
      }
      // RETAKE blinks, so the warning is not mistaken for a result at a glance; PASS is steady once the
      // sweep is over, because good news that keeps moving reads as uncertainty.
      if (!pass && ((now / cfg::DISPLAY_BLINK_MS) % 2) != 0) {
        break;
      }
      scoreMask(score, pass ? 'P' : 'E', mask);
      break;
    }
    case rig::Screen::Offline:
      // The link is gone: E0, the first code of the fault family, blinking at half a hertz. Losing the link
      // is a fault, so the numbering is honest rather than a workaround - and a code cannot be mistaken for
      // an idle panel the way four dashes can now that READY holds them for a second.
      if ((now / cfg::DISPLAY_OFFLINE_BLINK_MS) % 2 == 0) {
        mask[0] = segmentsFor('E');
        mask[1] = segmentsFor('0');
      }
      break;
  }
}

//: How long the whole self-test runs - the sweep, the settled eights and the blank - so that both the boot
//: path and the rehearsal read it from one place rather than repeating the sum.
constexpr uint32_t BOOT_SEQUENCE_MS =
    28 * cfg::DISPLAY_BOOT_SWEEP_MS + cfg::DISPLAY_BOOT_TEST_MS + cfg::DISPLAY_BOOT_BLANK_MS;

//: The boot self-test: one segment at a time through all 28 positions, then every segment lit for
//: `DISPLAY_BOOT_TEST_MS`; the blank after that is simply nothing. Sequential rather than a static `8888`,
//: because a dead segment then shows as a gap at a known position in the sweep instead of as a missing bar
//: in a row of eights that nobody can place.
void bootMask(uint32_t bootAge, uint8_t mask[4]) {
  const uint32_t sweep = 28 * cfg::DISPLAY_BOOT_SWEEP_MS;
  if (bootAge < sweep) {
    const uint8_t step = static_cast<uint8_t>(bootAge / cfg::DISPLAY_BOOT_SWEEP_MS);
    mask[step / 7] = static_cast<uint8_t>(1u << (step % 7));
    return;
  }
  if (bootAge < sweep + cfg::DISPLAY_BOOT_TEST_MS) {
    mask[0] = mask[1] = mask[2] = mask[3] = segmentsFor('8');
  }
}

//: The rehearsal's steps: the boot self-test, the idle dash, `CAP`, both verdicts, the three fault codes
//: and the link code, in that order, `cfg::REHEARSAL_STEP_MS` each and wrapping. It exists because some of
//: these faces are otherwise unreachable on a bench where nothing is failing - `E0` worst of all, since it
//: needs a cable pulled - and a face nobody has ever seen is a face that fails on the day.
void rehearsalMask(uint32_t now, uint8_t mask[4]) {
  constexpr uint8_t STEPS = 9;
  const uint32_t elapsed = now - rehearsal.startedAt;
  const uint8_t step = static_cast<uint8_t>((elapsed / cfg::REHEARSAL_STEP_MS) % STEPS);
  const uint32_t stepAge = elapsed % cfg::REHEARSAL_STEP_MS;

  switch (step) {
    case 0:
      bootMask(stepAge, mask);  // the real self-test: the sweep, then the settled eights
      break;
    case 1:
      screenFace(now, stepAge, rig::Screen::Ready, -1, mask);  // the travelling dash
      break;
    case 2:
      screenFace(now, stepAge, rig::Screen::Capturing, -1, mask);
      break;
    case 3:
      screenFace(now, stepAge, rig::Screen::Pass, 95, mask);  // the sweep plays, as it does on arrival
      break;
    case 4:
      screenFace(now, stepAge, rig::Screen::Retake, 30, mask);
      break;
    case 5:
      faultMask(now, rig::Fault::Timeout, mask);
      break;
    case 6:
      faultMask(now, rig::Fault::Stray, mask);
      break;
    case 7:
      faultMask(now, rig::Fault::Invariant, mask);
      break;
    default:
      screenFace(now, stepAge, rig::Screen::Offline, -1, mask);  // E0, blink and all
      break;
  }
}

//: The four digits' segment masks, digit 1 on the left. A face is a function of the screen, of `now` and
//: of how long the current screen has been up - the self-test runs once on boot and the PASS sweep once
//: on arrival - so nothing here blocks: a slow loop slows the motion down instead of stalling the link.
void displayMask(uint32_t now, uint32_t screenAge, uint8_t mask[4]) {
  mask[0] = mask[1] = mask[2] = mask[3] = 0;

  // A fault outranks everything, the rehearsal included. It is the one thing on this panel that must not
  // be missed: two seconds is long enough to read and short enough to be over, and no routine status
  // change can cut it short because this is decided before any screen is looked at.
  if (state.fault != rig::Fault::None && now - state.faultAt < cfg::FAULT_FACE_MS) {
    faultMask(now, state.fault, mask);
    return;
  }

  // The rehearsal is display-only: the rig stays READY, nothing goes on the wire, and the panel walks
  // through every face it has.
  if (rehearsal.active) {
    rehearsalMask(now, mask);
    return;
  }

  // The self-test, once, from the moment the loop takes over from the splash card.
  const uint32_t bootAge = now - displayStartedAt;
  if (bootAge < BOOT_SEQUENCE_MS) {
    bootMask(bootAge, mask);
    return;
  }

  screenFace(now, screenAge, state.screen, state.score, mask);
}

//: The segment and common pins as GPIO bitmasks, so the timer handler is four register writes instead of
//: sixteen `digitalWrite` calls. Recursive so `config.h` stays the only place a pin number is written.
constexpr uint32_t segmentBits(uint8_t index = 0) {
  return index < 7 ? (uint32_t{1} << cfg::SEGMENT_PINS[index]) | segmentBits(index + 1) : 0u;
}
constexpr uint32_t commonBits(uint8_t index = 0) {
  return index < 4 ? (uint32_t{1} << cfg::DIGIT_PINS[index]) | commonBits(index + 1) : 0u;
}
constexpr uint32_t SEGMENT_BITS = segmentBits();
constexpr uint32_t COMMON_BITS = commonBits();

//: The lit segments of one digit as GPIO bits. `IRAM_ATTR` because the timer handler calls it, and the
//: handler must not run code that lives in flash.
uint32_t IRAM_ATTR litBits(uint8_t mask) {
  uint32_t bits = 0;
  for (uint8_t s = 0; s < 7; ++s) {
    if ((mask & (uint8_t{1} << s)) != 0) {
      bits |= uint32_t{1} << cfg::SEGMENT_PINS[s];
    }
  }
  return bits;
}

//: The four digit masks: written by the loop, read by the timer one byte per tick. Publishing takes
//: `displayMux` and masks interrupts, so the handler can never read a half-updated face: four bytes
//: cannot tear if nothing can interrupt the copy. The index-flip alternative leaves a window that only
//: probability closes, and this costs a few hundred nanoseconds at animation rate.
volatile uint8_t displayMasks[4] = {0, 0, 0, 0};
portMUX_TYPE displayMux = portMUX_INITIALIZER_UNLOCKED;

//: Which digit the timer is on. Only the handler touches it.
volatile uint8_t displayDigit = 0;

//: The multiplexer, in a hardware timer: one digit per 250 us, whatever the loop is doing. That is the
//: point of moving it here - an OLED transfer blocks the loop for 20-25 ms, and a panel driven from the
//: loop spent that time showing one digit at full duty, which read as a flicker on the animated faces.
//: `IRAM_ATTR` and four GPIO register writes, because the handler has to finish well inside its own
//: period and must not call into flash.
void IRAM_ATTR displayTick() {
  // Release the digit that is on before selecting the next: its segments first, so it is already dark
  // when its common drops, then every common, then the next one and its segments.
  GPIO.out_w1ts = SEGMENT_BITS;  // a segment is lit by LOW, so HIGH releases it
  GPIO.out_w1tc = COMMON_BITS;   // no digit selected
  displayDigit = static_cast<uint8_t>((displayDigit + 1) & 3);
  GPIO.out_w1ts = uint32_t{1} << cfg::DIGIT_PINS[displayDigit];
  GPIO.out_w1tc = litBits(displayMasks[displayDigit]);
}

//: The timer that runs the multiplexer. Started once, in `beginDisplay`.
hw_timer_t* displayTimer = nullptr;

//: The panel's own setup: every pin an output and in its off state, then the timer that owns them. The
//: masks start at zero, so the panel stays dark until the loop publishes its first face.
void beginDisplay() {
  for (uint8_t s = 0; s < 7; ++s) {
    pinMode(cfg::SEGMENT_PINS[s], OUTPUT);
    digitalWrite(cfg::SEGMENT_PINS[s], HIGH);  // a segment is lit by LOW
  }
  for (uint8_t d = 0; d < 4; ++d) {
    pinMode(cfg::DIGIT_PINS[d], OUTPUT);
    digitalWrite(cfg::DIGIT_PINS[d], LOW);  // a common selects its digit by HIGH
  }

  displayTimer = timerBegin(1000000);  // one tick per microsecond, so the alarm is the digit period
  timerAttachInterrupt(displayTimer, &displayTick);
  timerAlarm(displayTimer, cfg::DISPLAY_DIGIT_US, true, 0);
}

//: What the panel shows: the four digit masks for the current face, published for the timer. The loop
//: never touches a pin; it works the face out and hands it over, so an OLED transfer can block for as
//: long as it likes. Published only when the face changes, so the handover happens at animation rate
//: rather than at loop rate. A face is a function of the screen and of `now`, so nothing here blocks.
void serviceDisplay(uint32_t now) {
  if (state.screen != lastDisplayedScreen) {
    lastDisplayedScreen = state.screen;
    lastDisplayChange = now;
  }

  uint8_t mask[4];
  displayMask(now, now - lastDisplayChange, mask);

  bool same = true;
  for (uint8_t d = 0; d < 4; ++d) {
    if (displayMasks[d] != mask[d]) {
      same = false;
    }
  }
  if (same) {
    return;
  }

  portENTER_CRITICAL(&displayMux);
  for (uint8_t d = 0; d < 4; ++d) {
    displayMasks[d] = mask[d];
  }
  portEXIT_CRITICAL(&displayMux);
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
  beginDisplay();

  transport::begin();

  Wire.begin(cfg::PIN_I2C_SDA, cfg::PIN_I2C_SCL);

  // Bring-up aid: say what answered on the bus, so a display or a sensor that is not wired shows up
  // in the serial log instead of only as a blank screen. The PC ignores line types it does not know.
  protocol::emitI2CScan();

  display.begin();

  screen::renderSplash(display);
  delay(cfg::SPLASH_MS);
  // The self-test belongs to the loop, not to the splash card: this is where the display's clock starts.
  displayStartedAt = millis();

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
  serviceVerdictTimeout(now);
  serviceDisplay(now);
  serviceLink(now);

  // The five reachable screen/link combinations are enforced here rather than assumed. This costs a
  // comparison per loop and turns a state bug into a serial line instead of a panel that quietly lies.
  static bool invariantReported = false;
  if (!rig::invariantHolds(state) && !invariantReported) {
    invariantReported = true;
    state.fault = rig::Fault::Invariant;
    state.faultAt = now;
    protocol::emitInvariant(state.screen, state.link);
  }

  if (state.dirty) {
    screen::render(display, state);
    state.dirty = false;
  }
}
