// Everything a person might want to change without reading the rest of the firmware.
//
// Pins and timings live here and nowhere else. If a wire moves, this file changes and nothing else
// does — that is the whole reason it exists.

#pragma once

#include <cstdint>

namespace cfg {

// ---------------------------------------------------------------------------- pins

constexpr int PIN_BUTTON = 4;      // to GND, INPUT_PULLUP: a press reads LOW
//: The four-digit seven-segment display is **common anode**: a digit's common pin driven HIGH selects
//: that digit, and a segment pin driven LOW lights that segment. Each segment has its own 240 ohm
//: resistor between the pin and the segment; the commons have none, so a common carries the sum of its
//: digit's segment currents and **only one common may be high at any moment**.
constexpr uint8_t SEGMENT_PINS[7] = {3, 13, 14, 15, 16, 17, 18};  // segments A, B, C, D, E, F, G
constexpr uint8_t DIGIT_PINS[4] = {5, 6, 7, 10};  // digit commons 1-4, digit 1 (left) first
constexpr int PIN_I2C_SDA = 8;
constexpr int PIN_I2C_SCL = 9;

// ---------------------------------------------------------------------------- i2c

constexpr uint8_t OLED_ADDR = 0x3C;

// ---------------------------------------------------------------------------- timing

constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 25;
//: The PC is required to send `CMD PING` at least every two seconds, and **this is the unit every other
//: interval in this file is a multiple of**: one keepalive is the fault face and one rehearsal step, two
//: is the capture timeout, three the rehearsal hold, five the offline threshold and six the verdict face.
//: They are written as products of it on purpose - a keepalive that changes must move all of them with
//: it, and this is the one number that cannot be edited alone.
constexpr uint32_t PC_KEEPALIVE_MS = 2000;
// Silence for five keepalives is a real disconnection rather than an idle rig - enough to ride out a busy
// PC without flashing `Offline` at a hiccup, at the cost of up to ten seconds of stale display.
constexpr uint32_t OFFLINE_AFTER_MS = 5 * PC_KEEPALIVE_MS;
// A capture that gets no verdict by then is reported as NO REPLY: the PC's answer normally lands inside a
// second, so two keepalives leave it ample room and still tell the operator early that this shot failed.
// Shorter than OFFLINE_AFTER_MS on purpose.
constexpr uint32_t CAPTURE_TIMEOUT_MS = 2 * PC_KEEPALIVE_MS;
constexpr uint32_t HEARTBEAT_PERIOD_MS = 1000;  // the OLED's header dot, not the PC keepalive
// The three-dot spinner on CAPTURING. Fast enough to read as motion, slow enough not to strobe.
constexpr uint32_t SPIN_PERIOD_MS = 250;
// The display lights one digit at a time, 250 us each, so the whole panel is refreshed at about 1 kHz -
// above the flicker the eye can see, which is what makes four multiplexed digits read as four steady
// ones. The pacing below is a rule rather than a set of numbers: **what is working runs at a steady pace,
// what failed blinks at a warning pace, and nothing on a desk instrument exceeds about 1 Hz.** The boot
// self-test walks one segment at a time and then settles, READY fills the four positions and holds them,
// CAPTURING turns the fourth digit a quarter second at a step - a turn in a second and a half, which reads
// as working rather than urging - PASS wipes left to right once, RETAKE blinks at one hertz, and OFFLINE
// reports E0 at half a hertz: slower than RETAKE, because a warning should be quicker than a fault report,
// and slow enough that E0 can never be taken for a blinking ` 40E`.
constexpr uint32_t DISPLAY_DIGIT_US = 250;
// The self-test walks all 28 segments at this pace - a little over a second - and then settles on `8888`
// for `DISPLAY_BOOT_TEST_MS` and blanks for `DISPLAY_BOOT_BLANK_MS`. Sequential rather than a static row
// of eights, because a dead segment then shows as a gap at a known position in the sweep; the whole
// sequence stays inside two seconds so a power cycle still feels immediate.
constexpr uint32_t DISPLAY_BOOT_SWEEP_MS = 40;
constexpr uint32_t DISPLAY_BOOT_TEST_MS = 400;
constexpr uint32_t DISPLAY_BOOT_BLANK_MS = 150;
// READY fills the four positions with one dash, half a second each, and then holds all four for a second
// before starting again. Slow on purpose - a waiting rig should sit quietly rather than perform - and the
// hold is what makes it read as breathing: filling and vanishing reads as a break. It cannot be mistaken
// for OFFLINE either, because that face is the code E0.
constexpr uint32_t DISPLAY_READY_STEP_MS = 500;
constexpr uint32_t DISPLAY_READY_HOLD_MS = 1000;
constexpr uint32_t DISPLAY_ROTATE_MS = 250;
constexpr uint32_t DISPLAY_SWEEP_MS = 300;
constexpr uint32_t DISPLAY_BLINK_MS = 500;           // RETAKE: half a second lit, half a second dark
constexpr uint32_t DISPLAY_OFFLINE_BLINK_MS = 1000;  // E0: one second lit, one second dark
// The fault faces: a capture timeout, a stray result and a broken invariant each take the panel for one
// keepalive, because those three events used to be swallowed and silence looks exactly like a healthy rig.
// The rehearsal walks every face for one keepalive and starts after a three-keepalive hold, which is what
// makes the fault faces reachable on a bench where nothing is failing.
constexpr uint32_t FAULT_FACE_MS = 1 * PC_KEEPALIVE_MS;
constexpr uint32_t REHEARSAL_STEP_MS = 1 * PC_KEEPALIVE_MS;
// The hold is three keepalives. Three seconds sat in the same order of magnitude as the capture timeout,
// where a slow press and a deliberate hold could be confused; three keepalives is unmistakably deliberate
// and collides with nothing.
constexpr uint32_t REHEARSAL_HOLD_MS = 3 * PC_KEEPALIVE_MS;
// A verdict is a conclusion, not a permanent label: six keepalives after the verdict the panel goes back to
// the idle face. The number is `OFFLINE_AFTER_MS` plus one keepalive, and that relationship is the point:
// **a verdict outlives the link-loss threshold on purpose**, so the link is always reported before a
// verdict clears on its own. Were it the other way round, a dead link would first look like an ordinary
// return to idle, and the operator would be shown a healthy panel for two seconds after the rig had
// stopped talking. Nothing else is lost by moving on - the OLED tally keeps the session and the PC keeps
// the record, and the panel's job is the present state. OFFLINE is deliberately excluded: a lost link is a
// fault, not a completion, and it stays visible until the link returns. A fault face keeps its own one
// keepalive as well.
constexpr uint32_t VERDICT_FACE_MS = 6 * PC_KEEPALIVE_MS;
constexpr uint32_t SPLASH_MS = 1500;

// ---------------------------------------------------------------------------- identity

//: Bumped whenever the wire protocol or what the panel shows changes, because `EVT HELLO` is how a host
//: knows which build is on the board - a feature added without a bump is a feature nobody can confirm is
//: running. 1.2 added the blue state lamp on GPIO7; 1.3 moved the lamps to the 5 V rail with the pin
//: switching the low side, which inverted what HIGH means for all three; 1.4 made the lamps follow the
//: screen instead of pulsing for 300 ms, so the two verdict lamps are steady while their verdict is shown;
//: 1.5 made the turbidity read address a register instead of reading whatever the pointer happened to hold;
//: 1.6 added `CMD TREAD`, which is how that register's command byte was found and how it stays findable;
//: 1.7 added `CMD TDUMP`, because two bytes turned out to be byte-identical in air and in water and the whole
//: frame had to be seen.
//: 1.12 removed all three: the vendor published no register map, a full sweep of the address space on a bus
//: that was proven clean found nothing that followed the light, and the sensor left with the bench commands it
//: had needed. The four-digit seven-segment display now sits on GPIO 3 and 13-18 for its segments, with its
//: digit commons on 5, 6, 7 and 10.
//: Turbidity is history from 1.12 on: 1.5-1.7 above are the record of what those builds did, not a description
//: of this one, and nothing they name is still in the firmware.
//: 1.13 puts the score and the process states on that display. The boot self-test walks all 28 segments one
//: at a time and then settles on eights; READY fills its four positions with one dash and then holds them;
//: CAPTURING shows `CAP` with a segment turning in the fourth digit; PASS wipes left to right once and then
//: shows the score right-aligned with `P`, and RETAKE blinks the same with `E`; the faults that used to be
//: swallowed are numbered codes - `E0` a lost link, `E1` a capture timeout, `E2` a stray result, `E3` a
//: broken invariant, which alternates with `HELP` - and a verdict goes back to READY after
//: `cfg::VERDICT_FACE_MS`. A hold of three keepalives on the button, from READY only, rehearses all nine
//: faces in turn; the multiplexer runs in a hardware timer, so an OLED transfer cannot stall the panel. The
//: ten-lamp bar never shipped, and the display's commons are the pins the three status lamps sat on, so
//: this build retires those as well.
constexpr char FIRMWARE_VERSION[] = "1.13";

}  // namespace cfg