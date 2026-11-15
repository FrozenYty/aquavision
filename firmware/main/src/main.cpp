// Rig controller for AquaVision (P1-06). Wiring only.
//
// The ESP32 reports a button press, drives the OLED, and multiplexes the four-digit seven-segment display.
// It does no imaging and no inference: the PC owns both, and the PC is the only authority on a frame's quality.
//
// What lives where, so a change stays small:
//   config.h     pins, timings, addresses ? the file to edit when hardware moves
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
#include "presentation.h"
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
uint32_t lastButtonEdge = 0;
bool lastButtonLevel = HIGH;
//: When the boot clock starts, and the only clock either screen reads for it. The OLED holds its splash
//: until `BOOT_SEQUENCE_MS` has passed on this clock, so the two screens cannot disagree about whether the
//: rig is still booting; the self-test runs in front of an operator who is already looking at the panel.
uint32_t displayStartedAt = 0;
//: The screen the display painted last, and when it changed. The PASS sweep is a one-shot on arrival, so
//: the face has to know how long the verdict has been up.
rig::Screen lastDisplayedScreen = rig::Screen::Ready;
uint32_t lastDisplayChange = 0;

//: The third machine's own reading of the wire (docs/rig-state-machine-en.md §11). `presentationAttached`
//: remembers the previous loop's carrier, so a transition - not a level - becomes B1 or B3; the state
//: painted last does the same job for the faces that the screen does for `state.screen`, so a change of
//: face starts that face's age at zero.
bool presentationAttached = false;
presentation::State lastDisplayedPresentation = presentation::State::Pairing;

//: The button has one meaning: a press captures. The edge is debounced here, and the capture is refused
//: when there is nothing to receive it - no link, or a shot already in flight - so the rig has one entry
//: point rather than a gesture to be interpreted. The release is not an event.
void serviceButton(uint32_t now) {
  const bool level = digitalRead(cfg::PIN_BUTTON);
  if (level == lastButtonLevel || now - lastButtonEdge < cfg::BUTTON_DEBOUNCE_MS) {
    return;
  }

  lastButtonEdge = now;
  lastButtonLevel = level;

  if (level != LOW) {
    return;  // only the press acts
  }

  // A capture needs a PC to receive it. `state.link` alone is not enough any more: during `Pairing` the
  // protocol still counts boot as `Alive`, so its ten-second grace would let a press start a frame with
  // nobody attached and then paint that capture on whichever PC arrives first. The presentation layer
  // knows there is no PC to send a trigger to, so a press there is refused and literally nothing happens
  // (docs/rig-state-machine-en.md §11).
  if (state.link != rig::Link::Alive || presentation::state() != presentation::State::Live) {
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
//: panel goes back to the idle face; the score is not lost, because the PC keeps the record and the
//: operator's own eyes had it for `cfg::VERDICT_FACE_MS`, and a panel still reading ` 95P` long after the
//: press looks hung rather than waiting.
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
  // The dot is part of the rig's own header, and that header exists only while the presentation is
  // showing the rig's screen. Marking dirty in `Pairing`, `NoLink` or `RadioFault` would repaint the
  // whole 1 kB frame once a second for a dot those faces do not draw - and because one second and the
  // three-second ring lap are commensurate, that 25 ms block lands on the same ring stop every lap,
  // which reads as a pause there. The ring's own step is the only thing that should animate in
  // `Pairing`, and it moves one dot at a time.
  if (state.screen != rig::Screen::Offline &&
      presentation::state() == presentation::State::Live) {
    state.markDirty();
  }
}

//: The alphabet this panel draws, and the rule that keeps it honest: **the digits, the letters A, C, E, F
//: and P, and a lowercase `r`.** `r` is admitted for `Err`, the one word the fault codes are built from,
//: and it is the only lowercase letter drawn. Every character in the table below is shown by a face that
//: exists - `C`,`A`,`P` by CAPTURING, `E` and `r` by the codes, `F` and `P` by the verdicts, `-` by the idle
//: dash, the digits by scores and codes - and nothing else may be added: an unused entry is how the next
//: person concludes a character is safe to draw. Characters outside the set either collide with a digit -
//: `O` is `0`, `S` is `5`, `I` is `1`, `G` resembles `6` and `9` - or cannot be formed at all, like M, W,
//: K, V, X, Y and Z. Transliterate the word into a code instead.
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
    case 'F': return 0x71;  // the left column with the top and middle bars
    case 'r': return 0x50;  // the middle bar and the lower-left corner: the only lowercase letter drawn
    case '-': return 0x40;
  }
  return 0x00;  // blank: all seven segments off
}

