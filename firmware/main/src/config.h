// Everything a person might want to change without reading the rest of the firmware.
//
// Pins and timings live here and nowhere else. If a wire moves, this file changes and nothing else
// does — that is the whole reason it exists.

#pragma once

#include <cstdint>

namespace cfg {

// ---------------------------------------------------------------------------- pins

constexpr int PIN_BUTTON = 4;      // to GND, INPUT_PULLUP: a press reads LOW
// The three lamps sit on the 5 V rail and the pin switches the low side, so **LOW lights a lamp and
// HIGH puts it out**. That is what makes them bright enough to read across a bench: from 3.3 V a 2 V LED
// has 1.3 V of headroom and 330 ohm leaves under 4 mA, while from 5 V the same resistor gives about 9 mA.
// The pin never sees 5 V - the LED is between it and the rail - and it sinks at most 9 mA.
// **Colour is a convention here, not a requirement**, and this set was chosen on three grounds.
// Red marks RETAKE, because the lamp that says "shoot it again" is the one that must not be missed and red
// is the colour a reader already stops for. White marks PASS: it is the brightest thing available at 9 mA
// and carries no bad news. Blue marks the state, because an always-on lamp must recede - white there would
// dominate the two that matter, and it blooms into a white blob on a phone camera.
// Green for PASS was the obvious choice and was given up twice over: the parts on hand were too dim at 9 mA
// to read from a metre, and red against green is the one pair a red-green colour-blind operator cannot
// separate. Red, white and blue differ in brightness as well as hue.
constexpr int PIN_LED_PASS = 5;    // white, anode to +5 V, cathode through 330 ohm: LOW lights it
constexpr int PIN_LED_RETAKE = 6;  // red, the same
constexpr int PIN_LED_STATE = 7;   // blue, the same
constexpr int PIN_I2C_SDA = 8;
constexpr int PIN_I2C_SCL = 9;

// ---------------------------------------------------------------------------- i2c

constexpr uint8_t OLED_ADDR = 0x3C;
constexpr uint8_t TURBIDITY_ADDR = 0x49;
//: The vendor manual specifies the *shape* of a register read - START, address+W, ACK, CMD, ACK, repeated
//: START, address+R, ACK, data, STOP - and states the address (`7'b100_1001`, which is 0x49), but publishes
//: **no table of CMD values**. So this byte is a bench finding rather than a quotation, and it is the one
//: number in this file that a different batch of the same sensor could invalidate. If the reading is ever a
//: constant 0 or 65535 again, sweep this value before suspecting the wiring.
//: **Not zero.** Register `0x00` turns out to echo whatever register was addressed before it - the periodic
//: reading tracked my sweeps (`65280`, `512`, `2560`) instead of tracking water, which is what an echo looks
//: like from the outside. `0x70` is the only register that has ever held two different values across sessions
//: (1280, then 2560) and its magnitude sits inside the documented output range, so it is the current best
//: candidate for the measurement. It reads a constant while the scene is constant, which is expected - and it
//: did not move when the probe was covered, which is the open question.
constexpr uint8_t TURBIDITY_CMD = 0x70;
//: Under investigation. Every register answers with one meaningful byte followed by zeros, and a device that
//: releases the bus floats high (`0xFF`), not low - so the second byte is either never driven or never made
//: it back here. The 3.3 V side of the level shifter relies on the ESP32's internal ~45 kOhm pull-up, which
//: is weak enough to ruin a rising edge at 100 kHz. A slow clock is the cheapest way to tell "slow edges"
//: apart from "the register does not exist": if the data appears at 10 kHz the pull-ups are the answer.
constexpr uint32_t I2C_CLOCK_HZ = 10000;

// ---------------------------------------------------------------------------- timing

constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 25;
// The blue state lamp is steady when the rig is idle, blinks slowly while a capture is in flight, and
// blinks fast when the link is gone. Two rates rather than one, because "busy" and "broken" are different
// questions, and a single pattern would make the operator read the panel twice to tell them apart.
constexpr uint32_t STATE_BLINK_MS = 500;
constexpr uint32_t FAULT_BLINK_MS = 150;
// The PC is required to send `CMD PING` at least every two seconds, so ten seconds of silence is five
// missed keepalives and therefore a real disconnection rather than an idle rig.
constexpr uint32_t OFFLINE_AFTER_MS = 10000;
// A capture that gets no verdict by then is reported as NO REPLY. Shorter than OFFLINE_AFTER_MS on
// purpose: the operator should learn that this shot failed before the whole link is declared dead.
constexpr uint32_t CAPTURE_TIMEOUT_MS = 5000;
constexpr uint32_t TURBIDITY_PERIOD_MS = 5000;
constexpr uint32_t HEARTBEAT_PERIOD_MS = 1000;
// The three-dot spinner on CAPTURING. Fast enough to read as motion, slow enough not to strobe.
constexpr uint32_t SPIN_PERIOD_MS = 250;
constexpr uint32_t SPLASH_MS = 1500;

// ---------------------------------------------------------------------------- identity

//: Bumped whenever the wire protocol or what the panel and lamps do changes, because `EVT HELLO` is how a
//: host knows which build is on the board - a feature added without a bump is a feature nobody can
//: confirm is running. 1.2 added the blue state lamp on GPIO7; 1.3 moved the lamps to the 5 V rail with
//: the pin switching the low side, which inverted what HIGH means for all three; 1.4 made the lamps follow
//: the screen instead of pulsing for 300 ms, so the two verdict lamps are steady while their verdict is shown;
//: 1.5 made the turbidity read address a register instead of reading whatever the pointer happened to hold;
//: 1.6 added `CMD TREAD`, which is how that register's command byte was found and how it stays findable;
//: 1.7 added `CMD TDUMP`, because two bytes turned out to be byte-identical in air and in water and the whole
//: frame had to be seen.
constexpr char FIRMWARE_VERSION[] = "1.11";

}  // namespace cfg