//: A score right-aligned in digits 1-3 with the verdict letter in the fourth: 95 reads ` 95P`. Clamped,
//: not trusted: the protocol clamps too, but this is the last place a -1 or a 137 could reach the glass.
void scoreMask(int score, char verdict, uint8_t mask[4]) {
  // A negative score means "no measurement" - the PC's `-1` - and it is drawn as blanks rather than as a
  // zero nobody measured. That matters most in the one case that produces it: a `NO REPLY` retake reads
  // `   F`, not `  0F`, because a `0` beside a timeout invents the very number the timeout says is missing.
  // The OLED draws no number at all for the same score, so the two screens agree. Every writer of a
  // negative score is listed in `rig_state.h`; the protocol clamps everything the PC sends into 0-100.
  if (score >= 0) {
    if (score > 100) {
      score = 100;  // the protocol clamps too, but this is the last place a 137 could reach the glass
    }
    char number[4];
    const int digits = snprintf(number, sizeof(number), "%d", score);
    for (int i = 0; i < digits; ++i) {
      mask[3 - digits + i] = segmentsFor(number[i]);
    }
  }
  mask[3] = segmentsFor(verdict);
}

//: The fault codes: **`Err0` the link is gone** (the OFFLINE screen), `Err1` a capture timeout, `Err2` a
//: stray result, `Err3` a broken invariant - looked up rather than pronounced, four characters to the width
//: of the panel. Numbered because the alphabet above has no unambiguous `t`, `O` or `I`, and because the
//: next fault then costs nothing: `Err4` needs no glyph work.
//:
//: **All five look the same: they blink at one hertz.** The code is the identifier and the rhythm carries
//: nothing, so there is no special case for the link and no second rate for the others. What differs is
//: only how long a face stays: `Err0` has no window at all, because a lost link lasts until the link comes
//: back, and `Err4` - a radio that did not start, or has dropped five times in a minute - has none either,
//: because waiting is what an operator does about `Err0` and the wrong thing to do about `Err4`. `Err1` to
//: `Err3` clear after `cfg::FAULT_FACE_MS`. That is when it leaves, not how it looks - do not "fix" the
//: two into agreement. The fault age is the phase, so the blink starts with the fault rather than wherever
//: the previous face happened to be.
void faultMask(uint32_t faultAge, rig::Fault fault, uint8_t mask[4]) {
  if ((faultAge / cfg::DISPLAY_BLINK_MS) % 2 != 0) {
    return;  // the dark half of the blink; every digit stays as it was left
  }
  const char* code = "Err2";
  if (fault == rig::Fault::Timeout) {
    code = "Err1";
  } else if (fault == rig::Fault::Invariant) {
    code = "Err3";
  } else if (fault == rig::Fault::Radio) {
    code = "Err4";
  }
  for (uint8_t i = 0; i < 4 && code[i] != '\0'; ++i) {
    mask[i] = segmentsFor(code[i]);
  }
}

//: One face of one screen: the idle dash, `CAP`, a verdict or the link code. `faceAge` is how long this
//: face has been up, and it is the only clock any of them reads: a face always starts at the beginning of
//: its own cycle, so the idle dash begins at position one and no face inherits a phase from the one before
//: it. Parameterised rather than read from `state` so the face is a pure function of its arguments.
void screenFace(uint32_t faceAge, rig::Screen screen, int score, uint8_t mask[4]) {
  switch (screen) {
    case rig::Screen::Ready: {
      // One dash walking the four positions - 1, 2, 3, 4, then back to 1 - at half a second each, so the
      // cycle is two seconds. The wraparound is deliberate: a conveyor with a visible break, which reads as
      // work in progress, rather than a there-and-back that would read as a bounce. No frame is ever dark
      // and no more than one dash is ever lit.
      const uint32_t cycle = 4 * cfg::DISPLAY_READY_STEP_MS;
      mask[(faceAge % cycle) / cfg::DISPLAY_READY_STEP_MS] = segmentsFor('-');
      break;
    }
    case rig::Screen::Capturing:
      // CAP, and one segment walking the rim of the fourth digit: A-B-C-D-E-F is clockwise, and G stays
      // out because the middle bar would read as a dropped frame in the rotation. A still fourth digit
      // would look like a character that failed to draw rather than like work in progress. It stays a dot
      // rather than becoming a count: the count is the OLED's job and a second one here would be noise.
      // The step comes from `presentation::rotationStep`, the same call the `Pairing` face makes.
      mask[0] = segmentsFor('C');
      mask[1] = segmentsFor('A');
      mask[2] = segmentsFor('P');
      mask[3] = static_cast<uint8_t>(1u << presentation::rotationStep(faceAge));
      break;
    case rig::Screen::Pass:
    case rig::Screen::Retake: {
      const bool pass = screen == rig::Screen::Pass;
      // On arrival a PASS wipes left to right once, each digit filling with all seven segments as the wipe
      // reaches it, and then settles on the score. One shot per verdict: it marks the moment the answer
      // came back, while a loop would turn the moment into decoration.
      if (pass && faceAge < cfg::DISPLAY_SWEEP_MS) {
        const uint8_t reached = static_cast<uint8_t>(faceAge * 4 / cfg::DISPLAY_SWEEP_MS) + 1;
        for (uint8_t d = 0; d < reached; ++d) {
          mask[d] = segmentsFor('8');
        }
        break;
      }
      // RETAKE blinks, so the warning is not mistaken for a result at a glance; PASS is steady once the
      // sweep is over, because good news that keeps moving reads as uncertainty. The letter is `F` and not
      // `E`: `E` begins every fault code, and a score of 40 on a retake reading ` 40E` sat one glance away
      // from an `Err` face.
      if (!pass && ((faceAge / cfg::DISPLAY_BLINK_MS) % 2) != 0) {
        break;
      }
      scoreMask(score, pass ? 'P' : 'F', mask);
      break;
    }
    case rig::Screen::Offline:
      // The link is gone: `Err0`, blinking at the same one hertz as every other code - see `faultMask`.
      // What marks this face out is duration, not appearance: there is no window on it, so it stays until
      // the link returns rather than clearing after two seconds like `Err1` to `Err3`.
      if ((faceAge / cfg::DISPLAY_BLINK_MS) % 2 == 0) {
        mask[0] = segmentsFor('E');
        mask[1] = segmentsFor('r');
        mask[2] = segmentsFor('r');
        mask[3] = segmentsFor('0');
      }
      break;
  }
}

//: How long the whole self-test runs - the sweep, the settled eights and the blank - so that the boot path
//: reads it from one place rather than repeating the sum.
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

//: How long the current face has been up: the screen's age, clamped to the end of the boot so that the
//: first face after the self-test begins at its own start instead of picking up mid-phase. One definition,
//: read by every face and by the spinner, because a second clock for the same event can only drift.
uint32_t faceAgeAt(uint32_t now, uint32_t screenAge) {
  const uint32_t sinceBoot = now - (displayStartedAt + BOOT_SEQUENCE_MS);
  return screenAge < sinceBoot ? screenAge : sinceBoot;
}

//: The four digits' segment masks, digit 1 on the left. A face is a function of the screen and of how long
//: that face has been up - the self-test runs once on boot, the PASS sweep once on arrival - so nothing
//: here blocks: a slow loop slows the motion down instead of stalling the link.
//: The seven segment bits run in the order `segmentsFor` and `litBits` use: A is bit 0, G bit 6. That is
//: also why the fourth digit's rotation is `1u << step` - six single bits, no table to be wrong in.

//: The `Pairing` panel face: the word `APP` on the first three digits and the fourth digit turning through
//: its six rim segments. `A`, `P`, `P` are all in the character set, so the word is doing the work and no
//: new glyph or table is needed; it names the PC-side application the operator is about to open, which is
//: the action this state is waiting for. The rotation is exactly `CAPTURING`'s, one segment every
//: `DISPLAY_ROTATE_MS`, from the same `presentation::rotationStep`, so the two faces cannot drift apart.
//: **There is no position table here on purpose.** The ring this replaces was twelve (digit, segment)
//: pairs, and one wrong pair both duplicated the fourth digit's bottom and dropped the first digit's; a
//: table is a place to be wrong, and the six-bit rotation below has no entry to get wrong.

void displayMask(uint32_t now, uint32_t screenAge, presentation::State presentationState,
                 uint8_t mask[4]) {
  mask[0] = mask[1] = mask[2] = mask[3] = 0;

  // The presentation layer outranks the screen (docs/rig-state-machine-en.md §11). `Err4` is decided
  // first, ahead of the boot self-test as well: a radio that refused at power-up is not fixed by waiting,
  // and the two-second test must not hide it. `Pairing` draws `APP` with a rotating fourth digit rather
  // than any of the rig's faces. `NoLink` draws the old `Offline` face, `Err0`, because a PC was there and
  // left. A fault window (`Err1` to `Err3`) is the screen's, so it is drawn only while the face is
  // `RigScreen` - the presentation layer replaces it with the other two.
  const presentation::Face& face = presentation::faceFor(presentationState);
  if (face.panel == presentation::PanelFace::Err4) {
    faultMask(now - state.faultAt, rig::Fault::Radio, mask);
    return;
  }

  // The self-test, once, from the moment the loop takes over from the splash card.
  const uint32_t bootAge = now - displayStartedAt;
  if (bootAge < BOOT_SEQUENCE_MS) {
    bootMask(bootAge, mask);
    return;
  }

  if (face.panel == presentation::PanelFace::Pairing) {
    mask[0] = segmentsFor('A');
    mask[1] = segmentsFor('P');
    mask[2] = segmentsFor('P');
    mask[3] = static_cast<uint8_t>(1u << presentation::rotationStep(faceAgeAt(now, screenAge)));
    return;
  }
  if (face.panel == presentation::PanelFace::Err0) {
    screenFace(faceAgeAt(now, screenAge), rig::Screen::Offline, state.score, mask);
    return;
  }

  // A fault outranks every screen. It is the one thing on this panel that must not be missed: one keepalive
  // is long enough to read a code and short enough to be over, and no routine status change can cut it
  // short because this is decided before any screen is looked at. `Err4` is the exception to the window,
  // not to the ranking: a dead radio is not fixed by waiting, so it has no window at all (§10) - and with
  // the presentation layer it is also the one fault that is answered before this point.
  const bool faultShowing =
      state.fault != rig::Fault::None &&
      (state.fault == rig::Fault::Radio || now - state.faultAt < cfg::FAULT_FACE_MS);
  if (faultShowing) {
    faultMask(now - state.faultAt, state.fault, mask);
    return;
  }

  // Every face runs on its own age, and the end of the boot is a face start like any other. Without this
  // clamp the idle cycle would pick up wherever the self-test happened to stop - which put the first dash
  // on digit 2 instead of digit 1 - and every other face would inherit a phase the same way.
  screenFace(faceAgeAt(now, screenAge), state.screen, state.score, mask);
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
  const presentation::State presentationState = presentation::state();
  // A change of face is a change of screen as far as this panel is concerned: it gets its own age, so the
  // `Ready` marquee in `Pairing` starts at digit 1 rather than inheriting a phase, and it forces one
  // repaint of both screens.
  if (presentationState != lastDisplayedPresentation) {
    lastDisplayedPresentation = presentationState;
    lastDisplayChange = now;
    state.markDirty();
  }
  if (state.screen != lastDisplayedScreen) {
    lastDisplayedScreen = state.screen;
    lastDisplayChange = now;
  }
  const uint32_t screenAge = now - lastDisplayChange;

  // The CAPTURING rotation owns `animPhase`: the panel turns through six rim segments and the OLED
  // draws six dots above its banner, one phase for both. It is the same mechanism at the small scale; the
  // `Pairing` face's fourth digit makes the same `presentation::rotationStep` call, so the two cannot
  // drift apart.
  if (state.screen == rig::Screen::Capturing) {
    const uint8_t phase = presentation::rotationStep(faceAgeAt(now, screenAge));
    if (state.animPhase != phase) {
      state.animPhase = phase;
      state.markDirty();
    }
  }

  uint8_t mask[4];
  displayMask(now, screenAge, presentationState, mask);

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

//: Drive the third machine from the two layers it reads (docs/rig-state-machine-en.md §11). Nothing here
//: writes to either of them: B1-B4 are readings of the carrier, B2 is the one-shot subscription event the
//: BLE layer already reports, P1 is `poll`'s return value and P2 is the protocol's own `Gone`. The
//: presentation layer is a reader, and that is why the two existing matrices are untouched.
void servicePresentation(uint32_t now) {
  // B4 first: a radio that reaches `Fault` also detaches, and the B3 edge that produces in the same pass
  // must not put the presentation back into `Pairing` behind the fault.
  const bool faulty = transport::faulted();
  if (faulty) {
    if (state.fault != rig::Fault::Radio) {
      // `state.fault` still carries the blink age and the panel's ranking; the presentation state is what
      // chooses the face (`displayMask`). Both are set from this one event, so they cannot disagree.
      state.fault = rig::Fault::Radio;
      state.faultAt = now;
      state.markDirty();
    }
    presentation::apply(presentation::Event::RadioFaulted);
  }

  const bool attached = transport::attached();
  if (attached != presentationAttached) {
    presentationAttached = attached;
    presentation::apply(attached ? presentation::Event::Attached : presentation::Event::Detached);
  }

  // P2 is the protocol's ten seconds of silence, applied while the fact holds rather than only on its
  // edge. `Subscribed` can enter `Live` after the rig has already gone `Gone` - a PC that attaches late -
  // and that rig has to reach `NoLink` in the same pass, not sit on `Live` with a dead protocol
  // underneath until the next command. In `Pairing` and `NoLink` the matrix consumes it, so repeating it
  // costs nothing and cannot move the state twice.
  if (state.link == rig::Link::Gone) {
    presentation::apply(presentation::Event::Silence);
  }
}

}  // namespace

void setup() {
  pinMode(cfg::PIN_BUTTON, INPUT_PULLUP);
  beginDisplay();

  // The wire: a UART always opens, and a radio can refuse. A refusal is not fatal - the rig keeps drawing
  // its panel - but it is `Err4` rather than a rig that looks merely unreachable (§8, §10).
  if (transport::begin() != transport::Result::Ok) {
    state.fault = rig::Fault::Radio;
    state.faultAt = millis();
  }

  // The third machine starts from the wire that actually opened: a radio with no central is `Pairing`;
  // a UART always answers attached, so a serial rig starts `Live` and never shows `WAITING`
  // (docs/rig-state-machine-en.md §11). Not an event and not in the matrix - a stack that starts has
  // exactly one thing to be.
  presentation::begin(transport::attached(), state.pcAlive());
  presentationAttached = transport::attached();
  lastDisplayedPresentation = presentation::state();

  Wire.begin(cfg::PIN_I2C_SDA, cfg::PIN_I2C_SCL);

  // Bring-up aid: say what answered on the bus, so a display or a sensor that is not wired shows up
  // in the serial log instead of only as a blank screen. The PC ignores line types it does not know.
  protocol::emitI2CScan();

  display.begin();

  // Drawn once and then *held* by the loop while the panel runs its self-test - there is deliberately no
  // delay here, because a blocking delay cannot be the thing another screen synchronises to. This is where
  // the boot clock starts.
  screen::renderSplash(display);
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
    // P1: a command is proof that somebody is on the other end, which is the only thing `NoLink` was
    // waiting for. In `Live` the cell is handled in place - a keepalive does not repaint anything.
    presentation::apply(presentation::Event::Command);
  }
  serviceButton(now);
  serviceHeartbeat(now);
  serviceCaptureTimeout(now);
  serviceVerdictTimeout(now);
  serviceLink(now);

  // The five reachable screen/link combinations are enforced here rather than assumed. This costs a
  // comparison per loop and turns a state bug into a serial line instead of a panel that quietly lies.
  //
  // One report per episode, re-armed as soon as the pairing is sound again: the check keeps watching after
  // it fires. A latch that reported once and then stayed quiet looked like a monitor while saying nothing at
  // all about the second violation.
  static bool invariantReported = false;
  if (rig::invariantHolds(state)) {
    invariantReported = false;
  } else if (!invariantReported) {
    invariantReported = true;
    state.fault = rig::Fault::Invariant;
    state.faultAt = now;
    protocol::emitInvariant(state.screen, state.link);
  }

  // A PC that has just subscribed missed every line emitted while nobody was listening - `EVT HELLO`, the
  // I2C scan, the starting screen - so the rig says where it is now instead of leaving the PC to infer it
  // from the next change. Asked once per subscription, and **not a liveness claim**: the keepalive rule
  // below is untouched, so a client that subscribes and then says nothing still makes the rig `Gone`.
  // The serial wire answers false: a port that is open reads the very next line already.
  if (transport::subscribed()) {
    protocol::emitScreen(state);
    // B2: the subscription completed. Both screens are still on `NoLink` at this point, so the PC that
    // just subscribed sees the link face until this event moves the presentation to `Live` - which is the
    // honest order: attaching is not the same fact as being able to hear the rig.
    presentation::apply(presentation::Event::Subscribed);
  }

  // The presentation layer is worked out after the link, the invariant and the subscription have been
  // read this pass, and the panel after that: a face worked out before the fact it reports would be one
  // loop behind, and a face age that starts a pass late would inherit a phase.
  //
  // `transport::faulted()` is called here, once per pass and not inside a condition, because the call is
  // also the BLE layer's clock for its own idle timer and for a refused advertisement - the one deadline
  // there that no radio callback will ever raise on its own. It is read after the invariant check so that
  // a dead radio wins the frame: both codes are true at the same moment and only one of them tells the
  // operator what to do (§10).
  servicePresentation(now);
  serviceDisplay(now);

  // Both screens read the one boot clock: while the panel is still walking its self-test the OLED keeps the
  // splash card, and the moment that sequence ends they both move to READY. Nothing else decides when the
  // rig is ready, and the pending screen change is simply held until then.
  if (now - displayStartedAt >= BOOT_SEQUENCE_MS && state.dirty) {
    // Every screen change and every ring step arrives here, and each one sends a whole frame. That is
    // deliberate: the partial tile update was the only writer in this change that addressed something
    // other than a full buffer, and it corrupted the glass on the bench. A frame is about 1184 bytes and
    // 25 ms; four ring steps a second is a ten-percent duty, and the panel is on its own timer, so the
    // only cost is up to 25 ms of loop latency - far inside the button's 25 ms debounce window and the
    // two-second keepalive. If a bench session ever shows that dragging, the one number to lower is the
    // ring's step interval, not this call.
    screen::render(display, state, presentation::state());
    state.dirty = false;
  }
}
